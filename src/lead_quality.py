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
    r"\b(bugs?|broken|missing|lack|pains?|struggl\w*|issues?|frustrat\w*|can't|cannot|"
    r"needs?|wish\w*|problems?|requests?|alternatives?|manually?|expensive|slow|fail\w*|"
    r"errors?|erro\w*|falha\w*|falta|precis\w*|necessit\w*|automatiz\w*|"
    r"problemas?|fallas?|necesit\w*|manualmente|descuadre|inconsistenc\w*|"
    r"reconcilia\w*|conciliac\w*|conciliaç\w*)\b", re.I
)
BUY = re.compile(
    r"\b(api|automation|automatiza\w*|saas|subscription|pricing|paid|pay|"
    r"commercial|customers?|clients?|clientes?|products?|produtos?|productos?|"
    r"calculators?|calculadoras?|generators?|generadores?|geradores?|"
    r"invoices?|facturas?|facturação|faturamento|fiscais?|fiscal|CFDI|SAT|"
    r"payroll|nomina|nómina|folha|pagamento|contabilidade|impuestos?|"
    r"compliance|tools?|software|workflows?|templates?|dashboards?|"
    r"plugins?|extensions?|billing|integrations?|integraç\w*)\b", re.I
)
NOISE = re.compile(
    r"(\b(ops comms|forever agent log|do not close|session_\w+|"
    r"trig_\w+|routine triage|fix typo|typo fix|update dependencies|"
    r"deps update|bump version|release notes|readme only|chore\b|"
    r"automated check|commit bot|test fixture)\b|"
    r"\b(election|political|president|celebrity|episode|movie review|"
    r"football|lottery|earthquake)\b)", re.I
)
INTERNAL_TASK_TITLE = re.compile(
    r"^\\s*(build|implement|refactor|revisar|fortalecer|create|add|update|fix|"
    r"document|write|setup|audit|migrate|test|expand|configure|integrate|"
    r"complete|develop|design|establish)\\b", re.I
)
EXPLICIT_CUSTOMER_REPORT = re.compile(
    r"\\b(our customers?|customers? report|users? report|users? complain|"
    r"as a user|user feedback|buyer requests?|customer requests?|"
    r"we need|i need|i cannot|we cannot|we can't|i can't|"
    r"preciso|necessit\\w*|clientes? reclam\\w*|usuários? relat\\w*|"
    r"necesito|clientes? reportan|usuarios? reportan)\\b", re.I
)

SOURCE_WEIGHT = {
    "github_issues": 22, "reddit_rss": 20, "reddit_index_fallback": 11,
    "github_repositories": 15, "google_news_rss": 12,
    "bing_rss": 8, "duckduckgo": 8, "hackernews_ask": 20
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
    # For broad exploratory queries, explicit buyer pain + tooling context
    # can qualify for review even when the title uses different vocabulary.
    alternative_intent = pain and monetization and source in ("github_issues", "reddit_rss", "hackernews_ask")
    eligible = (not spam and (bool(matched) or alternative_intent)
                and (pain or monetization)
                and pts >= EVIDENCE_MIN and bool(item.get("url")))
    if source not in SOURCE_WEIGHT:
        eligible = False
        notes.append("unknown_source_not_eligible")
    first_person_demand_sources = {"github_issues", "reddit_rss", "hackernews_ask"}
    contextual_sources = {"github_repositories", "google_news_rss", "bing_rss",
                          "duckduckgo", "reddit_index_fallback"}
    # News, SERP snippets, GitHub products and indexed Reddit copies are not
    # evidence that an identifiable user requested a feature or would pay.
    if source not in first_person_demand_sources:
        eligible = False
        notes.append("context_only_not_first_person_demand")
    if source == "github_issues" and INTERNAL_TASK_TITLE.search(title):
        if not EXPLICIT_CUSTOMER_REPORT.search(text):
            eligible = False
            notes.append("engineering_task_without_explicit_user_report")
    # A genuine user-reported pain signal is required in addition to industry terms.
    if not pain:
        eligible = False
        notes.append("no_explicit_user_pain_in_snippet")
    classification = ("review" if eligible
                      else "reference" if source in contextual_sources and not spam
                      else "discard")
    return {"score": max(0, min(100, pts)), "screening": classification,
            "reasons": notes, "matched_query_terms": matched,
            "published_age_days": age, "verified_volume": None, "verified_kd": None,
            "verified_cpc": None, "is_verified_opportunity": False}

def screen_result(result):
    query = result.get("query") or ""
    scored = []
    references = []
    dropped = []
    for item in result.get("items", []):
        s = score(item, query)
        enriched = dict(item, quality=s)
        if s["screening"] == "review":
            scored.append(enriched)
        elif s["screening"] == "reference":
            references.append(enriched)
        else:
            dropped.append({"url": item.get("url"), "title": item.get("title"),
                            "score": s["score"], "reasons": s["reasons"]})
    scored.sort(key=lambda i: (-i["quality"]["score"], i.get("url", "")))
    result["quality_screen"] = {
        "method": "heuristic source/text triage; not SEO volume, paid intent, or actual user demand",
        "review_count": len(scored), "reference_count": len(references),
        "discarded_count": len(dropped),
        "review_leads": scored, "competitor_references": references, "discarded": dropped,
        "next_validation": ["Check exact query Google Trends history", "Check Volume/KD/CPC using real source",
                            "Inspect local country SERP", "Verify independent user pain and payability"]
    }
    return result
