"""Merge-only publish for Sitemap research. Does not touch main radar state."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from sitemap_monitor import MAX_QUEUE, merge_queue
from sitemap_trends import render
from sitemap_newwords import render as render_newwords, combine_launch_data


ROOT = Path(__file__).resolve().parents[1]
FILES = ["state/sitemap/snapshots.json", "data/sitemap/queue.json",
         "data/sitemap/latest.json", "reports/sitemap/latest.md", "reports/sitemap/triage.md",
         "data/sitemap/validation.json", "reports/sitemap/validation.md",
         "data/sitemap/release_dates.json", "reports/sitemap/newwords.md"]


def cmd(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=check)


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path, val):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(val, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publish():
    bounds = load(ROOT / "config/sitemap_sources.json", {})
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    if not (bounds["trial_start"] <= today < bounds["trial_end_exclusive"]):
        print("Outside 14-day Sitemap pilot: no publish.")
        return
    if not (ROOT / ".git").exists():
        raise RuntimeError("Must run from GitHub Actions checkout")
    local_latest = load(ROOT / "data/sitemap/latest.json", {})
    if not local_latest.get("generated_at"):
        print("Nothing to publish (outside trial)")
        return
    daily = "data/sitemap/" + local_latest["date"] + ".json"
    paths = FILES + [daily]
    with tempfile.TemporaryDirectory() as tmp:
        backup = Path(tmp)
        for name in paths:
            source = ROOT / name
            if source.exists():
                dest = backup / name
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
        for attempt in range(5):
            cmd("fetch", "origin", "main")
            cmd("reset", "--hard", "origin/main")
            remote = load(ROOT / "data/sitemap/latest.json", {})
            local_newer = local_latest["generated_at"] >= remote.get("generated_at", "")
            if local_newer:
                for name in (daily, "data/sitemap/latest.json", "reports/sitemap/latest.md", "reports/sitemap/triage.md", "data/sitemap/validation.json", "reports/sitemap/validation.md", "data/sitemap/release_dates.json", "reports/sitemap/newwords.md"):
                    source = backup / name
                    if source.exists():
                        dest = ROOT / name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source, dest)
            # Prevent an older concurrent scan from reverting more recent baseline.
            # Each source is owned by exactly one configured scanner.
            remote_state = load(ROOT / "state/sitemap/snapshots.json", {})
            local_state = load(backup / "state/sitemap/snapshots.json", {})
            for key, row in local_state.items():
                prev = remote_state.get(key, {})
                if row.get("checked_at", "") >= prev.get("checked_at", "") and local_newer:
                    remote_state[key] = row
            save(ROOT / "state/sitemap/snapshots.json", remote_state)
            remote_queue = load(ROOT / "data/sitemap/queue.json", [])
            local_queue = load(backup / "data/sitemap/queue.json", [])
            save(ROOT / "data/sitemap/queue.json",
                 merge_queue(remote_queue, local_queue, limit=MAX_QUEUE))
            # Reconcile validation independently: never drop a newer result
            # when overlapping scans publish against an older checkout.
            remote_checks = load(ROOT / "data/sitemap/validation.json", {})
            local_checks = load(backup / "data/sitemap/validation.json", {})
            for key, row in local_checks.items():
                prev = remote_checks.get(key, {})
                if row.get("checked_at", "") >= prev.get("checked_at", ""):
                    remote_checks[key] = row
            save(ROOT / "data/sitemap/validation.json", remote_checks)
            # Launch dates are independently observed facts, never rewritten
            # by an older concurrent job with a failed page request.
            remote_age = load(ROOT / "data/sitemap/release_dates.json", {})
            local_age = load(backup / "data/sitemap/release_dates.json", {})
            for url, row in local_age.items():
                prev = remote_age.get(url, {})
                if row.get("checked_at", "") >= prev.get("checked_at", "") or (
                    row.get("release_date") and not prev.get("release_date")
                ):
                    remote_age[url] = row
            save(ROOT / "data/sitemap/release_dates.json", remote_age)
            stamp = max(local_latest.get("generated_at", ""),
                        remote.get("generated_at", ""))
            if stamp:
                (ROOT / "reports/sitemap/validation.md").write_text(
                    render(remote_checks, datetime.fromisoformat(stamp)), encoding="utf-8")
            # Re-render from reconciled URL queue and release metadata, never
            # accidentally erase proof observed by another Sitemap run.
            if stamp:
                live_queue = load(ROOT / "data/sitemap/queue.json", [])
                launch_evidence = load(ROOT / "data/sitemap/launch_evidence.json", {})
                main = load(ROOT / "data/latest.json", {})
                combined = combine_launch_data(launch_evidence, remote_age)
                (ROOT / "reports/sitemap/newwords.md").write_text(
                    render_newwords(live_queue, combined, main,
                                    datetime.fromisoformat(stamp).date().isoformat()),
                    encoding="utf-8")
            cmd("add", "--", "state/sitemap", "data/sitemap", "reports/sitemap")
            if cmd("diff", "--cached", "--quiet", check=False).returncode == 0:
                print("Already up to date")
                return
            cmd("commit", "-m", "data: publish sitemap delta research")
            pushed = cmd("push", "origin", "HEAD:main", check=False)
            if pushed.returncode == 0:
                print("Published Sitemap research")
                return
            print("Push race; retry", attempt + 1)
            time.sleep((attempt + 1) * 2)
    raise RuntimeError("Sitemap research publish failed after retries")


if __name__ == "__main__":
    publish()
