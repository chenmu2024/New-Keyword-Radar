import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from src.social_signal_scout import signal, safe_url, parse_feed, reconcile, run, source_indexed


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

    def test_secondary_index_never_becomes_direct_comment_evidence(self):
        with patch("src.social_signal_scout.bing_rss", return_value=[
            {"url": "https://www.bing.com/search", "title": "bad off-platform"}
        ]), patch("src.social_signal_scout.duckduckgo", return_value=[
            {"url": "https://www.tiktok.com/@real/video/77",
             "title": "how to make an AI effect"}
        ]):
            rows = source_indexed("tiktok", "site:tiktok.com ai effect",
                                  "2026-10-25T00:00:00+00:00", 5)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["discovery_engine"], "duckduckgo_html")
        self.assertEqual(rows[0]["evidence_type"], "search_index_pointer")
        self.assertFalse(rows[0]["user_demand_verified"])

    def test_first_party_social_posts_not_verified_payment(self):
        from src.social_direct import bluesky_posts, mastodon_hashtag
        def bsky_fetch(url, host):
            self.assertEqual(host, "public.api.bsky.app")
            return {"posts": [{"uri": "at://did:plc:abc/app.bsky.feed.post/3k9abc",
                 "author": {"handle": "sample.bsky.social"},
                 "record": {"text": "Does anyone know how to make a stick run game creator?",
                            "createdAt": "2026-10-25T00:00:00Z"}}]}
        items = bluesky_posts("how to make", "2026-10-25T01:00:00Z", 4, getter=bsky_fetch)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["evidence_type"], "direct_public_post")
        self.assertFalse(items[0]["user_demand_verified"])
        self.assertEqual(items[0]["url"], "https://bsky.app/profile/sample.bsky.social/post/3k9abc")
        def mastodon_fetch(url, host):
            self.assertEqual(host, "mastodon.social")
            return [{"url": "https://mastodon.social/@user/123",
                     "visibility": "public", "content": "<p>Looking for a tool to create a template</p>",
                     "created_at": "2026-10-24T12:00:00Z"}]
        mast = mastodon_hashtag("gamedev", "2026-10-25T01:00:00Z", 4, getter=mastodon_fetch)
        self.assertEqual(mast[0]["evidence_type"], "direct_public_post")
        self.assertTrue(mast[0]["primary_text_available"])

    def test_enabled_direct_sources_are_dispatched(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "config").mkdir()
            (root / "config/social_sources.json").write_text(json.dumps({
                "enabled_platforms": ["bluesky", "mastodon"],
                "bluesky_queries": ["need a tool"],
                "mastodon_hashtags": ["opensource"]
            }), encoding="utf-8")
            calls = []
            def bluesky_fetch(term, at, limit):
                calls.append(("bluesky", term))
                return [signal("bluesky",
                               "https://bsky.app/profile/name.bsky.social/post/3k9abc",
                               "Is there a tool for this?", at, "direct_public_post")]
            def mastodon_fetch(term, at, limit):
                calls.append(("mastodon", term))
                return [signal("mastodon",
                               "https://mastodon.social/@name/123",
                               "Need a free template", at, "direct_public_post")]
            out = run(root, datetime(2026, 10, 25, 1, tzinfo=timezone.utc),
                      fetchers={"bluesky": bluesky_fetch, "mastodon": mastodon_fetch})
            self.assertEqual(calls, [("bluesky", "need a tool"), ("mastodon", "opensource")])
            self.assertEqual(out["sources"]["bluesky"]["status"], "ok")
            self.assertEqual(out["sources"]["mastodon"]["status"], "ok")
            self.assertEqual(out["unique_in_run"], 2)

    def test_bluesky_falls_back_only_to_official_public_api(self):
        from src.social_direct import bluesky_posts
        from urllib.error import HTTPError
        calls = []
        def getter(url, host):
            calls.append(host)
            if host == "public.api.bsky.app":
                raise HTTPError(url, 403, "Forbidden", {}, None)
            self.assertEqual(host, "api.bsky.app")
            return {"posts": [{
                "uri": "at://did:plc:example/app.bsky.feed.post/3k7abc",
                "author": {"handle": "person.bsky.social"},
                "record": {"text": "I need a tool to batch resize Minecraft skins",
                           "createdAt": "2026-10-25T02:00:00Z"}
            }]}
        rows = bluesky_posts("need a tool", "2026-10-25T03:00:00Z", 5, getter=getter)
        self.assertEqual(calls, ["public.api.bsky.app", "api.bsky.app"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["evidence_type"], "direct_public_post")
        def banned(url, host):
            raise HTTPError(url, 429, "Too Many Requests", {}, None)
        with self.assertRaises(HTTPError):
            bluesky_posts("need a tool", "2026-10-25T03:00:00Z", 5, getter=banned)

    def test_official_ask_hn_api_yields_primary_public_questions(self):
        from src.social_direct import hackernews_ask
        calls = []
        def getter(url, host):
            calls.append(url)
            self.assertEqual(host, "hacker-news.firebaseio.com")
            if url.endswith("askstories.json"):
                return [123, 124]
            if url.endswith("item/123.json"):
                return {"type": "story", "title": "Ask HN: Is there a tool to convert local CSV files?",
                        "text": "<p>Need a batch CSV formatter.</p>",
                        "time": 1792886400}
            return {"type": "story", "title": "Ask HN: Spam", "deleted": True}
        rows = hackernews_ask("2026-10-25T03:00:00Z", 3, getter=getter)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["platform"], "hackernews_ask")
        self.assertEqual(rows[0]["url"], "https://news.ycombinator.com/item?id=123")
        self.assertTrue(rows[0]["primary_text_available"])
        self.assertEqual(len(calls), 3)

    def test_question_hypotheses_are_not_auto_promoted(self):
        from src.social_intent import mine_user_questions, hypothesis
        self.assertEqual(hypothesis("I need a tool to batch resize Minecraft skins"),
                         "to batch resize minecraft skins")
        self.assertIsNone(hypothesis("We just launched a new generator for marketers!"))
        original = {
            "platform": "hackernews_ask",
            "evidence_type": "direct_public_post",
            "primary_text_available": True,
            "title": "I need a tool to batch resize Minecraft skins",
            "description": "I need a tool to batch resize Minecraft skins",
            "url": "https://news.ycombinator.com/item?id=123",
            "published_at": "2026-10-25T01:00:00Z"
        }
        queries = mine_user_questions([original, {
            **original, "platform": "x", "evidence_type": "search_index_pointer",
            "url": "https://x.com/a/status/1"
        }])
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0]["demand_status"], "unverified_question_hint")
        self.assertIsNone(queries[0]["search_volume"])
        self.assertFalse(queries[0]["ready_to_build"])

    def test_direct_hn_flow_and_questions_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "config").mkdir()
            (root / "config/social_sources.json").write_text(json.dumps({
                "enabled_platforms": ["hackernews_ask"]
            }), encoding="utf-8")
            def hn_fetch(at, limit):
                row = signal("hackernews_ask", "https://news.ycombinator.com/item?id=123",
                             "Is there a free tool to batch convert SVG icons?",
                             at, "direct_public_post",
                             "2026-10-25T01:00:00Z")
                row["primary_text_available"] = True
                return [row]
            out = run(root, datetime(2026, 10, 25, 1, tzinfo=timezone.utc),
                      fetchers={"hackernews_ask": hn_fetch})
            self.assertEqual(out["sources"]["hackernews_ask"]["status"], "ok")
            questions = json.loads((root / "data/social-signals/correlations-latest.json").read_text())
            self.assertEqual(questions["public_question_hypotheses"], 1)
            self.assertFalse(questions["query_hypotheses"][0]["ready_to_build"])

    def test_unavailable_index_is_not_false_empty(self):
        from src.social_signal_scout import source_indexed
        from unittest.mock import patch
        with patch("src.social_signal_scout.bing_rss", side_effect=ValueError("blocked")), \
             patch("src.social_signal_scout.duckduckgo", side_effect=ValueError("blocked")):
            with self.assertRaisesRegex(RuntimeError, "Both public index sources unavailable"):
                source_indexed("x", "site:x.com maker", "2026-10-25T01:00:00Z", 4)

    def test_exact_multiword_social_query_correlation(self):
        from src.social_correlation import match_signals, viable_query, update_correlation
        self.assertFalse(viable_query("ai"))
        self.assertTrue(viable_query("stick run game creator"))
        social = [
            {"platform": "bluesky", "url": "https://bsky.app/profile/sample.bsky.social/post/3k9abc",
             "title": "Does anyone know how to make a stick run game creator?",
             "description": "", "evidence_type": "direct_public_post"},
            {"platform": "x", "url": "https://x.com/example/status/123",
             "title": "A new stick run game creator is here", "description": "",
             "evidence_type": "search_index_pointer"},
            {"platform": "tiktok", "url": "https://www.tiktok.com/@x/video/123",
             "title": "ai trends everywhere", "description": "", "evidence_type": "search_index_pointer"}
        ]
        matches = match_signals(social, {"stick run game creator": {
            "rise_value": 120.0, "seed": "creator"}, "ai": {"rise_value": 99999, "seed": "ai"}})
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["independent_platforms"], 2)
        self.assertEqual(matches[0]["original_post_question_hints"], 1)
        self.assertFalse(matches[0]["ready_to_build"])
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "data/seed-scout-daily").mkdir(parents=True)
            (root / "data/seed-scout-daily/2026-10-25.json").write_text(json.dumps({
                "scanned_seed_count": 74, "target_seed_count": 74,
                "complete_daily_target": True, "discoveries": [
                    {"query": "stick run game creator", "rise_value": 120, "seed": "creator"}
                ]}), encoding="utf-8")
            result = update_correlation(root, datetime(2026, 10, 25, 1, tzinfo=timezone.utc),
                {"generated_at": "2026-10-25T01:00:00Z", "unique_in_run": 3, "items": social})
            self.assertEqual(result["cross_matches"], 1)
            self.assertTrue((root / "reports/social-signals/correlations-latest.md").exists())

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
