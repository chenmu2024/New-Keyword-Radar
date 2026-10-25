# Social signal scout V4 — transparent public discovery

## Purpose
A source-diverse **discovery pointer feed** that complements 74-root Google Trends sweeps without changing keywords, existing hard gates, or the 07:00 sitemap research.

## Schedule
Runs every four hours on GitHub Actions (six times daily), independent of the 08:00 Chinese-language analytical task. Schedules are best effort, not real-time; GitHub-hosted runners and remote providers can delay, block, or rate-limit requests. No paid API, proxies, authentication bypass, browser automation, or cookie scraping.

## What is directly obtained
- **Product Hunt**: official public RSS at `https://www.producthunt.com/feed`; launches, NOT user demand.
- **Hugging Face Spaces**: public `/api/spaces` listing; new Spaces, NOT proven buyer demand.
- **YouTube channels**: optional, publicly published Atom feeds. Add verified UC channel IDs in `config/social_sources.json`. Empty list means `not_configured`.
- **TikTok, YouTube Shorts, Instagram Reels, X**: platform-targeted *Bing search RSS* links **only**. These are **indexed pointers**, not original posts/comments, not complete discovery, and RSS dates are not authoritative original publish dates. Off-platform URLs are rejected. No direct platform API connection is claimed.

## V4.1 direct social channels and exact-query linkage

The updated workflow also checks two independent public-first-party sources:

- **Bluesky AppView:** `https://public.api.bsky.app/xrpc/app.bsky.feed.searchPosts`; only public posts and plaintext returned by the source API, no login or scraping. Queries rotate between EN/PT/ES demand phrases. It is a primary-public-post lead; author text alone is **not** verified user purchase intent.
- **Mastodon:** `https://mastodon.social/api/v1/timelines/tag/<tag>`; only public statuses with visible content, rotating a few hashtags. Some servers disable unauthenticated access; `unavailable` is reported instead of zero demand.

Separately the scout reads that Beijing-local day's existing 7-day seed archive, normalizes complete multiword queries and matches exact word-bounded phrases in collected posts. It writes `data/social-signals/correlations-latest.json` and `reports/social-signals/correlations-latest.md` with source links, platforms, and possible first-person questions. It does not modify 74 seeds, `state/pending.json`, the 90-day/5-year newness gates, or previously rejected decisions. A positive phrase match never means the user wants to pay or that a site can rank.

For TikTok/X/Instagram/Shorts, Bing-index and public DuckDuckGo-index pointers remain the only free, reliable-to-label approach used in this workflow. When both index sources fail, the status is `unavailable`; when queries run successfully but return no usable link, status is `empty`. Both statuses mean **unknown**, not that a platform has no relevant content.

## V4.2: first-party question capture and query hypotheses (2026-10-25)

- **Bluesky official alternate host:** on ordinary HTTP 403 from the officially documented `public.api.bsky.app` post-search endpoint, try the also-official unauthenticated `api.bsky.app` once. This is not a 429 bypass. If unavailable, show the actual HTTP error and do not claim coverage. The posts are still *not* verified paying customers.
- **Official Ask HN Firebase:** read `askstories.json` and a bounded number of public `item/<id>.json` source posts. This provides original user-written title/body and server timestamps without cookies, login or a paid key; Ask HN posts can still be opinions and questions rather than paid needs.
- **User-question query mining:** Rule-based `src/social_intent.py` considers only source-verified `direct_public_post` text with an explicit help/need/request phrase. Proposes a short phrase in `query_hypotheses[]` with original post URL and timestamp. Outputs are explicitly `unverified_question_hint`, `search_volume=null`, `keyword_difficulty=null`, `actual_user_paid=false`, `ready_to_build=false`. No made-up Semrush evidence.
- **Complements exact query matching:** full-query matching against local 7-day 74-root Trends data stays conservative. It can return 0 independently of newly extracted social-first hypotheses.
- **Daily-report freshness:** schedule now targets **07:15 Asia/Shanghai** before the 08:00 ChatGPT brief (every four hours, best effort; GitHub cron execution can be delayed).
- **Consistent persistence:** latest and dated JSON archives include `cross_source_exact_matches` and `original_question_hypotheses`.

These public sources do **not** supply direct TikTok, X, Instagram Reels or YouTube Shorts comments, nor independent payment or traffic proof. Do not treat their 0 indexed links as absence of demand.

## V4.2 source quality and payment-self-report gate

