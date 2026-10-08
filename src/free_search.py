"""Free, read-only search adapters for opportunity discovery.

Independent implementation using only the Python standard library. It does not
scrape authenticated content, solve CAPTCHAs, or produce Volume/KD/CPC estimates.
"""
from __future__ import annotations

import argparse
import hashlib
import html
from html.parser import HTMLParser
import ipaddress
import json
import os
from pathlib import Path
import re
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlencode, urljoin, urlparse, urlunparse, unquote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "free-search-cache"
UA = "NewKeywordRadar/1.0 (+https://github.com/chenmu2024/New-Keyword-Radar)"
DEFAULT_TIMEOUT = 12
MAX_BYTES = 1_500_000
TRACKERS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def clean_text(value):
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def canonical_url(url):
    url = str(url or "").strip()
    if not url:
        return ""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc:
        return ""
    host = (p.hostname or "").lower()
    path = re.sub(r"/+$", "", p.path) or "/"
    parts = []
    for pair in p.query.split("&"):
        key = pair.split("=", 1)[0].lower()
        if pair and not key.startswith("utm_") and key not in TRACKERS:
            parts.append(pair)
    return urlunparse((p.scheme.lower(), host + ((":" + str(p.port)) if p.port else ""), path, "", "&".join(parts), ""))


def request(url, *, headers=None, timeout=DEFAULT_TIMEOUT):
    p = urlparse(url)
    if p.scheme != "https" or not p.hostname:
        raise ValueError("Only HTTPS sources are allowed")
    if p.hostname in ("localhost",) or p.hostname.endswith(".local"):
        raise ValueError("Local URLs are not allowed")
    try:
        ip = ipaddress.ip_address(p.hostname)
        if not ip.is_global:
            raise ValueError("Non-public IP URLs are not allowed")
    except ValueError as exc:
        if "Non-public" in str(exc):
            raise
    head = {"User-Agent": UA, "Accept": "application/json,application/xml,text/html;q=0.9,*/*;q=0.8"}
    head.update(headers or {})
    req = Request(url, headers=head)
    with urlopen(req, timeout=timeout) as response:
        if int(response.status) != 200:
            raise ValueError("Unexpected HTTP status: " + str(response.status))
        content = response.read(MAX_BYTES + 1)
        if len(content) > MAX_BYTES:
            raise ValueError("Response exceeds size limit")
        return content.decode(response.headers.get_content_charset() or "utf-8", errors="replace")


def cached_request(url, ttl=3600, headers=None):
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()
    path = CACHE / (key + ".json")
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if time.time() - float(payload["at"]) < ttl:
                return payload["body"], True
        except (ValueError, KeyError, OSError, TypeError):
            pass
    body = request(url, headers=headers)
    CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"at": time.time(), "body": body}, ensure_ascii=False), encoding="utf-8")
    return body, False


def row(platform, title, url, snippet="", published="", metrics=None, extra=None):
    normalized = canonical_url(url)
    if not normalized or not clean_text(title):
        return None
    return {"platform": platform, "title": clean_text(title)[:240],
            "url": normalized, "snippet": clean_text(snippet)[:700],
            "published_at": str(published or ""), "engagement": metrics or {},
            "metadata": extra or {}, "discovered_at": utc_now(),
            "volume": None, "kd": None, "cpc": None}


def dedupe(items):
    output, seen = [], set()
    for item in items:
        url = canonical_url(item.get("url"))
        if not url or url in seen:
            continue
        seen.add(url)
        output.append(item)
    return output


