import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import lead_quality as quality
import evidence_queue as queue


def make_item(url, source, title, author=None, score=75):
    return {
        "title": title, "url": url, "platform": source,
        "metadata": {"author": author} if author else {},
        "published_at": "2026-10-08T00:00:00Z",
        "quality": {"score": score},
    }


def result(review=None, references=None, market="BR", topic="payroll"):
    return {
        "query": "folha pagamento erro",
        "research_scope": {"market": market, "locale": "pt",
                           "topic": topic, "intent": "payroll_error",
                           "kind": "specific_buyer_problem"},
        "quality_screen": {"review_leads": review or [],
                           "competitor_references": references or [],
                           "discarded": []},
        "sources": {"github_issues": {"status": "ok"},
                    "reddit": {"status": "degraded"}},
    }


class EvidenceQueueTests(unittest.TestCase):
    def test_empty_market_stays_research_only(self):
        q = queue.build_queue({"date": "2026-10-08", "queries": [result()]})
        item = q["topics"][0]
        self.assertEqual(item["stage"], "needs_firsthand_problem_evidence")
        self.assertEqual(item["unreliable_sources"], ["reddit"])
        self.assertIsNone(item["keyword_candidate"])
        self.assertIsNone(item["metrics"]["volume"])
        self.assertIsNone(item["metrics"]["kd"])
        self.assertIsNone(item["metrics"]["cpc_usd"])
        self.assertFalse(item["may_be_recommended_for_build"])
        self.assertEqual(q["build_ready_count"], 0)

    def test_one_user_post_needs_independent_corroboration(self):
        r = result(review=[make_item("https://github.com/abc/xyz/issues/1",
                                     "github_issues", "Need payroll fix", "rachel")])
        q = queue.build_queue({"date": "2026-10-08", "queries": [r]})
        item = q["topics"][0]
        self.assertEqual(item["stage"], "needs_independent_corroboration")
        self.assertEqual(item["attributable_independent_authors"], 1)
        self.assertFalse(item["may_be_recommended_for_build"])

    def test_distinct_authors_still_not_build_ready(self):
        r = result(review=[
            make_item("https://github.com/abc/xyz/issues/1", "github_issues", "Issue A", "one"),
            make_item("https://news.ycombinator.com/item?id=123", "hackernews_ask", "Issue B", "two")
        ])
        q = queue.build_queue({"date": "2026-10-08", "queries": [r]})
        self.assertEqual(q["topics"][0]["stage"], "needs_search_and_payment_validation")
        self.assertEqual(q["build_ready_count"], 0)

    def test_same_person_and_repeated_link_not_independent(self):
        row = make_item("https://news.ycombinator.com/item?id=111", "hackernews_ask", "Issue", "one")
        row2 = dict(row, url="https://news.ycombinator.com/item?id=112")
        r = result(review=[row, row, row2])
        q = queue.build_queue({"date": "2026-10-08", "queries": [r]})
        self.assertEqual(q["topics"][0]["firsthand_evidence_count"], 2)
        self.assertEqual(q["topics"][0]["attributable_independent_authors"], 1)

    def test_context_links_are_not_firsthand(self):
        r = result(references=[make_item("https://example.org/intro", "bing_rss", "Guide")])
        q = queue.build_queue({"date": "2026-10-08", "queries": [r]})
        self.assertEqual(q["topics"][0]["firsthand_evidence_count"], 0)
        self.assertEqual(q["topics"][0]["contextual_reference_count"], 1)
        self.assertIn("not demand validation", queue.render_queue(q))

    def test_trend_query_is_unverified_keyword_candidate(self):
        r = result()
        r["research_scope"]["kind"] = "trend_lead_not_verified"
        q = queue.build_queue({"date": "2026-10-08", "queries": [r]})
        self.assertEqual(q["topics"][0]["keyword_candidate"], r["query"])
        self.assertFalse(q["topics"][0]["keyword_is_validated"])

    def test_missing_screen_rejected(self):
        with self.assertRaises(ValueError):
            queue.build_queue({"queries": [{"query": "x"}]})

    def test_offtopic_bing_sports_discarded(self):
        item = {"platform": "bing_rss", "title": "Basketball tournament schedule ESPN",
                "url": "https://example.com/basketball"}
        result = quality.screen_result({"query": "brotx optimizer v4", "items": [item]})
        self.assertEqual(result["quality_screen"]["reference_count"], 0)
        self.assertEqual(result["quality_screen"]["discarded_count"], 1)
        self.assertIn("off_topic_contextual_reference", result["quality_screen"]["discarded"][0]["reasons"])

if __name__ == "__main__":
    unittest.main()
