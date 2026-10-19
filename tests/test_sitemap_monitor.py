import io
import unittest
from urllib.error import URLError
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import sitemap_monitor as m


def urlset(*urls):
    return ('<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + ''.join("<url><loc>" + x + "</loc></url>" for x in urls) + "</urlset>").encode()


def sitemapindex(*urls):
    return ('<sitemapindex>' + ''.join("<sitemap><loc>" + x +
                                       "</loc></sitemap>" for x in urls) +
            '</sitemapindex>').encode()


class SitemapTests(unittest.TestCase):
    def test_baseline_then_delta_and_no_old_url_alert(self):
        root = "https://example.com/sitemap.xml"
        url1 = "https://example.com/game/dragon-codes"
        url2 = "https://example.com/game/new-puzzle-calculator"
        payload = [urlset(url1), urlset(url1, url2)]
        calls = [0]
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            if url == root:
                return payload[calls[0]]
            return b"<html><title>New Puzzle</title><h1>Calculator</h1></html>"
        cfg = {"sources": [{"id": "test", "sitemap": root, "geo": "US"}],
               "max_new_urls_per_source": 80}
        first, leads, s1 = m.scan(cfg, {}, fetch, today="2026-10-19")
        self.assertEqual(s1[0]["status"], "baseline")
        self.assertEqual(leads, [])
        calls[0] = 1
        second, leads, s2 = m.scan(cfg, first, fetch, enrich=True, today="2026-10-20")
        self.assertEqual(s2[0]["new_url_count"], 1)
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["query"], "new puzzle calculator")
        self.assertEqual(leads[0]["title"], "New Puzzle")
        self.assertEqual(len(second["test"]["hashes"]), 2)

    def test_error_does_not_erase_baseline(self):
        cfg = {"sources": [{"id": "test", "sitemap": "https://example.com/sitemap.xml"}]}
        old = {"test": {"hashes": ["abcdef"], "checked_at": "2026-10-19"}}
        def fail(url, allowed, max_bytes=m.MAX_BYTES):
            raise URLError("blocked")
        state, leads, status = m.scan(cfg, old, fail)
        self.assertEqual(state, old)
        self.assertEqual(leads, [])
        self.assertEqual(status[0]["status"], "error")

    def test_nested_sitemap_and_host_filter(self):
        base = "https://example.com/"
        index = base + "sitemap.xml"
        child = base + "game-sitemap.xml"
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            if url == index:
                return sitemapindex(child, "https://attacker.test/sitemap.xml")
            if url == child:
                return urlset(base + "game/special-codes", base + "tags/test")
            raise ValueError("unexpected request")
        links, count = m.collect_sitemap(index, fetch)
        self.assertEqual(links, [base + "game/special-codes"])
        self.assertEqual(count, 2)

    def test_marketplace_template_changelog_blog_scoped_only(self):
        root = "https://vercel.com/sitemap.xml"
        urls = [
            "https://vercel.com/marketplace/new-ai-tool",
            "https://vercel.com/changelog/new-thing",
            "https://vercel.com/templates/ai/assistant-demo",
            "https://vercel.com/blog/build-something",
            "https://vercel.com/docs/ai",
            "https://vercel.com/academy/deploy-nextjs",
            "https://vercel.com/kb/guide/something",
        ]
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            return urlset(*urls)
        chosen, count = m.collect_sitemap(
            root, fetch, include_prefixes=["/marketplace/", "/changelog/",
                                           "/templates/", "/blog/"])
        self.assertEqual(count, 1)
        self.assertEqual(len(chosen), 4)
        self.assertFalse(any("/docs/" in x or "/academy/" in x for x in chosen))

    def test_explicit_cdn_page_hosts_only(self):
        root = "https://d29lzieai721mu.cloudfront.net/sitemaps_v3/product_about_sitemap.xml.gz"
        items = [
            "https://www.producthunt.com/products/clean-invoice-tool",
            "https://www.producthunt.com/posts/marketing-news",
            "https://evil.invalid/products/bad",
        ]
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            self.assertEqual(allowed, "d29lzieai721mu.cloudfront.net")
            return urlset(*items)
        links, files = m.collect_sitemap(root, fetch,
                    include_prefixes=["/products/"],
                    page_hosts=["www.producthunt.com"])
        self.assertEqual(links, [items[0]])
        self.assertEqual(files, 1)

    def test_actor_page_dedup_and_scoping(self):
        root = "https://apify.com/sitemap/actors14.xml"
        urls = [
            "https://apify.com/vendor/review-scraper",
            "https://apify.com/vendor/review-scraper/api",
            "https://apify.com/vendor/review-scraper/examples/use-case",
            "https://apify.com/vendor/other-scraper",
        ]
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            return urlset(*urls)
        links, files = m.collect_sitemap(root, fetch,
                      page_path_regex=r"^/[^/]+/[^/]+/?$")
        self.assertEqual(links, sorted([urls[0], urls[3]]))
        self.assertEqual(files, 1)

    def test_bounded_path_prefixes(self):
        root = "https://railway.com/templates-sitemap.xml"
        urls = ["https://railway.com/deploy/ai-tool",
                "https://railway.com/deploy/category/ai",
                "https://railway.com/changelog/fix"]
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            return urlset(*urls)
        links, files = m.collect_sitemap(root, fetch, include_prefixes=["/deploy/"],
                    exclude_prefixes=["/deploy/category/"])
        self.assertEqual(links, [urls[0]])
        self.assertEqual(files, 1)

    def test_numeric_workflow_id_removed(self):
        self.assertEqual(m.candidate("https://n8n.io/workflows/19182-convert-images-to-pdf/"),
                         "convert images to pdf")

    def test_aborts_incomplete_index(self):
        root = "https://example.com/sitemap.xml"
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            return sitemapindex("https://example.com/one.xml", "https://example.com/two.xml")
        with self.assertRaises(ValueError):
            m.collect_sitemap(root, fetch, max_sitemaps=2)

    def test_slug_filter_and_prohibited_urls(self):
        self.assertEqual(m.candidate("https://site.test/category/games"), "")
        self.assertEqual(m.candidate("https://site.test/pt/simulador-de-frete"),
                         "simulador de frete")
        with self.assertRaises(ValueError):
            m.host("http://example.com/sitemap.xml")
        with self.assertRaises(ValueError):
            m.host("https://example.com:444/sitemap.xml")


if __name__ == "__main__":
    unittest.main()
