import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sitemap_cross_signal as m


class CrossSiteSignalTests(unittest.TestCase):
    def setUp(self):
        self.config = {"sources": [
            {"id": "crazygames-en", "sitemap": "https://www.crazygames.com/en/sitemap", "topic": "games"},
            {"id": "crazygames-br", "sitemap": "https://www.crazygames.com/br/sitemap", "topic": "games"},
            {"id": "gamepix-en", "sitemap": "https://www.gamepix.com/sitemaps/index.xml", "topic": "games"},
            {"id": "s1", "sitemap": "https://saas1.example/sitemap.xml", "topic": "saas-launchpad"},
            {"id": "s2", "sitemap": "https://saas2.example/sitemap.xml", "topic": "saas-launchpad"},
        ]}

    def test_same_root_language_mirrors_do_not_count_twice(self):
        rows = [{"query": "dragon dash", "source_records": [
            {"source_id": "crazygames-en", "url": "https://www.crazygames.com/game/dragon-dash", "first_seen": "2026-10-29"},
            {"source_id": "crazygames-br", "url": "https://www.crazygames.com/br/game/dragon-dash", "first_seen": "2026-10-30"},
        ]}]
        got = m.summarize(rows, self.config, "2026-10-30")
        self.assertEqual(got["group_counts"]["games"], 0)
        rows[0]["source_records"].append(
            {"source_id": "gamepix-en", "url": "https://www.gamepix.com/play/dragon-dash", "first_seen": "2026-10-30"})
        got = m.summarize(rows, self.config, "2026-10-30")
        self.assertEqual(got["group_counts"]["games"], 1)
        self.assertEqual(got["groups"]["games"][0]["independent_websites"], 2)

    def test_old_or_unknown_evidence_not_included(self):
        rows = [{"query": "invoice cleaner", "source_records": [
            {"source_id": "s1", "url": "https://saas1.example/p/invoice-cleaner", "first_seen": "2026-10-19"},
            {"source_id": "s2", "url": "https://saas2.example/p/invoice-cleaner", "first_seen": "2026-10-30"},
        ]}]
        self.assertEqual(m.summarize(rows, self.config, "2026-10-30")["group_counts"]["products"], 0)
        rows[0]["source_records"][0]["first_seen"] = "2026-10-28"
        self.assertEqual(m.summarize(rows, self.config, "2026-10-30")["group_counts"]["products"], 1)

    def test_version_names_and_unsupported_rows_do_not_merge(self):
        rows = [
            {"query": "Dragon Rush", "source_records": [
                {"source_id": "crazygames-en", "url": "https://www.crazygames.com/game/dragon-rush", "first_seen": "2026-10-30"}]},
            {"query": "Dragon Rush 2", "source_records": [
                {"source_id": "gamepix-en", "url": "https://www.gamepix.com/play/dragon-rush-2", "first_seen": "2026-10-30"}]},
        ]
        self.assertEqual(m.summarize(rows, self.config, "2026-10-30")["group_counts"]["games"], 0)
        self.assertEqual(m.domain("https://www.example.com.br/a"), "example.com.br")


if __name__ == "__main__":
    unittest.main()
