"""Explainable, conservative opportunity-lead scoring (NOT SEO metrics).

Evidence consists only of links, source metadata and visible text. Scores are
heuristic triage signals, not search demand or an Ahrefs/Semrush substitute.
"""
from __future__ import annotations
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import re
from urllib.parse import urlparse

STOPWORDS = {
    "the", "for", "and", "with", "from", "into", "online", "near", "new", "request",
    "micro", "brasil", "brazil", "mexico", "méxico", "de", "da", "do", "das", "dos", "para",
    "como", "com", "uma", "una", "por", "que", "del", "los", "las", "and", "software"
}
PAIN = re.compile(
    r"\b(bug|broken|missing|lack|pain|struggl|issue|frustrat|can't|cannot|need|"
    r"wish|problem|request|alternative|manual|expensive|slow|failing|"
    r"erro|falha|falta|preciso|necessito|automatizar|problema|"
    r"falla|necesito|automatización|solución|solucao|solução|"
    r"feature request|help wanted|looking for)\b", re.I
)
BUY = re.compile(
    r"\b(api|automation|automatiza\w*|saas|subscription|pricing|paid|pay|"
    r"commercial|customer|client|cliente|product|produto|producto|"
    r"calculator|calculadora|generator|generador|gerador|invoice|factura|"
    r"payroll|nomina|nómina|compliance|tool|software|workflow|template|"
    r"dashboard|plugin|extension|subscription|billing|integration)\b", re.I
)
NOISE = re.compile(
    r"(\b(ops comms|forever agent log|do not close|session_\w+|"
    r"trig_\w+|routine triage|fix typo|typo fix|update dependencies|"
    r"deps update|bump version|release notes|readme only|chore\b|"
    r"automated check|commit bot|test fixture)\b|"
    r"\b(election|political|president|celebrity|episode|movie review|"
    r"football|lottery|earthquake)\b)", re.I
)
SOURCE_WEIGHT = {
    "github_issues": 22, "reddit_rss": 20, "reddit_index_fallback": 11,
    "github_repositories": 15, "google_news_rss": 12,
    "bing_rss": 8, "duckduckgo": 8
}
EVIDENCE_MIN = 45

def words(text):
    return {w for w in re.findall(r"[\wÀ-ÿ]{3,}", str(text).casefold()) if w not in STOPWORDS}

def age_days(value, reference=None):
    if not value:
        return None
    now = reference or datetime.now(timezone.utc)
    try:
        s = str(value)
        dt = datetime.fromisoformat(s.replace("Z", "+00:00")) if "T" in s or s[:4].isdigit() else parsedate_to_datetime(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (now - dt.astimezone(timezone.utc)).days)
    except (ValueError, OverflowError, TypeError, IndexError):
        return None

def score(item, query, reference=None):
    title = str(item.get("title") or "")
    body = str(item.get("snippet") or "")
    text = title + " " + body
    source = str(item.get("platform") or "")
    tokens = words(query)
    content_words = words(text)
    matched = sorted(tokens & content_words)
    relevance = len(matched) / len(tokens) if tokens else 0
    pain = bool(PAIN.search(text))
    monetization = bool(BUY.search(text))
    spam = bool(NOISE.search(text))
    age = age_days(item.get("published_at"), reference=reference)
    notes = []
    pts = SOURCE_WEIGHT.get(source, 6)
    if matched:
        pts += min(30, round(30 * relevance))
        notes.append("query_terms:" + ",".join(matched[:4]))
    if pain:
        pts += 16
        notes.append("problem_or_request_language")
    if monetization:
        pts += 12
        notes.append("commercial_or_tool_context")
    if age is not None:
        if age <= 7:
            pts += 14
            notes.append("published_within_7_days")
        elif age <= 30:
            pts += 9
            notes.append("published_within_30_days")
        elif age <= 90:
            pts += 3
        elif age > 365:
            pts -= 16
            notes.append("stale_over_one_year")
    else:
        notes.append("publication_date_unverified")
    if spam:
        pts -= 75
        notes.append("non_opportunity_or_automated_noise")
    if len(title.strip()) < 9:
        pts -= 10
        notes.append("very_short_title")
    if not matched and tokens:
        pts -= 15
        notes.append("query_terms_not_found")
    # A result is only a REVIEW lead, never a verified opportunity.
    eligible = (not spam and bool(matched) and (pain or monetization)
                and pts >= EVIDENCE_MIN and bool(item.get("url")))
    if source not in SOURCE_WEIGHT:
        eligible = False
        notes.append("unknown_source_not_eligible")
    return {"score": max(0, min(100, pts)), "screening": "review" if eligible else "discard",
            "reasons": notes, "matched_query_terms": matched,
            "published_age_days": age, "verified_volume": None, "verified_kd": None,
            "verified_cpc": None, "is_verified_opportunity": False}

def screen_result(result):
    query = result.get("query") or ""
    scored = []
    dropped = []
    for item in result.get("items", []):
        s = score(item, query)
        enriched = dict(item, quality=s)
        if s["screening"] == "review":
            scored.append(enriched)
        else:
            dropped.append({"url": item.get("url"), "title": item.get("title"),
                            "score": s["score"], "reasons": s["reasons"]})
    scored.sort(key=lambda i: (-i["quality"]["score"], i.get("url", "")))
    result["quality_screen"] = {
        "method": "heuristic source/text triage; not SEO volume, paid intent, or actual user demand",
        "review_count": len(scored), "discarded_count": len(dropped),
        "review_leads": scored, "discarded": dropped,
        "next_validation": ["Check exact query Google Trends history", "Check Volume/KD/CPC using real source",
                            "Inspect local country SERP", "Verify independent user pain and payability"]
    }
    return result
