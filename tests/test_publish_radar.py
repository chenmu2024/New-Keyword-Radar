import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from src.publish_radar import merge_pending, merge_seen, publish, read_json


class PublishReconciliationTests(unittest.TestCase):
    def test_seen_merges_first_last_and_unique_sources(self):
        remote = {"a": {"first_seen": "2026-10-05", "last_seen": "2026-10-06", "sources": ["rss"]}}
        local = {"a": {"first_seen": "2026-10-04", "last_seen": "2026-10-08", "sources": ["rss", "autocomplete"]}}
        merged = merge_seen(remote, local)
        self.assertEqual(merged["a"]["first_seen"], "2026-10-04")
        self.assertEqual(merged["a"]["last_seen"], "2026-10-08")
        self.assertEqual(merged["a"]["sources"], ["rss", "autocomplete"])

    def test_pending_preserves_newest_and_non_decreasing_checks(self):
        remote = {"a": {"query": "a", "first_seen": "2026-10-06", "last_seen": "2026-10-08",
                        "last_checked": "2026-10-08", "checks": 3, "rise_value": 50, "geo": "US"}}
        local = {"a": {"query": "a", "first_seen": "2026-10-05", "last_seen": "2026-10-07",
                       "last_checked": "2026-10-07", "checks": 1, "rise_value": 100, "geo": ""}}
        merged = merge_pending(remote, local)
        self.assertEqual(merged["a"]["checks"], 3)
        self.assertEqual(merged["a"]["rise_value"], 100)
        self.assertEqual(merged["a"]["last_checked"], "2026-10-08")
        self.assertEqual(merged["a"]["geo"], "US")
        self.assertEqual(merged["a"]["first_seen"], "2026-10-05")

    def test_concurrent_report_keeps_newest_and_unions_state(self):
        def run(*args, cwd=None):
            return subprocess.run(["git", *args], cwd=cwd, check=True,
                                  text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            bare = base / "remote.git"
            run("init", "--bare", "-b", "main", str(bare))
            seed = base / "seed"
            run("clone", str(bare), str(seed))
            run("config", "user.name", "tester", cwd=seed)
            run("config", "user.email", "tester@example.invalid", cwd=seed)
            for name, obj in {
                "data/latest.json": {"generated_at": "2026-10-07T10:00:00+00:00", "formal_candidates": []},
                "state/seen.json": {"old": {"first_seen": "2026-10-07", "last_seen": "2026-10-07", "sources": ["rss"]}},
                "state/pending.json": {},
                "config/business_evidence.json": {},
            }.items():
                path = seed / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(obj))
            (seed / "reports").mkdir()
            (seed / "reports/latest.md").write_text("original")
            run("add", ".", cwd=seed)
            run("commit", "-m", "seed", cwd=seed)
            run("push", "-u", "origin", "main", cwd=seed)

            one = base / "one"
            two = base / "two"
            for path in [one, two]:
                run("clone", str(bare), str(path))
                run("config", "user.name", "tester", cwd=path)
                run("config", "user.email", "tester@example.invalid", cwd=path)
                (path / "state/seen.json").write_text(json.dumps({
                    "new-" + path.name: {"first_seen": "2026-10-08", "last_seen": "2026-10-08", "sources": ["rss"]}
                }))
                (path / "state/pending.json").write_text(json.dumps({
                    path.name: {"query": path.name, "checks": 1, "last_seen": "2026-10-08"}
                }))
                stamp = ("2026-10-08T08:02:00+00:00" if path == one
                         else "2026-10-08T08:01:00+00:00")
                (path / "data/latest.json").write_text(json.dumps({
                    "generated_at": stamp, "formal_candidates": []}))
                (path / "data/2026-10-08.json").write_text(json.dumps({
                    "generated_at": stamp, "formal_candidates": []}))
                (path / "reports/latest.md").write_text(path.name)
                (path / "reports/2026-10-08.md").write_text(path.name)

            publish(one, max_attempts=2)
            publish(two, max_attempts=2)

            check = base / "check"
            run("clone", str(bare), str(check))
            latest = read_json(check / "data/latest.json")
            self.assertEqual(latest["generated_at"], "2026-10-08T08:02:00+00:00")
            self.assertEqual((check / "reports/latest.md").read_text(), "one")
            self.assertEqual(set(read_json(check / "state/seen.json")), {"old", "new-one", "new-two"})
            self.assertEqual(set(read_json(check / "state/pending.json")), {"one", "two"})
            self.assertTrue((check / "data/business/latest.json").exists())
            self.assertTrue((check / "reports/business/latest.md").exists())


if __name__ == "__main__":
    unittest.main()
