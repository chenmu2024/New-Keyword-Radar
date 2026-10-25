"""Publish seed-scout output without losing concurrent radar state.

Seed-scout and 90-day radar may both update state/pending.json. This publisher
backs up the scout result, refreshes origin/main, merges pending state, restores
scout-only artifacts, and pushes with bounded retry. No force push.
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
    from .publish_radar import merge_pending
    from .opportunity_tracker import update_ledger
except ImportError:
    from publish_radar import merge_pending
    from opportunity_tracker import update_ledger


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def write_json(path: Path, value: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def parse_dt(raw) -> datetime:
    try:
        d = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def git(*argv: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *argv], cwd=cwd, text=True, capture_output=True, check=check
    )


def copy_if_exists(src: Path, dst: Path):
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        shutil.copyfile(src, dst)


def publish(root: Path, max_attempts: int = 6):
    root = root.resolve()
    if not (root / ".git").exists():
        raise ValueError("Only run in a GitHub Actions repo checkout.")

    latest = read_json(root / "data/seed-scout-latest.json")
    local_generated = latest.get("local_generated_at")
    if not local_generated:
        raise ValueError("Missing local_generated_at in seed-scout latest output.")
    day = datetime.fromisoformat(str(local_generated)).date().isoformat()

    rel_paths = [
        Path("data/seed-scout-latest.json"),
        Path("data/seed-scout-daily") / f"{day}.json",
        Path("reports/seed-scout-daily") / f"{day}.md",
        Path("data/seed-scout") / day,
        Path("state/seed_cursor.json"),
    ]

    with tempfile.TemporaryDirectory(prefix="seed-scout-publish-") as tmp:
        backup = Path(tmp)
        for rel in rel_paths:
            copy_if_exists(root / rel, backup / rel)
        copy_if_exists(root / "state/pending.json", backup / "state/pending.json")

        local_pending = read_json(backup / "state/pending.json")
        local_cursor = read_json(backup / "state/seed_cursor.json")

        for attempt in range(1, max_attempts + 1):
            git("fetch", "origin", "main", cwd=root)
            git("reset", "--hard", "origin/main", cwd=root)

            # Restore scout-only output. The seed-scout concurrency group
            # serializes seed runs, so these paths have a single writer.
            for rel in rel_paths:
                copy_if_exists(backup / rel, root / rel)

            # pending.json is multi-writer: radar + seed scout. Merge instead
            # of rebasing or overwriting.
            remote_pending = read_json(root / "state/pending.json")
            write_json(root / "state/pending.json", merge_pending(remote_pending, local_pending))

            # Preserve the freshest cursor if a newer seed-scout commit somehow
            # landed before this retry.
            remote_cursor = read_json(root / "state/seed_cursor.json")
            if parse_dt(remote_cursor.get("last_success_at")) > parse_dt(local_cursor.get("last_success_at")):
                write_json(root / "state/seed_cursor.json", remote_cursor)

            # Preserve cross-day candidate identity and human review verdicts.
            # This step runs after reset/merge, so it always reads the latest remote state.
            update_ledger(root)

            add_args = [
                "add", "-A", "--",
                "state/opportunities.json",
                "data/opportunities/latest.json",
                "reports/opportunities/latest.md",
                "data/seed-scout-latest.json",
                f"data/seed-scout-daily/{day}.json",
                f"reports/seed-scout-daily/{day}.md",
                f"data/seed-scout/{day}",
                "state/pending.json",
                "state/seed_cursor.json",
            ]
            git(*add_args, cwd=root)

            if git("diff", "--cached", "--quiet", cwd=root, check=False).returncode == 0:
                print("Seed scout already up to date; nothing to publish.")
                return

            git(
                "commit", "-m", f"data: publish reconciled seed scout {day}",
                cwd=root,
            )
            pushed = git("push", "origin", "HEAD:main", cwd=root, check=False)
            if pushed.returncode == 0:
                print(f"Published seed-scout output on attempt {attempt}.")
                return

            print(
                f"Seed-scout push race; retry {attempt}/{max_attempts}: "
                f"{pushed.stderr[-500:]}",
                file=sys.stderr,
            )
            time.sleep(min(2 * attempt, 10))

    raise RuntimeError("Seed-scout publish failed after bounded retries.")


if __name__ == "__main__":
    publish(Path(__file__).resolve().parents[1])