def github(query, kind="repositories", limit=8):
    if kind not in ("repositories", "issues"):
        raise ValueError("Invalid GitHub search type")
    url = "https://api.github.com/search/" + kind + "?" + urlencode({"q": query, "per_page": min(limit * 3 if kind == "issues" else limit, 30), "sort": "updated"})
    headers = {"Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    data = json.loads(cached_request(url, ttl=1800, headers=headers)[0])
    out = []
    for obj in data.get("items", [])[:limit]:
        if kind == "issues" and "pull_request" in obj:
            continue
        title = obj.get("full_name") if kind == "repositories" else obj.get("title")
        snippet = obj.get("description") if kind == "repositories" else obj.get("body")
        metrics = {"stars": obj.get("stargazers_count")} if kind == "repositories" else {"comments": obj.get("comments")}
        candidate = row("github_" + kind, title, obj.get("html_url"), snippet, obj.get("created_at"),
                        metrics, {"updated_at": obj.get("updated_at"), "state": obj.get("state")})
        if candidate:
            out.append(candidate)
    return out


def rss_items(url, limit=8, platform="rss"):
    raw, _ = cached_request(url, ttl=1800)
    root = ET.fromstring(raw)
    out = []
    # RSS and Atom, including Google News RSS and Reddit RSS
    entries = root.findall(".//item") + root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for item in entries[:limit * 2]:
        def field(*names):
            for name in names:
                x = item.find(name)
                if x is not None:
                    if name.endswith("link") and x.get("href"):
                        return x.get("href")
                    if x.text:
                        return x.text
            return ""
        title = field("title", "{http://www.w3.org/2005/Atom}title")
        link = field("link", "{http://www.w3.org/2005/Atom}link")
        desc = field("description", "{http://www.w3.org/2005/Atom}summary")
        published = field("pubDate", "{http://www.w3.org/2005/Atom}updated")
        candidate = row(platform, title, link, re.sub(r"<[^>]+>", " ", desc), published)
        if candidate:
            out.append(candidate)
    return out[:limit]


def google_news(query, limit=8, lang="en"):
    url = "https://news.google.com/rss/search?" + urlencode({
        "q": query, "hl": lang, "gl": "US", "ceid": "US:en"})
    return rss_items(url, limit, platform="google_news_rss")


class DDGParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []
        self.active = None

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        a = dict(attrs)
        classes = a.get("class", "").split()
        if "result__a" not in classes:
            return
        href = html.unescape(a.get("href", ""))
        p = urlparse(urljoin("https://html.duckduckgo.com", href))
        if "duckduckgo.com" in (p.hostname or ""):
            href = unquote(parse_qs(p.query).get("uddg", [""])[0])
        self.active = {"title": [], "url": href}

    def handle_data(self, data):
        if self.active is not None:
            self.active["title"].append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self.active is not None:
            candidate = row("duckduckgo", "".join(self.active["title"]), self.active["url"])
            if candidate:
                self.items.append(candidate)
            self.active = None


def duckduckgo(query, limit=8):
    url = "https://html.duckduckgo.com/html/?" + urlencode({"q": query})
    parser = DDGParser()
    parser.feed(cached_request(url, ttl=1800)[0])
    return dedupe(parser.items)[:limit]


def bing_rss(query, limit=8):
    # Public Bing search RSS, not the paid Bing Search API.
    url = "https://www.bing.com/search?" + urlencode({"q": query, "format": "rss"})
    return rss_items(url, limit, platform="bing_rss")


def reddit(query, limit=8):
    # Public RSS may return 403; report failure and provide an indexed discovery
    # fallback, clearly labeled rather than misrepresenting it as Reddit API.
    rss_url = "https://www.reddit.com/search.rss?" + urlencode({"q": query, "sort": "new", "limit": limit})
    try:
        result = rss_items(rss_url, limit, platform="reddit_rss")
        if result:
            return result, None
        failure = "Reddit public RSS returned no items"
    except Exception as exc:
        failure = type(exc).__name__ + ": " + str(exc)[:180]
    try:
        indexed = duckduckgo("site:reddit.com " + query, limit)
    except (OSError, ValueError):
        indexed = bing_rss("site:reddit.com " + query, limit)
    result = [item for item in indexed if (urlparse(item.get("url", "")).hostname or "").endswith("reddit.com")]
    for item in result:
        item["platform"] = "reddit_index_fallback"
        item["metadata"]["fallback_reason"] = failure
    return result, failure


def image_candidates(query, limit=8):
    # Wikimedia Commons file metadata includes machine-readable license URLs.
    params = {"action": "query", "generator": "search", "gsrsearch": "filetype:bitmap " + query,
              "gsrnamespace": 6, "gsrlimit": min(limit * 2, 30), "prop": "imageinfo",
              "iiprop": "url|extmetadata", "iiurlwidth": 900, "format": "json"}
    url = "https://commons.wikimedia.org/w/api.php?" + urlencode(params)
    payload = json.loads(cached_request(url, ttl=3600)[0])
    items = []
    for obj in payload.get("query", {}).get("pages", {}).values():
        info = (obj.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        license_url = meta.get("LicenseUrl", {}).get("value", "")
        credit = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", ""))
        page = info.get("descriptionurl") or info.get("url")
        x = row("wikimedia_commons", obj.get("title"), page, extra={
            "image_url": info.get("thumburl") or info.get("url"), "license_url": license_url,
            "credit": clean_text(credit), "requires_license_check": True})
        if x:
            items.append(x)
    return dedupe(items)[:limit]


class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.hidden = 0
        self.parts = []
        self.title = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "nav", "footer", "header"):
            self.hidden += 1
        if tag == "title":
            self.in_title = True
        if tag in ("p", "h1", "h2", "h3", "li", "article") and not self.hidden:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "footer", "header") and self.hidden:
            self.hidden -= 1
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if not self.hidden and not self.in_title:
            self.parts.append(data)


