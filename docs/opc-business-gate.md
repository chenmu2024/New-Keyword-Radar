# OPC-inspired business opportunity gate

A zero-paid-API, **original implementation** of evidence-based business screening.
Inspired by strategic concepts in [easychen/opc-methodology](https://github.com/easychen/opc-methodology), **not a copy or repackaging of its non-commercially licensed Skill files**.

## Scope and boundaries

1. Google Trends 90-day gate and five-year anti-old-keyword gate are unchanged.
2. Only entries from the existing **formal_candidates** are considered; never promote a trend-watch, old-history, rejected or failed result.
3. No fabricated keyword metrics, SERP weakness, traffic figures, customer interviews or model-generated citations.
4. Missing values are **null / UNVERIFIED**, never zero or guessed.
5. Scoring is an internal heuristic, **not an external market estimate or promise of success**.
6. No automatic build decisions, paid calls, account creation or deployment.
7. Preserve all user-approved keywords and original discovery roots.

## Local or CI use

```bash
python -m unittest discover -s tests -p 'test_opc_business_gate.py'
python src/opc_business_gate.py
```

The daily radar workflow runs this after the five-year history gate and includes its outputs in the standard data/reports commit.
Outputs:
- `data/business/latest.json` and dated archive
- `reports/business/latest.md` and dated archive

If the radar has zero formal new words, the business report correctly says there are none. **Never treat an empty report as a scraping or demand failure by itself.**

## Evidence-input contract

Human or external verified evidence is keyed by the **exact normalized full keyword** and Google Trends geo, separated with `|`; e.g. `"example calculator|US"`. Add only sourced, dated information to `config/business_evidence.json`. This file starts as `{}` intentionally.

Example below uses **placeholder numbers and sources solely to illustrate the JSON schema**; do not copy it as real market research:

```json
{
  "example calculator|US": {
    "keyword_metrics": {
      "volume": 1200,
      "kd": 24,
      "cpc": 0.6,
      "source": "PLACEHOLDER: keyword database and country",
      "checked_at": "2026-10-08"
    },
    "serp": {
      "notes": "PLACEHOLDER: top-10 SERP competitor / user intent evidence",
      "source": "PLACEHOLDER: actual SERP review",
      "checked_at": "2026-10-08"
    },
    "benchmark": {
      "monthly_visits": 22000,
      "source": "PLACEHOLDER: traffic estimate provider and reference domain",
      "checked_at": "2026-10-08"
    },
    "dimensions": {
      "pain": {"score": 4, "source": "PLACEHOLDER: interview evidence", "checked_at": "2026-10-08"},
      "leverage": {"score": 4, "source": "PLACEHOLDER: technical feasibility", "checked_at": "2026-10-08"},
      "timing": {"score": 3, "source": "PLACEHOLDER: trend and competitor history", "checked_at": "2026-10-08"},
      "resource_fit": {"score": 5, "source": "PLACEHOLDER: actual reusable assets", "checked_at": "2026-10-08"},
      "standardization": {"score": 4, "source": "PLACEHOLDER: workflow proof", "checked_at": "2026-10-08"},
      "cashflow": {"score": 3, "source": "PLACEHOLDER: verified comparable income", "checked_at": "2026-10-08"}
    },
    "business_model": "Ads",
    "acquisition_channel": "Organic search",
    "estimated_monthly_fixed_cost_usd": 0
  }
}
```

### Seven-day new-game exception

For a genuinely new game without a mature competitor, `benchmark` may instead provide `"verified_new_game_7d": true`, plus a real `game_evidence_url`, `source`, and `checked_at`. **It still requires actual nonzero keyword volume, KD and SERP review.** Merely seeing a related-query breakout is not enough.

## Advisory decision statuses

| Status | Meaning |
|---|---|
| `not-formal` | Newness/historical gate has not passed |
| `reject-zero-volume` | Explicitly verified zero search demand |
| `watch-high-kd` | KD > 40, outside the default low-competition target |
| `needs-evidence` | Required observations missing; no decision yet |
| `watch-business-risk` | Completed six-dimension score below internal threshold |
| `ready-for-human-review` | Evidence gates passed; **NOT** authorization to build |

Six dimensions: user pain, code/media/AI leverage, market-timing window, founder resource fit, standardizability, and cashflow potential. Each gets an **evidence-cited integer 0–5**. The current review heuristic is at least 22/30, pain >= 3, cashflow >= 3. This cutoff is adjustable business policy, **not** a validated conversion model.

Reference benchmark: preferred 10k–100k estimated monthly visits, with source and date, or a sourced 7-day newly released game. Verify that competitor traffic estimates and user demand are for the appropriate market and search intent.

## Practical OPC decision workflow

- **Niche**: check market scope, pain, SERP and realistic ability to reach users.
- **Business model**: write how money will be earned and which costs/risks are real.
- **MVP validation**: identify the riskiest assumption and a bounded evidence test.
- **Conversion**: define traffic acquisition, first meaningful action, and eventual revenue.
- **Dashboard/stop-loss**: after launch inspect GSC page/query/country data and actual revenue, not model guesses. Keep improving, pause or retire based on trend and opportunity cost.

Recommended post-launch scorecard: search clicks and impressions, CTR and top pages, task completion/conversion, verified revenue and costs, indexation and technical health. Record "unknown" for unavailable numbers; never fill gaps with estimated business outcomes.

## Manual confirmation

A human must explicitly choose **build / test / hold / stop** after reviewing cited data. The automated status `ready-for-human-review` deliberately does not contain a build approval.
