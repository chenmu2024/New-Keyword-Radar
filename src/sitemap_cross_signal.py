"""Evidence-only Sitemap cross-domain co-occurrence radar.

New sources first establish baselines. A matching title/format is a lead, not
proof of a genuine launch, shared ownership, search volume or revenue.
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
    "functions": "跨类型：明确输入输出的同功能工具候选",
}
UTILITY_TOPICS = {
    "calculators", "brazilian-online-utilities", "pdf-file-tools",
    "file-conversion-tools", "image-video-tools",
}
LOCAL_SUFFIXES = {"com.br", "net.br", "org.br", "co.uk", "com.au", "com.mx", "co.jp"}
FORMATS = {
    "xlsx": "excel", "xls": "excel", "excel": "excel",
    "doc": "word", "docx": "word", "word": "word",
    "jpeg": "jpg", "jpg": "jpg",
    "ppt": "powerpoint", "pptx": "powerpoint", "powerpoint": "powerpoint",
    "heif": "heic", "heic": "heic",
    "pdf": "pdf", "csv": "csv", "json": "json",
    "png": "png", "webp": "webp", "svg": "svg",
    "xml": "xml", "yaml": "yaml", "yml": "yaml",
    "gif": "gif", "mp4": "mp4", "mp3": "mp3",
    "wav": "wav", "zip": "zip", "epub": "epub",
}
CONVERSION_CUES = {
    "convert", "converter", "conversion", "conversor", "from",
    "file", "files", "online", "tool", "tools", "free", "batch",
}


def normalize(query):
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", str(query).casefold())).strip()


def domain(value):
    raw = str(value or "")
    h = urlsplit(raw).hostname if "://" in raw else raw
    h = (h or "").lower().removeprefix("www.")
    parts = h.split(".")
    if len(parts) >= 3 and ".".join(parts[-2:]) in LOCAL_SUFFIXES:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else h


def topic_group(src):
    topic = src.get("topic", "")
    if topic == "games":
        return "games"
    if topic in UTILITY_TOPICS or "online-utilit" in topic:
        return "tools"
    return "products"


def game_name(query, source_id):
    cleaned = normalize(query)
    if source_id == "gamepost-games":
        # GamePost places a large numeric database ID after the game title.
        # Retain small digits (version numbers, game sequels, etc.).
        return re.sub(r"\s+\d{5,}$", "", cleaned)
    return cleaned


def function_signature(query):
    """Only group explicit conversions with the same direction and file types.

    No embedding, AI semantic guesswork or broad similarities. Output remains
    a candidate requiring human review of the actual vendor/tool page.
    """
    tokens = normalize(query).split()
    positions = [i for i, word in enumerate(tokens) if word in {"to", "into"}]
    if len(positions) != 1:
        return ""
    index = positions[0]
    left = {FORMATS[x] for x in tokens[:index] if x in FORMATS}
    right = {FORMATS[x] for x in tokens[index + 1:] if x in FORMATS}
    if len(left) != 1 or len(right) != 1 or left == right:
        return ""
    other = [x for x in tokens
             if x not in FORMATS and x not in {"to", "into"} and x not in CONVERSION_CUES]
    if other:
        return ""
    return "file conversion " + next(iter(left)) + " to " + next(iter(right))

CATEGORY_TITLES = {
    "games": "游戏平台",
    "saas": "SaaS 产品发布目录",
    "ai": "AI 工具和 Agent 目录",
    "calculators": "计算器",
    "files": "PDF / 文件 / 图片工具",
    "developer": "开发者和自动化",
    "brazil": "巴西在线工具",
}


def source_category(src):
    topic = src.get("topic", "")
    if topic == "games":
        return "games"
    if topic == "brazilian-online-utilities":
        return "brazil"
    if topic == "calculators":
        return "calculators"
    if topic in {"pdf-tools", "pdf-file-tools", "file-conversion-tools", "image-video-tools"}:
        return "files"
    if topic.startswith("ai-"):
        return "ai"
    if topic in {"product-launches-saas", "saas-product-directory",
                 "saas-product-launches", "saas-launchpad"}:
        return "saas"
    if "developer" in topic or "automation" in topic or "deployable" in topic or "actors" in topic:
        return "developer"
    return "saas"


def summarize_coverage(config, latest):
    entries = {src["id"]: src for src in config.get("sources", [])}
    by_id = {row["source_id"]: row for row in latest.get("sources", [])
             if isinstance(row, dict) and row.get("source_id")}
    audit = {}
    for key in CATEGORY_TITLES:
        selected = [src for src in entries.values() if source_category(src) == key]
        status = [by_id.get(src["id"]) for src in selected]
        failures = [{"source_id": rec["source_id"], "error": rec.get("error", "unknown")}
                    for rec in status if rec and rec.get("status") == "error"]
        audit[key] = {
            "configured_sources": len(selected),
            "configured_domains": len({domain(
                (src.get("page_hosts") or [src["sitemap"]])[0]) for src in selected}),
            "reported": sum(row is not None for row in status),
            "successful": sum(bool(row and row.get("status") in {"baseline", "delta"})
                              for row in status),
            "baselines": sum(bool(row and row.get("status") == "baseline") for row in status),
            "delta_scans": sum(bool(row and row.get("status") == "delta") for row in status),
            "failed": len(failures),
            "new_urls": sum(int(row.get("new_url_count", 0)) for row in status if row),
            "over_scan_cap": sum(int(row.get("candidates_over_scan_cap", 0))
                                 for row in status if row),
            "failed_sources": failures,
        }
    return audit


def regroup_seven_types(groups):
    by_type = {key: [] for key in CATEGORY_TITLES}
    for group_name, matches in groups.items():
        for row in matches:
            for category in by_type:
                proofs = [r for r in row["evidence"] if r.get("source_category") == category]
                if len(proofs) < 2:
                    continue
                window = count_periods(proofs)
                period = (date.fromisoformat(proofs[-1]["first_seen"]) -
                          date.fromisoformat(proofs[0]["first_seen"])).days
                if window["three_calendar_day_peak"] >= 3:
                    priority = "high"
                elif window["three_calendar_day_peak"] >= 2 or len(proofs) >= 3:
                    priority = "medium"
                else:
                    priority = "watch"
                by_type[category].append({
                    **row, **window, "evidence": proofs,
                    "independent_websites": len(proofs),
                    "date_span_days": period,
                    "priority": priority,
                    "cross_signal_origin": group_name,
                })
    priority_score = {"high": 0, "medium": 1, "watch": 2}
    for category in by_type:
        by_type[category].sort(key=lambda row: (
            priority_score[row["priority"]],
            -row["three_calendar_day_peak"],
            -row["independent_websites"], row["query"]))
    return by_type



def count_periods(proofs):
    """Use day-granularity windows; do NOT claim exact rolling 24-hour times."""
    days = [date.fromisoformat(p["first_seen"]) for p in proofs]
    return {
        "same_calendar_day_peak": max((days.count(d) for d in set(days)), default=0),
        "three_calendar_day_peak": max(
            (sum(d >= start and d <= start + timedelta(days=2) for d in days)
             for start in set(days)), default=0),
        "seven_calendar_day_total": len(days),
    }


def summarize(queue, config, today):
    if isinstance(today, str):
        today = date.fromisoformat(today)
    cutoff = today - timedelta(days=6)
    sources = {row["id"]: row for row in config.get("sources", [])}
    buckets = defaultdict(dict)
    ignored = 0

    for row in queue:
        title = str(row.get("query", "")).strip()
        if len(normalize(title)) < 4:
            continue
        records = row.get("source_records")
        if not isinstance(records, list):
            records = [{"source_id": row.get("source_id"),
                        "url": row.get("url"),
                        "first_seen": row.get("first_seen")}]
        for proof in records:
            if not isinstance(proof, dict):
                ignored += 1
                continue
            source_id = proof.get("source_id")
            url = proof.get("url")
            stamp = proof.get("first_seen")
            if not all((source_id, url, stamp)) or source_id not in sources:
                ignored += 1
                continue
            try:
                day = date.fromisoformat(str(stamp)[:10])
            except ValueError:
                ignored += 1
                continue
            if not cutoff <= day <= today:
                continue
            site = domain(url)
            if not site:
                ignored += 1
                continue
            category = topic_group(sources[source_id])
            original = str(proof.get("query") or title)
            key = game_name(original, source_id) if category == "games" else normalize(original)
            if len(key) < 4:
                continue
            event = {
                "source_id": source_id, "website": site,
                "url": str(url), "first_seen": day.isoformat(),
                "observed_query": original,
                "source_category": source_category(sources[source_id]),
            }
            matching_groups = [(category, key)]
            function = function_signature(original) if category != "games" else ""
            if function:
                matching_groups.append(("functions", function))
            for kind, label in matching_groups:
                bucket = buckets[(kind, label)]
                old = bucket.get(site)
                if old is None or day.isoformat() < old["first_seen"]:
                    bucket[site] = event

    groups = {category: [] for category in CATEGORIES}
    for (kind, query), sites in buckets.items():
        if len(sites) < 2:
            continue
        evidence = sorted(sites.values(), key=lambda p: (p["first_seen"], p["website"]))
        span = (date.fromisoformat(evidence[-1]["first_seen"]) -
                date.fromisoformat(evidence[0]["first_seen"])).days
        periods = count_periods(evidence)
        if periods["three_calendar_day_peak"] >= 3:
            priority = "high"
        elif periods["three_calendar_day_peak"] >= 2 or len(evidence) >= 3:
            priority = "medium"
        else:
            priority = "watch"
        groups[kind].append({
            "query": query, "independent_websites": len(evidence),
            "date_span_days": span, "priority": priority,
            "match_basis": "same_direction_file_type_pair" if kind == "functions"
                           else "normalized_exact_title_only",
            **periods,
            "evidence": evidence,
        })
    scores = {"high": 0, "medium": 1, "watch": 2}
    for values in groups.values():
        values.sort(key=lambda p: (
            scores[p["priority"]], -p["three_calendar_day_peak"],
            -p["independent_websites"], p["date_span_days"], p["query"]))
    by_type = regroup_seven_types(groups)
    return {
        "date": today.isoformat(), "window_start": cutoff.isoformat(),
        "source_count": len(sources), "queue_count": len(queue),
        "ignored_unverifiable_proofs": ignored, "groups": groups,
        "group_counts": {key: len(items) for key, items in groups.items()},
        "by_type": by_type,
        "by_type_counts": {key: len(items) for key, items in by_type.items()},
    }


def render(payload, latest):
    lines = [
        "# 跨独立网站 Sitemap 同步上新观察", "",
        "观察截止：" + payload["date"] + "；滚动窗口：" +
        payload["window_start"] + "—" + payload["date"] + "（均为北京时间日期）。", "",
        "**Sitemap 首见并不等于首次发行、真实24小时内上架或搜索量；同名和文件格式归并必须人工核实。**",
        "只有具备真实source_id、详情URL和first_seen的相对基线新增，才能成为候选。",
        "同根域和语言镜像只算一个网站。不同根域也可能是同一运营主体，不自动等同独立厂商。",
        "日期精度仅为日历日，同日/连续3日不是严格24/72小时时间跨度。",
        "首次抓取建立基线，重新出现的旧URL不计新增。", "",
        "配置Sitemap来源：" + str(payload["source_count"]) +
        "；最新成功来源：" + str(latest.get("success_count", "未知")) + "/" +
        str(latest.get("source_count", "未知")) +
        "；数据生成：" + str(latest.get("generated_at", "未知")) +
        "；保留候选：" + str(payload["queue_count"]) + "。", "",
    ]
    for key, title in CATEGORIES.items():
        lines.extend(["## " + title, ""])
        selected = payload["groups"].get(key, [])[:10]
        if not selected:
            lines.extend(["**0：没有符合至少两个不同根域新增的候选。**", ""])
            continue
        for group in selected:
            lines.append(
                "- **" + group["query"] + "**：不同根域" +
                str(group["independent_websites"]) + "家；同一天峰值" +
                str(group["same_calendar_day_peak"]) + "家，连续3日峰值" +
                str(group["three_calendar_day_peak"]) + "家，7日累计" +
                str(group["seven_calendar_day_total"]) +
                "家；优先级 " + group["priority"] +
                "；证据匹配 " + group["match_basis"] + "。"
            )
            for proof in group["evidence"][:12]:
                lines.append("  - " + proof["website"] + " · " +
                             proof["source_id"] + " · " + proof["first_seen"] +
                             " · " + proof["url"] +
                             " · 原始查询 " + proof["observed_query"])
        lines.append("")
    lines.extend([
        "## 排除与限制", "",
        "精确同名仅是候选，不保证同款游戏或同一SaaS；跨类型文件格式相同，也不保证开发者不同。",
        "不执行Trends、Semrush、KD、CPC和后续SERP验证；不推断流量或收入。",
        "单站新增、失效源、缺失来源证据、旧URL复现、初次建基线均不能充当多站信号。",
        "原14天试运行结束后不自行续期。", "",
    ])
    return "\n".join(lines)


def run(root=ROOT):
    config = json.loads((root / "config/sitemap_sources.json").read_text(encoding="utf-8"))
    queue = json.loads((root / "data/sitemap/queue.json").read_text(encoding="utf-8"))
    latest = json.loads((root / "data/sitemap/latest.json").read_text(encoding="utf-8"))
    stamp = latest.get("generated_at")
    today = datetime.fromisoformat(stamp).date() if stamp else datetime.now(LOCAL_TZ).date()
    result = summarize(queue, config, today)
    result["coverage"] = summarize_coverage(config, latest)
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
