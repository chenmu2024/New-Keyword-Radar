"""Derive tentative long-tail search-intent hypotheses from public user questions.

This uses transparent rules only and never silently treats a question, phrase
overlap, published launch or keyword suggestion as proven SEO demand.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter

PROMO = re.compile(
    r"\b(we (just )?(launched|built|released)|i (just )?(launched|built|released)|"
    r"sign up|check out my|now available|launching today|special offer|"
    r"get started with|subscribe now)\b", re.I
)
ASK = re.compile(
    r"\b(does anyone know|any recommendations? for|is there (a|any)|"
    r"feature request|request:|please add|would it be possible to|"
    r"it would help if|support for|" 
    r"i (really )?need|looking for|how (do i|can i|to)|"
    r"any (free )?(tool|app|site)|"
    r"preciso de|algu[eé]m sabe|como (fazer|criar|posso)|"
    r"necesito (una?|algo)|alguna herramienta|cómo (hago|puedo|crear|hacer))\b", re.I
)
ACTION = re.compile(
    r"\b(?:a|an|any|free|online|simple|good|easy|the|best|opensource|open source)?\s*"
    r"(?:tool|app|site|software|generator|editor|converter|template|way|service|website)\s*"
    r"(?:to|for|that can|which can|para|de)?\s*", re.I
)
TRAIL = re.compile(r"\b(?:thanks|please help|any suggestions?|let me know|appreciated|thanks in advance)\b.*", re.I)
TOOL_INTENT = re.compile(
    r"\b(tool|app|application|website|web site|software|service|generator|"
    r"template|converter|editor|download|export|batch|bulk|csv|xlsx|svg|pdf|"
    r"script|spreadsheet|file|automation|automatizar|automate|"
    r"resize|merge|split|upload|import|format|filter|transform|" 
    r"ferramenta|herramienta|planilha|archivo|arquivo|modelo|plantilla)\b", re.I
)
SPEND_CLAIM = re.compile(
    r"\b(i (?:paid|bought|purchased|subscribed to)|"
    r"eu (?:paguei|comprei)|(?:pagué|compré|he pagado|he comprado))\b", re.I
)
AMOUNT = re.compile(r"(?i)\b(?:paid|paguei|pagué|pagado)\s*(?:about|around|roughly)?\s*([$€£]\s*\d+(?:[.,]\d{1,2})?)")
BORING = {"there", "anyone", "know", "looking", "free", "online", "tool", "tools",
          "app", "apps", "something", "this", "that", "those", "help", "with", "make",
          "create", "get", "some", "website", "would", "please", "thing",
          "there's", "any", "one", "it", "them", "for", "and", "you", "use"}

def normalize(s):
    return " ".join("".join(
        c if (unicodedata.category(c)[0] in "LN" or c.isspace()) else " "
        for c in unicodedata.normalize("NFKC", str(s or "")).casefold()
    ).split())

def hypothesis(text):
    """Returns post-grounded tentative query fragment, never an asserted search volume."""
    raw = re.sub(r"\s+", " ", str(text or "")).strip()
    if not raw or PROMO.search(raw):
        return None
    # A general how-to question is NOT evidence of demand for a web tool.
    # Require an explicit artefact, tool, file operation or automation context.
    if not TOOL_INTENT.search(raw):
        return None
    m = ASK.search(raw)
    if not m:
        return None
    rest = raw[m.end():].lstrip(" ,:?").strip()
    rest = ACTION.sub(" ", rest, count=1).strip()
    rest = TRAIL.sub("", rest).split("?", 1)[0].split("!", 1)[0]
    rest = re.split(r"[.;\n]", rest, maxsplit=1)[0]
    query = normalize(rest)
    parts = query.split()
    # Maximum 11 words, min 2 independently meaningful tokens, prevent guesses.
    parts = parts[:11]
    if len(parts) < 2:
        return None
    meaning = {word for word in parts if len(word) >= 3 and word not in BORING}
    if len(meaning) < 2:
        return None
    query = " ".join(parts)
    if len(query) > 95:
        return None
    return query

def mine_user_questions(rows, limit=15):
    """Only direct public posts can create primary-text hypotheses."""
    seen = set()
    candidates = []
    for row in rows:
        if not isinstance(row, dict) or row.get("evidence_type") not in ("direct_public_post", "direct_public_issue_api"):
            continue
        if not row.get("primary_text_available"):
            continue
        if row.get("evidence_type") == "direct_public_issue_api":
            # Issues can express 'feature request' in title while body
            # describes only the inputs and failure symptoms.
            text = " ".join([str(row.get("title") or ""),
                             str(row.get("description") or "")]).strip()
        else:
            text = str(row.get("description") or row.get("title") or "")
        proposal = hypothesis(text)
        if not proposal:
            continue
        key = (proposal, row.get("url"))
        if key in seen:
            continue
        seen.add(key)
        candidates.append({
            "proposed_query": proposal,
            "original_post_url": row.get("url"),
            "original_platform": row.get("platform"),
            "original_post_text": text[:350],
            "published_at": row.get("published_at"),
            "demand_status": "unverified_question_hint",
            "search_volume": None, "keyword_difficulty": None,
            "actual_user_paid": False, "ready_to_build": False,
            "necessary_verification": "Check authentic user intent, independent demand, Trends and current SERP; verify $0 ongoing cost.",
        })
    return candidates[:limit]



def mine_buyer_spend_claims(rows, limit=12):
    """First-person payment mentions from original posts, NEVER verified transactions."""
    seen = set()
    results = []
    for row in rows:
        if not isinstance(row, dict) or row.get("evidence_type") not in ("direct_public_post", "direct_public_issue_api"):
            continue
        if not row.get("primary_text_available"):
            continue
        body = str(row.get("description") or row.get("title") or "")
        if not SPEND_CLAIM.search(body):
            continue
        url = row.get("url")
        if not url or url in seen:
            continue
        seen.add(url)
        amount = AMOUNT.search(body)
        results.append({
            "original_post_url": url,
            "platform": row.get("platform"),
            "published_at": row.get("published_at"),
            "self_reported_amount": amount.group(1).replace(" ", "") if amount else None,
            "post_excerpt": body[:340],
            "evidence_level": "independent_author_self_report_not_payment_processor",
            "transaction_verified": False,
            "business_income_verified": False,
            "ready_to_build": False,
            "next_check": "Identify product, exact complaint, free alternatives, actual keyword demand and original post context.",
        })
    return results[:limit]
