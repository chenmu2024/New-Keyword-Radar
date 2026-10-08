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

    def test_internal_inventory_capabilities_not_customer_pain(self):
        row = {
            "platform": "github_issues",
            "title": "inventory(capabilities): classify Studio-owned authoring operations",
            "snippet": "Inventory sync spreadsheet workflow, integration errors, and API improvements.",
            "published_at": "2026-10-07T06:30:00Z",
            "url": "https://github.com/ankhorage/studio/issues/788",
        }
        verdict = q.score(row, "inventory sync spreadsheet")
        self.assertEqual(verdict["screening"], "discard")
        self.assertIn("github_issue_without_explicit_customer_voice", verdict["reasons"])

    def test_old_2016_hn_post_not_current_demand(self):
        item = {"platform": "hackernews_ask",
                "title": "Ask HN: Small business bank account – who do you use?",
                "snippet": "We need an account for payroll integration with accounting tools.",
                "published_at": "2016-04-06T14:31:06Z",
                "url": "https://news.ycombinator.com/item?id=11438973"}
        verdict = q.score(item, "payroll integration error")
        self.assertEqual(verdict["screening"], "discard")
        self.assertIn("firsthand_date_missing_or_older_than_180_days", verdict["reasons"])

    def test_internal_finance_task_without_customer_report_not_demand(self):
        item = {"platform": "github_issues",
                "title": "D1-C — integrated deterministic closeout, truth table, UAT",
                "snippet": "Integrate payroll reconciliation and error workflow for finance team.",
                "published_at": "2026-10-05T00:21:32Z",
                "url": "https://github.com/bensmullen/personal-finance-app/issues/80"}
        verdict = q.score(item, "payroll integration error")
        self.assertEqual(verdict["screening"], "discard")
        self.assertIn("no_topical_title_or_customer_attribution", verdict["reasons"])

    @patch.object(s, "cached_request")
    def test_hn_invalid_ids_ignored(self, mocked):
        mocked.return_value = (json.dumps({"hits": [{"objectID": "not_numeric",
                             "title": "Ask HN: a request"}]}), False)
        self.assertEqual(s.hackernews_ask("request"), [])


if __name__ == "__main__":
    unittest.main()
