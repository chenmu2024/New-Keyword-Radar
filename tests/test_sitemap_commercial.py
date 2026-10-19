import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sitemap_commercial as s


class CommercialTests(unittest.TestCase):
    def setUp(self):
        self.existing = [{"url": "https://example.test/a", "source_id": "apify-actors-a"}]
        self.evidence = [{
            "label": "Example check",
            "source_url": "https://example.test/a",
            "listing_label": "Published listing",
            "pricing_url": "https://example.test/pricing",
            "checked_on": "2026-10-19",
            "tariff": "from USD $1 per use",
            "sold_function": "Run an audit",
            "web_version": "Single-purpose audit site",
            "cost_warning": "Backend may be necessary",
            "evidence_limit": "No actual sales evidence",
            "check_term": "audit tool",
        }]

    def test_exact_queue_url_required_and_fewer_candidates_not_invented(self):
        self.assertEqual(len(s.matched_evidence([], self.evidence)), 0)
        self.assertEqual(len(s.matched_evidence(self.existing, self.evidence)), 1)

    def test_pricing_offer_must_not_be_called_real_revenue(self):
        r = s.render(self.existing, self.evidence, "2026-10-19")
        self.assertIn("commercial-offer observed; real revenue and SEO viability unverified", r)
        self.assertIn("not establish actual payments", r)
        self.assertIn("Verified independent paid customers / monthly revenue:", r)
        self.assertIn("audit tool", r)

    def test_no_evidence_shows_no_review(self):
        r = s.render([], self.evidence, "2026-10-19")
        self.assertIn("0", r)
        self.assertIn("No reviewed pricing source", r)


if __name__ == "__main__":
    unittest.main()
