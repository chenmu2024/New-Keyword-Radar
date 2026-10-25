"""Read-only primary-source public social posts. No auth, cookies or workarounds.

Bluesky AppView and Mastodon hashtag timelines may be unavailable or rate limited.
Search results are leads, not independently verified customer pain or payments.
"""
from __future__ import annotations

import html
import json
import re
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
    from .social_signal_scout import signal
    url = "https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts?" + urlencode({
        "q": query, "sort": "latest", "limit": min(limit, 15)
    })
    payload = getter(url, "public.api.bsky.app")
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
    from .social_signal_scout import signal
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
