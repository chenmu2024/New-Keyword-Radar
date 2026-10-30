import io
import json
import unittest
from urllib.error import URLError
from http.client import IncompleteRead
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

    def test_removed_url_return_is_reappearance_not_new_keyword(self):
        root = "https://example.com/sitemap.xml"
        first = "https://example.com/tools/domain-checker"
        second = "https://example.com/tools/seo-generator"
        stages = [urlset(first, second), urlset(first), urlset(first, second)]
        index = [0]
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            return stages[index[0]]
        config = {"sources": [{"id": "test", "sitemap": root, "geo": "US"}]}
        state, _, _ = m.scan(config, {}, fetch, today="2026-10-19")
        index[0] = 1
        state, leads, status = m.scan(config, state, fetch, today="2026-10-20")
        self.assertEqual(status[0]["removed_url_count"], 1)
        self.assertEqual(leads, [])
        index[0] = 2
        state, leads, status = m.scan(config, state, fetch, today="2026-10-21")
        self.assertEqual(status[0]["new_url_count"], 0)
        self.assertEqual(status[0]["reappeared_url_count"], 1)
        self.assertEqual(leads, [])

    def test_error_does_not_erase_baseline(self):
        cfg = {"sources": [{"id": "test", "sitemap": "https://example.com/sitemap.xml"}]}
        old = {"test": {"hashes": ["abcdef"], "checked_at": "2026-10-19"}}
        def fail(url, allowed, max_bytes=m.MAX_BYTES):
            raise URLError("blocked")
        state, leads, status = m.scan(cfg, old, fail)
        self.assertEqual(state, old)
        self.assertEqual(leads, [])
        self.assertEqual(status[0]["status"], "error")

    def test_incomplete_http_chunk_must_not_abort_other_sources(self):
        cfg = {"source_scan_workers": 2, "sources": [
            {"id": "broken", "sitemap": "https://broken.example/sitemap.xml"},
            {"id": "healthy", "sitemap": "https://healthy.example/sitemap.xml"},
        ]}
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            if allowed == "broken.example":
                raise IncompleteRead(b"", 200)
            return urlset("https://healthy.example/game/valid-puzzle")
        state, leads, rows = m.scan(cfg, {}, fetch, today="2026-10-30")
        self.assertEqual(rows[0]["status"], "error")
        self.assertIn("IncompleteRead", rows[0]["error"])
        self.assertEqual(rows[1]["status"], "baseline")
        self.assertEqual(leads, [])
        self.assertIn("healthy", state)
        self.assertNotIn("broken", state)

    def test_incomplete_metadata_read_stays_a_per_page_annotation(self):
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            raise IncompleteRead(b"", 99)
        meta = m.page_meta("https://example.com/game/dragon-rush", fetch)
        self.assertEqual(meta["page_error"], "IncompleteRead")
        self.assertEqual(meta["title"], "")

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

    def test_production_watchlist_stays_bounded(self):
        # Guard the approved 18-source inventory and the 14-day pilot cutoff.
        cfg = json.loads((m.ROOT / "config/sitemap_sources.json").read_text(encoding="utf-8"))
        feeds = cfg["sources"]
        ids = {x["id"] for x in feeds}
        self.assertEqual(len(feeds), len(ids))
        # Source inventory may grow, but stays bounded and preserves required feeds.
        self.assertGreaterEqual(len(feeds), 18)
        self.assertLessEqual(len(feeds), 160)
        required = {
            "n8n-workflows", "railway-templates", "railway-changelog",
            "apify-actors-a", "apify-actors-z", "futurepedia-tools",
            "netlify-product-watch", "onlinetools-br", "producthunt-products",
            "vercel-product-watch",
        }
        self.assertTrue(required.issubset(ids))
        producthunt = next(x for x in feeds if x["id"] == "producthunt-products")
        self.assertEqual(producthunt["page_hosts"], ["www.producthunt.com"])
        self.assertEqual(producthunt["include_path_prefixes"], ["/products/"])
        self.assertTrue(all(x["sitemap"].startswith("https://") for x in feeds))
        self.assertEqual(cfg["trial_end_exclusive"], "2026-11-02")

    def test_large_delta_samples_all_urls_not_lexicographic_first_page(self):
        urls = [f"https://example.com/tools/alpha-{i:04d}" for i in range(100)]
        important = "https://example.com/tools/zebra-calculator"
        chosen, eligible = m.select_novel_leads(urls + [important], 8)
        self.assertEqual(eligible, 101)
        self.assertEqual(len(chosen), 8)
        self.assertIn((important, "zebra calculator"), chosen)

    def test_queue_keeps_more_than_old_250_limit(self):
        rows = [{"query": f"work item {i:04d}", "geo": "US",
                 "source_id": "apify-actors-a", "first_seen": "2026-10-19",
                 "url": f"https://example.com/{i}"} for i in range(270)]
        merged = m.merge_queue([], rows)
        self.assertEqual(len(merged), 270)
        self.assertEqual(len({x["query"] for x in merged}), 270)

    def test_queue_dedups_by_market_and_retains_source_diversity(self):
        rows = [
            {"query": "invoice checker", "geo": "BR", "source_id": "onlinetools-br", "first_seen": "2026-10-18", "url": "https://a.test/br"},
            {"query": "invoice checker", "geo": "US", "source_id": "apify-actors-a", "first_seen": "2026-10-19", "url": "https://b.test/us"},
        ]
        rows += [{"query": f"random actor {i}", "geo": "US", "source_id": "apify-actors-a",
                  "first_seen": "2026-10-19", "url": f"https://c.test/{i}"} for i in range(100)]
        self.assertEqual(len(m.merge_queue([], rows)), 102)
        limited = m.merge_queue([], rows, limit=10)
        self.assertEqual(len(limited), 10)
        self.assertEqual({x["source_id"] for x in limited}, {"onlinetools-br", "apify-actors-a"})
        self.assertEqual(len(m.merge_queue(rows[:1], [rows[1]])), 2)

    def test_cross_site_source_provenance_survives_queue_merge(self):
        two = [
            {"query": "dragon rush", "geo": "US", "source_id": "game-a",
             "url": "https://a.example/game/dragon-rush", "first_seen": "2026-10-28"},
            {"query": "dragon rush", "geo": "US", "source_id": "game-b",
             "url": "https://b.example/game/dragon-rush", "first_seen": "2026-10-30"},
        ]
        merged = m.merge_queue([], two)
        self.assertEqual(len(merged), 1)
        self.assertEqual({x["source_id"] for x in merged[0]["source_records"]},
                         {"game-a", "game-b"})
        again = m.merge_queue(merged, [two[1]])
        self.assertEqual(len(again[0]["source_records"]), 2)

    def test_concurrent_collection_preserves_source_order_and_baselines(self):
        cfg = {"source_scan_workers": 3, "sources": [
            {"id": "a", "sitemap": "https://a.example/sitemap.xml", "geo": "US"},
            {"id": "b", "sitemap": "https://b.example/sitemap.xml", "geo": "US"},
        ]}
        def fake_fetch(url, allowed, max_bytes=m.MAX_BYTES):
            return urlset("https://" + allowed + "/game/dragon-rush")
        state, leads, status = m.scan(cfg, {}, fake_fetch, today="2026-10-30")
        self.assertEqual([r["source_id"] for r in status], ["a", "b"])
        self.assertTrue(all(r["status"] == "baseline" for r in status))
        self.assertEqual(leads, [])
        self.assertEqual(len(state), 2)


    def test_scoped_dynamic_index_only_collects_games(self):
        base = "https://example.com/"
        root = base + "sitemap-index.xml"
        child = base + "releases/20261030/sitemap-games-3.xml"
        other = base + "releases/20261030/sitemap-static.xml"
        mapping = {
            root: sitemapindex(other, child),
            other: urlset(base + "about-page"),
            child: urlset(base + "game/dragon-rush", base + "fr/jeu/dragon-rush"),
        }
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            return mapping[url]
        links, count = m.collect_sitemap(
            root, fetch, sitemap_path_regex=r"sitemap-games-3\.xml$",
            page_path_regex=r"^/game/[^/]+/?$")
        self.assertEqual(links, [base + "game/dragon-rush"])
        self.assertEqual(count, 2)

    def test_scoped_index_empty_match_rejected_without_baseline(self):
        root = "https://example.com/index.xml"
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            return sitemapindex("https://example.com/sitemap-static.xml")
        with self.assertRaisesRegex(ValueError, "no matching child feed"):
            m.collect_sitemap(root, fetch,
                              sitemap_path_regex=r"sitemap-games-3\.xml$")

    def test_gamepost_numeric_catalog_suffix_not_game_name(self):
        root = "https://www.gamepost.com/sitemap.xml"
        pages = [
            urlset("https://www.gamepost.com/game/old-puzzle-279262"),
            urlset("https://www.gamepost.com/game/old-puzzle-279262",
                   "https://www.gamepost.com/game/dragon-rush-279263"),
        ]
        index = [0]
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            return pages[index[0]]
        cfg = {"sources": [{"id": "gamepost-games", "sitemap": root,
                            "topic": "games", "geo": "US"}]}
        state, _, _ = m.scan(cfg, {}, fetch, today="2026-10-29")
        index[0] = 1
        _, leads, status = m.scan(cfg, state, fetch, today="2026-10-30")
        self.assertEqual(status[0]["new_url_count"], 1)
        self.assertEqual([r["query"] for r in leads], ["dragon rush"])


    def test_all_new_sitemap_url_signatures_survive_detail_sampling_cap(self):
        root_a = "https://a.example/sitemap.xml"
        root_b = "https://b.example/sitemap.xml"
        version = [0]
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            base = "https://" + allowed
            olds = [base + "/game/old-game"]
            news = [base + "/game/dragon-rush", base + "/game/another-puzzle",
                    base + "/game/unique-inventory"]
            return urlset(*(olds if version[0] == 0 else olds + news))
        cfg = {"max_new_urls_per_source": 1, "sources": [
            {"id": "a", "sitemap": root_a, "geo": "US", "topic": "games"},
            {"id": "b", "sitemap": root_b, "geo": "US", "topic": "games"},
        ]}
        baseline, _, status = m.scan(cfg, {}, fetch, today="2026-10-29")
        self.assertTrue(all(x["status"] == "baseline" for x in status))
        version[0] = 1
        sink = []
        _, chosen, status = m.scan(
            cfg, baseline, fetch, today="2026-10-30", candidate_sink=sink)
        self.assertEqual(len(chosen), 2)
        self.assertEqual(len(sink), 6)
        self.assertTrue(all(x["candidates_over_scan_cap"] == 2 for x in status))
        ledger = m.merge_delta_ledger([], sink, "2026-10-30")
        self.assertEqual(len(ledger), 6)
        self.assertEqual({x["source_id"] for x in ledger if x["query"] == "dragon rush"},
                         {"a", "b"})

    def test_ledger_expiration_and_round_robin(self):
        rows = [
            {"query": "convert pdf to excel", "geo": "US", "source_id": "a",
             "first_seen": "2026-10-29", "url": f"https://a.example/tools/convert-{i}"}
            for i in range(4)
        ]
        rows += [
            {"query": "convert pdf to excel", "geo": "US", "source_id": "b",
             "first_seen": "2026-10-30", "url": "https://b.example/tools/convert"}]
        rows += [
            {"query": "obsolete", "geo": "US", "source_id": "c",
             "first_seen": "2026-10-01", "url": "https://c.example/old"}]
        kept = m.merge_delta_ledger(rows, rows, "2026-10-30", limit=2)
        self.assertEqual(len(kept), 2)
        self.assertEqual({row["source_id"] for row in kept}, {"a", "b"})
        self.assertEqual(len(m.merge_delta_ledger(rows, [], "2026-11-08")), 0)

    def test_reappearing_urls_never_enter_new_signature_ledger(self):
        root = "https://example.com/sitemap.xml"
        pages = [urlset("https://example.com/game/old-puzzle"),
                 urlset(),
                 urlset("https://example.com/game/old-puzzle")]
        cfg = {"sources": [{"id": "site", "sitemap": root, "topic": "games"}]}
        phase = [0]
        def fetch(url, allowed, max_bytes=m.MAX_BYTES):
            return pages[phase[0]]
        baseline, _, _ = m.scan(cfg, {}, fetch, today="2026-10-28")
        phase[0] = 1
        state, _, _ = m.scan(cfg, baseline, fetch, today="2026-10-29")
        phase[0] = 2
        sink = []
        _, found, status = m.scan(cfg, state, fetch, today="2026-10-30", candidate_sink=sink)
        self.assertEqual(status[0]["reappeared_url_count"], 1)
        self.assertEqual(found, [])
        self.assertEqual(sink, [])

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
