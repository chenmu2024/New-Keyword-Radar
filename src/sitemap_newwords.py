"""New-name discovery, independent of software revenue research.

Observing a URL in a Sitemap is NOT a keyword's birth date. Confirm
first-party product/game launch date, then require Google Trends 90d and
five-year history to call it a verified emerging search keyword.
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo
import hashlib
import json
import re

from sitemap_triage import GAME_FEEDS
from sitemap_monitor import host, safe_fetch

ROOT = Path(__file__).resolve().parents[1]
TZ = ZoneInfo("Asia/Shanghai")
QUEUE = ROOT / "data/sitemap/queue.json"
EVIDENCE = ROOT / "data/sitemap/launch_evidence.json"
CACHE = ROOT / "data/sitemap/release_dates.json"
REPORT = ROOT / "reports/sitemap/newwords.md"
MAX_GAME_AUDITS = 4
WINDOW_DAYS = 14


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
    def handle_data(self, text):
        if not self.skip and text.strip():
            self.parts.append(text.strip())


def extract_release_date(html):
    """Read publisher's explicit release date; NEVER substitute sitemap lastmod."""
    parser = PlainText()
    parser.feed(html)
    tokens = parser.parts
    for i, value in enumerate(tokens):
        if value.strip().lower().strip(":") != "release date":
            continue
        for raw in tokens[i + 1:i + 4]:
            try:
                found = datetime.strptime(raw.strip(), "%B %d, %Y")
                return found.date().isoformat()
            except ValueError:
                continue
    return None


def combine_launch_data(manual, automatically):
    """Publisher-supported dates override unsuccessful fetches."""
    output = dict(automatically)
    output.update(manual)
    return output


def research_age(when, today):
    try:
        return (date.fromisoformat(today) - date.fromisoformat(when)).days
    except (ValueError, TypeError):
        return None


def observed_from_monitored_sitemap(row, today):
    """Only real URL deltas from the configured pilot feeds qualify."""
    config = json.loads((ROOT / "config/sitemap_sources.json").read_text(encoding="utf-8"))
    allowed = {source["id"] for source in config["sources"]}
    first = str(row.get("first_seen") or "")
    return (row.get("source_id") in allowed
            and str(row.get("url", "")).startswith("https://")
            and bool(row.get("query"))
            and config["trial_start"] <= first < config["trial_end_exclusive"]
            and first <= today)


def priority(queue, verified, today):
    """Return only launched-in-last-14-days names, not all new URLs."""
    out = []
    for entry in queue:
        if not observed_from_monitored_sitemap(entry, today):
            continue
        proof = verified.get(entry.get("url"), {})
        age = research_age(proof.get("release_date"), today)
        if age is None or not 0 <= age <= WINDOW_DAYS:
            continue
        out.append({
            "query": entry["query"], "url": entry["url"],
            "source_id": entry["source_id"], "geo": entry.get("geo", ""),
            "released": proof["release_date"], "age_days": age,
            "sitemap_first_seen": entry.get("first_seen"),
            "status": "recent_launch_not_search_verified"
        })
    out.sort(key=lambda x: (x["age_days"], x["query"]))
    return out


def audit_games(queue, known, today, fetch=safe_fetch, limit=MAX_GAME_AUDITS):
    """A strict request budget; no arbitrary URL fetches or expensive API."""
    if not 0 <= limit <= MAX_GAME_AUDITS:
        raise ValueError("game audit budget exceeded")
    need = []
    for row in queue:
        if row.get("source_id") not in GAME_FEEDS:
            continue
        url = row.get("url", "")
        if not url.startswith("https://www.gamepix.com/"):
            continue
        prior = known.get(url, {})
        if prior.get("release_date"):
            continue
        previous = prior.get("checked_date", "")
        if previous:
            try:
                if (date.fromisoformat(today) - date.fromisoformat(previous)).days < 2:
                    continue
            except ValueError:
                pass
        need.append(row)
    # Hash-based stable sampling avoids alphabetical bias and spread over pages.
    need.sort(key=lambda x: hashlib.sha256(x["url"].encode()).hexdigest())
    output = dict(known)
    for item in need[:limit]:
        url = item["url"]
        record = {"query": item["query"], "source": "GamePix publisher page",
                  "source_url": url, "checked_date": today,
                  "checked_at": datetime.now(TZ).isoformat()}
        try:
            html = fetch(url, host(url), 350_000).decode("utf-8", "replace")
            observed = extract_release_date(html)
            if observed:
                record["release_date"] = observed
                record["status"] = "publisher_date_observed"
            else:
                record["status"] = "date_not_visible"
        except (OSError, ValueError, UnicodeError) as exc:
            record["status"] = "fetch_failed"
            record["error"] = type(exc).__name__
        output[url] = record
    return output


