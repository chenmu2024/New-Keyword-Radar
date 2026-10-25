"""Re-use the EXISTING zero-cost targeted research feed without new network calls.

Only GitHub Issues API result bodies are classed as direct public issues.
Reddit RSS and Algolia Ask HN excerpts are NOT marked verified full originals.
Stale or missing free-intelligence data is not silently treated as current.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from .social_signal_scout import signal
except ImportError:
    from social_signal_scout import signal


SOURCES = {
    "github_issues": ("github_issue", "direct_public_issue_api"),
    "reddit_rss": ("reddit", "public_rss_excerpt"),
    "reddit_index_fallback": ("reddit", "search_index_pointer"),
    "hackernews_ask": ("hackernews_ask", "indexed_public_post_excerpt"),
}


def parsed_time(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def import_free_intelligence(root: Path, when: datetime, max_age_hours=36, cap=50):
    path = root / "data/free-intelligence/latest.json"
    if not path.exists():
        return [], {"status": "missing", "count": 0, "message": "Existing free-intelligence snapshot unavailable"}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        updated = parsed_time(raw.get("generated_at"))
        if updated is None:
            return [], {"status": "bad_timestamp", "count": 0}
        delay = (when.astimezone(timezone.utc) - updated).total_seconds()
        if delay < -120 or delay > max_age_hours * 3600:
            return [], {"status": "stale", "count": 0,
                        "data_generated_at": updated.isoformat(),
                        "max_age_hours": max_age_hours}
        collected, source_urls = [], set()
        for plan in raw.get("queries", [])[:12]:
            query = str(plan.get("query") or "")[:160]
            for item in plan.get("items", [])[:80]:
                if not isinstance(item, dict):
                    continue
                original_platform = item.get("platform")
                if original_platform not in SOURCES:
                    continue
                platform, evidence_type = SOURCES[original_platform]
                address = str(item.get("url") or "")
                if platform == "github_issue":
                    # Only actual issue pages fetched from GitHub public Issues search.
                    if not re.fullmatch(r"https://github\.com/[^/?#]+/[^/?#]+/issues/\d+/?", address):
                        continue
                title = item.get("title") or ""
                body = item.get("snippet") or ""
                row = signal(platform, address, title, when.isoformat(), evidence_type,
                             item.get("published_at"), body,
                             date_kind="source_created_timestamp_if_available")
                if not row or row["id"] in source_urls:
                    continue
                source_urls.add(row["id"])
                row["source_query"] = query
                row["discovery_path"] = "existing_free_intelligence_snapshot"
                row["primary_text_available"] = evidence_type == "direct_public_issue_api"
                row["user_demand_verified"] = False
                row["payment_verified"] = False
                row["serp_verified"] = False
                if evidence_type == "direct_public_issue_api":
                    row["source_warning"] = ("GitHub Issue author title/body returned by official public Issues search. "
                                              "A feature request or bug report is NOT independently verified commercial demand.")
                elif evidence_type == "indexed_public_post_excerpt":
                    row["source_warning"] = ("HN Algolia indexed post excerpt; check original post URL to verify full text and context.")
                elif evidence_type == "public_rss_excerpt":
                    row["source_warning"] = ("Reddit search RSS excerpt, not necessarily full post or authentic comments.")
                else:
                    row["source_warning"] = ("Reddit search-engine result pointer only; original comments and body not verified.")
                collected.append(row)
                if len(collected) >= cap:
                    break
            if len(collected) >= cap:
                break
        return collected, {"status": "ok" if collected else "empty",
                           "count": len(collected),
                           "data_generated_at": updated.isoformat(),
                           "age_hours": round(max(0, delay) / 3600, 2),
                           "note": "Reused previously persisted evidence; not a new crawl and not buyer proof."}
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
        return [], {"status": "unavailable", "count": 0, "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
