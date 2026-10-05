# New Keyword Radar

A zero-paid-API Google Trends pipeline for finding **genuinely new search queries that can be monetized**.

The core rule is strict: **a new product is not automatically a new keyword**. A formal candidate must show that the **complete query itself** had a near-zero historical baseline and only started rising recently. It must also have a credible monetization path.

## What it does

Every day the workflow:

1. Reads Google Trends Trending Now RSS for `US / BR / MX / ES / GB`.
2. Collects exact related queries plus manually supplied seed queries.
3. Selects only a small number of candidates for Explore, to avoid Google rate limits.
4. Fetches a 90-day Google Trends interest series using `trendspyg`.
5. Measures the early baseline versus the last 30 days.
6. Separately scores monetization intent (`calculator`, `codes`, `values`, `checker`, `pricing`, etc.).
7. Writes machine-readable JSON and a human-readable Markdown report.
8. Commits the result back to the repository so ChatGPT can read it with the GitHub connector.

## Why `trendspyg`, not `pytrends`

`pytrends` is effectively unmaintained/archived. `trendspyg` is a maintained open-source replacement and provides a pytrends-compatible `TrendReq`, plus RSS and Explore support. No paid API key is required.

Google can still rate-limit unofficial access. This repo intentionally validates only a handful of queries per run, spaces Explore requests, and never performs aggressive retries.

## Output files

- `data/latest.json` — latest complete machine-readable result.
- `data/YYYY-MM-DD.json` — daily snapshot.
- `reports/latest.md` — latest readable shortlist.
- `reports/YYYY-MM-DD.md` — daily report.
- `state/seen.json` — first-seen history for discovered queries.

A formal candidate includes the raw 0–100 series, so another agent can independently inspect the curve instead of trusting only the score.

## Add candidate queries

Edit `config/seeds.txt`, one **exact full query** per line. Do not add broad topics merely because they are new products.

Example:

```text
grand blue codes
some new game values
some new feature calculator
```

The radar will still reject a seed if its 90-day baseline shows it is an old query.

## New-word gate

Defaults in `config/settings.json`:

- baseline average `<= 1.5`
- baseline non-zero ratio `<= 10%`
- baseline peak `<= 10`
- recent 30-day peak `>= 20`
- a first meaningful rise must occur in the recent window

These are relative Google Trends values, **not absolute search volume**.

## Money gate

High-priority query structures include:

- Tool: `calculator`, `generator`, `checker`, `converter`, `tracker`
- Repeat data: `codes`, `values`, `stats`, `database`, `tier list`
- Transactional: `pricing`, `cost`, `compare`, `alternative`, `coupon`
- Digital product: `template`, `prompt`, `preset`
- SaaS/B2B: `api`, `automation`, `workflow`, `reporting`, `compliance`

A query may be truly new but still be excluded from the formal shortlist if it has no clear way to make money.

## Schedule

GitHub Actions runs at `23:05 UTC`, approximately **07:05 Asia/Shanghai**, leaving time for an 08:00 downstream report.

You can also run it manually:

`Actions → New Keyword Radar → Run workflow`

## Cost

- Google Trends: free
- `trendspyg`: free / MIT
- GitHub Actions: uses the repository/account's included GitHub Actions allowance
- Paid Trends API: none
- Proxy: none by default

## Important limitations

Google Trends is a relative-interest signal. It does not provide Semrush/Ahrefs-style absolute `Volume / KD / CPC`. The intended workflow is:

**discover new query → verify 90-day newness → verify monetization → only then check Volume/KD/CPC for the strongest 1–3 queries.**

If Google returns a rate-limit error, do not hammer retry. Wait for the next scheduled run or reduce `max_explore_per_run`.
