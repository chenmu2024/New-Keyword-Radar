"""Publish generated radar output without losing concurrent GitHub Actions updates.

Use only inside the transient GitHub Actions checkout. No force push.
The newest generated_at wins for daily report files; tracker state is merged.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from .opc_business_gate import run as business_review
except ImportError:
    from opc_business_gate import run as business_review


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    x = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(x, dict):
        raise ValueError(f"Invalid JSON dict: {path}")
    return x


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def timestamp(raw) -> datetime:
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return datetime.min.replace(tzinfo=timezone.utc)


def nonempty_min(a, b):
    present = [x for x in (a, b) if x]
    return min(present) if present else ""


def nonempty_max(a, b):
    present = [x for x in (a, b) if x]
    return max(present) if present else ""


def merge_seen(remote: dict, local: dict) -> dict:
    result = {k: dict(v) for k, v in remote.items() if isinstance(v, dict)}
    for key, cur in local.items():
        if not isinstance(cur, dict):
            continue
        prev = result.get(key)
        if prev is None:
            result[key] = dict(cur)
            continue
        chosen = dict(prev)
        chosen["first_seen"] = nonempty_min(prev.get("first_seen"), cur.get("first_seen"))
        chosen["last_seen"] = nonempty_max(prev.get("last_seen"), cur.get("last_seen"))
        chosen["sources"] = list(dict.fromkeys(
            list(prev.get("sources") or []) + list(cur.get("sources") or [])
        ))
        result[key] = chosen
    return result


def merge_pending(remote: dict, local: dict) -> dict:
    result = {k: dict(v) for k, v in remote.items() if isinstance(v, dict)}
    for key, cur in local.items():
        if not isinstance(cur, dict):
            continue
        prev = result.get(key)
        if prev is None:
            result[key] = dict(cur)
            continue
        # Preserve freshest sampled record and the greatest checked count, without
        # letting stale runs reset a query's "last_checked".
        p_time = nonempty_max(prev.get("last_checked"), prev.get("last_seen"))
        c_time = nonempty_max(cur.get("last_checked"), cur.get("last_seen"))
        chosen = dict(prev)
        if c_time >= p_time:
            chosen.update(cur)
        chosen["query"] = chosen.get("query") or key
        chosen["first_seen"] = nonempty_min(prev.get("first_seen"), cur.get("first_seen"))
        chosen["last_seen"] = nonempty_max(prev.get("last_seen"), cur.get("last_seen"))
        chosen["last_checked"] = nonempty_max(prev.get("last_checked"), cur.get("last_checked"))
        chosen["checks"] = max(int(prev.get("checks", 0) or 0), int(cur.get("checks", 0) or 0))
        chosen["rise_value"] = max(float(prev.get("rise_value", 0) or 0), float(cur.get("rise_value", 0) or 0))
        if not chosen.get("geo"):
            chosen["geo"] = cur.get("geo") or prev.get("geo") or ""
        result[key] = chosen
    # Preserve the existing queue bound while preferring recently observed items.
    sorted_items = sorted(result.items(), key=lambda kv: (
        int(kv[1].get("checks", 0) or 0),
        -timestamp((kv[1].get("last_seen") or "1970-01-01") + "T00:00:00+00:00").timestamp(),
        kv[0],
    ))
    return dict(sorted_items[:250])


def git(*argv: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["git", *argv]
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True, check=check)


def publish(root: Path, max_attempts: int = 6):
    root = root.resolve()
    if not (root / ".git").exists():
        raise ValueError("Only run in a GitHub Actions repo checkout.")
    local_report = read_json(root / "data/latest.json")
    if not local_report.get("generated_at"):
        raise ValueError("Missing generated_at: abort unsafe publication.")
    day = timestamp(local_report["generated_at"]).date().isoformat()
    report_paths = [
        "data/latest.json", f"data/{day}.json",
        "reports/latest.md", f"reports/{day}.md",
    ]
    state_paths = ["state/seen.json", "state/pending.json"]
    with tempfile.TemporaryDirectory(prefix="radar-publish-") as tmp:
        backup = Path(tmp)
        for path in report_paths + state_paths:
            src = root / path
            if src.exists():
                dest = backup / path
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
        local_seen = read_json(backup / "state/seen.json")
        local_pending = read_json(backup / "state/pending.json")
        for attempt in range(1, max_attempts + 1):
            git("fetch", "origin", "main", cwd=root)
            git("reset", "--hard", "origin/main", cwd=root)
            remote_report = read_json(root / "data/latest.json")
            local_is_newer = timestamp(local_report["generated_at"]) > timestamp(remote_report.get("generated_at"))
            if local_is_newer:
                for path in report_paths:
                    if (backup / path).exists():
                        dest = root / path
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(backup / path, dest)
            # Union instead of rebase conflict over daily evolving JSON maps.
            write_json(root / "state/seen.json", merge_seen(read_json(root / "state/seen.json"), local_seen))
            write_json(root / "state/pending.json", merge_pending(read_json(root / "state/pending.json"), local_pending))
            # Recompute from the winning report; never carry over a stale companion file.
            business_review(root)
            git("add", "-A", "--", "data", "reports", "state", cwd=root)
            if git("diff", "--cached", "--quiet", cwd=root, check=False).returncode == 0:
                print("Already up to date; nothing to publish.")
                return
            git("commit", "-m", f"data: publish reconciled radar output {day}", cwd=root)
            pushed = git("push", "origin", "HEAD:main", cwd=root, check=False)
            if pushed.returncode == 0:
                print(f"Published output (attempt {attempt}, local_report_newer={local_is_newer}).")
                return
            print(f"Push race, retry {attempt}/{max_attempts}: {pushed.stderr[-500:]}", file=sys.stderr)
            time.sleep(min(2 * attempt, 10))
    raise RuntimeError("Publish failed after bounded retries; no force push performed.")


if __name__ == "__main__":
    publish(Path(__file__).resolve().parents[1])
