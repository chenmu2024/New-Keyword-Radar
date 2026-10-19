"""Bounded, read-only competitor Sitemap delta monitor.

New URLs are *leads*, NOT verified new words, search demand or revenue evidence.
The first successful scan of each source only establishes a baseline.
"""
from __future__ import annotations

import argparse
from datetime import datetime
from hashlib import sha256
from html.parser import HTMLParser
import gzip
import io
import json
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
CONFIG = ROOT / "config/sitemap_sources.json"
STATE = ROOT / "state/sitemap/snapshots.json"
QUEUE = ROOT / "data/sitemap/queue.json"
LATEST = ROOT / "data/sitemap/latest.json"
REPORT = ROOT / "reports/sitemap/latest.md"
MAX_BYTES = 7_000_000
MAX_QUEUE = 2000  # Research leads, not the hashed Sitemap baseline. Bounded Git footprint.
USER_AGENT = "NewKeywordRadar-SitemapResearch/1.0 (+public-sitemaps; polite daily checks)"
SKIP = re.compile(
    r"(^|/)(tag|tags|category|categories|author|authors|login|signup|"
    r"search|feed|page|privacy|terms|contact|about|account|cdn-cgi)(/|$)", re.I
)
SKIP_SLUG = {"home", "index", "games", "game", "tools", "blog", "en", "pt",
             "es", "fr", "new", "popular", "all", "sitemap", "products"}
CUE = re.compile(r"\b(calculator|calculadora|calculador|generator|generador|gerador|"
                 r"converter|conversor|convertidor|checker|verificador|tracker|"
                 r"simulator|simulador|codes|codigos|códigos|values|valores|"
                 r"builder|editor|planner|plantilla|template|download|descargar|"
                 r"baixar|compress|compressor|optimizer|optimizador)\b", re.I)


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def host(url):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port:
        raise ValueError("Only plain HTTPS URLs are permitted")
    return p.hostname.lower()


