"""Cross-reference current public social links against exact 7-day rising queries.

Only exact normalized multi-token mentions become matches. This is a discovery
linkage, NOT proof of keyword search volume, rankings, original customer need,
payment, or evidence to bypass the established 90-day/5-year gates.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ZoneInfo("Asia/Shanghai")
NOISY = {"casino", "slots", "slot", "bet", "betting", "lottery", "gambling",
         "government", "eleição", "elecciones", "president", "trump", "xxx",
         "porn", "deva555"}
INTENT = re.compile(
    r"\b(how (can|do|to)|where can i|does anyone know|any tool|need (a|an|to)|"
    r"looking for|is there a|wish there (was|were)|"
    r"como (puedo|hago|fazer|crear|hacer)|preciso de|algu[eé]m sabe|"
    r"necesito (una?|hacer)|alguna herramienta|alguem sabe)\b", re.I)


def normalize(s):
    return " ".join("".join(
        ch if (unicodedata.category(ch)[0] in "LN" or ch.isspace()) else " "
        for ch in unicodedata.normalize("NFKC", str(s or "")).casefold()
    ).split())


def viable_query(query):
    words = normalize(query).split()
    if len(words) < 2 or len(words) > 9:
        return False
    if not (9 <= len(" ".join(words)) <= 65):
        return False
    if any(word in NOISY for word in words):
        return False
    if len(set(words)) == 1:
        return False
    return True


def read_json(path, default):
    if not path.exists():
        return default
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected object: " + str(path))
    return value


def recent_seed_queries(root, when, day_offset=0):
    date_local = when.astimezone(LOCAL).date() - timedelta(days=day_offset)
    data = read_json(root / "data/seed-scout-daily" / f"{date_local.isoformat()}.json", {})
    # Freshest scan first; do not assert complete unless archive says complete.
    entries = data.get("discoveries") or []
    result = {}
    for row in entries:
        if not isinstance(row, dict):
            continue
        q = normalize(row.get("query"))
        if viable_query(q):
            try:
                rising = float(row.get("rise_value") or 0)
            except (TypeError, ValueError):
                rising = 0
            if q not in result or rising > result[q]["rise_value"]:
                result[q] = {"query": q, "seed": str(row.get("seed") or ""),
                             "rise_value": rising}
    return result, {
        "archive_date": date_local.isoformat(),
        "scanned_seed_count": data.get("scanned_seed_count"),
        "target_seed_count": data.get("target_seed_count"),
        "complete_daily_target": data.get("complete_daily_target"),
        "rising_total": len(entries),
        "eligible_exact_queries": len(result),
    }


def match_signals(rows, keywords, max_rows=30):
    matches = {}
    for item in rows:
        if not isinstance(item, dict) or not item.get("url"):
            continue
        text = normalize((item.get("title") or "") + " " + (item.get("description") or ""))
        if not text:
            continue
        # Boundary match protects against unrelated substring matches.
        for q, obj in keywords.items():
            if not viable_query(q):
                continue
            if (" " + q + " ") not in (" " + text + " "):
                continue
            bucket = matches.setdefault(q, {"query": q,
                "relative_rising_value": obj["rise_value"],
                "seed": obj["seed"], "sources": {}, "links": []})
            p = item.get("platform") or "unknown"
            bucket["sources"][p] = bucket["sources"].get(p, 0) + 1
            is_direct = item.get("evidence_type") == "direct_public_post"
            has_question = is_direct and bool(INTENT.search(text))
            bucket["links"].append({
                "platform": p, "url": item["url"], "title": item.get("title"),
                "published_at": item.get("published_at"),
                "evidence_type": item.get("evidence_type"),
                "potential_first_person_question": bool(has_question),
                "verified_customer_demand": False,
                "original_comments_verified": False,
            })
    scored = list(matches.values())
    for match in scored:
        urls = {l["url"] for l in match["links"]}
        match["independent_platforms"] = len(match["sources"])
        match["distinct_urls"] = len(urls)
        match["original_post_question_hints"] = sum(
            bool(l["potential_first_person_question"]) for l in match["links"])
        match["ready_to_build"] = False
        match["requires"] = ("Human verification of an explicit user need, "
                             "complete-query SEO history and current SERP; no API cost.")
        match["links"] = match["links"][:6]
    return sorted(scored, key=lambda x: (
        -x["original_post_question_hints"],
        -x["independent_platforms"],
        -x["distinct_urls"],
        -x["relative_rising_value"], x["query"]
    ))[:max_rows]


def update_correlation(root=ROOT, when=None, social=None):
    when = when or datetime.now(timezone.utc)
    social = social or read_json(root / "data/social-signals/latest.json", {})
    keywords, coverage = recent_seed_queries(root, when)
    if not keywords:
        keywords, coverage = recent_seed_queries(root, when, day_offset=1)
        coverage["fallback_previous_day"] = True
    rows = social.get("items") or []
    ranked = match_signals(rows, keywords)
    result = {"generated_at": when.isoformat(),
              "social_generated_at": social.get("generated_at"),
              "trends_coverage": coverage,
              "social_unique_in_run": social.get("unique_in_run"),
              "cross_matches": len(ranked),
              "candidates": ranked,
              "caveat": ("Exact multiword overlap is only a research lead, not verified "
                         "demand, traffic, money, recent trend trajectory, or easy SERP. "
                         "No automatic recommendation or modification of pending keywords.")}
    dest = root / "data/social-signals/correlations-latest.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# V4 exact query × social-source linkage", "",
        f"- Generated: {result['generated_at']}",
        f"- Source last updated: {result['social_generated_at']}",
        f"- Trends archive: {coverage['archive_date']} ({coverage.get('scanned_seed_count')}/{coverage.get('target_seed_count')}; complete={coverage.get('complete_daily_target')})",
        f"- Eligible multiword rising queries: {coverage['eligible_exact_queries']}",
        f"- Cross-source matches this run: {len(ranked)}",
        "- Matches are *discovery leads only*; neither original demand nor revenue are proven.", "",
    ]
    for entry in ranked[:12]:
        lines += [
            f"## {entry['query']}", "",
            f"- Relative Trends rising value: {entry['relative_rising_value']} (NOT Volume)",
            f"- Distinct matched platforms: {entry['independent_platforms']}",
            f"- Direct public-post question hints: {entry['original_post_question_hints']}",
        ]
        lines.extend(f"- {link['platform']}: {link['url']} ({link['evidence_type']})"
                     for link in entry["links"])
        lines.append("")
    if not ranked:
        lines += ["No reliable full-query cross-source overlap found in this scan.", ""]
    report = root / "reports/social-signals/correlations-latest.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines), encoding="utf-8")
    return result


if __name__ == "__main__":
    print(json.dumps({k: v for k, v in update_correlation().items() if k != "candidates"}, ensure_ascii=False))
