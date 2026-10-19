"""Low-rate, isolated Google Trends checks of Sitemap research leads.

Uses the exact 90-day and five-year methods of the main radar, but DOES NOT
insert leads into main pending/formal queues or pretend relative Trends data
are Semrush Volume/KD/CPC or proof of business revenue.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import re

from sitemap_triage import classify

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CFG = ROOT / "config/settings.json"
QUEUE = ROOT / "data/sitemap/queue.json"
STORE = ROOT / "data/sitemap/validation.json"
REPORT = ROOT / "reports/sitemap/validation.md"
MAX_CHECKS = 2  # Total per scan, not per source. Avoid Google rate limits.
RESEARCH_CUE = re.compile(r"\b(backup|checker|calculator|generator|converter|monitor|transcript|planner|export|audit|invoice|price|seo|workflow|automation|data cleaning)\b", re.I)


def key(lead):
    return str(lead.get("geo") or "WORLD") + "|" + str(lead.get("query", "")).casefold()


def eligible(lead):
    tier, _ = classify(lead)
    return tier == "review" and bool(lead.get("query")) and bool(lead.get("url", "").startswith("https://"))


def select(queue, past, today, limit=MAX_CHECKS):
    """Return at most two *previously unchecked* meaningful research leads.

    The full queue is evaluated, not just the first N URLs. Successful
    experiments rest seven days; errors can be retried on a later date.
    """
    if limit < 0 or limit > MAX_CHECKS:
        raise ValueError("Validation quota exceeds fixed safety limit")
    if limit == 0:
        return []
    choices = []
    for lead in queue:
        if not eligible(lead):
            continue
        prior = past.get(key(lead), {})
        date_string = prior.get("checked_date")
        if date_string:
            try:
                delta = (datetime.fromisoformat(today).date() -
                         datetime.fromisoformat(date_string).date()).days
                cooldown = 1 if prior.get("status") == "error" else 7
                if delta < cooldown:
                    continue
            except (TypeError, ValueError):
                pass
        choices.append(lead)
    # Research priority only: tool wording + practical workflow/problem terms.
    # These are NOT newness, SERP difficulty, absolute volume or revenue scores.
    choices.sort(key=lambda x: (-int(bool(x.get("tool_intent_hint"))),
                                -int(bool(RESEARCH_CUE.search(x.get("query", "")))),
                                -int(str(x.get("first_seen") or "1970-01-01").replace("-", "")),
                                x.get("source_id", ""), x.get("query", "")))
    selected, seen, sources = [], set(), set()
    # Reserve variety when available so one fast-growing Actor Sitemap cannot
    # consume the entire validation quota for days.
    for row in choices:
        source = row.get("source_id", "")
        if source in sources or key(row) in seen:
            continue
        selected.append(row)
        seen.add(key(row))
        sources.add(source)
        if len(selected) == limit:
            return selected
    for row in choices:
        if key(row) not in seen:
            selected.append(row)
            seen.add(key(row))
        if len(selected) == limit:
            break
    return selected


def check(lead, cfg, now, explore=None, five_year=None):
    """Always fail closed on missing observations or rate limits."""
    if explore is None:
        from radar import explore as explore
    if five_year is None:
        from history_gate import history_summary as five_year
    row = {
        "query": lead["query"], "geo": lead.get("geo", ""),
        "source_id": lead.get("source_id", ""),
        "url": lead["url"], "checked_date": now.date().isoformat(),
        "checked_at": now.isoformat(), "status": "unknown",
        "relative_trends_only": True,
        "semrush_volume": None, "semrush_kd": None, "semrush_cpc": None,
        "serp_checked": False, "revenue_verified": False,
        "independently_verified_new_keyword": False,
    }
    try:
        result = explore({"query": lead["query"], "geo": lead.get("geo", ""),
                          "source": "sitemap:" + lead.get("source_id", "")}, {}, cfg)
        row.update({field: result.get(field) for field in (
            "verdict", "money_score", "money_type", "newness_score",
            "baseline_avg", "baseline_peak", "baseline_nonzero_ratio",
            "recent_peak", "retention_pct", "first_rise_date", "true_new")})
        if result.get("verdict") == "error" or not result.get("series"):
            row["error"] = result.get("error", "Missing Google Trends observations")
            row["status"] = ("insufficient_data" if
                             "Missing Google Trends observations" in row["error"] else "error")
        elif result.get("true_new") is True:
            history = five_year(lead["query"], lead.get("geo", ""), cfg)
            row["history_5y"] = history
            state = history.get("historically_new")
            row["status"] = ("trends_history_pass" if state is True else
                             "older_interest" if state is False else "history_unknown")
        elif result.get("recent_peak") == 0:
            # Relative zero means no detectable signal, NOT 0 monthly searches.
            row["status"] = "insufficient_relative_signal"
        else:
            row["status"] = "no_recent_trends_breakout"
    except Exception as exc:
        row["status"] = "error"
        row["error"] = type(exc).__name__ + ": " + str(exc)[:200]
    return row


def coverage(store):
    """Availability of actual Trends time-series, not a measure of SEO demand."""
    rows = list(store.values())
    usable = sum(row.get("baseline_avg") is not None and
                 row.get("recent_peak") is not None for row in rows)
    missing = len(rows) - usable
    hard_errors = sum(row.get("status") == "error" for row in rows)
    return {"total": len(rows), "usable": usable, "missing": missing,
            "hard_errors": hard_errors,
            "status": "no_usable_series" if rows and usable == 0 else
                      "partial_coverage" if missing else
                      "not_checked" if not rows else "series_available"}


def render(store, now):
    items = sorted(store.values(), key=lambda x: x.get("checked_at", ""), reverse=True)
    quality = coverage(store)
    lines = ["# Sitemap to Google Trends validation — " + now.date().isoformat(), "",
             "This is independent research; original keyword seeds, commercial",
             "thresholds and the main radar candidate ranking are untouched.",
             "**Google Trends values are relative interest, not monthly search volume.**",
             "No URL finding or Trends spike alone establishes a new keyword,",
             "a winnable SERP, paid demand or monthly search volume.", "",
             f"- Total distinct expressions researched: {len(items)}",
             f"- Usable Google Trends time series: {quality['usable']}/{quality['total']}",
             f"- Missing or failed Google Trends time series: {quality['missing']}/{quality['total']}",
             f"- Data coverage status: {quality['status']} (not a keyword verdict)",
             f"- 90-day + historical-interest passes: {sum(x.get('status') == 'trends_history_pass' for x in items)}",
             f"- Confirmed absolute Volume/KD/CPC: 0 (not supplied)",
             "- A zero relative Trends peak does NOT establish zero searches.", "",
             "## Checked expressions", ""]
    if not items:
        lines.append("- No eligible commercial/tool-oriented Sitemap leads awaiting validation.")
    for item in items[:40]:
        lines += [
            f"### {item['query']} ({item.get('geo') or 'Worldwide'})",
            f"- Source: [{item.get('source_id')}]({item.get('url')})",
            f"- Checked: {item.get('checked_at')} | Status: **{item.get('status')}**",
            f"- Google Trends 90d baseline avg: {item.get('baseline_avg')}; recent peak: {item.get('recent_peak')}; newness score: {item.get('newness_score')}",
            f"- Historical 5y gate: {item.get('history_5y', {}).get('historically_new', 'not run')}",
            f"- Monetary score is only a heuristic: {item.get('money_score')} ({item.get('money_type')}); actual earnings unknown",
        ]
        if item.get("error"):
            lines.append("- Data error: " + str(item["error"]).replace("\n", " ")[:200])
        lines.append("")
    lines += ["## Next independent checks", "",
              "Confirm actual original publication date, 5-year demand consistency,",
              "country-specific absolute Volume/KD/CPC, non-brand SERP and revenue pathway.",
              "A trends_history_pass is a Trends signal, NOT a build recommendation.", ""]
    return "\n".join(lines)


def run(now=None):
    now = now or datetime.now(TZ)
    cfg = json.loads(CFG.read_text(encoding="utf-8"))
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    saved = json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}
    selected = select(queue, saved, now.date().isoformat())
    for lead in selected:
        result = check(lead, cfg, now)
        saved[key(lead)] = result
        print(f"Trends sitemap check {lead['query']}: {result['status']}")
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render(saved, now), encoding="utf-8")
    health = coverage(saved)
    print(f"Sitemap validation: checked {len(selected)}, saved {len(saved)} results")
    print(f"Google Trends coverage: {health['usable']}/{health['total']} usable series; "
          f"{health['missing']} missing/failed; status={health['status']}")
    return saved


if __name__ == "__main__":
    run()
