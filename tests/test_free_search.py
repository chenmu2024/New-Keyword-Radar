import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import free_search as f


class FreeSearchTests(unittest.TestCase):
    def test_canonical_removes_tracking(self):
        self.assertEqual(f.canonical_url("https://Example.com/post/?utm_source=x&a=1#part"),
                         "https://example.com/post?a=1")

    def test_ddg_anchor_exact_and_redirect(self):
        parser = f.DDGParser()
        parser.feed('<div class="results_links"><a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fone">One</a>'
                    '<a class="result__a" href="https://example.org/two">Two</a></div>')
        self.assertEqual(len(parser.items), 2)
        self.assertEqual(parser.items[0]["url"], "https://example.com/one")

    def test_dedupe_by_canonical_url(self):
        r = [f.row("a", "One", "https://example.com/p?utm_campaign=x"),
             f.row("b", "Other title", "https://example.com/p")]
        self.assertEqual(len(f.dedupe(r)), 1)

    @patch.object(f, "cached_request")
    def test_rss_parsing(self, mock):
        mock.return_value = ('<rss><channel><item><title>Hello</title><link>https://a.example/test</link>'
                             '<description>Some text</description></item></channel></rss>', False)
        got = f.rss_items("https://example.com/feed.xml")
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["title"], "Hello")

    @patch.object(f, "github")
    def test_failures_are_explicit(self, mock):
        mock.side_effect = ValueError("not available")
        result = f.collect("test", ["github_repos"], limit=1)
        self.assertEqual(result["sources"]["github_repos"]["status"], "error")
        self.assertEqual(result["total"], 0)
        self.assertIsNone(result["keyword_metrics"]["volume"])

    def test_local_extractor(self):
        p = f.TextParser()
        p.feed("<html><title>Hello</title><nav>No</nav><article><p>Yes</p></article></html>")
        self.assertIn("Yes", "".join(p.parts))
        self.assertNotIn("No", "".join(p.parts))


if __name__ == "__main__":
    unittest.main()
