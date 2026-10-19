import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sitemap_triage as triage


class SitemapTriageTests(unittest.TestCase):
    def test_numbered_railway_templates_are_low_priority(self):
        self.assertEqual(triage.classify({"source_id": "railway-templates",
                                          "query": "chromium 1"})[0], "low")
        self.assertEqual(triage.classify({"source_id": "railway-templates",
                                          "query": "ubuntu 2"})[0], "low")

    def test_substantive_research_stays_unverified(self):
        tier, reason = triage.classify({"source_id": "railway-templates",
                                        "query": "dumpling backup"})
        self.assertEqual(tier, "review")
        self.assertIn("not-search-demand", reason)

    def test_government_procurement_is_not_an_actionable_lead(self):
        self.assertEqual(triage.classify({"source_id": "apify-actors-a",
                                          "query": "uk public tenders tracker",
                                          "tool_intent_hint": True})[0], "low")
        self.assertEqual(triage.classify({"source_id": "apify-actors-a",
                                          "query": "uk planning applications"})[0], "low")

    def test_game_titles_are_watch_only(self):
        self.assertEqual(triage.classify({"source_id": "gamepix-pt",
                                          "query": "new puzzle game"})[0], "watch")

    def test_report_does_not_invent_keyword_evidence_or_delete_queue(self):
        queue = [{"source_id": "gamepix-pt", "query": "game abc", "url": "https://example.com/a"},
                 {"source_id": "railway-templates", "query": "ubuntu 2",
                  "url": "https://example.com/b"}]
        before = repr(queue)
        report = triage.build_report({"date": "2026-10-19", "success_count": 18,
                                      "source_count": 18, "new_url_count": 1,
                                      "new_candidate_count": 1,
                                      "candidates": [queue[1]]}, queue)
        self.assertEqual(repr(queue), before)
        self.assertIn("not established", report)
        self.assertIn("Accumulated queue: 2", report)
        self.assertIn("ubuntu 2", report)


if __name__ == "__main__":
    unittest.main()
