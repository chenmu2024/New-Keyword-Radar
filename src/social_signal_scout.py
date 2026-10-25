"""V4 public social-signal discovery, with explicit source provenance.

Never signs in, bypasses platform restrictions, calls paid APIs, infers
search volume, or treats search index snippets as original user comments.
This is a separate discovery feed; existing 74-root and 90-day gates
are intentionally untouched.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

try:
    from .free_search import bing_rss, duckduckgo
except ImportError:
    from free_search import bing_rss, duckduckgo

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/social_sources.json"
STATE = ROOT / "state/social_seen.json"
DATA = ROOT / "data/social-signals"
REPORTS = ROOT / "reports/social-signals"

HOSTS = {
    "tiktok": ("tiktok.com",),
    "youtube_shorts": ("youtube.com", "youtu.be"),
    "instagram_reels": ("instagram.com",),
    "x": ("x.com", "twitter.com"),
    "bluesky": ("bsky.app",),
    "mastodon": ("mastodon.social",),
    "hackernews_ask": ("news.ycombinator.com",),
}
INTENT_WORDS = re.compile(
    r"\b(how to|how do i|make one|generator|template|filter|editor|download|"
    r"create|tool|any app|need an app|request|tutorial|como fazer|como crear|"
    r"como hacer|plantilla|modelo|gerador|criador|descargar|exportar)\b",
    re.I,
)


def now_utc():
    return datetime.now(timezone.utc)


def normalize_text(s):
    return re.sub(r"\s+", " ", str(s or "").strip())


def https_get(url, timeout=9):
    """Only fixed trusted origins are supplied by our direct adapters."""
    host = urlparse(url).hostname or ""
    if host not in {"www.producthunt.com", "huggingface.co", "www.youtube.com"}:
        raise ValueError("Unsupported direct source host")
    req = Request(url, headers={"User-Agent": "NewKeywordRadar/1.0 (public feeds; contact repo owner)",
                                "Accept": "application/rss+xml,application/atom+xml,application/json,*/*"})
    with urlopen(req, timeout=timeout) as f:
        return f.read(1_500_000)


def safe_url(url, platform):
    value = str(url or "").strip()
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host:
        return ""
    allowed = HOSTS.get(platform, ())
    if platform == "producthunt":
        allowed = ("producthunt.com",)
    if platform == "huggingface":
        allowed = ("huggingface.co",)
    if platform == "youtube_channel":
        allowed = ("youtube.com",)
    if not any(host == h or host.endswith("." + h) for h in allowed):
        return ""
    # Exclude tracking parameters without rewriting any social post identity.
    clean_query = urlencode([(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                             if not k.lower().startswith("utm_")])
    return urlunparse(("https", host, parsed.path.rstrip("/") or "/", "", clean_query, ""))


def parse_date(value):
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        try:
            d = parsedate_to_datetime(raw)
        except (ValueError, TypeError, IndexError):
            return None
    return (d.replace(tzinfo=timezone.utc) if d.tzinfo is None
            else d.astimezone(timezone.utc)).isoformat()


def signal(platform, url, title, observed_at, evidence_type, published_at=None,
           description="", date_kind="original_feed_date"):
    valid_url = safe_url(url, platform)
    if not valid_url:
        return None
    title = normalize_text(title)
    if not title:
        return None
    return {
        "id": hashlib.sha256((platform + "|" + valid_url).encode("utf-8")).hexdigest()[:24],
        "platform": platform, "url": valid_url, "title": title[:280],
        "description": normalize_text(description)[:500],
        "observed_at": observed_at, "published_at": parse_date(published_at),
        "date_kind": ("search_index_date_not_post_date" if evidence_type == "search_index_pointer" and published_at else
                      (date_kind if published_at else "no_verified_publication_date")),
        "evidence_type": evidence_type,
        "intent_hint": bool(INTENT_WORDS.search(title + " " + str(description or ""))),
        "user_demand_verified": False, "payment_verified": False, "serp_verified": False,
        "source_warning": (
            "SEARCH INDEX ONLY: neither post body nor comments were verified."
            if evidence_type == "search_index_pointer"
            else "PUBLIC FEED ONLY: publication is not evidence of demand, sales or SEO traffic."
        ),
    }


def parse_feed(data, observed_at, platform, limit=12):
    """Handle RSS 2.0 and Atom (including YouTube channels)."""
    root = ET.fromstring(data)
    out = []
    entries = root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for node in entries[:limit]:
        title = (node.findtext("title") or node.findtext("{http://www.w3.org/2005/Atom}title") or "")
        url = node.findtext("link")
        if not url:
            links = node.findall("{http://www.w3.org/2005/Atom}link")
            url = next((x.attrib.get("href") for x in links if x.attrib.get("rel") in (None, "alternate")), "")
        published = (node.findtext("pubDate") or node.findtext("published") or
                     node.findtext("{http://www.w3.org/2005/Atom}published") or
                     node.findtext("{http://www.w3.org/2005/Atom}updated"))
        desc = (node.findtext("description") or node.findtext("summary") or
                node.findtext("{http://www.w3.org/2005/Atom}summary") or "")
        result = signal(platform, url, title, observed_at, "direct_public_feed",
                        published, desc)
        if result:
            out.append(result)
    return out


def source_producthunt(observed_at, limit):
    # Product Hunt's published no-auth RSS feed, not its paid/user-auth GraphQL API.
    raw = https_get("https://www.producthunt.com/feed")
    return parse_feed(raw, observed_at, "producthunt", limit)


def source_huggingface(observed_at, limit):
    # Hub documents this open, rate-limited API. Never fetch private spaces.
    url = "https://huggingface.co/api/spaces?" + urlencode(
        {"sort": "createdAt", "direction": "-1", "limit": min(limit, 15)}
    )
    rows = json.loads(https_get(url))
    if not isinstance(rows, list):
        raise ValueError("Unexpected Hugging Face response")
    out = []
    for item in rows:
        if not isinstance(item, dict) or item.get("private"):
            continue
        sid = str(item.get("id") or "").strip()
        if not re.fullmatch(r"[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+", sid):
            continue
        result = signal("huggingface", "https://huggingface.co/spaces/" + sid,
                        sid, observed_at, "direct_public_api",
                        item.get("createdAt"), "New public Hugging Face Space")
        if result:
            out.append(result)
    return out


def source_youtube_channels(observed_at, channels, limit):
    out, problems = [], []
    for channel_id in channels[:4]:
        if not re.fullmatch(r"UC[a-zA-Z0-9_-]{22}", channel_id):
            problems.append("invalid channel ID")
            continue
        url = "https://www.youtube.com/feeds/videos.xml?" + urlencode({"channel_id": channel_id})
        try:
            out.extend(parse_feed(https_get(url), observed_at, "youtube_channel", limit))
        except (OSError, HTTPError, URLError, ValueError, ET.ParseError) as exc:
            problems.append(type(exc).__name__)
    return out, problems


def source_indexed(platform, query, observed_at, limit):
    """Search engine index is ONLY a discovery pointer to social URLs."""
    def usable(items, engine):
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            row = signal(platform, item.get("url"), item.get("title"), observed_at,
                         "search_index_pointer",
                         item.get("published_at") or item.get("published"),
                         item.get("snippet", ""),
                         date_kind="search_index_date_not_post_date")
            if row:
                row["discovery_engine"] = engine
                out.append(row)
        return out

    working = 0
    errors = []
    try:
        bing = usable(bing_rss(query, limit=limit), "bing_rss")
        working += 1
    except (HTTPError, URLError, OSError, ValueError, ET.ParseError) as exc:
        errors.append("Bing: " + type(exc).__name__)
        bing = []
    if bing:
        return bing
    # Query availability is distinguished from indexed silence.
    try:
        ddg = usable(duckduckgo(query, limit=limit), "duckduckgo_html")
        working += 1
        if ddg:
            return ddg
    except (HTTPError, URLError, OSError, ValueError, ET.ParseError) as exc:
        errors.append("DDG: " + type(exc).__name__)
    if not working:
        raise RuntimeError("Both public index sources unavailable: " + ", ".join(errors))
    return []


def read_json(path, default):
    if not path.exists():
        return default
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise ValueError("Expected JSON object at " + str(path))
    return result


def write_json(path, result):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def reconcile(history, rows, observed_at, max_history=2500):
    previous = history.get("items") or {}
    if not isinstance(previous, dict):
        previous = {}
    merged = dict(previous)
    new_count = 0
    for row in rows:
        old = merged.get(row["id"])
        if old is None:
            new_count += 1
            old = {}
        stored = dict(old)
        stored.update(row)
        stored["first_seen"] = old.get("first_seen") or observed_at
        stored["last_seen"] = observed_at
        stored["observations"] = int(old.get("observations", 0)) + 1
        # Retain manually verified flags if an external reviewer adds them.
        for field in ("user_demand_verified", "payment_verified", "serp_verified"):
            stored[field] = bool(old.get(field)) or bool(row.get(field))
        merged[row["id"]] = stored
    merged = dict(sorted(merged.items(), key=lambda pair: (
        pair[1].get("last_seen", ""), pair[0]), reverse=True)[:max_history])
    return {"schema_version": 1, "updated_at": observed_at, "items": merged}, new_count


def run(root=ROOT, when=None, fetchers=None):
    when = when or now_utc()
    observed_at = when.isoformat()
    config = read_json(root / "config/social_sources.json", {})
    limit = max(1, min(int(config.get("per_source_limit", 6)), 12))
    queries = config.get("indexed_queries", {})
    channels = config.get("youtube_channel_ids") or []
    enabled = set(config.get("enabled_platforms", [
        "tiktok", "youtube_shorts", "instagram_reels", "x", "producthunt", "huggingface",
        "bluesky", "mastodon", "hackernews_ask"
    ]))
    fetchers = fetchers or {}
    all_rows, health = [], {}
    for platform in ("tiktok", "youtube_shorts", "instagram_reels", "x",
                     "producthunt", "huggingface", "bluesky", "mastodon",
                     "hackernews_ask", "youtube_channel"):
        if platform not in enabled:
            health[platform] = {"status": "disabled", "count": 0}
            continue
        try:
            warning = None
            if platform in ("tiktok", "youtube_shorts", "instagram_reels", "x"):
                opts = queries.get(platform) or []
                if not opts:
                    health[platform] = {"status": "not_configured", "count": 0}
                    continue
                chosen = opts[(when.hour // 4) % len(opts)]
                fn = fetchers.get(platform) or source_indexed
                result = fn(platform, chosen, observed_at, limit)
                warning = "Search-index-only coverage. Original post/comments unverified."
            elif platform == "producthunt":
                result = (fetchers.get(platform) or source_producthunt)(observed_at, limit)
            elif platform == "huggingface":
                result = (fetchers.get(platform) or source_huggingface)(observed_at, limit)
            elif platform == "hackernews_ask":
                try:
                    from .social_direct import hackernews_ask
                except ImportError:
                    from social_direct import hackernews_ask
                result = (fetchers.get(platform) or hackernews_ask)(observed_at, limit)
                warning = "Official Ask HN public posts; question text is not verified paid demand."
            elif platform in ("bluesky", "mastodon"):
                try:
                    from .social_direct import bluesky_posts, mastodon_hashtag
                except ImportError:
                    from social_direct import bluesky_posts, mastodon_hashtag
                candidates = config.get("bluesky_queries" if platform == "bluesky" else "mastodon_hashtags") or []
                if not candidates:
                    health[platform] = {"status": "not_configured", "count": 0}
                    continue
                term = candidates[(when.hour // 4) % len(candidates)]
                fn = fetchers.get(platform) or (
                    bluesky_posts if platform == "bluesky" else mastodon_hashtag
                )
                result = fn(term, observed_at, limit)
                warning = "Direct public post text, not verified customer payment or SEO demand."
            else:
                if not channels:
                    health[platform] = {"status": "not_configured", "count": 0}
                    continue
                result, problems = (fetchers.get(platform) or source_youtube_channels)(
                    observed_at, channels, limit)
                warning = "; ".join(problems) if problems else None
            result = [r for r in result if isinstance(r, dict) and r.get("id")]
            all_rows.extend(result)
            health[platform] = {"status": "ok" if result else "empty", "count": len(result),
                                "warning": warning}
        except Exception as exc:
            health[platform] = {"status": "unavailable", "count": 0,
                                "error": f"{type(exc).__name__}: {str(exc)[:120]}"}
    unique = {r["id"]: r for r in all_rows}
    # Persistent discovery history can be reused by 08:00 ChatGPT research.
    new_history, n_new = reconcile(read_json(root / "state/social_seen.json", {}), unique.values(), observed_at)
    day = when.strftime("%Y-%m-%d")
    stamp = when.strftime("%H%M")
    result = {"generated_at": observed_at, "schema_version": 1,
              "kind": "SOCIAL_DISCOVERY_POINTERS_NOT_VERIFIED_BUYER_DEMAND",
              "sources": health, "new_discoveries": n_new,
              "unique_in_run": len(unique), "history_total": len(new_history["items"]),
              "items": list(unique.values())[:90],
              "caveat": "Indexed X/TikTok/Shorts/Instagram links are search pointers, not original comments. HN/Mastodon/Bluesky direct public posts and Product Hunt/HF listings do not verify paid demand, SEO traffic, or feasible project opportunity. Never auto-promote into formal 90-day candidates."}
    write_json(root / "state/social_seen.json", new_history)
    write_json(root / "data/social-signals/latest.json", result)
    write_json(root / f"data/social-signals/{day}/{stamp}.json", result)
    report = ["# V4 Social signal discovery — " + observed_at, "",
              f"- Unique links this run: {len(unique)}, newly seen: {n_new}, history: {len(new_history['items'])}",
              "- IMPORTANT: Candidate links are leads only; neither user demand, SEO volume nor payment is verified.",
              "", "## Source health", ""]
    for platform, status in health.items():
        report.append(f"- {platform}: {status['status']} ({status['count']})"
                      + (f" — {status.get('warning')}" if status.get("warning") else "")
                      + (f" — {status.get('error')}" if status.get("error") else ""))
    report.extend(["", "## Links (not validated project opportunities)", ""])
    for row in list(unique.values())[:40]:
        report.append(f"- [{row['title'].replace(']', '')}]({row['url']})"
                      + f" — {row['platform']} — {row['evidence_type']}"
                      + (" — intent keyword found" if row["intent_hint"] else ""))
    report.append("")
    dest = root / "reports/social-signals/latest.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(report), encoding="utf-8")
    # Independent query linkage: never auto-promote a raw social mention to a formal candidate.
    try:
        from .social_correlation import update_correlation
    except ImportError:
        from social_correlation import update_correlation
    linkage = update_correlation(root, when, result)
    result["cross_source_exact_matches"] = linkage["cross_matches"]
    return result


if __name__ == "__main__":
    print(json.dumps({k: v for k, v in run().items() if k != "items"},
                     ensure_ascii=False, indent=2))
