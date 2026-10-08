# Free Search Intelligence

**Zero paid API; no copied code from union-search-skill (upstream has no LICENSE file).**

This is a separate read-only evidence collection layer. The existing Google
Trends 90-day / 5-year gates, original keywords, 20-seed daily scanning and
07:05 radar remain unchanged.

## Supported source adapters

- Public GitHub repository search and Issues search (optional built-in GITHUB_TOKEN)
- Google News RSS, any public HTTPS RSS/Atom feed
- DuckDuckGo HTML public results; individual anchors parsed, not whole result containers
- Public Reddit RSS; if blocked, fallback to indexed discovery, **not** reported as Reddit API success
- Wikimedia Commons image discovery including provenance/license fields (manual review needed)
- Local HTML -> Markdown approximation, no cloud content extraction charges
- Standardized JSON with URL de-duplication, disk caching, per-source errors

CLI examples:

```bash
python src/free_search.py "AI agent" --platforms github_repos github_issues google_news_rss duckduckgo reddit --limit 5
python src/free_search.py "fashion palette" --platforms images --limit 5
python src/free_search.py --url-to-markdown https://example.com
python src/free_search.py --rss-url https://example.com/feed.xml
python -m unittest discover -s tests -p test_free_search.py
```

Daily standalone action: **06:40 China time**; outputs
`data/free-intelligence/latest.json` and
`reports/free-intelligence/latest.md` (plus dated archives).

### Operational guardrails

- Never invent Volume/KD/CPC. These always remain null until external verification.
- Neither an RSS hit nor a trend is a verified new keyword.
- A platform HTTP 403/429 remains visible as an error or degraded condition.
- No TikHub, SerpAPI, paid proxies, authentication cookies or TinyFish.
- Use modest request counts (four queries by default); avoid CAPTCHA circumvention.
- Image discovery is not a publication license: examine license/source per image.
- Public sources may throttle/deny unattended GitHub Actions IPs.
- GitHub Action schedule timing is approximate; cache files are deliberately not committed.
