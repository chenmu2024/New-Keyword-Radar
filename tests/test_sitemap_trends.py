import unittest
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sitemap_trends as s

NOW = datetime.fromisoformat("2026-10-19T10:00:00+08:00")


def lead(q, source="railway-templates", first="2026-10-19", geo="US", cue=False):
    return {"query": q, "source_id": source, "url": "https://railway.com/deploy/" + q.replace(" ", "-"),
            "geo": geo, "first_seen": first, "tool_intent_hint": cue}


class SitemapTrendsTests(unittest.TestCase):
    def test_does_not_let_early_games_bury_last_qualified_lead(self):
        queue = [lead(f"new fun game {i}", source="gamepix-pt", geo="BR")
                 for i in range(85)]
        queue.append(lead("database backup generator", cue=True))
        self.assertEqual([x["query"] for x in s.select(queue, {}, "2026-10-19")],
                         ["database backup generator"])

    def test_limit_and_dedup_and_numbered_template(self):
        queue = [lead("ubuntu 2"), lead("workflow creator"), lead("workflow creator"),
                 lead("invoice checker"), lead("database backups")]
        selected = s.select(queue, {}, "2026-10-19")
        self.assertEqual(len(selected), 2)
        self.assertNotIn("ubuntu 2", {x["query"] for x in selected})
        self.assertEqual(len({x["query"] for x in selected}), 2)
        with self.assertRaises(ValueError):
            s.select(queue, {}, "2026-10-19", limit=3)
        self.assertEqual(s.select(queue, {}, "2026-10-19", limit=0), [])

    def test_validation_quota_is_not_monopolized_by_one_source(self):
        q = [lead("youtube transcript scraper", source="apify-actors-a"),
             lead("shopify price monitor", source="apify-actors-a"),
             lead("database backup", source="railway-templates")]
        chosen = s.select(q, {}, "2026-10-19")
        self.assertEqual(len(chosen), 2)
        self.assertEqual(len({row["source_id"] for row in chosen}), 2)

    def test_government_keywords_do_not_enter_validation(self):
        queue = [lead("uk public tenders tracker", source="apify-actors-a", cue=True),
                 lead("database backup", source="railway-templates")]
        chosen = s.select(queue, {}, "2026-10-19")
        self.assertEqual([row["query"] for row in chosen], ["database backup"])

    def test_cooldown_and_retry_failed(self):
        queue = [lead("database backup"), lead("invoice checker")]
        state = {s.key(queue[0]): {"checked_date": "2026-10-19", "status": "older_interest"},
                 s.key(queue[1]): {"checked_date": "2026-10-19", "status": "error"}}
        self.assertEqual(s.select(queue, state, "2026-10-19"), [])
        self.assertEqual([x["query"] for x in s.select(queue, state, "2026-10-20")],
                         ["invoice checker"])
        self.assertEqual(len(s.select(queue, state, "2026-10-26")), 2)

    def test_no_recent_rise_skips_five_year(self):
        calls = []
        def mock_explore(row, seen, cfg):
            calls.append("90d")
            return {"verdict": "reject", "true_new": False,
                    "recent_peak": 0, "series": [{"value": 0}]}
        def mock_history(*args):
            calls.append("5y")
            return {"historically_new": True}
        row = s.check(lead("database backups"), {}, NOW, mock_explore, mock_history)
        self.assertEqual(row["status"], "insufficient_relative_signal")
        self.assertEqual(calls, ["90d"])
        self.assertIsNone(row["semrush_volume"])
        self.assertFalse(row["independently_verified_new_keyword"])

    def test_five_year_gate_must_pass_before_trends_signal(self):
        def mock_explore(*args):
            return {"verdict": "trend-watch", "true_new": True,
                    "recent_peak": 100, "series": [{"value": 100}]}
        for val, expected in [(True, "trends_history_pass"),
                              (False, "older_interest"),
                              (None, "history_unknown")]:
            def mock_history(*args):
                return {"historically_new": val}
            row = s.check(lead("invoice generator"), {}, NOW, mock_explore, mock_history)
            self.assertEqual(row["status"], expected)
            self.assertFalse(row["independently_verified_new_keyword"])
            self.assertFalse(row["serp_checked"])
            self.assertFalse(row["revenue_verified"])

    def test_errors_cannot_be_promoted(self):
        def mock_explore(*args):
            raise RuntimeError("Google blocked")
        row = s.check(lead("invoice generator"), {}, NOW, mock_explore, lambda *x: {})
        self.assertEqual(row["status"], "error")
        self.assertIn("blocked", row["error"])
        self.assertFalse(row["independently_verified_new_keyword"])

    def test_report_distinguishes_workflow_success_from_data_coverage(self):
        now = NOW
        rows = {"x": {"query": "test", "url": "https://a.test", "status": "error",
                      "checked_at": now.isoformat(), "baseline_avg": None,
                      "recent_peak": None, "source_id": "example"},
                "y": {"query": "test2", "url": "https://a.test", "status": "no_recent_trends_breakout",
                      "checked_at": now.isoformat(), "baseline_avg": 1.1,
                      "recent_peak": 2, "source_id": "example"}}
        summary = s.coverage(rows)
        self.assertEqual(summary["usable"], 1)
        self.assertEqual(summary["missing"], 1)
        self.assertEqual(summary["status"], "partial_coverage")
        report = s.render(rows, now)
        self.assertIn("Usable Google Trends time series: 1/2", report)
        self.assertIn("Missing or failed Google Trends time series: 1/2", report)

    def test_trial_cutoff_is_exclusive_and_date_scoped(self):
        trial = {"trial_start": "2026-10-19", "trial_end_exclusive": "2026-11-02"}
        self.assertTrue(s.in_pilot("2026-10-19", trial))
        self.assertTrue(s.in_pilot("2026-11-01", trial))
        self.assertFalse(s.in_pilot("2026-11-02", trial))
        self.assertFalse(s.in_pilot("2026-10-18", trial))

    def test_rate_limit_fail_closed_and_global_backoff(self):
        from datetime import timedelta
        def blocked(*args):
            return {"verdict": "error", "series": [], "error": "RateLimitError: HTTP 429"}
        row = s.check(lead("invoice checker"), {}, NOW, blocked, lambda *args: {})
        self.assertEqual(row["status"], "rate_limited")
        self.assertFalse(row["independently_verified_new_keyword"])
        until = s.rate_limit_until({"x": row}, NOW + timedelta(hours=20))
        self.assertEqual(until, NOW + timedelta(hours=36))
        self.assertIsNone(s.rate_limit_until({"x": row}, NOW + timedelta(hours=37)))

    def test_legacy_rate_limit_error_activates_backoff(self):
        from datetime import timedelta
        stored = {"test": {"status": "error",
                           "error": "RateLimitError: Google rate-limited Explore",
                           "checked_at": NOW.isoformat()}}
        self.assertIsNotNone(s.rate_limit_until(stored, NOW + timedelta(hours=1)))

    def test_no_observations_is_insufficient_not_zero_volume(self):
        row = s.check(lead("local tool"), {}, NOW,
                      lambda *args: {"verdict": "reject", "true_new": False,
                                     "series": []}, lambda *args: {})
        self.assertEqual(row["status"], "insufficient_data")
        self.assertIsNone(row["semrush_volume"])

    def test_report_has_no_false_volume_claim(self):
        row = s.check(lead("database backups"), {}, NOW,
                      lambda *x: {"verdict": "reject", "true_new": False,
                                  "series": [{"value": 0}]}, lambda *x: {})
        report = s.render({s.key(row): row}, NOW)
        self.assertIn("relative interest", report)
        self.assertIn("Confirmed absolute Volume/KD/CPC: 0", report)
        self.assertIn("does NOT establish zero searches", report)
        self.assertIn("No URL finding", report)


if __name__ == "__main__":
    unittest.main()
