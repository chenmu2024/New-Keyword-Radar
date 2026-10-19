import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sitemap_newwords as n


class GameReleaseTests(unittest.TestCase):
    def html(self, text):
        return "<html><body><p>Release date:</p><span>" + text + "</span></body></html>"

    def test_parse_explicit_publisher_release_date_not_sitemap_lastmod(self):
        self.assertEqual(n.extract_release_date(self.html("October 14, 2026")), "2026-10-14")
        self.assertIsNone(n.extract_release_date("<html>Last update: October 14, 2026</html>"))

    def test_real_old_games_excluded_even_if_just_seen(self):
        queue = [{"query": "no mice in the kitchen", "source_id": "gamepix-pt",
                  "url": "https://www.gamepix.com/play/no-mice-in-the-kitchen", "geo": "BR"},
                 {"query": "nations royale", "source_id": "gamepix-pt",
                  "url": "https://www.gamepix.com/play/nations-royale", "geo": "BR"}]
        verified = {
            queue[0]["url"]: {"release_date": "2024-03-04"},
            queue[1]["url"]: {"release_date": "2026-10-14"}
        }
        matched = n.priority(queue, verified, "2026-10-19")
        self.assertEqual([x["query"] for x in matched], ["nations royale"])

    def test_bounded_game_page_date_audit(self):
        q = [{"query": "new title", "source_id": "gamepix-pt",
              "url": "https://www.gamepix.com/play/new-title", "geo": "BR"},
             {"query": "random", "source_id": "apify-actors-a",
              "url": "https://apify.com/user/random", "geo": "US"}]
        calls = []
        def fetch(url, allowed, max_bytes):
            calls.append((url, allowed))
            return self.html("October 15, 2026").encode("utf-8")
        results = n.audit_games(q, {}, "2026-10-19", fetch)
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[q[0]["url"]]["release_date"], "2026-10-15")
        again = n.audit_games(q, results, "2026-10-19", fetch)
        self.assertEqual(again, results)
        with self.assertRaises(ValueError):
            n.audit_games(q, {}, "2026-10-19", fetch, limit=100)

    def test_failed_publisher_request_is_not_new_date(self):
        q = [{"query": "old-game", "source_id": "gamepix-pt",
              "url": "https://www.gamepix.com/play/old-game", "geo": "BR"}]
        def blocked(*args):
            raise OSError("403")
        result = n.audit_games(q, {}, "2026-10-19", blocked)
        self.assertNotIn("release_date", result[q[0]["url"]])
        self.assertEqual(n.priority(q, result, "2026-10-19"), [])

    def test_main_radar_signal_kept_separate_from_date_and_semrush(self):
        report = n.render([], {}, {"all_checked": [{"keyword": "eclipse animator roblox",
                        "true_new": True, "first_rise_date": "2026-10-11",
                        "newness_score": 100, "recent_peak": 100}]}, "2026-10-19")
        self.assertIn("eclipse animator roblox", report)
        self.assertIn("5年旧兴趣核验", report)
        self.assertIn("Semrush Volume/KD/CPC = 未验证", report)


if __name__ == "__main__":
    unittest.main()