def page_to_markdown(url):
    raw = request(url)
    parser = TextParser()
    parser.feed(raw)
    title = clean_text(" ".join(parser.title))
    lines = [clean_text(x) for x in "".join(parser.parts).split("\n")]
    content = "\n\n".join(x for x in lines if x)
    return {"url": canonical_url(url), "title": title, "markdown": ("# " + title + "\n\n" if title else "") + content[:60000],
            "extraction_method": "local_html", "note": "Static HTML only; not a headless browser."}


def collect(query, platforms, limit=8, source_queries=None):
    source_queries = source_queries or {}
    def q(source):
        return source_queries.get(source) or query
    handlers = {
        "github_repos": lambda: github(q("github_repos"), "repositories", limit),
        "github_issues": lambda: github(q("github_issues"), "issues", limit),
        "google_news_rss": lambda: google_news(q("google_news_rss"), limit),
        "duckduckgo": lambda: duckduckgo(q("duckduckgo"), limit),
        "bing_rss": lambda: bing_rss(q("bing_rss"), limit),
        "reddit": lambda: reddit(q("reddit"), limit),
        "images": lambda: image_candidates(q("images"), limit),
    }
    if not query.strip() or limit < 1 or limit > 30:
        raise ValueError("Nonempty query and 1 <= limit <= 30 required")
    result = {"query": query, "captured_at": utc_now(), "sources": {}, "items": [],
              "cost_model": "no paid API", "source_queries": {name: q(name) for name in platforms},
              "keyword_metrics": {"volume": None, "kd": None, "cpc": None}}
    for source in platforms:
        if source not in handlers:
            result["sources"][source] = {"status": "unsupported"}
            continue
        try:
            got = handlers[source]()
            items, warning = got if isinstance(got, tuple) else (got, None)
            result["sources"][source] = {"status": "degraded" if warning else ("ok" if items else "empty"),
                                         "count": len(items), "warning": warning}
            result["items"].extend(items)
        except (HTTPError, URLError, OSError, ValueError, ET.ParseError, KeyError) as exc:
            reason = type(exc).__name__ + ": " + str(exc)[:200]
            if source == "duckduckgo":
                # Hosted runners can receive HTTP 202; no evasion or proxy usage.
                try:
                    fallback = bing_rss(query, limit)
                    for entry in fallback:
                        entry["metadata"]["fallback_for"] = "duckduckgo"
                    result["items"].extend(fallback)
                    result["sources"][source] = {"status": "degraded", "count": len(fallback),
                                                  "warning": reason, "fallback": "bing_rss"}
                    continue
                except (HTTPError, URLError, OSError, ValueError, ET.ParseError) as alt:
                    reason += "; bing_rss: " + str(alt)[:150]
            result["sources"][source] = {"status": "error", "count": 0, "error": reason}
    result["items"] = dedupe(result["items"])
    result["total"] = len(result["items"])
    return result


def main():
    p = argparse.ArgumentParser(description="Free search discovery; never outputs estimated KD/Volume/CPC.")
    p.add_argument("query", nargs="?")
    p.add_argument("--platforms", nargs="+", default=["github_repos", "github_issues", "google_news_rss", "duckduckgo", "reddit"])
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--url-to-markdown")
    p.add_argument("--rss-url")
    p.add_argument("--output")
    args = p.parse_args()
    if args.url_to_markdown:
        result = page_to_markdown(args.url_to_markdown)
    elif args.rss_url:
        result = {"items": rss_items(args.rss_url, args.limit), "captured_at": utc_now()}
    else:
        result = collect(args.query or "", args.platforms, args.limit)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
