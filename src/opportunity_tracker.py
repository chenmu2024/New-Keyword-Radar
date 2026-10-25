"""Persistent, evidence-first opportunity ledger for the existing Seed Scout.

No network calls. Raw Trends discovery never becomes an automatic build/paid
recommendation. The publisher calls update_ledger AFTER refreshing origin/main.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
ALLOWED = {"discovered", "needs-evidence", "serp-review", "ready-to-test", "watch", "paused", "rejected"}

def load_json(path: Path, fallback):
    if not path.exists():
        return fallback
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value

def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def normalize(value):
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()

def identity(query, geo):
    return hashlib.sha256(f"{normalize(query)}|{str(geo or '').upper()}".encode("utf-8")).hexdigest()[:24]

def safe_date(raw, fallback):
    try:
        return date.fromisoformat(str(raw or "")[:10]).isoformat()
    except ValueError:
        return fallback

def review_status(review):
    """Ready to test requires dated user + SERP evidence, not a self-score."""
    stage = review.get("stage", "discovered")
    if stage not in ALLOWED:
        return "needs-evidence", "invalid review stage"
    if stage == "ready-to-test":
        valid = (
            review.get("checked_at")
            and review.get("user_evidence_url")
            and review.get("serp_evidence_url")
            and review.get("feasible_zero_fixed_cost") is True
        )
        if not valid:
            return "needs-evidence", "missing dated user evidence, SERP, or zero-cost feasibility"
    return stage, ""

def update_ledger(root: Path = ROOT, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(LOCAL_TZ)
    today = local.date().isoformat()
    pending = load_json(root / "state/pending.json", {})
    existing = load_json(root / "state/opportunities.json", {"schema_version": 1, "candidates": {}})
    reviews = load_json(root / "config/opportunity_reviews.json", {})
    candidates = existing.get("candidates", {})
    if not isinstance(candidates, dict):
        raise ValueError("Invalid opportunities.candidates")
    created = 0
    changed = 0
    for query, p in pending.items():
        if not isinstance(p, dict):
            continue
        normalized = normalize(p.get("query") or query)
        if not normalized:
            continue
        geo = str(p.get("geo") or "").upper()
        cid = identity(normalized, geo)
        old = candidates.get(cid, {})
        if not isinstance(old, dict):
            old = {}
        first = min(
            safe_date(old.get("first_seen"), today),
            safe_date(p.get("first_seen"), today),
        )
        last = max(
            safe_date(old.get("last_seen"), first),
            safe_date(p.get("last_seen"), first),
        )
        source = str(p.get("source") or old.get("source") or "unknown")
        source_set = list(dict.fromkeys((old.get("sources") or []) + [source]))
        rec = dict(old)
        rec.update({"id": cid, "query": normalized, "geo": geo, "first_seen": first,
                    "last_seen": last, "source": source, "sources": source_set})
        # Additive history: do not rewrite earlier human assessment on discovery.
        rec.setdefault("stage", "discovered")
        rec.setdefault("reviewed_at", None)
        rec.setdefault("user_evidence_url", None)
        rec.setdefault("serp_evidence_url", None)
        rec.setdefault("monetization_evidence", None)
        rec.setdefault("notes", "")
        # Query volume and paid demand are never inferred from Trends growth.
        rec["verified_volume"] = old.get("verified_volume")
        rec["verified_kd"] = old.get("verified_kd")
        if not old:
            created += 1
        if rec != old:
            changed += 1
        candidates[cid] = rec

    for key, review in reviews.items():
        if not isinstance(review, dict) or not review.get("query"):
            continue
        cid = identity(review["query"], review.get("geo", ""))
        if cid not in candidates:
            # Review does not create an invented discovery.
            continue
        stage, error = review_status(review)
        rec = candidates[cid]
        rec["stage"] = stage
        rec["review_error"] = error or None
        rec["reviewed_at"] = review.get("checked_at")
        for field in ("user_evidence_url", "serp_evidence_url",
                      "monetization_evidence", "notes", "intent", "feasible_zero_fixed_cost"):
            if field in review:
                rec[field] = review[field]

    due = []
    current_date = local.date()
    for cid, rec in candidates.items():
        age = (current_date - date.fromisoformat(rec["first_seen"])).days
        if rec["stage"] in ("rejected", "paused"):
            continue
        for days in (7, 14, 30):
            checked = (rec.get("review_checks") or {}).get(str(days))
            if age >= days and not checked:
                due.append({"id": cid, "query": rec["query"], "due_day": days, "age_days": age})
                break

    eligible = sorted(
        (x for x in candidates.values() if x["stage"] not in ("rejected", "paused")),
        key=lambda x: (x.get("last_seen", ""), x.get("first_seen", "")),
        reverse=True
    )
    state = {"schema_version": 1, "updated_at": now.isoformat(), "candidates": candidates}
    summary = {"generated_at": now.isoformat(), "schema_version": 1,
               "discovered_total": len(candidates), "new_candidates": created,
               "changed_candidates": changed, "review_due_count": len(due),
               "review_due": due[:40],
               "recent_candidates": [
                   {k: x.get(k) for k in ("id", "query", "geo", "first_seen", "last_seen", "stage", "source")}
                   for x in eligible[:25]
               ],
               "important": "Automatically tracked discovery only. User-demand evidence, SERP, KD, volume, and feasibility remain unverified unless sourced."}
    write_json(root / "state/opportunities.json", state)
    write_json(root / "data/opportunities/latest.json", summary)
    report = [
        "# New Keyword Opportunity Ledger (V3)", "",
        f"- Updated (UTC): {now.isoformat()}",
        f"- Historical candidates: {len(candidates)}",
        f"- Newly recorded from pending: {created}",
        f"- Awaiting 7/14/30-day evidence review: {len(due)}",
        "- WARNING: Trending queries are not verified buyer demand, paid sales, or ranking opportunities.",
        "- This report does NOT confirm the 24h/72h trends or SERP window; those require dated external evidence.",
        "",
        "## Recent tracked queries (not build recommendations)", ""
    ]
    report.extend(f"- {x['query']} [{x.get('geo') or 'Global'}] — {x['stage']} — first {x['first_seen']}, last {x['last_seen']}" for x in eligible[:25])
    report.extend(["", "## Due for follow-up", ""])
    report.extend(f"- D+{x['due_day']} {x['query']} (age {x['age_days']}d)" for x in due[:25])
    report.append("")
    path = root / "reports/opportunities/latest.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(report), encoding="utf-8")
    return summary

if __name__ == "__main__":
    print(json.dumps(update_ledger(), ensure_ascii=False))
