# Data contract

The radar writes two forms of output:

- `data/latest.json`: canonical machine-readable output.
- `reports/latest.md`: human-readable summary.

## `data/latest.json`

Top-level fields:

- `generated_at`: UTC generation timestamp.
- `timeframe`: Google Trends timeframe used for Explore.
- `source_geos`: geographies scanned through Trending Now RSS.
- `checked_count`: number of exact queries sent through Explore.
- `formal_count`: number of candidates that passed both gates.
- `formal_candidates`: strongest monetizable true-new queries.
- `all_checked`: every query checked during the run.
- `discovered_count`: raw RSS/related-query discovery count.

Each checked candidate includes:

- `keyword`: exact full query.
- `geo`: Explore geography; empty means Worldwide.
- `source`: discovery source.
- `first_seen`: first date this radar observed the exact query.
- `baseline_avg`: average Google Trends interest before the recent window.
- `baseline_peak`: maximum interest in the baseline window.
- `baseline_nonzero_ratio`: fraction of baseline points above zero.
- `recent_peak`: peak in the recent window.
- `current_level`: average of the last three available points.
- `retention_pct`: current level divided by recent peak.
- `first_rise_date`: first recent point crossing the rise threshold.
- `peak_date`: date of the recent peak.
- `newness_score`: 0-100 relative score for the desired “near-zero then first rise” shape.
- `money_score`: 0-100 rule-based commercial-intent score.
- `money_type`: best matching monetization class.
- `true_new`: whether the strict new-word gate passed.
- `verdict`: `formal`, `trend-watch`, `commercial-watch`, `reject`, or `error`.
- `related_rising`: Google Trends rising related queries, when available.
- `series`: raw 0-100 time series used for adjudication.
- `error`: failure detail if Explore could not be read.

## Interpretation

A “formal” candidate is not equivalent to an absolute search-volume recommendation. Google Trends is relative. The intended second step is to inspect only the best 1–3 candidates in Semrush/Ahrefs or another keyword database for Volume/KD/CPC and then inspect SERP weakness and monetization feasibility.
