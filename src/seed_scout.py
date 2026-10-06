from __future__ import annotations

import json, math, re, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trendspyg.compat.request import TrendReq

ROOT = Path(__file__).resolve().parents[1]
CFG = ROOT / "config/settings.json"
SEEDS = ROOT / "config/discovery_seeds.txt"
PENDING = ROOT / "state/pending.json"
CURSOR = ROOT / "state/seed_cursor.json"
OUT = ROOT / "data/seed-scout-latest.json"


def now():
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
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_seeds():
    if not SEEDS.exists():
        return []
    out = []
    seen = set()
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
        {
            "query": q,
            "geo": "",
            "source": source,
            "first_seen": today,
            "checks": 0,
        },
    )
    x["last_seen"] = today
    x["seed_source"] = seed
    x["rise_value"] = max(float(x.get("rise_value", 0) or 0), float(rise_value or 0))
    if not str(x.get("source", "")).startswith("seed-rising:"):
        x["source"] = source


def main():
    cfg = load(CFG, {})
    seeds = parse_seeds()
    if not seeds:
        raise SystemExit("No discovery seeds configured")

    state = load(CURSOR, {"index": 0, "runs": 0})
    start = int(state.get("index", 0)) % len(seeds)
    batch_size = max(1, min(5, int(cfg.get("seed_batch_size", 5))))
    batch = [seeds[(start + i) % len(seeds)] for i in range(batch_size)]
    timeframe = cfg.get("seed_scan_timeframe", "now 7-d")
    per_seed = int(cfg.get("seed_related_per_keyword", 15))
    today = now().date().isoformat()

    result = {
        "generated_at": now().isoformat(),
        "timeframe": timeframe,
        "geo": "Worldwide",
        "seed_batch": batch,
        "start_index": start,
        "discoveries": [],
        "status": "ok",
    }

    pending = load(PENDING, {})

    try:
        tr = TrendReq(
            hl="en-US",
            tz=0,
            cache="disk",
            cookies="disk",
            engine="auto",
        )
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
                rv = value_num(row.get("value"))
                discoveries.append(
                    {
                        "seed": seed,
                        "query": q,
                        "rise_value": rv,
                        "raw_value": row.get("value"),
                    }
                )
                queue(pending, q, seed, rv, today)

        discoveries.sort(key=lambda x: (-x["rise_value"], x["query"]))
        result["discoveries"] = discoveries
        result["discovery_count"] = len(discoveries)

        state["index"] = (start + batch_size) % len(seeds)
        state["runs"] = int(state.get("runs", 0)) + 1
        state["last_success_at"] = now().isoformat()
        state["last_batch"] = batch
        state["seed_count"] = len(seeds)

        save(PENDING, pending)
        save(CURSOR, state)
        save(OUT, result)
        print(f"Scanned {len(batch)} seeds; found {len(discoveries)} rising queries")
        for x in discoveries[:20]:
            print(f"{x['seed']} -> {x['query']} ({x['rise_value']})")
        return 0

    except Exception as e:
        result["status"] = "error"
        result["error"] = f"{type(e).__name__}: {e}"
        save(OUT, result)
        print(result["error"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
