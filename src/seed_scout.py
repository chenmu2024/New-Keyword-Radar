from __future__ import annotations

import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from trendspyg.compat.request import TrendReq

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/settings.json"
SEEDS = ROOT / "config/discovery_seeds.txt"
PENDING = ROOT / "state/pending.json"
CURSOR = ROOT / "state/seed_cursor.json"
LATEST = ROOT / "data/seed-scout-latest.json"
BATCH_DIR = ROOT / "data/seed-scout"
DAILY_DIR = ROOT / "data/seed-scout-daily"
DAILY_REPORT_DIR = ROOT / "reports/seed-scout-daily"
LOCAL_TZ = ZoneInfo("Asia/Shanghai")


def utc_now():
    return datetime.now(timezone.utc)


def norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s).strip()).lower()


def load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def save(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_seeds():
    if not SEEDS.exists():
        return []
    out, seen = [], set()
    for line in SEEDS.read_text(encoding="utf-8").splitlines():
        q = norm(line)
        if not q or q.startswith("#") or q in seen:
            continue
        seen.add(q)
        out.append(q)
    return out


def value_num(v):
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower().replace(",", "").replace("%", "")
    if s == "breakout":
        return 5000.0
    try:
        return float(s)
    except Exception:
        return 0.0


def queue(pending, query, seed, rise_value, today):
    q = norm(query)
    if len(q) < 2 or len(q) > 100 or q.isdigit():
        return
    source = f"seed-rising:{seed}"
    x = pending.setdefault(
        q,
        {"query": q, "geo": "", "source": source, "first_seen": today, "checks": 0},
    )
    x["last_seen"] = today
    x["seed_source"] = seed
    x["rise_value"] = max(float(x.get("rise_value", 0) or 0), float(rise_value or 0))
    if not str(x.get("source", "")).startswith("seed-rising:"):
        x["source"] = source


def daily_default(day: str, timeframe: str, target: int):
    return {
        "local_date": day,
        "timezone": "Asia/Shanghai",
        "timeframe": timeframe,
        "geo": "Worldwide",
        "target_seed_count": target,
        "batches": [],
        "errors": [],
        "scanned_seeds": [],
        "discoveries": [],
    }


def rotated_seeds(seeds: list[str], day: str) -> list[str]:
    if not seeds:
        return []
    # Rotate the starting point every Beijing-local day so a partial day never
    # favors the same roots repeatedly.
    offset = (date.fromisoformat(day).toordinal() * 7) % len(seeds)
    return seeds[offset:] + seeds[:offset]


def failed_seeds(daily: dict) -> set[str]:
    out = set()
    for e in daily.get("errors", []):
        for seed in e.get("seed_batch", []) or []:
            out.add(seed)
    return out


def select_next_batch(daily: dict, seeds: list[str], day: str, batch_size: int) -> list[str]:
    scanned = set(daily.get("scanned_seeds", []) or [])
    failed = failed_seeds(daily)
    ordered = rotated_seeds(seeds, day)

    # First keep moving through never-attempted roots. Failed roots are retried
    # only after the rest of the day's universe has had a chance to run.
    fresh = [s for s in ordered if s not in scanned and s not in failed]
    retry = [s for s in ordered if s not in scanned and s in failed]
    return (fresh + retry)[:batch_size]


def write_daily_report(daily: dict):
    day = daily["local_date"]
    discoveries = daily.get("discoveries", []) or []
    errors = daily.get("errors", []) or []
    target = int(daily.get("target_seed_count", 0) or 0)
    scanned = int(daily.get("scanned_seed_count", 0) or 0)

    DAILY_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# 7-Day Seed Scout — {day}",
        "",
        "- Timezone: Asia/Shanghai",
        f"- Daily target roots: {target}",
        f"- Scanned roots: {scanned}",
        f"- Attempted unique roots: {daily.get('attempted_seed_count', scanned)}",
        f"- Successful batches: {daily.get('batch_count', 0)}",
        f"- Failed attempts: {len(errors)}",
        f"- Rising queries: {daily.get('discovery_count', 0)}",
        f"- Complete daily target: {'YES' if daily.get('complete_daily_target') else 'NO'}",
        f"- Legacy >=20 roots gate: {'YES' if daily.get('complete_20_seeds') else 'NO'}",
        "",
        "## Scanned roots",
        "",
        ", ".join(daily.get("scanned_seeds", [])) if daily.get("scanned_seeds") else "(none)",
        "",
    ]
    if errors:
        lines += ["## Failed attempts", ""]
        for e in errors[-20:]:
            lines.append(
                f"- {e.get('local_generated_at')} — {', '.join(e.get('seed_batch', []))} — {e.get('error')}"
            )
        lines.append("")

    lines += ["## Top Rising queries", ""]
    for x in discoveries[:100]:
        lines.append(f"- {x['query']} <- {x.get('seed')} — rise {x.get('rise_value')}")
    (DAILY_REPORT_DIR / f"{day}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def refresh_daily_meta(daily: dict, target: int):
    scanned = []
    for b in daily.get("batches", []):
        for seed in b.get("seed_batch", []) or []:
            if seed not in scanned:
                scanned.append(seed)
    daily["scanned_seeds"] = scanned
    daily["scanned_seed_count"] = len(scanned)
    daily["batch_count"] = len(daily.get("batches", []))

    attempted = list(scanned)
    for e in daily.get("errors", []):
        for seed in e.get("seed_batch", []) or []:
            if seed not in attempted:
                attempted.append(seed)
    daily["attempted_seed_count"] = len(attempted)
    daily["target_seed_count"] = target
    daily["complete_20_seeds"] = daily["scanned_seed_count"] >= min(20, target)
    daily["complete_daily_target"] = daily["scanned_seed_count"] >= target
    daily["completion_pct"] = round(daily["scanned_seed_count"] / max(1, target) * 100, 1)
    daily["failed_seed_count"] = len(failed_seeds(daily) - set(scanned))
    return daily


def merge_daily(result: dict, target: int):
    local_dt = datetime.fromisoformat(result["local_generated_at"])
    day = local_dt.date().isoformat()
    daily_path = DAILY_DIR / f"{day}.json"
    daily = load(daily_path, daily_default(day, result["timeframe"], target))

    batch_id = result.get("batch_id") or result["generated_at"]
    batches = {str(x.get("batch_id") or x.get("generated_at")): x for x in daily.get("batches", [])}
    batches[batch_id] = {
        "batch_id": batch_id,
        "start_index": result.get("start_index"),
        "seed_indices": result.get("seed_indices", []),
        "generated_at": result["generated_at"],
        "local_generated_at": result["local_generated_at"],
        "seed_batch": result["seed_batch"],
        "discovery_count": result.get("discovery_count", 0),
        "status": "ok",
    }
    daily["batches"] = sorted(
        batches.values(), key=lambda x: str(x.get("generated_at", ""))
    )

    existing = {x["query"]: x for x in daily.get("discoveries", []) if x.get("query")}
    for x in result.get("discoveries", []):
        q = x["query"]
        prev = existing.get(q)
        if prev is None or float(x.get("rise_value", 0)) > float(prev.get("rise_value", 0)):
            if prev and prev.get("also_from_seeds"):
                x["also_from_seeds"] = list(prev["also_from_seeds"])
            existing[q] = x
        elif x.get("seed") and x["seed"] != prev.get("seed"):
            also = prev.setdefault("also_from_seeds", [])
            if x["seed"] not in also:
                also.append(x["seed"])

    daily["discoveries"] = sorted(
        existing.values(), key=lambda x: (-float(x.get("rise_value", 0)), x["query"])
    )
    daily["discovery_count"] = len(daily["discoveries"])
    daily["updated_at"] = result["generated_at"]
    refresh_daily_meta(daily, target)
    save(daily_path, daily)
    write_daily_report(daily)
    return daily


def record_error(result: dict, target: int):
    day = datetime.fromisoformat(result["local_generated_at"]).date().isoformat()
    daily_path = DAILY_DIR / f"{day}.json"
    daily = load(daily_path, daily_default(day, result["timeframe"], target))
    errors = daily.setdefault("errors", [])
    errors.append(
        {
            "generated_at": result["generated_at"],
            "local_generated_at": result["local_generated_at"],
            "start_index": result.get("start_index"),
            "seed_indices": result.get("seed_indices", []),
            "seed_batch": result["seed_batch"],
            "error": result.get("error", "unknown error"),
        }
    )
    daily["updated_at"] = result["generated_at"]
    refresh_daily_meta(daily, target)
    save(daily_path, daily)
    write_daily_report(daily)
    return daily


def scan_batch(batch: list[str], timeframe: str, per_seed: int):
    tr = TrendReq(hl="en-US", tz=0, cache="disk", cookies="disk", engine="auto")
    tr.build_payload(batch, timeframe=timeframe, geo="")
    related = tr.related_queries()
    discoveries = []
    for seed in batch:
        group = related.get(seed) or {}
        rising = group.get("rising")
        if rising is None:
            continue
        try:
            rows = rising.to_dict("records")
        except Exception:
            rows = []
        for row in rows[:per_seed]:
            q = norm(row.get("query", ""))
            if not q:
                continue
            discoveries.append(
                {
                    "seed": seed,
                    "query": q,
                    "rise_value": value_num(row.get("value")),
                    "raw_value": row.get("value"),
                }
            )
    discoveries.sort(key=lambda x: (-x["rise_value"], x["query"]))
    return discoveries


def main():
    cfg = load(CFG, {})
    seeds = parse_seeds()
    if not seeds:
        raise SystemExit("No discovery seeds configured")

    batch_size = max(1, min(5, int(cfg.get("seed_batch_size", 5))))
    configured_target = int(cfg.get("daily_seed_target", 0) or 0)
    target = min(len(seeds), configured_target if configured_target > 0 else len(seeds))
    max_batches = max(1, int(cfg.get("seed_batches_per_run", 20)))
    delay = max(15, int(cfg.get("seed_batch_delay_seconds", 90)))
    timeframe = cfg.get("seed_scan_timeframe", "now 7-d")
    per_seed = int(cfg.get("seed_related_per_keyword", 15))

    state = load(CURSOR, {"index": 0, "runs": 0})
    pending = load(PENDING, {})
    successful_batches = 0

    for run_index in range(max_batches):
        u = utc_now()
        l = u.astimezone(LOCAL_TZ)
        today = l.date().isoformat()
        daily_path = DAILY_DIR / f"{today}.json"
        daily = load(daily_path, daily_default(today, timeframe, target))
        refresh_daily_meta(daily, target)

        if daily.get("complete_daily_target"):
            print(
                f"Daily seed scout complete for {today}: "
                f"{daily.get('scanned_seed_count', 0)}/{target} roots; no-op"
            )
            save(daily_path, daily)
            write_daily_report(daily)
            break

        batch = select_next_batch(daily, seeds, today, batch_size)
        if not batch:
            print(f"No remaining seed batch for {today}; stopping")
            break

        seed_indices = [seeds.index(s) for s in batch]
        start = seed_indices[0] if seed_indices else 0
        result = {
            "batch_id": f"{u.isoformat()}-{'-'.join(str(i) for i in seed_indices)}",
            "generated_at": u.isoformat(),
            "local_generated_at": l.isoformat(),
            "timezone": "Asia/Shanghai",
            "timeframe": timeframe,
            "geo": "Worldwide",
            "seed_batch": batch,
            "seed_indices": seed_indices,
            "start_index": start,
            "discoveries": [],
            "status": "ok",
        }

        print(
            f"[{run_index + 1}/{max_batches}] {today}: scanning "
            f"{batch} (current {daily.get('scanned_seed_count', 0)}/{target})"
        )

        try:
            discoveries = scan_batch(batch, timeframe, per_seed)
            result["discoveries"] = discoveries
            result["discovery_count"] = len(discoveries)

            for x in discoveries:
                queue(pending, x["query"], x["seed"], x["rise_value"], today)

            state["index"] = (max(seed_indices) + 1) % len(seeds)
            state["runs"] = int(state.get("runs", 0)) + 1
            state["last_success_at"] = u.isoformat()
            state["last_batch"] = batch
            state["seed_count"] = len(seeds)

            save(PENDING, pending)
            save(CURSOR, state)
            save(LATEST, result)
            save(BATCH_DIR / today / f"{l.strftime('%H%M%S')}-batch-{start}.json", result)
            daily = merge_daily(result, target)
            successful_batches += 1

            print(
                f"Success: +{len(batch)} roots, {len(discoveries)} rising; "
                f"daily {daily['scanned_seed_count']}/{target}, "
                f"{daily['discovery_count']} unique rising"
            )

            if daily.get("complete_daily_target"):
                break
            time.sleep(delay)

        except Exception as e:
            result["status"] = "error"
            result["error"] = f"{type(e).__name__}: {e}"
            save(LATEST, result)
            save(
                BATCH_DIR / today / f"{l.strftime('%H%M%S')}-batch-{start}-error.json",
                result,
            )
            daily = record_error(result, target)
            print(result["error"], file=sys.stderr)
            print(
                f"Failed batch deferred; next run will continue with other roots. "
                f"Daily {daily.get('scanned_seed_count', 0)}/{target}."
            )

            # A Google rate limit is usually runner/IP scoped. Do not hammer it.
            # Exit cleanly so the next scheduled sweep can resume from a fresh runner.
            if "TooManyRequests" in result["error"] or "rate-limit" in result["error"].lower():
                break

            time.sleep(min(delay, 60))

    final_local = utc_now().astimezone(LOCAL_TZ)
    final_day = final_local.date().isoformat()
    final_daily = load(DAILY_DIR / f"{final_day}.json", daily_default(final_day, timeframe, target))
    refresh_daily_meta(final_daily, target)
    save(DAILY_DIR / f"{final_day}.json", final_daily)
    write_daily_report(final_daily)

    print(
        f"Sweep finished: {final_day} {final_daily.get('scanned_seed_count', 0)}/{target} roots, "
        f"{final_daily.get('discovery_count', 0)} unique rising, "
        f"{successful_batches} successful batches this run"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
