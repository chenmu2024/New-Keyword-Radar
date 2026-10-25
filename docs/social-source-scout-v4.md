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
