import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from src.opportunity_tracker import identity, review_status, update_ledger

class OpportunityTrackerTests(unittest.TestCase):
    def test_stable_identity_and_review_gate(self):
        self.assertEqual(identity("  Hotel   Lobby AI ", "us"), identity("hotel lobby ai", "US"))
        self.assertEqual(review_status({"stage": "ready-to-test"})[0], "needs-evidence")
        self.assertEqual(review_status({
            "stage": "ready-to-test",
            "checked_at": "2026-10-25",
            "user_evidence_url": "https://example.com/comment",
            "serp_evidence_url": "https://example.com/serp",
            "feasible_zero_fixed_cost": True,
        })[0], "ready-to-test")

    def test_first_seen_review_retention_and_followup(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "state").mkdir()
            (root / "config").mkdir()
            (root / "state/pending.json").write_text(json.dumps({
                "hotel lobby ai video": {
                    "query": "Hotel Lobby AI Video",
                    "first_seen": "2026-10-15",
                    "last_seen": "2026-10-25",
                    "source": "seed-rising:video"
                }}), encoding="utf-8")
            first = update_ledger(root, datetime(2026, 10, 25, 4, tzinfo=timezone.utc))
            self.assertEqual(first["new_candidates"], 1)
            self.assertEqual(first["review_due_count"], 1)
            cid = identity("hotel lobby ai video", "")
            state = json.loads((root / "state/opportunities.json").read_text())
            self.assertEqual(state["candidates"][cid]["first_seen"], "2026-10-15")
            (root / "config/opportunity_reviews.json").write_text(json.dumps({
                "hotel lobby ai video": {
                    "query": "Hotel Lobby AI Video",
                    "stage": "rejected",
                    "checked_at": "2026-10-25",
                    "notes": "Unviable ongoing model costs."
                }}), encoding="utf-8")
            second = update_ledger(root, datetime(2026, 10, 26, 4, tzinfo=timezone.utc))
            self.assertEqual(second["new_candidates"], 0)
            state = json.loads((root / "state/opportunities.json").read_text())
            self.assertEqual(state["candidates"][cid]["stage"], "rejected")
            self.assertEqual(second["review_due_count"], 0)

if __name__ == "__main__":
    unittest.main()
