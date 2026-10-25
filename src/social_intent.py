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
        if not isinstance(row, dict) or row.get("evidence_type") != "direct_public_post":
            continue
        if not row.get("primary_text_available"):
            continue
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
