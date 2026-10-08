"""Zero-paid-API buyer pain discovery. Not an SEO Volume/KD/CPC provider.

Two rotating targeted queries per market plus one screened 7-day rising
query. The existing Google Trends newness / five-year gates are independent.
"""
from __future__ import annotations

import argparse
from datetime import datetime, date
import json
from pathlib import Path
import re
from zoneinfo import ZoneInfo

try:
    from .free_search import collect, canonical_url
    from .lead_quality import screen_result
except ImportError:
    from free_search import collect, canonical_url
    from lead_quality import screen_result

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ZoneInfo("Asia/Shanghai")
OUT = ROOT / "data/free-intelligence"
REPORTS = ROOT / "reports/free-intelligence"
SEED_FILE = ROOT / "data/seed-scout-latest.json"
CONFIG = ROOT / "config/free_intelligence.json"

COMMERCIAL_TERMS = re.compile(
    r"\b(calculator|generator|checker|converter|tracker|planner|builder|editor|"
    r"downloader|simulator|codes|values|template|dashboard|optimizer|api|"
    r"pricing|automation|compliance|invoice|payroll|analytics)\b", re.I
)


def queries(max_queries=7, reference_date=None):
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    day = reference_date or datetime.now(LOCAL).date()
    groups = cfg.get("pain_query_groups", {})
    per_market = max(1, min(3, int(cfg.get("queries_per_market", 2))))
    chosen = []
    # Independently rotate two issue-focused seeds per locale each day.
    for locale in ("en", "pt", "es"):
        options = groups.get(locale, [])
        if not options:
            continue
        start = day.toordinal() % len(options)
        for offset in range(min(per_market, len(options))):
            item = dict(options[(start + offset) % len(options)])
            item["locale"] = locale
            item["kind"] = "specific_buyer_problem"
            if item.get("query") and item.get("market"):
                chosen.append(item)
    chosen = chosen[:max_queries]
    slots = min(int(cfg.get("max_rising_candidate_queries", 1)), max(0, max_queries - len(chosen)))
    if slots and SEED_FILE.exists():
        try:
            payload = json.loads(SEED_FILE.read_text(encoding="utf-8"))
            excluded = cfg.get("exclusions", [])
            items = sorted(payload.get("discoveries", []), key=lambda x: -float(x.get("rise_value", 0) or 0))
            for item in items:
                phrase = " ".join(str(item.get("query") or "").split())
                norm = phrase.casefold()
                if not (5 <= len(phrase) <= 75) or not COMMERCIAL_TERMS.search(phrase):
                    continue
                if any(e.casefold() in norm for e in excluded):
                    continue
                if norm in {x["query"].casefold() for x in chosen}:
                    continue
                chosen.append({
                    "query": phrase, "issue_query": phrase, "locale": "multi",
                    "market": "Worldwide", "topic": "seed_rising",
                    "intent": "emerging_query", "kind": "trend_lead_not_verified",
                    "trend_rise_value": item.get("rise_value")
                })
                if len(chosen) >= max_queries:
                    break
        except (OSError, ValueError, TypeError):
            pass
    return chosen[:max_queries], cfg


