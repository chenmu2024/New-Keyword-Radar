import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from src.social_signal_scout import signal, safe_url, parse_feed, reconcile, run


class SocialSignalTests(unittest.TestCase):
    def test_host_validation_and_canonical_dedupe(self):
        self.assertEqual(safe_url("https://www.tiktok.com/@abc/video/123?utm_source=foo",
                                  "tiktok"), "https://www.tiktok.com/@abc/video/123")
        self.assertEqual(safe_url("https://evil.example.com/post", "tiktok"), "")
        self.assertEqual(safe_url("http://x.com/x/status/12", "x"), "")
        first = signal("x", "https://x.com/foo/status/123?utm_medium=social",
                       "how to make template", "2026-10-25T00:00:00+00:00",
                       "search_index_pointer", "2026-10-24")
        second = signal("x", "https://x.com/foo/status/123", "same",
                        "2026-10-25T04:00:00+00:00", "search_index_pointer")
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(first["date_kind"], "search_index_date_not_post_date")
        self.assertFalse(first["user_demand_verified"])

    def test_atom_feed_parses_real_links_not_guesses(self):
        xml = b'''<feed xmlns="http://www.w3.org/2005/Atom">
        <entry><title>How to make a video</title><link rel="alternate"
        href="https://www.youtube.com/watch?v=123"/>
        <published>2026-10-25T00:00:00+00:00</published></entry></feed>'''
        parsed = parse_feed(xml, "2026-10-25T02:00:00+00:00", "youtube_channel")
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["published_at"], "2026-10-25T00:00:00+00:00")

    def test_collect_health_no_payment_claim_and_state_survives_rerun(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "config").mkdir()
            (root / "config/social_sources.json").write_text(json.dumps({
                "enabled_platforms": ["tiktok", "producthunt", "youtube_channel"],
                "per_source_limit": 3, "youtube_channel_ids": [],
                "indexed_queries": {"tiktok": ["site:tiktok.com generator"]},
            }), encoding="utf-8")
            ts = datetime(2026, 10, 25, 4, tzinfo=timezone.utc)
            indexed = signal("tiktok", "https://www.tiktok.com/@abc/video/123",
                             "how to make ai effect", ts.isoformat(),
                             "search_index_pointer")
            ph = signal("producthunt", "https://www.producthunt.com/posts/sample",
                        "new tool", ts.isoformat(), "direct_public_feed")
            fetchers = {
                "tiktok": lambda *args: [indexed],
                "producthunt": lambda *args: [ph],
            }
            result = run(root, ts, fetchers=fetchers)
            self.assertEqual(result["new_discoveries"], 2)
            self.assertEqual(result["sources"]["youtube_channel"]["status"], "not_configured")
            self.assertEqual(result["items"][0]["user_demand_verified"], False)
            self.assertEqual(run(root, ts, fetchers=fetchers)["new_discoveries"], 0)
            stored = json.loads((root / "state/social_seen.json").read_text())
            self.assertEqual(len(stored["items"]), 2)
            self.assertTrue((root / "reports/social-signals/latest.md").exists())

    def test_failure_is_visible(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "config").mkdir()
            (root / "config/social_sources.json").write_text(json.dumps({
                "enabled_platforms": ["x"], "indexed_queries": {"x": ["site:x.com tool"]}
            }), encoding="utf-8")
            def fail(*args):
                raise RuntimeError("429 Too Many Requests")
            out = run(root, datetime(2026, 10, 25, tzinfo=timezone.utc),
                      fetchers={"x": fail})
            self.assertEqual(out["sources"]["x"]["status"], "unavailable")
            self.assertEqual(out["new_discoveries"], 0)


if __name__ == "__main__":
    unittest.main()
