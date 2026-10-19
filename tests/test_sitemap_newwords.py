import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sitemap_newwords as n


class SitemapOnlyNewWordTests(unittest.TestCase):
    def game(self, query="nations royale", source="gamepix-pt", date="2026-10-19"):
        return {"query": query, "source_id": source,
                "url": "https://www.gamepix.com/pt/play/" + query.replace(" ", "-"),
                "geo": "BR", "first_seen": date}

    def test_gamepix_release_date_read_from_page_not_sitemap_lastmod(self):
        html = "<html><p>Release date:</p><span>October 14, 2026</span></html>"
        self.assertEqual(n.extract_release_date(html), "2026-10-14")
        self.assertIsNone(n.extract_release_date("<html>Last update: October 14, 2026</html>"))

    def test_pilot_provenance_rejects_rss_and_nontrial_pages(self):
        self.assertTrue(n.observed_from_monitored_sitemap(self.game(), "2026-10-19"))
        self.assertFalse(n.observed_from_monitored_sitemap(self.game(source="rss-trends"), "2026-10-19"))
        self.assertFalse(n.observed_from_monitored_sitemap(self.game(date="2026-10-18"), "2026-10-17"))
        self.assertFalse(n.observed_from_monitored_sitemap(self.game(date="2026-10-01"), "2026-10-19"))
        bad = self.game()
        del bad["first_seen"]
        self.assertFalse(n.observed_from_monitored_sitemap(bad, "2026-10-19"))

    def test_recent_game_from_sitemap_and_old_game_excluded(self):
        new = self.game()
        old = self.game("wyrm saga")
        launched = {new["url"]: {"release_date": "2026-10-14"},
                    old["url"]: {"release_date": "2026-03-30"}}
        chosen = n.priority([new, old], launched, "2026-10-19")
        self.assertEqual([x["query"] for x in chosen], ["nations royale"])
        self.assertEqual(chosen[0]["sitemap_first_seen"], "2026-10-19")

    def test_radar_keyword_without_sitemap_url_never_appears_in_report(self):
        candidate = self.game()
        dates = {candidate["url"]: {"release_date": "2026-10-14"}}
        main_radar = {"all_checked": [
            {"keyword":"eclipse animator roblox","true_new":True,
             "recent_peak":100, "first_rise_date":"2026-10-11"},
            {"keyword":"hood warfare 2","true_new":True}]}
        report = n.render([candidate], dates, main_radar, "2026-10-19")
        self.assertIn("###", report) if "###" in report else self.assertIn("nations royale", report)
        self.assertNotIn("eclipse animator roblox", report)
        self.assertNotIn("hood warfare 2", report)
        self.assertIn("nations royale", report)

    def test_sitemap_trends_only_annotation_by_exact_market_keyword(self):
        candidate = self.game()
        dates = {candidate["url"]: {"release_date": "2026-10-14"}}
        validation = {
            "BR|nations royale": {"status":"trends_history_pass",
                                  "history_5y":{"historically_new":True},
                                  "first_rise_date":"2026-10-16"},
            "US|unrelated": {"status":"trends_history_pass",
                              "first_rise_date":"2026-10-14"}}
        report = n.render([candidate], dates, validation, "2026-10-19")
        self.assertIn("Trends状态：trends_history_pass", report)
        self.assertNotIn("unrelated", report)

    def test_bounded_publisher_page_probe_and_fail_closed(self):
        game = self.game()
        called = []
        def fake(url, allowed, max_bytes):
            called.append(url)
            return b"<p>Release date:</p><span>October 15, 2026</span>"
        rows = n.audit_games([game], {}, "2026-10-19", fake)
        self.assertEqual(rows[game["url"]]["release_date"], "2026-10-15")
        self.assertEqual(len(n.audit_games([game], rows, "2026-10-19", fake)), 1)
        self.assertEqual(len(called), 1)
        with self.assertRaises(ValueError):
            n.audit_games([game], {}, "2026-10-19", fake, limit=100)
        def blocked(*args):
            raise OSError("403")
        error = n.audit_games([game], {}, "2026-10-19", blocked)
        self.assertNotIn("release_date", error[game["url"]])

    def test_report_cannot_promote_manually_supplied_url_not_in_sitemap(self):
        new = self.game()
        dates = {new["url"]: {"release_date":"2026-10-14"},
                 "https://create.roblox.com/asset/eclipse": {"release_date":"2026-10-14"}}
        report = n.render([], dates, {}, "2026-10-19")
        self.assertIn("没有符合真实 Sitemap", report)
        self.assertNotIn("nations royale", report)
        report2 = n.render([new], dates, {}, "2026-10-19")
        self.assertIn("nations royale", report2)
        self.assertNotIn("eclipse", report2)


if __name__ == "__main__":
    unittest.main()
