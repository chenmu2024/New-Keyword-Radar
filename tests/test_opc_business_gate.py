import json
import tempfile
import unittest
from pathlib import Path

from src.opc_business_gate import DIMENSIONS, evaluate, evidence_key, run


def item():
    return {
        "keyword": "grand blue codes",
        "geo": "US",
        "verdict": "formal",
        "newness_score": 91,
        "money_score": 86,
    }


def source(**kwargs):
    return {"source": "Manual dated external research", "checked_at": "2026-10-08", **kwargs}


def complete_record():
    return {
        "keyword_metrics": source(volume=1200, kd=18, cpc=0),
        "serp": source(notes="Reviewed top 10 organic results and intent overlap"),
        "benchmark": source(monthly_visits=20000),
        "dimensions": {name: source(score=4) for name in DIMENSIONS},
        "business_model": "Ads and optional digital templates",
        "acquisition_channel": "Organic search",
        "estimated_monthly_fixed_cost_usd": 0,
    }


class EvidenceGateTests(unittest.TestCase):
    def test_exact_keyword_and_geo_key(self):
        self.assertEqual(evidence_key(item()), "grand blue codes|US")

    def test_no_manually_provided_evidence_means_unknown_not_zero(self):
        result = evaluate(item(), {})
        self.assertEqual(result["status"], "needs-evidence")
        self.assertIsNone(result["volume"])
        self.assertIsNone(result["score_total"])
        self.assertIn("dated Volume/KD and source", result["missing"])

    def test_never_promote_non_formal_candidate(self):
        candidate = {**item(), "verdict": "old-history"}
        result = evaluate(candidate, complete_record())
        self.assertEqual(result["status"], "not-formal")

    def test_zero_volume_stops_review(self):
        evidence = complete_record()
        evidence["keyword_metrics"]["volume"] = 0
        self.assertEqual(evaluate(item(), evidence)["status"], "reject-zero-volume")

    def test_high_kd_stops_review(self):
        evidence = complete_record()
        evidence["keyword_metrics"]["kd"] = 43
        self.assertEqual(evaluate(item(), evidence)["status"], "watch-high-kd")

    def test_full_sourced_candidate_requires_human_review(self):
        result = evaluate(item(), complete_record())
        self.assertEqual(result["status"], "ready-for-human-review")
        self.assertEqual(result["score_total"], 24)
        self.assertTrue(result["advisory_only"])

    def test_uncited_dimension_never_counts(self):
        evidence = complete_record()
        evidence["dimensions"]["cashflow"] = {"score": 5}
        result = evaluate(item(), evidence)
        self.assertEqual(result["status"], "needs-evidence")
        self.assertIsNone(result["score_total"])

    def test_low_pain_is_not_build_ready(self):
        evidence = complete_record()
        evidence["dimensions"]["pain"]["score"] = 2
        result = evaluate(item(), evidence)
        self.assertEqual(result["status"], "watch-business-risk")

    def test_rising_trends_alone_does_not_count_as_traffic(self):
        evidence = complete_record()
        evidence["benchmark"]["monthly_visits"] = 150
        result = evaluate(item(), evidence)
        self.assertEqual(result["status"], "needs-evidence")

    def test_run_creates_artifacts_without_overwriting_radar(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "data").mkdir()
            (root / "config").mkdir()
            orig = {"generated_at": "2026-10-08T00:00:00+00:00", "formal_candidates": [item()]}
            (root / "data/latest.json").write_text(json.dumps(orig), encoding="utf-8")
            (root / "config/business_evidence.json").write_text("{}", encoding="utf-8")
            result = run(root)
            self.assertEqual(result["formal_candidate_count"], 1)
            self.assertEqual(result["assessments"][0]["status"], "needs-evidence")
            self.assertTrue((root / "reports/business/latest.md").exists())
            self.assertEqual(json.loads((root / "data/latest.json").read_text()), orig)


if __name__ == "__main__":
    unittest.main()