def safe_fetch(url, allowed_host, max_bytes=MAX_BYTES):
    if host(url) != allowed_host:
        raise ValueError("Cross-host sitemap/page request blocked")
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/xml,text/xml,text/html,*/*"})
    with urlopen(req, timeout=15) as response:
        if host(response.geturl()) != allowed_host:
            raise ValueError("Cross-host redirect blocked")
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Response exceeds size limit")
        # Decompress *boundedly*, including Product Hunt's public .xml.gz archive.
        # An untrusted gzip bomb must never be expanded unbounded in memory.
        if data.startswith(b"\x1f\x8b"):
            with gzip.GzipFile(fileobj=io.BytesIO(data)) as packed:
                data = packed.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError("Decompressed response exceeds size limit")
        return data


def xml_items(raw):
    # ElementTree does not fetch external XML entities; cap bytes before parse.
    root = ET.fromstring(raw)
    tag = root.tag.rsplit("}", 1)[-1].lower()
    if tag not in {"sitemapindex", "urlset"}:
        raise ValueError("Not an XML sitemap index/urlset")
    out = []
    child_name = "sitemap" if tag == "sitemapindex" else "url"
    for entry in root:
        if entry.tag.rsplit("}", 1)[-1].lower() != child_name:
            continue
        loc = next((el.text.strip() for el in entry
                    if el.tag.rsplit("}", 1)[-1].lower() == "loc" and el.text), "")
        if loc:
            out.append(loc)
    return tag, out


def collect_sitemap(root_url, fetch=safe_fetch, max_sitemaps=18, max_urls=50000, max_bytes=MAX_BYTES,
                    include_prefixes=None, page_hosts=None, page_path_regex=None,
                    exclude_prefixes=None):
    """Reject incomplete scans: an incomplete set must never replace baseline."""
    allowed = host(root_url)
    # XML may live on a CDN, while its <loc> URLs point to the official product site.
    # This *explicit* allowlist does not authorize arbitrary cross-site requests.
    trusted_pages = set(page_hosts or [allowed])
    for item in trusted_pages:
        if host("https://" + item + "/") != item:
            raise ValueError("Invalid explicit page host")
    path_pattern = re.compile(page_path_regex) if page_path_regex else None
    blocked_prefixes = exclude_prefixes or []
    todo = [(root_url, 0)]
    fetched, pages, seen = 0, set(), set()
    while todo:
        url, depth = todo.pop(0)
        if url in seen:
            continue
        if depth > 3 or fetched >= max_sitemaps:
            raise ValueError("Sitemap index exceeds configured traversal limit")
        seen.add(url)
        tag, links = xml_items(fetch(url, allowed, max_bytes))
        fetched += 1
        if tag == "sitemapindex":
            if depth >= 3:
                raise ValueError("Nested sitemap index too deep")
            for link in links:
                if host(link) != allowed:
                    continue
                # Deliberately avoid image/video/news feeds, keep content sitemaps.
                if re.search(r"image|video|news|author|tag-sitemap", urlsplit(link).path, re.I):
                    continue
                todo.append((link, depth + 1))
            if fetched + len(todo) > max_sitemaps:
                raise ValueError("More sitemap files than safety cap; increase deliberately")
        else:
            for link in links:
                if host(link) in trusted_pages and not SKIP.search(urlsplit(link).path):
                    path = urlsplit(link).path
                    if (include_prefixes and not any(path.startswith(p) for p in include_prefixes)):
                        continue
                    if any(path.startswith(p) for p in blocked_prefixes):
                        continue
                    if path_pattern and not path_pattern.fullmatch(path):
                        continue
                    pages.add(link.split("#", 1)[0])
                if len(pages) > max_urls:
                    raise ValueError("Page count exceeds safety cap")
    return sorted(pages), fetched


def digest(url):
    return sha256(url.encode("utf-8")).hexdigest()[:24]


def select_novel_leads(novel, limit):
    """Evaluate all novel URLs before capping, with deterministic non-alphabetical sampling.

    Previously, only the first 80 lexicographically sorted URLs were inspected,
    systematically ignoring later URLs including meaningful tools.
    """
    eligible = [(link, candidate(link)) for link in novel]
    eligible = [(link, q) for link, q in eligible if q]
    eligible.sort(key=lambda pair: (-int(bool(CUE.search(pair[1]))), digest(pair[0])))
    cap = max(0, int(limit))
    return eligible[:cap], len(eligible)


def candidate(url):
    p = urlsplit(url)
    path = unquote(p.path).strip("/")
    if SKIP.search("/" + path + "/") or not path:
        return ""
    slug = path.split("/")[-1]
    slug = re.sub(r"\.(html?|php|aspx?)$", "", slug, flags=re.I)
    slug = re.sub(r"[_\-.]+", " ", slug)
    slug = re.sub(r"\s+", " ", slug).strip().lower()
    # n8n workflow slugs begin with a numeric catalog ID, not part of the query.
    if re.match(r"^\d+\s+", slug):
        slug = re.sub(r"^\d+\s+", "", slug)
    if (slug in SKIP_SLUG or len(slug) < 5 or len(slug) > 90 or
            len(slug.split()) > 10 or slug.isnumeric() or
            re.search(r"^(20\d{2}|page \d+)$", slug)):
        return ""
    return slug


class HeadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tag = ""
        self.title = ""
        self.h1 = ""
    def handle_starttag(self, tag, attrs):
        if tag in ("title", "h1") and not getattr(self, tag):
            self.tag = tag
    def handle_endtag(self, tag):
        if self.tag == tag:
            self.tag = ""
    def handle_data(self, data):
        if self.tag in ("title", "h1"):
            old = getattr(self, self.tag)
            setattr(self, self.tag, (old + " " + data).strip()[:240])


def page_meta(url, fetch=safe_fetch):
    try:
        parser = HeadParser()
        parser.feed(fetch(url, host(url), 350_000).decode("utf-8", "replace"))
        return {"title": parser.title[:180], "h1": parser.h1[:180]}
    except (OSError, ValueError, ET.ParseError, UnicodeError) as exc:
        return {"title": "", "h1": "", "page_error": type(exc).__name__}


def scan(config, previous, fetch=safe_fetch, enrich=False, today=None):
    today = today or datetime.now(TZ).date().isoformat()
    states = dict(previous)
    findings, status = [], []
    max_pages = int(config.get("max_urls_per_source", 50000))
    max_files = int(config.get("max_sitemaps_per_source", 18))
    enrich_budget = int(config.get("max_page_enrich_per_run", 8)) if enrich else 0
    for source in config["sources"]:
        name, url = source["id"], source["sitemap"]
        previous_site = states.get(name)
        try:
            urls, nfiles = collect_sitemap(
                url, fetch, max_files, int(source.get("max_urls", max_pages)),
                int(source.get("max_bytes", MAX_BYTES)),
                source.get("include_path_prefixes"), source.get("page_hosts"),
                source.get("include_page_path_regex"), source.get("exclude_path_prefixes"))
            hashes = {digest(link) for link in urls}
            old = set(previous_site["hashes"]) if previous_site and "hashes" in previous_site else None
            novel = [] if old is None else [link for link in urls if digest(link) not in old]
            removed_count = len(old - hashes) if old is not None else 0
            stage = "baseline" if old is None else "delta"
            chosen, eligible_count = select_novel_leads(
                novel, int(config.get("max_new_urls_per_source", 80)))
            for link, query in chosen:
                meta = page_meta(link, fetch) if enrich_budget and source.get("enrich_pages", True) else {"title": "", "h1": ""}
                if enrich_budget and source.get("enrich_pages", True):
                    enrich_budget -= 1
                findings.append({"query": query, "url": link, "source_id": name,
                                 "geo": source.get("geo", ""), "topic": source.get("topic", ""),
                                 "first_seen": today, "tool_intent_hint": bool(CUE.search(query)),
                                 **meta})
            states[name] = {"hashes": sorted(hashes), "checked_at": today,
                            "count": len(urls), "files": nfiles}
            status.append({"source_id": name, "status": stage, "page_count": len(urls),
                           "new_url_count": len(novel), "removed_url_count": removed_count,
                           "eligible_candidate_count": eligible_count,
                           "candidate_count": len(chosen),
                           "candidates_over_scan_cap": max(0, eligible_count - len(chosen)),
                           "sitemap_files": nfiles})
        except (OSError, ValueError, ET.ParseError, HTTPError, URLError) as exc:
            # Fail closed: do NOT replace the previous snapshot or fabricate deltas.
            status.append({"source_id": name, "status": "error",
                           "error": type(exc).__name__ + ": " + str(exc)[:150]})
    return states, findings, status


def merge_queue(old, findings, limit=MAX_QUEUE):
    """Keep market-distinct leads with source-balanced retention.

    Snapshots store all checked URL hashes; this bounded queue is only
    research metadata. It must not silently collapse US/BR/ES queries.
    """
    merged = {}
    for row in old:
        q = str(row.get("query", "")).strip().casefold()
        if q:
            key = (q, str(row.get("geo", "")).upper())
            merged[key] = {**row, "additional_urls": list(row.get("additional_urls", []))}
    for finding in findings:
        q = str(finding.get("query", "")).strip().casefold()
        if not q:
            continue
        key = (q, str(finding.get("geo", "")).upper())
        existing = merged.get(key)
        if existing is None:
            merged[key] = dict(finding)
        else:
            existing["last_seen"] = finding.get("first_seen", "")
            links = existing.setdefault("additional_urls", [])
            url = finding.get("url", "")
            if url and url != existing.get("url") and url not in links:
                links.append(url)

    groups = {}
    for row in merged.values():
        groups.setdefault(row.get("source_id", "unknown"), []).append(row)
    for entries in groups.values():
        entries.sort(key=lambda x: (x.get("first_seen", ""), bool(x.get("tool_intent_hint")),
                                     x.get("query", "")), reverse=True)
    keys = sorted(groups)
    output = []
    # Round-robin retention stops one bulk index such as Apify from crowding
    # out every other source when the research-queue safety limit is reached.
    while keys and len(output) < max(0, int(limit)):
        remaining = []
        for source in keys:
            group = groups[source]
            if group and len(output) < limit:
                output.append(group.pop(0))
            if group:
                remaining.append(source)
        keys = remaining
    return output


def run(root=ROOT, enrich=True):
    cfg = load_json(root / "config/sitemap_sources.json", {})
    now = datetime.now(TZ)
    day = now.date().isoformat()
    if not cfg.get("sources"):
        raise ValueError("No Sitemap sources configured")
    if not (cfg["trial_start"] <= day < cfg["trial_end_exclusive"]):
        print("Outside 14-day research pilot; no collection and no writes.")
        return {"status": "outside_trial", "date": day}
    state_path = root / "state/sitemap/snapshots.json"
    queue_path = root / "data/sitemap/queue.json"
    previous = load_json(state_path, {})
    updated, findings, status = scan(cfg, previous, enrich=enrich, today=day)
    previous_queue = load_json(queue_path, [])
    queue = merge_queue(previous_queue, findings)
    success = sum(x["status"] != "error" for x in status)
    payload = {"generated_at": now.isoformat(), "date": day, "trial_start": cfg["trial_start"],
               "trial_end_exclusive": cfg["trial_end_exclusive"], "source_count": len(status),
               "success_count": success, "new_url_count": sum(
                   x.get("new_url_count", 0) for x in status),
               "new_candidate_count": len(findings), "queue_size": len(queue),
               "queue_limit": MAX_QUEUE,
               "keyword_metrics_verified": False, "newness_verified": False,
               "sources": status, "candidates": findings[:100]}
    # Retain successful partial progress when other sources fail. Zero-success runs
    # are errors, not empty snapshots or a misleading completed scan.
    if success == 0:
        raise RuntimeError("All Sitemap sources failed; state not overwritten")
    save_json(state_path, updated)
    save_json(queue_path, queue)
    save_json(root / "data/sitemap/latest.json", payload)
    save_json(root / ("data/sitemap/" + day + ".json"), payload)
    lines = ["# Sitemap delta research — " + day, "",
             "Unverified leads only. Baseline URL snapshots are NOT discoveries.",
             f"Sources succeeded: {success}/{len(status)}; new URLs: {payload['new_url_count']}; "
             f"candidate leads: {len(findings)}; retained queue: {len(queue)}.", "",
             "## Sources", ""]
    for row in status:
        lines.append("- " + row["source_id"] + ": " + row["status"] + "; "
                     + str(row.get("new_url_count", 0)) + " new URLs; "
                     + str(row.get("page_count", "?")) + " pages"
                     + "; removed " + str(row.get("removed_url_count", "?"))
                     + "; candidate scan cap skipped " + str(row.get("candidates_over_scan_cap", "?"))
                     + ("; " + row["error"] if row.get("error") else ""))
    lines.extend(["", "## New URL leads (not proven new keywords)", ""])
    for finding in findings[:60]:
        lines.append("- [" + finding["query"].replace("]", "") + "](" + finding["url"] +
                     ") — " + finding["source_id"] + " / " + finding["geo"])
    if not findings:
        lines.append("None. First successful scans create baselines without alerts.")
    lines.extend(["", "Next: verify original keyword age, country search demand, "
                  "SERP and monetization independently."])
    path = root / "reports/sitemap/latest.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return payload


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-enrich", action="store_true", help="Only read sitemaps, no detail pages")
    args = p.parse_args()
    result = run(enrich=not args.no_enrich)
    print(json.dumps({k: v for k, v in result.items() if k not in ("sources", "candidates")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
