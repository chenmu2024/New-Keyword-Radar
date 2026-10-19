"""Merge-only publish for Sitemap research. Does not touch main radar state."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
FILES = ["state/sitemap/snapshots.json", "data/sitemap/queue.json",
         "data/sitemap/latest.json", "reports/sitemap/latest.md", "reports/sitemap/triage.md",
         "data/sitemap/validation.json", "reports/sitemap/validation.md"]


def cmd(*args, check=True):
    return subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True, check=check)


def load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save(path, val):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(val, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def publish():
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
                for name in (daily, "data/sitemap/latest.json", "reports/sitemap/latest.md", "reports/sitemap/triage.md", "data/sitemap/validation.json", "reports/sitemap/validation.md"):
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
            merged = {x["query"]: x for x in remote_queue if x.get("query")}
            for x in local_queue:
                if x.get("query") and x["query"] not in merged:
                    merged[x["query"]] = x
            save(ROOT / "data/sitemap/queue.json",
                 sorted(merged.values(), key=lambda r: r.get("first_seen", ""), reverse=True)[:250])
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
