"""Local-only cross-day observation and exact-keyword research suggestions.

A link repeated on several dates is not independent demand. Saved dated queues
provide observation history only, not article publication dates, traffic
measurements, or an automatic approval gate.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import json
import re

DATED_QUEUE = re.compile(r"^(\d{4}-\d{2}-\d{2})-validation-queue\.json$")
DEFAULT_LOOKBACK = 14


def _links(topic, key):
    return {str(item.get("url", "")).strip()
            for item in topic.get(key, []) if str(item.get("url", "")).strip()}


def load_history(directory, today, lookback_days=DEFAULT_LOOKBACK):
    """Return dated prior snapshots only; ignore malformed and today's queue."""
    today = date.fromisoformat(str(today))
    if not 1 <= lookback_days <= 30:
        raise ValueError("lookback_days must be between 1 and 30")
    folder = Path(directory)
    days, errors = {}, []
    if not folder.is_dir():
        return days, errors
    for file in sorted(folder.glob("*-validation-queue.json")):
        match = DATED_QUEUE.fullmatch(file.name)
        if not match:
            continue
        try:
            day = date.fromisoformat(match.group(1))
        except ValueError:
            continue
        if day >= today or day < today - timedelta(days=lookback_days):
            continue
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or payload.get("date") != day.isoformat():
                raise ValueError("date or structure mismatch")
            if not isinstance(payload.get("topics"), list):
                raise ValueError("topics list absent")
            days[day.isoformat()] = payload
        except (OSError, ValueError, TypeError):
            errors.append(file.name)
    return dict(sorted(days.items())), errors


def same_research_area(a, b):
    """Research-area recurrence is not proof of the *same* customer problem."""
    if a.get("market") != b.get("market"):
        return False
    intent_a, intent_b = a.get("research_intent"), b.get("research_intent")
    if intent_a and intent_b:
        return intent_a == intent_b
    return (a.get("research_topic") == b.get("research_topic") and
            a.get("query_used_for_discovery") == b.get("query_used_for_discovery"))


def annotate_queue(queue, archive_dir, target_config, lookback_days=DEFAULT_LOOKBACK):
    """Annotate in place. Does not change stages or build-ready decisions."""
    if not queue.get("date"):
        raise ValueError("dated queue required")
    history, unreadable = load_history(archive_dir, queue["date"], lookback_days)
    cfg = json.loads(Path(target_config).read_text(encoding="utf-8"))
    settings = cfg.get("targets", {})
    for item in queue.get("topics", []):
        market = item.get("market")
        intent = item.get("research_intent")
        config = settings.get(str(market) + ":" + str(intent), {})
        terms = list(config.get("terms", []))[:5]
        if not all(isinstance(term, str) and term.strip() for term in terms):
            raise ValueError("Invalid exact-keyword research terms in configuration")
        item["keyword_research"] = {
            "country": market,
            "language": config.get("language") or item.get("language"),
            "exact_terms_to_check": terms,
            "hypotheses_only": True,
            "original_website_keywords_unchanged": True,
            "monthly_search_volumes": None,
            "keyword_difficulties": None,
            "cpc_values": None,
            "evidence_provider": None,
            "market_serp_checked": False,
            "monetization_hypothesis": config.get("monetization_hypothesis") or
                                        "Undetermined; validate business model",
            "needs_manual_volume_kd_cpc_validation": True,
        }
        earlier, area_dates, exact_query_dates = [], set(), set()
        for day, prior in history.items():
            matches = [topic for topic in prior.get("topics", [])
                       if isinstance(topic, dict) and same_research_area(item, topic)]
            if matches:
                earlier.extend(matches)
                area_dates.add(day)
                if any(topic.get("query_used_for_discovery") ==
                       item.get("query_used_for_discovery") for topic in matches):
                    exact_query_dates.add(day)
        old_direct = set().union(*(_links(t, "firsthand_evidence") for t in earlier))
        old_context = set().union(*(_links(t, "contextual_references") for t in earlier))
        now_direct = _links(item, "firsthand_evidence")
        now_context = _links(item, "contextual_references")
        # Repeat daily sightings don't make an item a fresh report or
        # independent originator; dates here are archive capture dates.
        item["history"] = {
            "history_window_days": lookback_days,
            "prior_archive_days_scanned": len(history),
            "previous_days_in_same_research_area": len(area_dates),
            "previous_days_with_exact_query": len(exact_query_dates),
            "new_firsthand_urls_in_saved_sample": len(now_direct - old_direct),
            "returning_firsthand_urls_in_saved_sample": len(now_direct & old_direct),
            "new_context_urls_in_saved_sample": len(now_context - old_context),
            "returning_context_urls_in_saved_sample": len(now_context & old_context),
            "historical_firsthand_urls_in_saved_sample": len(old_direct),
            "historical_context_urls_in_saved_sample": len(old_context),
            "is_repeat_user_demand_verified": False,
            "interpretation": (
                "Observed links in saved, truncated report samples only. "
                "Repeated links are not independent demand. A recurring topic "
                "may be a rotating query, not recurring customer complaints."
            )
        }
    queue["historical_analysis"] = {
        "lookback_days": lookback_days,
        "prior_archive_days_found": len(history),
        "prior_archive_dates": list(history),
        "unreadable_archive_files": unreadable,
        "confidence": "insufficient_history" if len(history) < 3 else "observation_only",
        "metrics_verified": False,
        "independent_users_inferred_from_repeat_urls": 0,
    }
    return queue
