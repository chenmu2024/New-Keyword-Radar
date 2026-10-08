import json
import tempfile
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import validation_history as h
import evidence_queue as e

TARGETS = Path(__file__).resolve().parents[1] / "config" / "validation_targets.json"


def topic(query="facturas SAT errores", intent="invoice_rejection", direct=None, context=None):
    return {
        "market": "MX", "language": "es",
        "research_topic": "tax_compliance", "research_intent": intent,
        "query_used_for_discovery": query, "stage": "needs_firsthand_problem_evidence",
        "may_be_recommended_for_build": False, "firsthand_evidence": direct or [],
        "contextual_references": context or [],
    }


def queue(day="2026-10-08", topics=None):
    entries = topics if topics is not None else [topic()]
    return {"date": day, "topics": entries, "total_topics": len(entries),
            "firsthand_qualified_topics": 0, "build_ready_count": 0}


def sight(url):
    return {"title": "Real article", "url": url, "source": "github_issues", "author": "one"}


class LongitudinalTests(unittest.TestCase):
    def test_no_archive_does_not_claim_history(self):
        with tempfile.TemporaryDirectory() as td:
            data = h.annotate_queue(queue(), td, TARGETS)
        self.assertEqual(data["historical_analysis"]["confidence"], "insufficient_history")
        self.assertEqual(data["historical_analysis"]["prior_archive_days_found"], 0)
        item = data["topics"][0]
        self.assertEqual(item["keyword_research"]["country"], "MX")
        self.assertIn("validar facturas SAT", item["keyword_research"]["exact_terms_to_check"])
        self.assertIsNone(item["keyword_research"]["monthly_search_volumes"])
        self.assertFalse(item["may_be_recommended_for_build"])

    def test_rotating_query_same_intent_is_area_only_not_same_customer(self):
        url = "https://github.com/repo/a/issues/1"
        older = topic(query="facturas SAT errores", direct=[sight(url)])
        previous = topic(query="validar facturas SAT", direct=[sight(url)])
        with tempfile.TemporaryDirectory() as td:
            for day, record in (("2026-10-06", older), ("2026-10-07", previous)):
                Path(td, day + "-validation-queue.json").write_text(
                    json.dumps(queue(day, [record])), encoding="utf-8")
            current = queue(topics=[topic(query="facturas SAT errores",
                                          direct=[sight(url), sight("https://a.example/new")])])
            result = h.annotate_queue(current, td, TARGETS)
        history = result["topics"][0]["history"]
        self.assertEqual(history["previous_days_in_same_research_area"], 2)
        self.assertEqual(history["previous_days_with_exact_query"], 1)
        self.assertEqual(history["returning_firsthand_urls_in_saved_sample"], 1)
        self.assertEqual(history["new_firsthand_urls_in_saved_sample"], 1)
        self.assertEqual(result["build_ready_count"], 0)
        self.assertFalse(history["is_repeat_user_demand_verified"])

    def test_refresh_same_day_is_not_another_archive_day(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "2026-10-08-validation-queue.json").write_text(
                json.dumps(queue()), encoding="utf-8")
            data = h.annotate_queue(queue(), td, TARGETS)
        self.assertEqual(data["historical_analysis"]["prior_archive_days_found"], 0)

    def test_outside_window_and_corrupt_files_ignored(self):
        with tempfile.TemporaryDirectory() as td:
            Path(td, "2026-09-01-validation-queue.json").write_text(
                json.dumps(queue("2026-09-01")), encoding="utf-8")
            Path(td, "2026-10-07-validation-queue.json").write_text(
                "this is not valid json", encoding="utf-8")
            data = h.annotate_queue(queue(), td, TARGETS)
        self.assertEqual(data["historical_analysis"]["prior_archive_days_found"], 0)
        self.assertEqual(data["historical_analysis"]["unreadable_archive_files"],
                         ["2026-10-07-validation-queue.json"])

    def test_different_market_or_intent_is_not_same_area(self):
        with tempfile.TemporaryDirectory() as td:
            older = topic()
            older["market"] = "BR"
            other_intent = topic(intent="invoice_validation")
            Path(td, "2026-10-07-validation-queue.json").write_text(
                json.dumps(queue("2026-10-07", [older, other_intent])), encoding="utf-8")
            result = h.annotate_queue(queue(), td, TARGETS)
        self.assertEqual(result["topics"][0]["history"]["previous_days_in_same_research_area"], 0)

    def test_render_has_separate_exact_keywords_and_history(self):
        with tempfile.TemporaryDirectory() as td:
            enriched = h.annotate_queue(queue(), td, TARGETS)
        rendered = e.render_queue(enriched)
        self.assertIn("Exact keyword hypotheses", rendered)
        self.assertIn("Volume: unknown; KD: unknown; CPC: unknown", rendered)
        self.assertIn("14-day cross-report observations", rendered)


if __name__ == "__main__":
    unittest.main()
