"""Evidence-first business opportunity gate for New Keyword Radar.

Independent from the Google Trends new-word and five-year history gates.
No external APIs, no inferred keyword metrics, and no automatic build approval.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = (
    "pain", "leverage", "timing", "resource_fit",
    "standardization", "cashflow",
)
DIMENSION_LABELS = {
    "pain": "痛点强度",
    "leverage": "杠杆密度",
    "timing": "窗口红利",
    "resource_fit": "资源匹配",
    "standardization": "交付标准化",
    "cashflow": "现金流潜力",
}


def read_json(path: Path, fallback: dict) -> dict:
    if not path.exists():
        return fallback
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def number(value):
    if isinstance(value, bool) or value is None:
        return None
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def cited(field) -> bool:
    return isinstance(field, dict) and bool(
        str(field.get("source") or "").strip()
        and str(field.get("checked_at") or "").strip()
    )


def evidence_key(candidate: dict) -> str:
    return str(candidate.get("keyword") or "").strip().lower() + "|" + str(candidate.get("geo") or "").strip().upper()


def evaluate(candidate: dict, record: dict) -> dict:
    """Advisory status only. Never turns a formal radar candidate into an auto-launch."""
    record = record if isinstance(record, dict) else {}
    key = evidence_key(candidate)
    row = {
        "keyword": candidate.get("keyword"),
        "geo": candidate.get("geo", ""),
        "radar_verdict": candidate.get("verdict", "unknown"),
        "newness_score": candidate.get("newness_score"),
        "money_score": candidate.get("money_score"),
        "volume": None, "kd": None, "cpc": None,
        "six_dimensions": {},
        "score_total": None,
        "status": "needs-evidence",
        "missing": [],
        "reasons": [],
        "evidence_key": key,
        "advisory_only": True,
    }
    if candidate.get("verdict") != "formal":
        row["status"] = "not-formal"
        row["reasons"].append("The 90-day and 5-year new-word gates must be passed first.")
        return row

    metrics = record.get("keyword_metrics", {})
    metrics = metrics if isinstance(metrics, dict) else {}
    if cited(metrics):
        row["volume"] = number(metrics.get("volume"))
        row["kd"] = number(metrics.get("kd"))
        row["cpc"] = number(metrics.get("cpc"))
    if row["volume"] is None or row["kd"] is None:
        row["missing"].append("dated Volume/KD and source")
    elif row["volume"] <= 0:
        row["status"] = "reject-zero-volume"
        row["reasons"].append("Verified search volume is zero; do not recommend building.")
        return row
    elif not (0 <= row["kd"] <= 100):
        row["missing"].append("valid KD (0-100)")
    elif row["kd"] > 40:
        row["status"] = "watch-high-kd"
        row["reasons"].append("KD > 40: competition exceeds the default low-competition target.")
        return row

    serp = record.get("serp", {})
    if not cited(serp) or not isinstance(serp.get("notes"), str) or not serp["notes"].strip():
        row["missing"].append("dated SERP inspection and notes")

    comparable = record.get("benchmark", {})
    if not cited(comparable):
        row["missing"].append("dated reference-site traffic or verified recent-game signal")
    else:
        traffic = number(comparable.get("monthly_visits"))
        fresh = comparable.get("verified_new_game_7d") is True
        if not ((traffic is not None and 10000 <= traffic <= 100000) or fresh):
            row["missing"].append("10k–100k/month comparable OR documented seven-day game breakout")
        if fresh and not str(comparable.get("game_evidence_url") or "").strip():
            row["missing"].append("source URL supporting seven-day game breakout")

    scores = []
    dimensions = record.get("dimensions", {})
    dimensions = dimensions if isinstance(dimensions, dict) else {}
    for name in DIMENSIONS:
        item = dimensions.get(name, {})
        val = number(item.get("score")) if isinstance(item, dict) and cited(item) else None
        if val is None or val != int(val) or not (0 <= val <= 5):
            row["six_dimensions"][name] = None
            row["missing"].append(f"evidence-backed score: {name}")
        else:
            row["six_dimensions"][name] = int(val)
            scores.append(int(val))
    if len(scores) == len(DIMENSIONS):
        row["score_total"] = sum(scores)

    if not str(record.get("business_model") or "").strip():
        row["missing"].append("monetization model")
    if not str(record.get("acquisition_channel") or "").strip():
        row["missing"].append("acquisition channel")
    cost = number(record.get("estimated_monthly_fixed_cost_usd"))
    if cost is None or cost < 0:
        row["missing"].append("estimated monthly fixed cost (USD)")
    elif cost > 0:
        row["reasons"].append("Nonzero recurring cost: confirm owner approval before adopting.")

    # Evidence incompleteness always blocks any ready-for-human-review signal.
    if row["missing"]:
        row["status"] = "needs-evidence"
    elif row["score_total"] < 22 or row["six_dimensions"]["pain"] < 3 or row["six_dimensions"]["cashflow"] < 3:
        row["status"] = "watch-business-risk"
        row["reasons"].append("Six-dimension heuristic below threshold: human review needed.")
    else:
        row["status"] = "ready-for-human-review"
        row["reasons"].append("Meets internal evidence gates; NOT approval to develop or purchase.")
    return row


def make_report(payload: dict) -> str:
    lines = [
        "# OPC-inspired business evidence review", "",
        f"Generated: {payload['generated_at']}", "",
        "**Advisory only.** The module does not collect keyword metrics, prove demand,",
        "approve a launch, or change the radar's formal verdict.", "",
        f"Formal radar candidates: {payload['formal_candidate_count']}.",
        "No candidate may be recommended for development without external source evidence.", "",
    ]
    if not payload["assessments"]:
        lines.extend(["**No formal radar candidates to evaluate.**", ""])
    for item in payload["assessments"]:
        metrics = lambda k: "UNVERIFIED" if item[k] is None else str(item[k])
        lines.extend([
            f"## {item['keyword']} ({item['geo'] or 'Worldwide'})", "",
            f"- Status: **{item['status']}** (never automatic approval)",
            f"- Volume: {metrics('volume')}; KD: {metrics('kd')}; CPC: {metrics('cpc')}",
            f"- OPC six-dimension score: {metrics('score_total')}/30 (internal heuristic)",
            f"- Missing evidence: {', '.join(item['missing']) if item['missing'] else 'none'}",
            f"- Notes: {'; '.join(item['reasons']) if item['reasons'] else 'Requires human decision'}", "",
        ])
    return "\n".join(lines)


def run(root: Path = ROOT) -> dict:
    radar = read_json(root / "data/latest.json", {})
    manual = read_json(root / "config/business_evidence.json", {})
    if not radar:
        raise ValueError("Radar data/latest.json missing: run radar and history gate first.")
    candidates = radar.get("formal_candidates", [])
    if not isinstance(candidates, list):
        raise ValueError("Radar formal_candidates must be a list.")
    assessments = [evaluate(c, manual.get(evidence_key(c), {})) for c in candidates if isinstance(c, dict)]
    result = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_radar_generated_at": radar.get("generated_at"),
        "formal_candidate_count": len(candidates),
        "assessments": assessments,
        "status_counts": {x: sum(a["status"] == x for a in assessments)
                          for x in sorted({a["status"] for a in assessments})},
        "policy": "Evidence-first, human-reviewed; never infer Volume/KD/CPC or auto-launch.",
    }
    out_data, out_reports = root / "data/business", root / "reports/business"
    out_data.mkdir(parents=True, exist_ok=True)
    out_reports.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date().isoformat()
    for path in (out_data / "latest.json", out_data / f"{today}.json"):
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = make_report(result)
    for path in (out_reports / "latest.md", out_reports / f"{today}.md"):
        path.write_text(report, encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = run(args.root)
    print("OPC business gate:", result["status_counts"], "formal candidates:", result["formal_candidate_count"])


if __name__ == "__main__":
    main()
