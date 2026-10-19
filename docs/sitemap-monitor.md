# Competitor Sitemap delta monitor — 14-day pilot

Pilot: **2026-10-19 through 2026-11-01** (Beijing time), stops scanning 2026-11-02.
Two GitHub Actions sweeps/day: **10:35 and 22:35** Beijing time (UTC cron 02:35/14:35).
The normal keyword radar's 08:00 briefing and all existing seed/Trends settings are unchanged.

## Evidence / limitations

Eight starter source entries are *provisional candidates*. CrazyGames EN/BR/ES
use the verified locale-specific XML URLs from its live 25-sitemap index; GamePix EN/PT,
MiniJuegos, Friv, and CalculatorSoup use public Sitemap URLs observed in robots.txt.
The broad XML files for Omni Calculator, Smallpdf and Remove.bg exceeded the safe
response-size limit during the first live run and have been excluded from scheduled
retries rather than treated as "zero demand." Inclusion does **not** demonstrate
their pages have SEO traffic or represent verified keywords. Keep only sources producing
useful independently validated leads after the trial.

- First successful source scan stores a URL hash baseline and reports **zero new URLs**.
- Subsequent scans calculate set additions, independently of often-misleading lastmod.
- Errors, truncated XML, too many pages/sitemaps and blocked requests preserve old snapshot.
- Cross-domain URLs/redirects, non-HTTPS, very large downloads and image/video feeds are blocked. CrazyGames locale XML uses a bounded 25 MB per-source cap because the default 7 MB cap was exceeded in the first pilot run; other sources retain 7 MB.
- Newly seen slugs provide leads; a small bounded HTML title/H1 lookup is optional. A URL is
  NOT a new keyword, not search Volume, and not revenue evidence.
- Output is isolated under state/sitemap/, data/sitemap/, reports/sitemap/.
- Fresh leads can be picked up in src/radar.py via data/sitemap/queue.json; they still have
  to pass the **original 90-day, 5-year and money gates**, not a separate shortcut.
- No external paid API, browser extension, account signup or new monthly hosting bill.

## How to assess after 14 days

Record (1) successful scans / total, (2) first-time URLs vs baseline,
(3) distinct relevant queries, (4) verified newly emerging keywords,
(5) exact market search intent and SERP competition, (6) actually implementable
ad/tool/SaaS opportunities. **Do not** rate performance by raw URL count alone.

When a source is blocked or exceeds cap, do not treat that as zero keyword demand.
Improve targeting by selecting its content-specific sitemap in config/sitemap_sources.json.

Manual offline tests:
    python -m unittest discover -s tests -p test_sitemap_monitor.py -v

Manual research run (while pilot dates are valid):
    python src/sitemap_monitor.py --no-enrich

This workflow is independent of the main radar and has no capability to send notifications.

## Vercel product intelligence scope (added 2026-10-19)

- Source: `https://vercel.com/sitemap.xml` (published in robots.txt), approximately 7,069 URLs when investigated.
- Included URL prefixes: `/marketplace/`, `/templates/`, `/changelog/`, `/blog/`.
- Excluded: `/docs/`, `/academy/`, `/kb/`, APIs and account pages, reducing update noise.
- URL changes are clues about new third-party tools, developer products and SaaS offerings, not proof of a genuinely new query, actual customer revenue or achievable SEO ranking.
- First successful poll only creates a baseline; subsequent new URLs go through the unchanged validation pipeline and are tagged with source `vercel-product-watch`.
- This source shares the existing 14-day pilot end date; it is not a permanent monitor until reviewed.

## Additional sources (2026-10-19)

The following URLs were inspected before inclusion. Public sitemap *appearance* does not confirm SEO, recent launches, payment, or viable demand.

| Source ID | Public sitemap URL | Page selection |
|---|---|---|
| `n8n-workflows` | `https://n8n.io/sitemap-workflows.xml` | /workflows/ |
| `railway-templates` | `https://railway.com/templates-sitemap.xml` | /deploy/ |
| `railway-changelog` | `https://railway.com/changelog-sitemap.xml` | /changelog/ |
| `apify-actors-a` | `https://apify.com/sitemap/actors1.xml` | ^/[^/]+/[^/]+/?$ |
| `apify-actors-z` | `https://apify.com/sitemap/actors14.xml` | ^/[^/]+/[^/]+/?$ |
| `futurepedia-tools` | `https://www.futurepedia.io/sitemap_tools.xml` | /tool/ |
| `netlify-product-watch` | `https://www.netlify.com/sitemap-0.xml` | /integrations/, /changelog/ |
| `onlinetools-br` | `https://onlinetools.com.br/sitemap.xml` | /pt/ |
| `producthunt-products` | `https://d29lzieai721mu.cloudfront.net/sitemaps_v3/product_about_sitemap.xml.gz` | /products/ |

**Product Hunt:** The robots.txt-declared `www.producthunt.com/sitemaps_v3/product_about_sitemap.xml.gz` redirects to the exact public CloudFront distribution `d29lzieai721mu.cloudfront.net`; anonymous requests to the origin may be blocked. Only `www.producthunt.com/products/` loc URLs from that exact CDN XML are accepted; page enrichment is disabled, and arbitrary redirects are NOT permitted.

**Apify:** The full index currently contains 14 enormous Actor sitemap shards with API, examples and issue subpages. For bounded first-pass evidence, only shard 1 and 14 are scanned; direct two-segment Actor URLs are retained, and this must be labelled **partial alphabetical sample**, never full Apify coverage. Scale only after the 14-day trial demonstrates utility.

**Safety/performance:** Incoming XML is capped by per-source compressed+decompressed byte limits. The gzip payload is expanded incrementally up to that byte cap. XML from a CDN may list product pages at a single explicitly allowlisted hostname. The main Trends pipeline, seed lists, KPI gates and 08:00 briefing remain unchanged.
