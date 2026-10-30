"""Conservative, evidence-only cross-domain Sitemap co-occurrence radar.

First successful Sitemap snapshots are baselines, never launches. This report
only uses evidence retained from genuine per-source URL delta findings.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
CATEGORIES = {
    "games": "游戏：同款名称跨站新收录",
    "products": "SaaS / AI：同名产品跨目录新收录",
    "tools": "在线工具：具体功能标题跨站新收录",
}
UTILITY_TOPICS = {
    "calculators", "brazilian-online-utilities", "pdf-file-tools",
    "file-conversion-tools", "image-video-tools",
}
LOCAL_SUFFIXES = {"com.br", "net.br", "org.br", "co.uk", "com.au", "com.mx", "co.jp"}


def normalize(query):
    """Normalize punctuation and case without erasing versions or keywords."""
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", str(query).casefold())).strip()


def domain(value):
    """Distinct registered domain approximation for monitored public sites."""
    raw = str(value or "")
    host = urlsplit(raw).hostname if "://" in raw else raw
    host = (host or "").lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in LOCAL_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def topic_group(src):
    topic = src.get("topic", "")
    if topic == "games":
        return "games"
    if topic in UTILITY_TOPICS or "online-utilit" in topic:
        return "tools"
    return "products"


def summarize(queue, config, today):
    """Use only authentic source_id + URL + first_seen evidence from the queue."""
    if isinstance(today, str):
        today = date.fromisoformat(today)
    cutoff = today - timedelta(days=6)
    sources = {row["id"]: row for row in config.get("sources", [])}
    buckets = defaultdict(dict)
    ignored = 0
    for row in queue:
        name = str(row.get("query", "")).strip()
        keyname = normalize(name)
        if not keyname or len(keyname) < 4:
            continue
        records = row.get("source_records")
        if not isinstance(records, list):
            records = [{"source_id": row.get("source_id"),
                        "url": row.get("url"), "first_seen": row.get("first_seen")}]
        for rec in records:
            if not isinstance(rec, dict):
                ignored += 1
                continue
            source_id, url, stamp = rec.get("source_id"), rec.get("url"), rec.get("first_seen")
            if not all((source_id, url, stamp)) or source_id not in sources:
                ignored += 1
                continue
            try:
                first = date.fromisoformat(str(stamp)[:10])
            except ValueError:
                ignored += 1
                continue
            if not (cutoff <= first <= today):
                continue
            src = sources[source_id]
            # Prefer the actual observed page host, not a CDN hosting Sitemap XML.
            site = domain(url)
            if not site:
                ignored += 1
                continue
            group = topic_group(src)
            bucket = buckets[(group, keyname)]
            ev = {"source_id": source_id, "website": site,
                  "url": str(url), "first_seen": first.isoformat()}
            prior = bucket.get(site)
            if prior is None or ev["first_seen"] < prior["first_seen"]:
                bucket[site] = ev
    groups = {kind: [] for kind in CATEGORIES}
    for (group, query), sites in buckets.items():
        if len(sites) < 2:
            continue
        evidence = sorted(sites.values(), key=lambda x: (x["first_seen"], x["website"]))
        first = date.fromisoformat(evidence[0]["first_seen"])
        last = date.fromisoformat(evidence[-1]["first_seen"])
        span = (last - first).days
        n = len(evidence)
        if span <= 2 and n >= 3:
            priority = "high"
        elif span <= 2 or (span <= 6 and n >= 3):
            priority = "medium"
        else:
            priority = "watch"
        groups[group].append({"query": query, "independent_websites": n,
                              "date_span_days": span, "priority": priority,
                              "match_basis": "normalized_exact_title_only",
                              "evidence": evidence})
    priority_score = {"high": 0, "medium": 1, "watch": 2}
    for rows in groups.values():
        rows.sort(key=lambda x: (priority_score[x["priority"]],
                                 -x["independent_websites"],
                                 x["date_span_days"], x["query"]))
    return {"date": today.isoformat(), "window_start": cutoff.isoformat(),
            "source_count": len(sources), "queue_count": len(queue),
            "ignored_unverifiable_proofs": ignored,
            "groups": groups,
            "group_counts": {k: len(v) for k, v in groups.items()}}


def render(payload, latest):
    lines = [
        "# 跨独立网站 Sitemap 同步上新观察",
        "",
        "观察截止：" + payload["date"] + "（北京时间日期）；滚动窗口：" +
        payload["window_start"] + "—" + payload["date"] + "（7个日历日）。",
        "",
        "**注意：Sitemap 首见不是产品首发或真实搜索量；标题相同不是同功能、同开发者或搜索需求的证明。**",
        "只计具有源ID、明确URL及 first_seen 的真实 delta 记录；初次建基线、旧URL复现和语言镜像不计跨站新增。",
        "不同URL语言路径按网站注册根域合并；不同域名是否由同一家运营公司控制，需要额外核实。",
        "first_seen 只有日期精度，因此不宣称精确24小时同步上线。",
        "",
        "本次数据：配置来源 " + str(payload["source_count"]) +
        "；最新扫描成功来源 " + str(latest.get("success_count", "未知")) +
        "/" + str(latest.get("source_count", "未知")) +
        "；最新数据时间 " + str(latest.get("generated_at", "未知")) +
        "；当前队列 " + str(payload["queue_count"]) + "。",
        "",
    ]
    for name, heading in CATEGORIES.items():
        lines.extend(["## " + heading, ""])
        candidates = payload["groups"].get(name, [])[:10]
        if not candidates:
            lines.extend(["**0：目前没有足够的两站以上独立 Sitemap 新增证据。**", ""])
            continue
        for row in candidates:
            lines.append(
                "- **" + row["query"] + "**：" + str(row["independent_websites"]) +
                "家独立域名，相隔" + str(row["date_span_days"]) +
                "个日历日；优先级 " + row["priority"] +
                "；仅精确标题匹配，尚未确认同款或同功能。"
            )
            for proof in row["evidence"][:12]:
                lines.append("  - " + proof["website"] + " · " + proof["source_id"] +
                             " · " + proof["first_seen"] + " · " + proof["url"])
        lines.append("")
    lines.extend([
        "## 解释及排除",
        "",
        "结果不含 Trends / Volume / KD / CPC 验证，也不推断收入或排名。",
        "同名跨站只是优先研究的供给/分发信号；需审阅页面确认是否相同游戏、相同产品或具体功能。",
        "单站新增和无法核实真实 first_seen/source_id 的页面不进入跨站榜。",
        "新增来源首次建立基线不计新 URL，原定14天试运行结束后不自行续期。",
        "",
    ])
    return "\n".join(lines)


def run(root=ROOT):
    config = json.loads((root / "config/sitemap_sources.json").read_text(encoding="utf-8"))
    queue = json.loads((root / "data/sitemap/queue.json").read_text(encoding="utf-8"))
    latest = json.loads((root / "data/sitemap/latest.json").read_text(encoding="utf-8"))
    stamp = latest.get("generated_at")
    today = datetime.fromisoformat(stamp).date() if stamp else datetime.now(LOCAL_TZ).date()
    result = summarize(queue, config, today)
    result["generated_at"] = stamp or datetime.now(LOCAL_TZ).isoformat()
    out = root / "data/sitemap/cross_signals.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = root / "reports/sitemap/cross_signals.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(render(result, latest), encoding="utf-8")
    return result


if __name__ == "__main__":
    result = run()
    print(json.dumps({"generated_at": result["generated_at"],
                      "group_counts": result["group_counts"],
                      "queue_count": result["queue_count"]}, ensure_ascii=False))
