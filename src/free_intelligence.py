"""Read-only evidence brief. Leaves the Google Trends newness gate unchanged."""
from __future__ import annotations
import argparse
from datetime import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    from .free_search import collect
    from .lead_quality import screen_result
except ImportError:
    from free_search import collect
    from lead_quality import screen_result

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ZoneInfo("Asia/Shanghai")
OUT = ROOT / "data/free-intelligence"
REPORTS = ROOT / "reports/free-intelligence"
SEED_FILE = ROOT / "data/seed-scout-latest.json"
CONFIG = ROOT / "config/free_intelligence.json"


def queries(max_queries=4):
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    fixed = list(cfg.get("opportunity_queries", []))
    if SEED_FILE.exists():
        try:
            obj = json.loads(SEED_FILE.read_text(encoding="utf-8"))
            for item in sorted(obj.get("discoveries", []), key=lambda x: -float(x.get("rise_value", 0) or 0)):
                phrase = str(item.get("query") or "").strip()
                if 4 <= len(phrase) <= 75 and phrase not in fixed and not any(w in phrase.lower() for w in cfg.get("exclusions", [])):
                    fixed.append(phrase)
                if len(fixed) >= max_queries:
                    break
        except (OSError, ValueError, TypeError):
            pass
    return fixed[:max_queries], cfg


def run(max_queries=4, platforms=None, limit=4):
    selected, cfg = queries(max_queries)
    sources = platforms or cfg.get("platforms", ["github_repos", "github_issues", "google_news_rss", "duckduckgo", "reddit"])
    results = [screen_result(collect(q, sources, limit=limit)) for q in selected]
    date = datetime.now(LOCAL).date().isoformat()
    summary = {"date": date, "timezone": "Asia/Shanghai", "generated_at": datetime.now(LOCAL).isoformat(),
               "mode": "read_only_discovery", "keyword_metrics": {"volume": None, "kd": None, "cpc": None},
               "newness_verified": False, "queries": results,
               "warnings": ["Search presence and engagement do not prove search volume or newness.",
                            "Do not edit existing keyword lists or treat this as a formal candidate gate."]}
    lines = ["# Free search intelligence — " + date, "",
             "Free, preliminary discovery only. **Volume / KD / CPC: unverified**, not zero.", ""]
    for result in results:
        screen = result["quality_screen"]
        lines += ["## " + result["query"], "",
                  "Sources: " + ", ".join(k + "=" + v["status"] for k, v in result["sources"].items()), "",
                  "**Review leads:** " + str(screen["review_count"]) + " / " + str(result["total"]) +
                  " raw unique links (heuristic screening only).", ""]
        for item in screen["review_leads"][:8]:
            score = item["quality"]
            lines.append("- [" + item["title"].replace("]", "") + "](" + item["url"] + ") — "
                         + item["platform"] + " · triage " + str(score["score"]) + "/100 · " +
                         ", ".join(score["reasons"]))
        if not screen["review_leads"]:
            lines.append("- No sufficiently relevant **buyer-pain review leads**. This does not imply zero demand.")
        lines += ["", "Competitor/tool references (not purchase intent): " + str(screen["reference_count"]), ""]
        for item in screen["competitor_references"][:4]:
            lines.append("- [" + item["title"].replace("]", "") + "](" + item["url"] + ") — reference only")
        lines += ["", "Rejected/noise: " + str(screen["discarded_count"]), "",
                  "Next: validate exact Trends history, Volume/KD/CPC, local SERP and willingness to pay.", ""]
    return summary, "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-queries", type=int, default=4)
    ap.add_argument("--limit", type=int, default=4)
    args = ap.parse_args()
    summary, text = run(max_queries=max(1, min(args.max_queries, 8)), limit=max(1, min(args.limit, 10)))
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    (OUT / (summary["date"] + ".json")).write_text(payload, encoding="utf-8")
    (OUT / "latest.json").write_text(payload, encoding="utf-8")
    (REPORTS / (summary["date"] + ".md")).write_text(text, encoding="utf-8")
    (REPORTS / "latest.md").write_text(text, encoding="utf-8")
    print("queries=", len(summary["queries"]), "items=", sum(x["total"] for x in summary["queries"]))


if __name__ == "__main__":
    main()
