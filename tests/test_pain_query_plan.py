import sys
import unittest
from collections import Counter
from datetime import date
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import free_intelligence as intel
import free_search as search
import lead_quality as quality


class PainPlanTests(unittest.TestCase):
    def test_balanced_market_rotation(self):
        selected, cfg = intel.queries(max_queries=7, reference_date=date(2026, 10, 8))
        groups = Counter(x["locale"] for x in selected)
        self.assertEqual(groups["en"], 2)
        self.assertEqual(groups["pt"], 2)
        self.assertEqual(groups["es"], 2)
        self.assertLessEqual(groups["multi"], 1)
        self.assertEqual({x["market"] for x in selected[:6]}, {"US", "BR", "MX"})
        self.assertTrue(all(x["issue_query"] for x in selected[:6]))

    def test_next_day_rotates_each_locale(self):
        today = intel.queries(max_queries=6, reference_date=date(2026, 10, 8))[0]
        tomorrow = intel.queries(max_queries=6, reference_date=date(2026, 10, 9))[0]
        self.assertNotEqual([x["query"] for x in today], [x["query"] for x in tomorrow])

    @patch.object(search, "github")
    def test_separate_source_query_is_recorded(self, github):
        github.return_value = []
        result = search.collect("invoice reconciliation manual", ["github_issues"], 2,
                                source_queries={"github_issues": "invoice reconciliation"})
        self.assertEqual(result["source_queries"]["github_issues"], "invoice reconciliation")
        github.assert_called_once_with("invoice reconciliation", "issues", 2)

    def test_media_article_does_not_prove_buyer_demand(self):
        row = {"platform": "bing_rss", "title": "Customers need manual invoice reconciliation automation",
               "url": "https://example.com/article", "snippet": "expensive tool feature request"}
        self.assertEqual(quality.score(row, "invoice reconciliation manual")["screening"], "reference")

    def test_only_explicit_user_pain_is_reviewable(self):
        product = {"platform": "github_issues", "title": "Invoice API integration",
                   "url": "https://github.com/x/y/issues/12",
                   "snippet": "Docs for the invoice API"}
        self.assertNotEqual(quality.score(product, "invoice integration")["screening"], "review")


if __name__ == "__main__":
    unittest.main()