- **Demand question phrases are conservative:** a generic 'how to make art' or conversational post is ignored unless the same *direct public post* includes an identifiable tool, downloadable file, batch action, converter, export, template, or similar artefact. This avoids inflating candidate counts with unrelated chatter. False negatives are acceptable at the collection stage.
- **Actual spend vs self-reported spend:** public posts saying 'I paid $19' are separately surfaced as `self_reported_buyer_feedback` in the correlations JSON, with the original post link and author-reported amount. Such an assertion is **not** a verified Stripe/Polar/merchant transaction, not SaaS business revenue, and not justification to copy a paid API product. It is a lead for further manual competitor/demand research.
- `buyer_self_reports_unverified` in the latest run summary and `original_question_hypotheses` are real rule-based counter outputs, not 'qualified businesses'.
- **Cross-source exact Query matches may remain 0**, even with direct source coverage. The system does not forcibly manufacture correlations when the 74-root Trends list has unrelated query contexts.

## V4.3: reusing the existing pain-research feed

**No new social-network scraper or paid account was added here.** Existing `src/free_intelligence.py` already gathers GitHub public Issues, Reddit RSS/index pointers and Ask HN indexed posts with six daily locale/topic searches. Previously, the social scout did not systematically consume these saved results. Now `src/social_evidence_bridge.py` reads `data/free-intelligence/latest.json` if its own reported generation timestamp is within 36 hours.

- GitHub Issues from the existing official public search are labeled `direct_public_issue_api` (issue title and potentially truncated original body), **not verified buyer or independent user demand**. A GitHub issue might be authored by a maintainer, not a customer.
- Reddit RSS is `public_rss_excerpt`; indexed fallback is `search_index_pointer`. Neither is original full comment evidence.
- The targeted Ask HN search via Algolia is `indexed_public_post_excerpt`; the separate official HN Firebase adapter has higher precedence as `direct_public_post` if both point to the same post.
- Source health includes `existing_free_intelligence_bridge`, data age and count. Stale, missing, failed and zero-result states remain visible. The bridge uses only existing saved JSON, so it makes no additional remote requests.
- Newly accumulated social findings are reviewed against up to **72 hours** of saved sightings and exact multiword Trends queries from the **last three Beijing-local archive dates**. This comparison can find an older GitHub issue recently indexed or rediscovered; the issue's original publication date must be preserved and the 72h review window must NEVER be called 72h of newly published issues.
- Source-precedence keeps original-source public post body ahead of third-party indexed excerpts for the same link.

Even with broader evidence, query hypotheses are unverified, and confirmed commercial opportunities may still number **zero**. Respect the original 74 seeds, 90-day and 5-year gates, non-brand keyword/competition checks, and zero-paid-API principle.

## V4.4: intent-focused public GitHub Issues (not new crawler subscriptions)

The 72h evidence bridge improves coverage, but generic issue search can return irrelevant maintenance tasks. `config/social_sources.json` now includes 12 precise rotating EN/PT/ES public GitHub Issue searches centered on batch processing, SVG/PDF/CSV, export/import, and downloadable outputs. Each four-hour run selects only **two** queries with up to five results each. On GitHub Actions the existing ephemeral built-in workflow token is used for public Issues API rate limits; this is **not** a paid API, an installed plugin, or a personal access credential.

- Public official Issues search yields author issue title and partial body; the runner filters PR links, known bot authors and missing concrete file-related action terms.
- `targeted_github_issues` reports `ok`, `empty` or `unavailable` separately, with error context.
- Results can support idea exploration but cannot prove actual paying customers, original independent demand, Semrush Volume/KD, current SERP weakness or feasibility.
- Queries rotate; absence of hits in a scan is not absence of market demand.

### V4.4.1 explicit-need filter

Initial live targeted GitHub Issue search returned a machine-agent engineering benchmark containing "convert PDF", rather than an explicit tool user request. To prevent marketing/roadmap noise, a qualifying issue must now mention **both** a concrete file/export/conversion operation and an explicit problem/request such as "feature request", "I need", "can't export", "would be helpful", "preciso de" or "necesito". The exact original author URL remains attached and demand/SEO/buyer verification remains false. Strict filtering may miss less explicit opportunities; those are not fabricated as positive signals.

## Output
- `data/social-signals/latest.json` and UTC-dated scan archives.
- `reports/social-signals/latest.md` includes each platform's success/failure and evidence class.
- `state/social_seen.json` tracks first seen / last seen / repeated sightings by canonical URL.

Never convert these pointers into verified SEO opportunities or append automatically to formal Trends candidates. The ChatGPT 08:00 task must look up a candidate's original source/comments, new-intent complete Query, Trends, and current SERP before giving a build recommendation.

## Reading source health
- `ok`: a query returned actual on-domain links / records; does **not** mean the original post or comments were read.
- `empty`: source accessible but no usable matching links.
- `unavailable`: network failure, 403, 429, parse failure, or other adapter error.
- `not_configured`: no verified channel IDs / search queries supplied.
- `disabled`: explicitly excluded by config.

## Boundaries
Google Trends rise ≠ absolute Volume. A mention ≠ a first-person demand comment. A Product Hunt launch or Hugging Face app ≠ evidence of payments. No guaranteed rankings, free storage/API uptime or instant indexing. Respect source access and terms.
