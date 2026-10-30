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


    def test_explicit_conversion_equivalence_and_reversed_direction(self):
        self.assertEqual(m.function_signature("convert pdf to excel"),
                         "file conversion pdf to excel")
        self.assertEqual(m.function_signature("PDF to XLSX converter"),
                         "file conversion pdf to excel")
        self.assertNotEqual(m.function_signature("Excel to PDF"),
                            m.function_signature("PDF to XLSX"))
        self.assertEqual(m.function_signature("PDF summary AI"), "")
        self.assertEqual(m.function_signature("PDF to JPEG to PNG"), "")

    def test_cross_type_file_conversion_signal_has_provenance(self):
        cfg = {"sources": [
            {"id": "file", "topic": "pdf-file-tools"},
            {"id": "ai", "topic": "ai-tool-directory"},
        ]}
        rows = [
            {"query": "PDF to XLSX", "source_records": [
                {"source_id": "file", "url": "https://pdfsite.example/pdf-to-xlsx",
                 "first_seen": "2026-10-29"}]},
            {"query": "convert pdf to excel", "source_records": [
                {"source_id": "ai", "url": "https://aitools.example/tool/convert-pdf-to-excel",
                 "first_seen": "2026-10-30"}]},
        ]
        result = m.summarize(rows, cfg, "2026-10-30")
        self.assertEqual(result["group_counts"]["functions"], 1)
        item = result["groups"]["functions"][0]
        self.assertEqual(item["independent_websites"], 2)
        self.assertEqual(item["three_calendar_day_peak"], 2)
        self.assertEqual({p["observed_query"] for p in item["evidence"]},
                         {"PDF to XLSX", "convert pdf to excel"})

    def test_peak_three_days_not_entire_seven_days(self):
        dates = ["2026-10-24", "2026-10-28", "2026-10-29", "2026-10-30"]
        cfg = {"sources": [{"id": str(i), "topic": "games"} for i in range(4)]}
        rows = [{"query": "same-name-game", "source_records": [
            {"source_id": str(i), "url": "https://game" + str(i) + ".example/game/same-name-game",
             "first_seen": dates[i]} for i in range(4)
        ]}]
        item = m.summarize(rows, cfg, "2026-10-30")["groups"]["games"][0]
        self.assertEqual(item["seven_calendar_day_total"], 4)
        self.assertEqual(item["three_calendar_day_peak"], 3)
        self.assertEqual(item["priority"], "high")

    def test_gamepost_catalog_id_is_not_game_version(self):
        cfg = {"sources": [
            {"id": "gamepost-games", "topic": "games"},
            {"id": "other", "topic": "games"},
        ]}
        rows = [
            {"query": "dragon rush 279263", "source_records": [
                {"source_id": "gamepost-games", "url": "https://www.gamepost.com/game/dragon-rush-279263",
                 "first_seen": "2026-10-29"}]},
            {"query": "dragon rush", "source_records": [
                {"source_id": "other", "url": "https://www.gamepix.com/play/dragon-rush",
                 "first_seen": "2026-10-30"}]},
        ]
        self.assertEqual(m.summarize(rows, cfg, "2026-10-30")["group_counts"]["games"], 1)


    def test_seven_category_classification_is_mutually_exclusive(self):
        samples = {
            "games": "games",
            "saas-product-directory": "saas",
            "ai-agent-directory": "ai",
            "calculators": "calculators",
            "pdf-tools": "files",
            "developer-automation": "developer",
            "brazilian-online-utilities": "brazil",
            "paid-data-automation-actors-partial-sample": "developer",
        }
        for topic, expected in samples.items():
            with self.subTest(topic=topic):
                self.assertEqual(m.source_category({"topic": topic}), expected)

    def test_same_product_in_different_categories_is_not_two_saas_sites(self):
        config = {"sources": [
            {"id": "saas", "topic": "saas-product-directory"},
            {"id": "ai", "topic": "ai-tool-directory"},
            {"id": "game", "topic": "games"},
        ]}
        rows = [{"query": "dream mint", "source_records": [
            {"source_id": "saas", "url": "https://saas.example/p/dream-mint",
             "first_seen": "2026-10-29"},
            {"source_id": "ai", "url": "https://ai.example/p/dream-mint",
             "first_seen": "2026-10-30"},
        ]}]
        got = m.summarize(rows, config, "2026-10-30")
        self.assertEqual(got["group_counts"]["products"], 1)
        self.assertEqual(got["by_type_counts"]["saas"], 0)
        self.assertEqual(got["by_type_counts"]["ai"], 0)
        self.assertEqual(got["by_type_counts"]["games"], 0)

    def test_two_saas_publishers_count_only_in_saas_category(self):
        config = {"sources": [
            {"id": "one", "topic": "saas-launchpad"},
            {"id": "two", "topic": "saas-product-directory"},
            {"id": "three", "topic": "ai-tool-directory"},
        ]}
        rows = [{"query": "dream mint", "source_records": [
            {"source_id": "one", "url": "https://startup.example/p/dream-mint",
             "first_seen": "2026-10-29"},
            {"source_id": "two", "url": "https://software.example/p/dream-mint",
             "first_seen": "2026-10-30"},
            {"source_id": "three", "url": "https://catalog.example/p/dream-mint",
             "first_seen": "2026-10-30"},
        ]}]
        got = m.summarize(rows, config, "2026-10-30")
        self.assertEqual(got["by_type_counts"]["saas"], 1)
        self.assertEqual(got["by_type_counts"]["ai"], 0)
        self.assertEqual(got["by_type"]["saas"][0]["independent_websites"], 2)

    def test_coverage_reports_errors_and_omits_unscanned_sources(self):
        config = {"sources": [
            {"id": "a", "topic": "games", "sitemap": "https://www.game-a.example/sitemap.xml"},
            {"id": "b", "topic": "games", "sitemap": "https://www.game-a.example/pt/sitemap.xml"},
            {"id": "c", "topic": "games", "sitemap": "https://game-b.example/sitemap.xml"},
            {"id": "d", "topic": "calculators", "sitemap": "https://math.example/sitemap.xml"},
        ]}
        latest = {"sources": [
            {"source_id": "a", "status": "delta", "new_url_count": 8,
             "candidates_over_scan_cap": 3},
            {"source_id": "b", "status": "baseline", "new_url_count": 0},
            {"source_id": "c", "status": "error", "error": "HTTP Error 403"},
        ]}
        coverage = m.summarize_coverage(config, latest)
        self.assertEqual(coverage["games"]["configured_sources"], 3)
        self.assertEqual(coverage["games"]["configured_domains"], 2)
        self.assertEqual(coverage["games"]["successful"], 2)
        self.assertEqual(coverage["games"]["failed"], 1)
        self.assertEqual(coverage["games"]["baselines"], 1)
        self.assertEqual(coverage["games"]["over_scan_cap"], 3)
        self.assertEqual(coverage["calculators"]["successful"], 0)
        self.assertEqual(coverage["calculators"]["reported"], 0)



    def test_uncapped_delta_proof_detects_game_absent_from_detail_queue(self):
        config = {"sources": [
            {"id": "gameA", "topic": "games"},
            {"id": "gameB", "topic": "games"},
        ]}
        queue = [{"query": "different old game", "source_id": "gameA",
                  "url": "https://a.example/game/different-old-game",
                  "first_seen": "2026-10-29"}]
        ledger = [
            {"query": "dragon rush", "source_id": "gameA",
             "url": "https://a.example/game/dragon-rush",
             "first_seen": "2026-10-29"},
            {"query": "dragon rush", "source_id": "gameB",
             "url": "https://b.example/game/dragon-rush",
             "first_seen": "2026-10-30"},
        ]
        self.assertEqual(m.summarize(queue, config, "2026-10-30")["group_counts"]["games"], 0)
        result = m.summarize(queue + ledger, config, "2026-10-30")
        self.assertEqual(result["group_counts"]["games"], 1)
        self.assertEqual(result["groups"]["games"][0]["three_calendar_day_peak"], 2)
        self.assertEqual(result["by_type_counts"]["games"], 1)


if __name__ == "__main__":
    unittest.main()