def run(max_queries=7, platforms=None, limit=4):
    selected, cfg = queries(max_queries)
    sources = platforms or cfg.get("platforms", ["github_repos", "github_issues", "google_news_rss", "duckduckgo", "reddit"])
    results = []
    seen_links = set()
    for plan in selected:
        phrase = plan["query"]
        target = plan.get("issue_query") or phrase
        overrides = {"github_issues": target, "github_repos": target,
                     "hackernews_ask": target}
        # Ask HN search is predominantly English. Do not pretend its lack of
        # Portuguese/Spanish hits is evidence of absent demand in BR/MX.
        applicable = [source for source in sources
                      if source != "hackernews_ask" or plan.get("locale") == "en"]
        result = screen_result(collect(phrase, applicable, limit=limit, source_queries=overrides))
        result["research_scope"] = {k: v for k, v in plan.items() if k != "query"}
        # A URL appearing in multiple query sets is one lead, not independent validation.
        repeats = []
        for item in result["items"]:
            url = canonical_url(item.get("url"))
            if url in seen_links:
                repeats.append(url)
            else:
                seen_links.add(url)
        result["repeat_links_across_queries"] = repeats
        results.append(result)

    now = datetime.now(LOCAL)
    summary = {"date": now.date().isoformat(), "timezone": "Asia/Shanghai",
               "generated_at": now.isoformat(), "mode": "read_only_buyer_pain_research",
               "keyword_metrics": {"volume": None, "kd": None, "cpc": None},
               "newness_verified": False, "queries": results,
               "unique_evidence_links_across_queries": len(seen_links),
               "warnings": [
                   "Search occurrences, heuristic scores and user issues do not prove search volume or willingness to pay.",
                   "Article/news hits and competitor repositories are contextual leads, not verified buyer demand.",
                   "Do not modify existing keyword lists or bypass exact-query Trends gates."
               ]}
    lines = ["# Free SaaS pain and new-keyword intelligence — " + summary["date"], "",
             "Research only. **Volume / KD / CPC: unverified, not zero.**",
             "Sources can be rate-limited. A zero-lead day is not evidence of zero demand.", ""]
    for result in results:
        screen = result["quality_screen"]
        meta = result["research_scope"]
        lines += ["## " + result["query"], "",
                  "Market: " + meta.get("market", "?") + " · Topic: " + meta.get("topic", "?") +
                  " · Intent: " + meta.get("intent", "?") + " · Category: " + meta.get("kind", "?"), "",
                  "Queries by source: " + ", ".join(k + " = " + v for k, v in result["source_queries"].items()), "",
                  "Sources: " + ", ".join(k + "=" + v["status"] for k, v in result["sources"].items()), "",
                  "**Buyer-pain review leads:** " + str(screen["review_count"]) +
                  " / " + str(result["total"]) + " raw unique links. Filtered, not verified.", ""]
        for item in screen["review_leads"][:6]:
            rank = item["quality"]
            lines.append("- [" + item["title"].replace("]", "") + "](" + item["url"] + ") · "
                         + item["platform"] + " · triage " + str(rank["score"]) +
                         "/100 · " + ", ".join(rank["reasons"]))
        if not screen["review_leads"]:
            lines.append("- No qualifying buyer-pain evidence. Do not infer absence of demand.")
        lines += ["", "Competitor / contextual references: " + str(screen["reference_count"]), ""]
        for item in screen["competitor_references"][:3]:
            lines.append("- [" + item["title"].replace("]", "") + "](" + item["url"] + ")")
        lines += ["", "Discarded/noise: " + str(screen["discarded_count"]) +
                  "; repeated URLs across queries: " + str(len(result["repeat_links_across_queries"])), "",
                  "Next: verify exact Trends history, real Volume/KD/CPC, local SERP and user payability.", ""]
    return summary, "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-queries", type=int, default=7)
    ap.add_argument("--limit", type=int, default=4)
    args = ap.parse_args()
    summary, markdown = run(max_queries=max(1, min(args.max_queries, 8)), limit=max(1, min(args.limit, 10)))
    OUT.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    for p in (OUT / (summary["date"] + ".json"), OUT / "latest.json"):
        p.write_text(payload, encoding="utf-8")
    for p in (REPORTS / (summary["date"] + ".md"), REPORTS / "latest.md"):
        p.write_text(markdown, encoding="utf-8")
    print("queries=", len(summary["queries"]),
          "raw_links=", sum(x["total"] for x in summary["queries"]),
          "unique_links=", summary["unique_evidence_links_across_queries"],
          "review_leads=", sum(x["quality_screen"]["review_count"] for x in summary["queries"]))


if __name__ == "__main__":
    main()
