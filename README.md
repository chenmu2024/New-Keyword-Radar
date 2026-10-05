# New Keyword Radar

A zero-paid-API Google Trends pipeline for finding **genuinely new search queries that can be monetized**.

The hard rule is: **a new product is not automatically a new keyword**. A formal candidate must show that the **complete query itself** had a near-zero recent baseline, started rising only recently, and also has no meaningful historical footprint over the previous five years. It must also have a credible monetization path.

## Daily pipeline

1. Read Google Trends Trending Now RSS for `US / BR / MX / ES / GB`.
2. Collect exact related queries.
3. Query Google Autocomplete for a small number of fresh topics and keep only suggestions with clear commercial/tool intent.
4. Reuse rising related queries discovered by prior Explore checks through `state/pending.json`.
5. Validate a small number of exact full queries with Google Trends Explore over the past 90 days.
6. Score the desired shape: **old baseline near zero → first meaningful rise in the configured recent window (default 45 days)**.
7. For provisional winners, run a second **5-year exact-query history gate** to reject seasonal or previously established phrases that only look new in a 90-day chart.
8. Separately score monetization intent such as `calculator`, `codes`, `values`, `checker`, `pricing`, `template`, and `tracker`.
9. Save raw series plus a shortlist so ChatGPT can inspect the evidence directly.

## Output files

- `data/latest.json` — latest machine-readable result.
- `data/YYYY-MM-DD.json` — daily snapshot.
- `reports/latest.md` — latest readable shortlist.
- `reports/YYYY-MM-DD.md` — daily report.
- `state/seen.json` — first-seen history for exact queries.
- `state/pending.json` — self-expanding queue fed by RSS, Autocomplete and rising related queries.

## Add exact seed queries

Edit `config/seeds.txt`, one **exact full query** per line. Do not add a broad topic merely because the product/game itself is new.

Benchmark examples currently included:

```text
grand blue codes
jev ai
```

The radar can still reject a seed if either its 90-day curve or its five-year history shows it is not actually new.

## New-word gates

90-day gate defaults:

- baseline average `<= 1.5`
- baseline non-zero ratio `<= 10%`
- baseline peak `<= 10`
- recent 45-day peak `>= 20`
- first meaningful rise must occur inside the recent 45-day window

Five-year anti-old-query gate defaults:

- historical average before the recent window `<= 0.5`
- historical peak `<= 8`
- historical **material** ratio (points `>= 5`) `<= 3%`

Values 1–4 in a five-year series are treated as low-level background/noise for the material-ratio test; they are still reported. This prevents a genuinely new query such as a new `<game> codes` phrase from being rejected only because Google sampled tiny historical values. These are relative Google Trends values, **not absolute search volume**.

## Money gate

Higher-priority query structures:

- Tools: `calculator / generator / checker / converter / tracker`
- Repeat data: `codes / values / stats / database / tier list`
- Transactional: `pricing / cost / compare / alternative / deals`
- Digital products: `template / prompt / preset`
- SaaS/B2B: `api / automation / workflow / reporting / compliance`

A query can be truly new and still be excluded if it has no clear way to make money.

## Schedule

GitHub Actions runs at `23:05 UTC`, approximately **07:05 UTC+8**, leaving time for the 08:00 downstream new-word report.

The workflow also runs after changes to the radar code/config so setup and fixes can be verified immediately.

## Cost

- Google Trends: free
- Google Autocomplete: free
- `trendspyg`: free / MIT
- GitHub Actions: uses the repository/account's included allowance
- Paid Trends API: none
- Proxy: none by default

## Important limitations

Google Trends is a relative-interest signal. It does not provide Semrush/Ahrefs-style absolute `Volume / KD / CPC`.

The intended decision flow is:

**discover exact query → verify 90-day newness → reject older/seasonal queries with the 5-year gate → verify monetization → inspect only the strongest 1–3 in a keyword database → inspect SERP → decide whether to build.**

Google can rate-limit unofficial Explore access. The workflow deliberately checks only a few queries, spaces requests, uses disk cache/cookies, and does not hammer retries.
