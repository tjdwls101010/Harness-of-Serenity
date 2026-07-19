# Pipeline Reference

Complete reference for `scripts/serenity_pipeline.py` — every subcommand, every flag, and every
output field. This is the lookup page; for the reasoning behind the design see
[Architecture](Architecture.md).

All examples assume `PY=scripts/.venv/bin/python` and the repository root as working directory.

## Command overview

| Command | Purpose | Network | Typical time |
| --- | --- | --- | --- |
| [`macro`](#macro) | Raw macro gauges, no regime label | Yes | 20–60 s |
| [`analyze`](#analyze) | Full single-name evidence dossier | Yes | 30–90 s |
| [`discover`](#discover) | Side-by-side comparator | Yes | 10–30 s |
| [`evidence`](#evidence) | Replay a frozen fixture | **No** | < 1 s |

An equivalent module entry point exists — `python -m pipeline <subcommand>`, run from `scripts/`
— with identical arguments but without per-argument help text.

---

## `macro`

Raw macro gauges. It deliberately does **not** classify the regime; that reading is the analyst's.

```bash
$PY scripts/serenity_pipeline.py macro
$PY scripts/serenity_pipeline.py macro --no-capex
```

| Flag | Type | Default | Effect |
| --- | --- | --- | --- |
| `--no-capex` | flag | off | Skips the hyperscaler CapEx fan-out (MSFT, GOOG, META, AMZN). Meaningfully faster — that fetch is a second serial wave of four subprocesses. |

### Output

Two top-level keys: `evidence_contract` (with `kind: "serenity_macro_evidence"`) and
`macro_inputs`.

| Field | Source | Meaning |
| --- | --- | --- |
| `erp_pct` | FRED + YCharts CAPE | Equity risk premium: (1 ÷ CAPE) − 10-year yield |
| `vix_spot` | CBOE | VIX index level |
| `vix_structure` | CBOE | Term-structure shape from VX1 vs VX2 (contango / backwardation) |
| `net_liq_direction` | FRED | Direction of Fed balance sheet − TGA − reverse repo |
| `fear_greed` | CNN | Composite sentiment index, 0–100 |
| `fedwatch_next_meeting` | CME futures | Next FOMC date |
| `fedwatch_probabilities` | CME futures | Cut / hold / hike probabilities |
| `bdi_z_score` | yfinance (`BDRY` ETF proxy) | Baltic Dry Index z-score |
| `dxy_z_score` | yfinance (`DX-Y.NYB`) | Dollar index z-score |
| `real_rate` | FRED | 10-year nominal minus 10-year breakeven |
| `hyperscaler_capex` | yfinance | Per-ticker `{latest_capex, avg_capex, direction, quarters}` |

**Null convention.** A gauge that could not be fetched is **dropped entirely**, not emitted as
`null`. Zeros and `false` are kept — those are real readings. If every gauge fails,
`macro_inputs` collapses to `null`.

This means a missing `erp_pct` is ambiguous between "FRED was down" and "no API key configured."
Because macro modules do not load `.env`, the second case is common — see
[Known Limitations](Known-Limitations.md#env-is-not-loaded-for-macro-modules).

**Deliberately absent:** `vix_regime`, `bdi_demand`, `dxy_strength`. The source modules compute
those labels; the pipeline strips them.

---

## `analyze`

The full single-name evidence dossier — the primary command.

```bash
$PY scripts/serenity_pipeline.py analyze NVDA
$PY scripts/serenity_pipeline.py analyze NVDA --skip-macro
```

| Argument | Type | Required | Effect |
| --- | --- | --- | --- |
| `ticker` | positional | yes | Symbol, upper-cased automatically |
| `--skip-macro` | flag | no | Skips the macro fetch entirely; `macro_inputs` emits as `null` |

**Use `--skip-macro` for batch work.** Macro data is identical across names and is the slowest
part of a run. Fetch it once, then reuse it across every name in a cohort.

### The `analyze` output schema

Nine top-level keys, always present:

```
evidence_contract · ticker · macro_inputs · key_facts · fundamental_inputs
valuation_inputs · market_structure_inputs · catalyst_inputs · filing_evidence
```

#### `evidence_contract`

```json
{
  "kind": "serenity_evidence",
  "judgment_owner": "agent",
  "code_role": "load_and_normalize_evidence",
  "boundary": "No verdicts, portfolio actions, numeric conviction scores, option vehicles, or a regime/risk_level label — the macro_inputs gauges are raw; the agent classifies the regime."
}
```

#### `key_facts`

The anchor numbers. Field names are yfinance's verbatim camelCase. **Between 0 and 20 keys** —
a field whose value is `None` is omitted rather than emitted as `null`.

| Field | Notes |
| --- | --- |
| `sector`, `industry` | Classification strings |
| `marketCap` | **The denominator every ratio must divide by.** Use this value, not a remembered one. |
| `enterpriseValue` | |
| `currentPrice` | |
| `beta` | |
| `fiftyTwoWeekLow`, `fiftyTwoWeekHigh` | Price-position context |
| `fiftyDayAverage`, `twoHundredDayAverage` | |
| `sharesOutstanding`, `floatShares` | |
| `shortPercentOfFloat` | **A fraction, not a percent** — `0.084` means 8.4% |
| `totalRevenue` | Trailing twelve months |
| `bookValue`, `totalCash` | |
| `grossMargins`, `operatingMargins` | **Decimal fractions** — `0.296` means 29.6% |
| `heldPercentInsiders`, `heldPercentInstitutions` | Also fractions |

#### `fundamental_inputs`

| Sub-key | Fields |
| --- | --- |
| `revenue_trajectory` | `revenue_by_quarter` — raw pass-through, may be `null` |
| `margins` | `quarters_analyzed`, `latest_quarter`, `gross_margin_qoq_change`, `operating_margin_qoq_change`, `gross_margin_yoy_change`, `operating_margin_yoy_change`, `trajectory` |
| `sbc_and_dilution` | `sbc_annual`, `sbc_pct_revenue`, `reported_fcf`, `real_fcf`, `shares_outstanding_current`, `shares_outstanding_prior_quarter`, `shares_change_qoq_pct`, `total_dilution_annual_pct` |
| `debt_and_cash` | `total_debt`, `cash_and_equivalents`, `net_debt`, `total_assets`, `inventory`, `market_cap`, `net_debt_to_mcap`, `total_revenue`, `interest_expense`, `interest_pct_revenue`, `debt_to_equity`, `implied_interest_rate`, `interest_coverage_ratio`, `interest_coverage_metric` |
| `capex` | `quarters`, `latest_capex`, `avg_capex`, `direction` |

`real_fcf` is reported free cash flow minus stock-based compensation — the pipeline's one
opinionated derivation, and pure subtraction rather than a threshold.

#### `valuation_inputs`

| Sub-key | Fields |
| --- | --- |
| `forward_pe` | `current_price`, `forward_pe_1y`, `forward_pe_2y`, `peg_ratio`, `peg_ratio_unit`, `eps_growth_rate_used`, `revenue_growth_yoy`, `gross_margin_pct` |
| `no_growth` | `current_revenue`, `net_margin_pct`, `implied_earnings`, `no_growth_pe_multiple`, `no_growth_fair_value`, `current_market_cap`, `margin_of_safety_pct`, `negative_earnings` |
| `analyst_price_targets` | `{current, high, low, mean, median}`, or `{}` |
| `recommendation_distribution` | A **list** of `{period, strongBuy, buy, hold, sell, strongSell}` |
| `ev_multiples` | `enterprise_value`, `total_revenue`, `real_fcf`, plus `ev_to_revenue` and `ev_to_fcf` when computable |

Two things to note:

- `no_growth` uses a **fixed 15× multiple** as its zero-growth assumption. That constant lives in
  `modules/no_growth_valuation.py:79`. It is a stated modeling assumption rather than a threshold
  that decides anything, but it is the closest thing to a judgment on the code side — read the
  output as "value at a 15× no-growth multiple," not as fair value.
- `ev_to_fcf` appears **only when free cash flow is positive**. A negative multiple is a division
  artifact, so it is suppressed rather than emitted misleadingly.
- `recommendation_distribution` legitimately contains the strings `buy` and `sell` as *keys of an
  analyst tally*. The contract test exempts filing text from value scanning and matches
  `recommendation` exactly rather than as a substring, so this raw count survives without
  weakening the ban on a code-emitted verdict.

#### `market_structure_inputs`

| Sub-key | Fields |
| --- | --- |
| `institutional_holders` | `total`, `top_holders` — up to 10 entries reduced to `{name, shares}` only |
| `relative_strength` | `rs_rating` (IBD-style 1–99), `spy_rs`, `history` |
| `short_interest_depth` | `days_to_cover`, `si_trend` |
| `insider_flow` | `net_value`, `net_shares_6m`, `buy_value_12m`, `sell_value_12m`, `buy_count_12m`, `sell_count_12m` |
| `volatility` | `current_price`, `iv30`, `iv30_annual_high`, `iv30_annual_low`, `iv_rank`, `hv30_annual_high`, `hv30_annual_low`, `iv_vs_hv_spread`, `hv30_current`, `typical_daily_move_pct`, `iv_rv_ratio` |

`top_holders` carries names and share counts only — the source module's holder-type
classification is deliberately dropped. `insider_flow` likewise omits the module's
`net_direction` label.

#### `catalyst_inputs`

| Sub-key | Fields |
| --- | --- |
| `next_report` | `{date, eps_estimate}` or `null` — **currently always `null`**, see below |
| `earnings_history` | `surprise_history`, `consecutive_beats`, `avg_surprise_pct`, `total_quarters_analyzed` |
| `estimate_revisions` | `by_horizon`, `net_revisions_7d`, `net_revisions_30d` |

`by_horizon` is keyed `0q`, `+1q`, `0y`, `+1y`, each holding `eps` (`current`, `7d_ago`,
`30d_ago`, `90d_ago`, `low`, `high`, `yoy_pct`, `up_7d`, `down_7d`, `up_30d`, `down_30d`) and
`revenue` (`avg`, `low`, `high`, `yoy_pct`). The module's `trend_direction` and `thresholds` are
stripped.

> ⚠️ `next_report` is always `null` — yfinance returns earnings dates in the DataFrame *index*,
> and the normalizer emits columns only. See
> [Known Limitations](Known-Limitations.md#next_report-is-always-null).

#### `filing_evidence`

| Sub-key | Contains |
| --- | --- |
| `dossier` | Consolidated filing facts: `filing_facts`, `geographic_concentration`, `customer_concentration`, `inventory_mix`, `purchase_obligations` |
| `absence_evidence_flags` | Objective flags with their editorial `signal` text stripped |
| `recent_events` | Recent material 8-K events |

> ⚠️ **On the live path all three are empty.** The in-pipeline SEC extraction is a stub since the
> capability was consolidated into the `serenity-filings` subagent, and `recent_events` is
> additionally lost to a type mismatch. Frozen fixtures captured before the consolidation still
> show populated data. Use [`serenity_filings.py`](Filings-and-SEC.md) for filing facts. See
> [Known Limitations](Known-Limitations.md#filing_evidence-is-empty-on-the-live-path).

---

## `discover`

A side-by-side comparator across several tickers. **Not a ranking** — candidates come back in
input order, unsorted, because ordering them would be a judgment.

```bash
$PY scripts/serenity_pipeline.py discover TSM ASML ARM AMAT
```

| Argument | Type | Required | Effect |
| --- | --- | --- | --- |
| `tickers` | positional, one or more | yes | Symbols to compare |

### Output

Five top-level keys: `evidence_contract` (`kind: "serenity_discovery_comparator"`), `candidates`,
`metric_definitions`, `missing_data`, `metadata`.

Each candidate carries the same 18 fields, with explicit `null` where unavailable (unlike
`key_facts`, which omits):

```
ticker · sector · industry · marketCap · currentPrice
forward_pe_1y · forward_pe_2y · peg_ratio · revenue_growth_yoy · gross_margin_pct
eps_accelerating · sales_accelerating · rs_rating · no_growth_mos_pct
beta · pct_above_52w_low · pct_below_52w_high · short_pct_float
```

`missing_data` maps each ticker to the list of fields that came back null — so a gap is visible
rather than silently absent. `metric_definitions` explains each computed metric inline.

---

## `evidence`

Replays a frozen input payload through the evidence builder. **No network.** Because
`build_evidence()` is a pure function of its input, output is byte-stable across machines and runs
— which is what makes it usable as a contract test.

```bash
$PY scripts/serenity_pipeline.py evidence --fixture scripts/tests/golden/AAOI.inputs.json
$PY scripts/serenity_pipeline.py evidence --fixture path/to/custom.json --ticker XYZ
```

| Flag | Type | Required | Effect |
| --- | --- | --- | --- |
| `--fixture` | path | **yes** | A frozen `*.inputs.json` payload |
| `--ticker` | string | no | Overrides the ticker; otherwise inferred from the filename |
| `--json` | flag | no | **No-op.** Always on and never read. Present for call-site compatibility. |

Output is identical in shape to `analyze`. The 16 shipped fixtures are AAOI, AEHR, AXTI, CRCL,
HIMS, HOOD, IONQ, LITE, MU, NBIS, POET, QBTS, RGTI, RKLB, SIVE, SSYS.

---

## Cross-cutting behavior

### Errors

Every command is wrapped so that an uncaught exception replaces the entire payload:

```json
{ "error": "TypeError: unsupported operand type(s) for -: 'NoneType' and 'int'" }
```

with exit code 1. **Partial failures never surface this way** — a failed data module becomes a
missing field inside an otherwise valid payload. A top-level `error` means the pipeline itself
broke, not an upstream source.

### Timeouts and concurrency

| Setting | Value |
| --- | --- |
| Per-module timeout | 60 s (SEC events: 120 s) |
| Thread pool per fetch group | 10 workers |
| Top-level fan-out | 3 workers (fundamentals · catalysts · SEC) |

None of these are configurable by flag.

### No caching

Every run re-fetches everything. There is no memoization, no on-disk cache, and no HTTP cache
layer. `--skip-macro` is the only reuse mechanism. If you are analyzing a cohort, run `macro` once
and redirect it to a file yourself.

### Piping and jq

Output goes to stdout as UTF-8 JSON with 2-space indentation, so it pipes cleanly:

```bash
$PY scripts/serenity_pipeline.py analyze NVDA > nvda.json

jq '.key_facts | {marketCap, currentPrice, grossMargins}' nvda.json
jq '.valuation_inputs.ev_multiples' nvda.json
jq -r '.fundamental_inputs.debt_and_cash | "net debt: \(.net_debt)"' nvda.json
```

Note that the `PostToolUse` integrity hook only fires on unpiped `analyze` output — it parses the
tool's stdout, and a pipe hides it. That is a deliberate trade (a piped run is not a failure), but
it means redirected runs skip the arithmetic audit.

---

**Next:** [Data Modules](Data-Modules.md) for what sits behind each field, or
[Filings and SEC](Filings-and-SEC.md) for the filing surface. · [Back to index](README.md)