def render(queue, age_map, sitemap_checks, today):
    # Only rows in the actual scanned Sitemap delta queue can produce output.
    observed = [row for row in queue if observed_from_monitored_sitemap(row, today)]
    fresh = priority(observed, age_map, today)
    known_urls = {r.get("url") for r in queue}
    older = []
    for row in observed:
        proof = age_map.get(row.get("url"), {})
        age = research_age(proof.get("release_date"), today)
        if age is not None and age > WINDOW_DAYS:
            older.append((row, proof))
    lines = [
        "# 新词雷达 — 仅来自同行 Sitemap 新增 URL", "",
        f"研究日期：{today}；公开发布窗口：最近 {WINDOW_DAYS} 天。", "",
        "**重要：产品或游戏刚发布，不等于该名字已有搜索量，也不等于已经通过五年历史新词核验。**",
        "硬性规则：没有被监控同行的 Sitemap 新增 URL 发现，就不得进入本报告。",
        "Sitemap URL 首次出现时间、Google Trends 相对热度与搜索月量是三种不同数据。", "",
        f"- 已核查近期发布并进入 Sitemap 队列的名称：{len(fresh)}",
        f"- 已明确排除为旧发布的 URL：{len(older)}",
        "- 仅 Sitemap 新词部分：Semrush Volume/KD/CPC = 未验证",
        "- 从未将 Apify 收费功能或 SaaS 真实收入当成新词依据", "",
        "## 近期真实上线的名称（等待搜索需求验证）", "",
    ]
    if not fresh:
        lines.append("当前无最近14天内、经发布方日期证实的 Sitemap 游戏/产品名称；不可凑数。")
    for i, x in enumerate(fresh[:20], 1):
        location_note = "（葡语目录≠巴西搜索需求）" if x["geo"] == "BR" else ""
        lines += [
            f"{i}. **[{x['query']}]({x['url']})** — 发布 {x['released']}，"
            f"距今 {x['age_days']} 天；Sitemap 首见 {x.get('sitemap_first_seen','unknown')}；来源 {x['source_id']} / {x['geo']} {location_note}。",
            "   状态：名称近期上线；Google Trends 90天+5年和 Volume/KD/CPC 尚待验证。",
        ]
    lines += ["", "## 趋势检查：只标注 Sitemap 队列中的候选", ""]
    # IMPORTANT: independent radar discoveries must never be appended here.
    # Only match existing observed Sitemap leads by exact market+query key.
    for lead in fresh[:20]:
        key = (lead.get("geo") or "WORLD") + "|" + lead["query"].casefold()
        result = sitemap_checks.get(key, {})
        status = result.get("status", "not_checked")
        history = result.get("history_5y", {}).get("historically_new", "not_checked")
        first_rise = result.get("first_rise_date") or "unknown"
        lines.append(
            f"- **[{lead['query']}]({lead['url']})** — "
            f"Sitemap来源：{lead['source_id']}；"
            f"Trends状态：{status}；首次上升：{first_rise}；"
            f"5年历史排旧：{history}。搜索量/KD/CPC：未知。"
        )
    if not fresh:
        lines.append("- 没有符合真实 Sitemap 来源 + 近期发布证据的候选，不从其他雷达补词。")
    lines += ["", "## 防止旧词混入（发布方确认的旧游戏）", ""]
    for item, proof in sorted(older, key=lambda x: x[1]["release_date"])[:12]:
        lines.append(f"- ~~{item['query']}~~ — {proof['release_date']} 上线，"
                     f"不是 {today} 的新发布。[{item['source_id']}]({item['url']})")
    lines += ["", "## 继续核验，不提前宣布搜索量", "",
              "- 对最近上线名称，检查 7天/90天热度、五年历史、发布日期和新近 Google SERP。",
              "- 用户如提供 Semrush，补充指定国家 Volume/KD/CPC 与真实落地页竞争。",
              "- 游戏 /pt/ 页面只是葡语站点栏目；巴西/西语本地实际搜索尚不确定。",
              "- 真实新词推荐最多 1–3 个；没有足够依据时报告 0，不为了20个数量凑词。",
              "- 商业收入数据不参与此雷达新词资格判定。",
              ""]
    return "\n".join(lines)


def run():
    now = datetime.now(TZ)
    today = now.date().isoformat()
    bounds = json.loads((ROOT / "config/sitemap_sources.json").read_text(encoding="utf-8"))
    if not bounds["trial_start"] <= today < bounds["trial_end_exclusive"]:
        print("Outside trial; skip launch-date audit")
        return None
    queue = json.loads(QUEUE.read_text(encoding="utf-8"))
    manual = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    saved = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    for url, proof in manual.items():
        saved.setdefault(url, proof)
    updated = audit_games(queue, saved, today)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(updated, ensure_ascii=False, indent=2)+"\n",
                     encoding="utf-8")
    checked = ROOT / "data/sitemap/validation.json"
    latest = json.loads(checked.read_text(encoding="utf-8")) if checked.exists() else {}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(render(queue, combine_launch_data(manual, updated),
                             latest, today), encoding="utf-8")
    print("New-word launch checks:", len(updated), "known publication records;",
          len(priority(queue, updated, today)), "newly launched Sitemap names")
    return updated


if __name__ == "__main__":
    run()
