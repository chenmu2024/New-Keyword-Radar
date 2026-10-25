"""Read-only primary-source public social posts. No auth, cookies or workarounds.

Bluesky AppView and Mastodon hashtag timelines may be unavailable or rate limited.
Search results are leads, not independently verified customer pain or payments.
"""
from __future__ import annotations

import html
import json
import re
from urllib.error import HTTPError
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, text):
        self.parts.append(text)

    def text(self):
        return re.sub(r"\s+", " ", html.unescape(" ".join(self.parts))).strip()


def plain_html(value):
    parser = PlainText()
    parser.feed(str(value or "")[:8000])
    return parser.text()


def fetch_public_json(url, host, timeout=9):
    """Strict host restriction; only preselected public GET resources."""
    from urllib.parse import urlparse
    p = urlparse(url)
    if p.scheme != "https" or p.hostname != host:
        raise ValueError("Unapproved public JSON origin")
    req = Request(url, headers={"User-Agent": "NewKeywordRadar/1.0 (public research)",
                                "Accept": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        data = response.read(900_000)
    return json.loads(data)


def bluesky_posts(query, observed_at, limit, getter=fetch_public_json):
    try:
        from .social_signal_scout import signal
    except ImportError:
        from social_signal_scout import signal
    url = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?" + urlencode({
        "q": query, "sort": "latest", "limit": min(limit, 15)
    })
    try:
        payload = getter(url, "public.api.bsky.app")
    except HTTPError as err:
        # Bluesky's other documented unauthenticated AppView hostname has
        # different availability on ordinary 403 responses. Never retry 429.
        if err.code != 403:
            raise
        fallback = "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?" + urlencode({
            "q": query, "sort": "latest", "limit": min(limit, 15)
        })
        payload = getter(fallback, "api.bsky.app")
    if not isinstance(payload, dict) or not isinstance(payload.get("posts"), list):
        raise ValueError("Unexpected Bluesky AppView response")
    results = []
    for post in payload["posts"][:limit]:
        if not isinstance(post, dict):
            continue
        uri = str(post.get("uri") or "")
        author = post.get("author") or {}
        handle = str(author.get("handle") or "")
        record = post.get("record") or {}
        text = str(record.get("text") or "").strip()
        m = re.fullmatch(r"at://[^/]+/app\.bsky\.feed\.post/([a-zA-Z0-9]+)", uri)
        if not m or not re.fullmatch(r"[a-zA-Z0-9.-]{3,120}", handle):
            continue
        post_url = f"https://bsky.app/profile/{handle}/post/{m.group(1)}"
        item = signal("bluesky", post_url, text[:180], observed_at, "direct_public_post",
                      record.get("createdAt"), text, date_kind="author_claimed_post_timestamp")
        if item:
            item["source_query"] = query
            item["primary_text_available"] = True
            item["source_warning"] = ("Full public post text observed via AppView; "
                                      "not a verified customer need or a payment.")
            results.append(item)
    return results


def mastodon_hashtag(tag, observed_at, limit, getter=fetch_public_json):
    try:
        from .social_signal_scout import signal
    except ImportError:
        from social_signal_scout import signal
    if not re.fullmatch(r"[a-zA-Z0-9_]{2,40}", tag):
        raise ValueError("Invalid hashtag")
    url = "https://mastodon.social/api/v1/timelines/tag/" + quote(tag) + "?" + urlencode(
        {"limit": min(limit, 15)})
    payload = getter(url, "mastodon.social")
    if not isinstance(payload, list):
        raise ValueError("Unexpected public Mastodon status response")
    results = []
    for post in payload[:limit]:
        if not isinstance(post, dict):
            continue
        if post.get("visibility") != "public":
            continue
        txt = plain_html(post.get("content"))
        if not txt:
            continue
        item = signal("mastodon", post.get("url"), txt[:180], observed_at,
                      "direct_public_post", post.get("created_at"), txt)
        if item:
            item["source_query"] = "#" + tag
            item["primary_text_available"] = True
            item["source_warning"] = ("Public Mastodon post observed directly; "
                                      "not verified purchase intent.")
            results.append(item)
    return results


def hackernews_ask(observed_at, limit, getter=fetch_public_json):
    """Official Firebase public Ask HN item endpoints (not Algolia snippets).

    Read up to 'limit' newest IDs; no recursion into comment trees. Bounded
    request count protects no-key public access. The topic is user-authored
    question text, NOT evidence of actual buyers.
    """
    try:
        from .social_signal_scout import signal
    except ImportError:
        from social_signal_scout import signal
    base = "https://hacker-news.firebaseio.com/v0/"
    ids = getter(base + "askstories.json", "hacker-news.firebaseio.com")
    if not isinstance(ids, list):
        raise ValueError("Unexpected HN askstories response")
    out = []
    errors = 0
    for raw_id in ids[:min(limit, 9)]:
        if not isinstance(raw_id, int) or raw_id < 1:
            continue
        try:
            entry = getter(base + f"item/{raw_id}.json", "hacker-news.firebaseio.com")
        except (HTTPError, OSError, ValueError, KeyError):
            errors += 1
            continue
        if not isinstance(entry, dict) or entry.get("deleted") or entry.get("dead"):
            continue
        if entry.get("type") != "story":
            continue
        title = str(entry.get("title") or "")
        if not title:
            continue
        body = plain_html(entry.get("text"))
        ts = entry.get("time")
        created = datetime.fromtimestamp(ts, timezone.utc).isoformat() if isinstance(ts, int) and ts > 0 else None
        row = signal("hackernews_ask", f"https://news.ycombinator.com/item?id={raw_id}",
                     title, observed_at, "direct_public_post", created, body,
                     date_kind="source_server_created_at")
        if row:
            row["primary_text_available"] = True
            row["source_warning"] = ("Official HN Firebase Ask post; text may express "
                                     "a question, but is not a verified customer or payment.")
            out.append(row)
    if errors and not out:
        raise OSError(f"All {errors} Ask HN item lookups failed")
    return out
