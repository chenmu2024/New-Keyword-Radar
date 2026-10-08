import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import lead_quality as q


class LeadQualityTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 8, tzinfo=timezone.utc)

    def test_genuine_issue_becomes_review_only_not_verified(self):
        item = {"platform": "github_issues", "title": "Need SaaS automation integration",
                "snippet": "Our customers need a feature request workflow; manual work is expensive.",
                "published_at": "2026-10-05T10:00:00Z", "url": "https://github.com/example/repo/issues/3"}
        s = q.score(item, "micro SaaS feature request", reference=self.now)
        self.assertEqual(s["screening"], "review")
        self.assertFalse(s["is_verified_opportunity"])
        self.assertIsNone(s["verified_volume"])

    def test_clearly_automated_noise_is_discarded(self):
        item = {"platform": "github_issues", "title": "[OPS COMMS] forever agent log do not close",
                "snippet": "automated workflow feature request automation",
                "url": "https://github.com/example/repo/issues/5",
                "published_at": "2026-10-06T00:00:00Z"}
        self.assertEqual(q.score(item, "micro SaaS feature request", reference=self.now)["screening"], "discard")

    def test_multilingual_problem(self):
        item = {"platform": "github_issues", "title": "Problema com ferramenta de faturamento",
                "snippet": "Preciso automatizar faturamento dos clientes; integração é manual",
                "url": "https://github.com/example/repo/issues/7",
                "published_at": "2026-10-07T00:00:00Z"}
        s = q.score(item, "problema ferramenta online Brasil", reference=self.now)
        self.assertEqual(s["screening"], "review")

    def test_search_does_not_infer_volume(self):
        item = {"platform": "bing_rss", "title": "AI SaaS generator pricing and templates",
                "snippet": "Tool subscription", "url": "https://example.com/saas"}
        screened = q.screen_result({"query": "SaaS generator", "items": [item]})
        self.assertIn("quality_screen", screened)
        self.assertIsNone(q.score(item, "SaaS generator")["verified_cpc"])

    def test_repo_is_competitor_not_demand(self):
        item = {"platform": "github_repositories", "title": "Feature request management SaaS",
                "snippet": "Software tool to collect user requests and manage clients",
                "published_at": "2026-10-05T00:00:00Z",
                "url": "https://github.com/example/featurehub"}
        result = q.screen_result({"query": "micro SaaS feature request", "items": [item]})
        self.assertEqual(result["quality_screen"]["review_count"], 0)
        self.assertEqual(result["quality_screen"]["reference_count"], 1)
        self.assertEqual(result["quality_screen"]["competitor_references"][0]["quality"]["screening"], "reference")

    def test_staleness_is_not_recent(self):
        item = {"platform": "github_issues", "title": "Need automation feature",
                "snippet": "customers need tools", "url": "https://github.com/x/y/issues/1",
                "published_at": "2021-10-01T00:00:00Z"}
        s = q.score(item, "feature automation", reference=self.now)
        self.assertIn("stale_over_one_year", s["reasons"])

    def test_unknown_source_not_reviewable(self):
        item = {"platform": "paid_unknown", "title": "SaaS tool broken missing feature request",
                "snippet": "Need automation", "url": "https://example.com/one"}
        self.assertEqual(q.score(item, "SaaS feature request", reference=self.now)["screening"], "discard")

if __name__ == "__main__":
    unittest.main()
