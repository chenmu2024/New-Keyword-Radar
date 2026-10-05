# New Keyword Radar

A zero-paid-API Google Trends pipeline for finding **genuinely new search queries that can be monetized**.

The hard rule is: **a new product is not automatically a new keyword**. A formal candidate must show that the **complete query itself** had a near-zero historical baseline and only started rising recently. It must also have a credible monetization path.

## Daily pipeline

1. Read Google Trends Trending Now RSS for `US / BR / MX / ES / GB`.
2. Collect exact related queries.
3. Query Google Autocomplete for a small number of fresh topics and keep only suggestions with clear commercial/tool intent.
4. Reuse rising related queries discovered by prior Explore checks through `state/pending.json`.
5. Validate only a handful of exact full queries with Google Trends Explore over the past 90 days.
6. Score the desired shape: **old baseline near zero → first meaningful rise in the last 30 days**.
7. Separately score monetization intent such as `calculator`, `codes`, `values`, `checker`, `pricing`, `template`, and `tracker`.
8. Save raw 0–100 series plus a shortlist so ChatGPT can inspect the evidence directly.

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

The radar can still reject a seed if its 90-day curve shows it is not actually new.

## New-word gate

Default thresholds:

- baseline average `<= 1.5`
- baseline non-zero ratio `<= 10%`
- baseline peak `<= 10`
- recent 30-day peak `>= 20`
- first meaningful rise must occur inside the recent window

These are relative Google Trends values, **not absolute search volume**.

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

**discover exact query → verify 90-day newness → verify monetization → inspect only the strongest 1–3 in a keyword database → inspect SERP → decide whether to build.**

Google can rate-limit unofficial Explore access. The workflow deliberately checks only a few queries, spaces requests, uses disk cache/cookies, and does not hammer retries.
