"""Build an auditable, non-promotional validation queue from free discovery.

Discovery queries are NOT SEO keywords. Neither a ranked post, repository
nor complaint proves paid demand. All Volume/KD/CPC stay genuinely unknown.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlparse

FIRSTHAND = {"github_issues", "reddit_rss", "hackernews_ask"}
URL_CAP = 4


def stable_key(market, topic, query):
    raw = "\0".join((str(market), str(topic), str(query))).casefold()
    return sha256(raw.encode("utf-8")).hexdigest()[:14]


def link_record(item):
    return {
        "title": item.get("title", ""),
        "url": item.get("url", ""),
        "source": item.get("platform", ""),
        "published_at": item.get("published_at") or None,
        "author": (item.get("metadata") or {}).get("author") or None,
        "heuristic_score": (item.get("quality") or {}).get("score"),
        "verified_willingness_to_pay": False,
    }


def build_queue(scan, max_links=URL_CAP):
    if not 1 <= max_links <= 10:
        raise ValueError("max_links out of bounds")
    items = []
    all_links = set()
    for result in scan.get("queries", []):
        if "quality_screen" not in result:
            raise ValueError("Screen query evidence before building validation queue")
        meta = result.get("research_scope") or {}
        screen = result["quality_screen"]
        market = meta.get("market") or "Unspecified"
        topic = meta.get("topic") or "unspecified"
        query = result.get("query") or ""
        direct, references = [], []
        seen, verified_originators = set(), set()
        for entry in screen.get("review_leads", []):
            source = entry.get("platform")
            url = entry.get("url")
            if not url or url in seen or source not in FIRSTHAND:
                continue
            seen.add(url)
            direct.append(link_record(entry))
            author = ((entry.get("metadata") or {}).get("author") or "").strip().casefold()
            # Without an attributable originator, uniqueness of user is unknown.
            if author:
                verified_originators.add((source, author))
        for entry in screen.get("competitor_references", []):
            url = entry.get("url")
            if not url or url in seen:
                continue
            seen.add(url)
            references.append(link_record(entry))
        all_links.update(seen)
        has_direct = bool(direct)
        stage = ("needs_independent_corroboration" if has_direct else
                 "needs_firsthand_problem_evidence")
        if len(verified_originators) >= 2:
            stage = "needs_search_and_payment_validation"
        source_health = {name: (status.get("status") or "unknown")
                         for name, status in result.get("sources", {}).items()}
        unavailable = [name for name, value in source_health.items()
                       if value in ("degraded", "error", "unsupported")]
        keyword_from_trends = query if meta.get("kind") == "trend_lead_not_verified" else None
        items.append({
            "id": stable_key(market, topic, query),
            "market": market,
            "language": meta.get("locale"),
            "research_topic": topic,
            "research_intent": meta.get("intent"),
            "query_used_for_discovery": query,
            "keyword_candidate": keyword_from_trends,
            "keyword_is_validated": False,
            "stage": stage,
            "priority": "review_first" if has_direct else "source_research",
            "firsthand_evidence_count": len(direct),
            "attributable_independent_authors": len(verified_originators),
            "contextual_reference_count": len(references),
            "firsthand_evidence": direct[:max_links],
            "contextual_references": references[:max_links],
            "source_health": source_health,
            "unreliable_sources": unavailable,
            "evidence_gaps": [
                "independent_firsthand_user_reports" if len(verified_originators) < 2 else None,
                "exact_local_keyword_search_volume",
                "keyword_difficulty",
                "CPC_and_advertiser_demand",
                "local_SERP_competitor_traffic_and_content_gap",
                "willingness_to_pay_or_verified_ads_business_model"
            ],
            "metrics": {
                "volume": None, "kd": None, "cpc_usd": None,
                "country": market, "data_source": None, "checked_at": None,
                "verified_by_human": False,
            },
            "search_validation_actions": [
                "Identify exact search query used by customers (not the discovery string).",
                "Check country-specific Volume, KD, CPC and cite provider and date.",
                "Verify local SERP type, target competitors, site traffic and feasibility.",
                "Find >=2 attributable, independent firsthand accounts of the same problem.",
                "Test ad/SaaS monetization and budget; do not propose a build before validation.",
            ],
            "may_be_recommended_for_build": False,
            "note": "No verified keyword or monetization data; query is a research prompt only.",
        })
        items[-1]["evidence_gaps"] = [x for x in items[-1]["evidence_gaps"] if x]
    # A single source linked in multiple markets is NOT corroborating demand.
    items.sort(key=lambda x: (x["priority"] != "review_first",
                              {"US": 0, "BR": 1, "MX": 2}.get(x["market"], 3),
                              x["research_topic"], x["id"]))
    return {
        "date": scan.get("date"),
        "generated_at": scan.get("generated_at"),
        "schema_version": 1,
        "status": "research_queue_not_approved_opportunities",
        "total_topics": len(items),
        "firsthand_qualified_topics": sum(x["firsthand_evidence_count"] > 0 for x in items),
        "build_ready_count": 0,
        "independent_discovery_urls": len(all_links),
        "market_counts": dict(sorted(Counter(x["market"] for x in items).items())),
        "topics": items,
        "rules": [
            "Never infer Volume/KD/CPC from free search or Trends relative indices.",
            "Independent evidence requires distinct attributable originators, not links or repeated listings.",
            "Even independent pain does not prove local organic demand or willingness to pay.",
            "Continue scanning when no opportunity qualifies; never invent 1-3 candidates.",
        ],
    }


def render_queue(queue):
    lines = [
        "# SaaS / new-keyword validation queue — " + str(queue.get("date") or "unknown"),
        "", "**RESEARCH ONLY. 0 build-ready opportunities unless separately validated.**",
        "",
        "Topics: " + str(queue["total_topics"]) +
        " · Topics with first-person leads: " + str(queue["firsthand_qualified_topics"]) +
        " · Ready to build: " + str(queue["build_ready_count"]),
        "", "Volume / KD / CPC: **not available**. These discovery queries are not "
        "necessarily commercially searched keywords.", ""
    ]
    for item in queue["topics"]:
        lines += [
            "## " + item["market"] + " · " + item["research_topic"],
            "", "Search for user pain: `" + item["query_used_for_discovery"] + "`",
            "", "Stage: **" + item["stage"] + "**; priority: " + item["priority"] +
            "; identifiable originators: " + str(item["attributable_independent_authors"]),
            "", "Source limitations: " + (", ".join(item["unreliable_sources"]) or "none reported"),
            "", "**Firsthand requests**"
        ]
        if not item["firsthand_evidence"]:
            lines.append("- No qualifying public first-person request yet.")
        for e in item["firsthand_evidence"]:
            lines.append("- [" + e["title"].replace("]", "") + "](" + e["url"] + ") "
                         + "(" + e["source"] + ", source author: " + (e["author"] or "unknown") + ")")
        lines.append("")
        lines.append("**Competitor / context references (not demand validation)**")
        if not item["contextual_references"]:
            lines.append("- No relevant references identified.")
        for e in item["contextual_references"]:
            lines.append("- [" + e["title"].replace("]", "") + "](" + e["url"] + ") "
                         + "(" + e["source"] + ")")
        lines += ["", "**Next checks:**",
                  "- Determine the actual customer search keyword.",
                  "- Check " + item["market"] + " Volume/KD/CPC with dated source.",
                  "- Verify SERP competitors (ideally 10k–100k monthly traffic evidence).",
                  "- Confirm independent problem reports, feasibility and monetization.",
                  ""]
    return "\n".join(lines)
