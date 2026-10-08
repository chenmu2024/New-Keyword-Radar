import json
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import free_search as s
import lead_quality as q


class FirstPersonDemandTests(unittest.TestCase):
    @patch.object(s, "cached_request")
    def test_keyless_hn_ask_with_source_and_no_invented_metrics(self, mocked):
        hit = {"hits": [{"objectID": "12345", "title": "Ask HN: Need help with invoice reconciliation",
                         "story_text": "<p>We need a tool to avoid expensive manual reconciliation.</p>",
                         "created_at": "2026-10-07T10:00:00.000Z", "points": 4,
                         "num_comments": 9, "author": "founder"}]}
        mocked.return_value = (json.dumps(hit), False)
        items = s.hackernews_ask("invoice reconciliation", limit=3)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["url"], "https://news.ycombinator.com/item?id=12345")
        self.assertEqual(items[0]["metadata"]["buyer_intent_verified"], False)
        self.assertIsNone(items[0]["volume"])
        self.assertEqual(q.score(items[0], "invoice reconciliation manual")["screening"], "review")

    def test_internal_implementation_tasks_not_user_demands(self):
        samples = [
            ("Build complete source-to-Legacy feature and route acceptance matrix",
             "Inventory sync feature request on an internal workflows platform"),
            ("Revisar e fortalecer Rendimentos do trabalho ponta a ponta",
             "Conciliação bancária manual e integração de folha de pagamento")
        ]
        for title, snippet in samples:
            with self.subTest(title=title):
                item = {"title": title, "snippet": snippet,
                        "platform": "github_issues", "url": "https://github.com/example/a/issues/13",
                        "published_at": "2026-10-07T10:00:00Z"}
                verdict = q.score(item, "conciliação bancária manual",
                                  reference=datetime(2026, 10, 8, tzinfo=timezone.utc))
                self.assertNotEqual(verdict["screening"], "review")
                self.assertIn("engineering_task_without_explicit_user_report", verdict["reasons"])

    def test_actual_customer_report_survives_task_title(self):
        item = {"title": "Fix invoice errors for customers",
                "snippet": "Users report an invoice upload error and need an automated fix.",
                "platform": "github_issues", "url": "https://github.com/example/issues/99",
                "published_at": "2026-10-07T10:00:00Z"}
        verdict = q.score(item, "invoice error",
                          reference=datetime(2026, 10, 8, tzinfo=timezone.utc))
        self.assertEqual(verdict["screening"], "review")

    @patch.object(s, "cached_request")
    def test_hn_invalid_ids_ignored(self, mocked):
        mocked.return_value = (json.dumps({"hits": [{"objectID": "not_numeric",
                             "title": "Ask HN: a request"}]}), False)
        self.assertEqual(s.hackernews_ask("request"), [])


if __name__ == "__main__":
    unittest.main()
