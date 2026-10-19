# Competitor Sitemap delta monitor — 14-day pilot

Pilot: **2026-10-19 through 2026-11-01** (Beijing time), stops scanning 2026-11-02.
Two GitHub Actions sweeps/day: **10:35 and 22:35** Beijing time (UTC cron 02:35/14:35).
The normal keyword radar's 08:00 briefing and all existing seed/Trends settings are unchanged.

## Evidence / limitations

All nine starter source entries are *provisional candidates*, chosen because their Sitemap URL
was explicitly observed in their public robots.txt (CrazyGames, GamePix EN/PT, MiniJuegos,
Friv, Omni Calculator, CalculatorSoup, Smallpdf, Remove.bg). This does **not** demonstrate
their pages have SEO traffic or represent verified keywords. Keep only sources producing
useful independently validated leads after the trial.

- First successful source scan stores a URL hash baseline and reports **zero new URLs**.
- Subsequent scans calculate set additions, independently of often-misleading lastmod.
- Errors, truncated XML, too many pages/sitemaps and blocked requests preserve old snapshot.
- Cross-domain URLs/redirects, non-HTTPS, very large downloads and image/video feeds are blocked.
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
