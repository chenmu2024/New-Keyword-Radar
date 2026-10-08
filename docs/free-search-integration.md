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

## Opportunity-lead quality screening

The daily report now distinguishes **raw search links** from **review leads**.
`src/lead_quality.py` scores source credibility, topical relevance, explicit
user pain, commercial/tool context, freshness (only when dated), and automated
noise. It keeps explanatory reasons and discarded links in JSON for auditing.

A score only routes a link to human verification: it **never** means 10,000
monthly visits, nonzero search volume, KD below a threshold, confirmed
search-term newness, or willingness to pay. All SEO metrics remain null until
independently sourced. We keep the existing exact-query 90-day + 5-year Trends
validation untouched, including user-selected keywords and geographic groups.

PT-BR, ES-MX, and English discovery each keep their own fixed search slot;
another slot follows commercial-intent rising query candidates.

## Pain-oriented queries by market

The independent free-search layer now rotates **two precise problem queries per
market daily**, from 4 configured options each: US (English), Brazil
(Portuguese), Mexico (Spanish). It preserves one slot for a commercial-intent
rising query observed in the existing 7-day seed report. The user-selected
Google Trends seed files and site SEO keywords do not change.

Set source-specific, shorter issue queries in
`config/free_intelligence.json` (`pain_query_groups.*[].issue_query`);
the full user-pain phrase is retained for web/news and scoring. Each record
shows its actual query per platform, country, sector and intended problem.

Default total: **7 queries/day, 4 hits/platform/query**. No paid provider is
introduced, and no computer needs to remain on. This is an initial lead
generation screen: GitHub Issues or original Reddit posts can yield firsthand
requests; news articles, search snippets, and GitHub repos are **contextual
references**, not paid-demand evidence. If Reddit is rate-limited, the
fallback is labeled and not counted as firsthand demand.

Cross-query duplicate URLs are reported. Verification of user need, willingness
to pay, exact-query 90-day/5-year newness, and independently sourced
Volume/KD/CPC is still required before an opportunity is recommended.

## Evidence-to-validation queue (new)

Every standalone daily free discovery run now additionally writes:
- `data/free-intelligence/validation-queue-latest.json`
- `reports/free-intelligence/validation-queue-latest.md`
- Dated JSON and Markdown versions next to each day's discovery report.

Each market/topic is a **research task**, not a vetted business opportunity.
Cards have firsthand user complaint citations, weaker market/competitor
references, relevant source failures, and an explicit five-step verification
checklist. The initial fields for exact localized SEO keyword,
monthly search Volume, KD, CPC, data provider/date, 10k–100k/month
competitor evidence and paying-user evidence remain missing until independently
verified. Existing Google Trends rising phrases appear as an **unverified
keyword candidate**, not an automatically approved target keyword.

Two attributable source-author pairs can move a topic to
`needs_search_and_payment_validation`, but never directly to a build-approved
state. Cross-query duplicate links, unknown authors and off-topic SERP news
cannot count as independent user demand. This avoids treating a high
heuristic score, repeated press hits, or a competitor repository as evidence
of paying customers.

The queue deliberately shows **0 ready-to-build** unless a separate,
provenanced and independently verified process establishes the user's
minimum nonzero search demand, acceptable competition, and commercial route.
This does not change original keyword lists, daily Trends pipelines,
report cadences or code for user websites.

## Cross-day observations and exact keyword research (14 days)

Daily `validation-queue-latest.json` now compares up to 14 **previous dated
validation-queue JSON archives** already stored in
`data/free-intelligence/`. It reports:

- Earlier archived days containing the same **market + research intent**
  (topic coverage only, **not** proof the demand is growing).
- Days when the **same discovery query** appeared and counts of new versus
  repeated saved URLs, split into firsthand evidence and background/context.
- A data sufficiency signal. Until at least three distinct prior archived
  days exist, the history is labelled `insufficient_history`.
- Entries with missing or mismatched dates, corrupted JSON, or timestamps
  outside the 14-day lookback are skipped. Today's rerun is **not** counted as
  a separate historical observation.

Keyword verification templates are declared in
`config/validation_targets.json` for twelve English / Brazilian Portuguese /
Mexican Spanish pain-research categories. Each has up to three **suggested
exact search terms to research**, language, target country, and a clearly
unverified monetization hypothesis. None of these terms are replacements for
website keywords and none are claims of real monthly Volume, KD or CPC.

Read the actionable list at
`reports/free-intelligence/validation-queue-latest.md` after the independent
06:40 Asia/Shanghai GitHub Actions research job. Daily archives are retained
in `reports/free-intelligence/YYYY-MM-DD-validation-queue.md`.

**Boundaries:** same URL seen 5 times is one reference, not 5 users;
different terms from a rotating research set do not prove one identical buyer
problem; a Google Trends spike is not validated organic search demand;
even two independent complaints cannot authorize a build without SEO,
competition and monetization evidence. No paid API, browser runner, proxy,
always-on PC, or change to the existing radar schedule is involved.
