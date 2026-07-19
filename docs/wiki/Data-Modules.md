# Data Modules

The 27 files in `scripts/modules/` that actually fetch data, plus two shared helpers. Each is a
standalone CLI you can run directly — useful for debugging a single field without waiting for a
full dossier.

## The module contract

Every module follows the same shape, and a new one must too:

- **A standalone argparse CLI.** The pipeline invokes it as
  `python modules/<name>.py <subcommand> [args]` in a subprocess.
- **`cmd_<name>(args)` handlers** taking an argparse `Namespace`.
- **JSON to stdout** via `utils.output_json`. Return value is ignored.
- **Errors as JSON**, never tracebacks: the `@safe_run` decorator catches everything and emits
  `{"error": "TypeName: message"}` with exit 1.

There is no `modules/__init__.py` — Python puts the script's own directory on `sys.path[0]`, so
siblings import as `from utils import ...`. This is what lets each module run standalone.

Run any module directly:

```bash
scripts/.venv/bin/python scripts/modules/vix_curve.py analyze
scripts/.venv/bin/python scripts/modules/debt_structure.py analyze NVDA
scripts/.venv/bin/python scripts/modules/rs_ranking.py screen --min-rating 90 --limit 20
```

## External sources at a glance

| Source | Modules | Key needed |
| --- | --- | --- |
| **yfinance** | 14 | No |
| **FRED** | 4 | **Yes** — `FRED_API_KEY` |
| **CBOE** delayed quotes | 2 | No |
| **SEC EDGAR** (direct HTTP) | 2 | No (identity recommended) |
| **CNN** via `fear-greed` | 1 | No |
| **CME** via `cme-fedwatch` | 1 | No |
| **Supabase** via `ibd-rs-rating` | 1 | No |
| **YCharts** (scraped with `curl`) | 1 | No |

---

## Shared helpers

| File | Role |
| --- | --- |
| `utils.py` | `normalize(obj)` — recursive pandas/numpy → JSON-safe conversion (NaN → `null`, Timestamp → ISO string, DataFrame → column-oriented dict). Plus `output_json`, `error_json`, `output_json_records`, and the `@safe_run` decorator. No network. |
| `_sec_common.py` | Vendored SEC EDGAR helpers: `get_cik_from_symbol(symbol)` → zero-padded 10-digit CIK, `get_company_info(cik)` → submissions JSON. Sets the required `User-Agent`. Normalizes `.` → `-` in symbols (`BRK.B` → `BRK-B`). |

`normalize()` has one behavior worth knowing: it emits DataFrame **columns only**. Data living in
a DataFrame *index* is lost. That is the root cause of the `next_report` bug in
[Known Limitations](Known-Limitations.md#next_report-is-always-null).

---

## Macro gauges

Ten modules feeding `serenity_pipeline.py macro`.

| Module | Fetches | Source | Subcommands | Key |
| --- | --- | --- | --- | --- |
| `rates.py` | Fed funds, Treasury yields, SOFR, TIPS, mortgage, international yields, spreads | FRED | `fed-funds`, `yield-curve`, `sofr`, `tips`, `mortgage`, `international-yield`, `yield-spread` | ✅ |
| `inflation.py` | CPI, PCE, breakeven inflation, U. Michigan expectations | FRED | `cpi`, `pce`, `breakeven-inflation`, `michigan` | ✅ |
| `net_liquidity.py` | Net liquidity = Fed balance sheet − TGA − reverse repo | FRED | `net-liquidity` (`--include-reserves`, `--lookback`, `--limit`) | ✅ |
| `erp.py` | Equity risk premium = (1 ÷ CAPE) − 10-year yield | YCharts (scraped) + FRED | `erp` (`--period`, `--refresh`) | ✅ |
| `vix_curve.py` | VIX spot and the VX1–VX9 futures term structure | CBOE | `analyze` (`--date`) | — |
| `iv_context.py` | IV30 / HV30 one-year range → IV Rank | CBOE + yfinance | `analyze` | — |
| `fear_greed.py` | CNN Fear & Greed composite plus 7 sub-indicators | CNN via `fear-greed` | *(flat, no subcommand)* `--include-indicators` | — |
| `fedwatch.py` | FOMC cut/hold/hike probabilities | CME via `cme-fedwatch` | *(flat, no arguments)* | — |
| `dxy.py` | Dollar index level, z-score, percentile | yfinance `DX-Y.NYB` | *(flat)* `--period`, `--interval` | — |
| `bdi.py` | Baltic Dry Index proxy and z-score | yfinance `BDRY` ETF | *(flat)* `--period`, `--interval` | — |

Two caveats worth carrying into a reading:

- **`bdi.py` measures a proxy, not the index.** The Baltic Dry Index itself is published with a
  delay, so the module tracks the `BDRY` ETF instead. Tracking error is roughly 2–5% per year.
- **`erp.py` scrapes YCharts via `curl`** for the CAPE ratio, with a fallback to a cached Shiller
  CSV at `scripts/.cache/shiller_cape.csv`. A scraper against a third-party page is the most
  fragile thing in the tree; if `erp_pct` disappears, this is usually why.

The four FRED modules are the ones affected by the `.env` loading issue — see
[Getting Started](Getting-Started.md#configure) for the export workaround.

---

## Single-name financials

Twelve modules, all yfinance, no API key.

| Module | Computes | Subcommands |
| --- | --- | --- |
| `info.py` | Company metadata, fast quote, ISIN, share counts, history metadata, SEC filing links, short interest | `get-info`, `get-fast-info`, `get-info-fields`, `get-isin`, `get-shares`, `get-shares-full`, `get-history-metadata`, `get-sec-filings` |
| `financials.py` | Income statement, balance sheet, cash flow | `get-income-stmt`, `get-balance-sheet`, `get-cash-flow` — each `--freq {yearly,quarterly,trailing}` |
| `actions.py` | Dividends, splits, capital gains, earnings, earnings dates, calendar, news, insider transactions | `get-dividends`, `get-splits`, `get-capital-gains`, `get-actions`, `get-earnings`, `get-earnings-dates`, `get-calendar`, `get-news`, `get-insider` |
| `analysis.py` | Analyst consensus: targets, EPS/revenue estimates, EPS trend and revisions, growth estimates, recommendations, upgrades/downgrades, ESG | 12 subcommands including `get-analyst-price-targets`, `get-revisions`, `get-recommendations-summary` |
| `growth.py` | EPS and sales acceleration, margin expansion | `profile`, `trends` |
| `surprise.py` | Beat/miss history, post-earnings gap and 1-day/5-day drift | `history` |
| `margin_tracker.py` | Gross/operating/net margin quarter-over-quarter and year-over-year | `track`, `flag-expansion` |
| `debt_structure.py` | Net debt, interest burden, debt-to-equity, implied rate, coverage, rate-hike stress | `analyze`, `stress-test` |
| `sbc_analyzer.py` | Stock-based comp in dollars and as % of revenue; **real FCF = reported FCF − SBC** | `get-sbc`, `compare-sbc` |
| `capex_tracker.py` | Quarterly CapEx trend, supply-chain layer cascade, pairwise comparison | `track`, `cascade`, `compare` |
| `forward_pe.py` | Forward P/E 1-year and 2-year, PEG | `calculate`, `compare`, `batch` |
| `no_growth_valuation.py` | Zero-growth fair value at a fixed 15× multiple, margin of safety | `calculate`, `compare` |

Implementation details that affect how you read the output:

- **`capex_tracker.py`** takes absolute values — yfinance reports `CapitalExpenditure` as
  negative. It is sector-agnostic with no hardcoded tickers; the hyperscaler list lives in the
  pipeline, not the module.
- **`actions.py` insider parsing** is a workaround: yfinance leaves the `Transaction` column
  blank, so buy/sell direction is parsed out of the free-text `Text` column.
- **`no_growth_valuation.py`** hardcodes a 15× multiple. It is a stated modeling assumption, not
  a threshold that decides anything, but treat the output as "value at 15× no-growth" rather than
  as fair value.

---

## Sentiment and positioning

| Module | Computes | Source | Subcommands |
| --- | --- | --- | --- |
| `institutional_quality.py` | Classifies holders (passive / long-only / hedge / quant-MM) into a weighted 1–10 quality score | yfinance | `score`, `compare` |
| `rs_ranking.py` | IBD-style RS Rating 1–99 across ~4,600 US stocks | `ibd-rs-rating` (Supabase) | `score`, `screen`, `compare` |

`rs_ranking.py` computes `0.4·ROC(63) + 0.2·ROC(126) + 0.2·ROC(189) + 0.2·ROC(252)` and converts
to a percentile. It does not use yfinance at all.

`institutional_quality.py` is the clearest example of the boundary in action: the module computes
holder classifications and a score, and the pipeline keeps only `{name, shares}` per holder. The
classification is a judgment, so it does not survive into the payload.

---

## Filings

| Module | Fetches | Notes |
| --- | --- | --- |
| `filings.py` | Filing index (form, dates, accession, URL) and MD&A extraction | Flat parser: `filings.py TICKER --form 10-K --limit 20 [--mda]` |
| `events.py` | Supply-chain events regex-extracted from recent 8-Ks | `events TICKER --limit 10 --days 180`. **No LLM** — pure regex. |

Both hit SEC EDGAR over plain HTTP using the shared headers from `_sec_common.py`. These are
distinct from `scripts/serenity_filings.py`, which is the edgartools-based CLI documented in
[Filings and SEC](Filings-and-SEC.md).

`events.py` is fetched during every `analyze` run — it is the single slowest job in the fan-out at
a 120-second timeout — but its results are then discarded by a type mismatch in the evidence
builder. See [Known Limitations](Known-Limitations.md#recent_events-is-always-empty).

---

## Which module feeds which field

Reverse lookup, for when an `analyze` field looks wrong and you want to reproduce it in isolation.

| Output field | Module | Direct command |
| --- | --- | --- |
| `key_facts.*` | `info.py` | `info.py get-info-fields NVDA` |
| `fundamental_inputs.revenue_trajectory` | `financials.py` | `financials.py get-income-stmt NVDA --freq quarterly` |
| `fundamental_inputs.margins` | `margin_tracker.py` | `margin_tracker.py track NVDA` |
| `fundamental_inputs.sbc_and_dilution` | `sbc_analyzer.py` | `sbc_analyzer.py get-sbc NVDA` |
| `fundamental_inputs.debt_and_cash` | `debt_structure.py` | `debt_structure.py analyze NVDA` |
| `fundamental_inputs.capex` | `capex_tracker.py` | `capex_tracker.py track NVDA --quarters 8` |
| `valuation_inputs.forward_pe` | `forward_pe.py` | `forward_pe.py calculate NVDA` |
| `valuation_inputs.no_growth` | `no_growth_valuation.py` | `no_growth_valuation.py calculate NVDA` |
| `valuation_inputs.analyst_price_targets` | `analysis.py` | `analysis.py get-analyst-price-targets NVDA` |
| `market_structure_inputs.institutional_holders` | `institutional_quality.py` | `institutional_quality.py score NVDA` |
| `market_structure_inputs.relative_strength` | `rs_ranking.py` | `rs_ranking.py score NVDA` |
| `market_structure_inputs.insider_flow` | `actions.py` | `actions.py get-insider NVDA` |
| `market_structure_inputs.volatility` | `iv_context.py` | `iv_context.py analyze NVDA` |
| `catalyst_inputs.earnings_history` | `surprise.py` | `surprise.py history NVDA` |
| `catalyst_inputs.estimate_revisions` | `analysis.py` | `analysis.py get-revisions NVDA` |

---

## Adding a module

1. Create `scripts/modules/your_module.py` following the contract at the top of this page:
   argparse CLI, `cmd_*` handlers, `@safe_run`, `output_json`.
2. **Return measurements, not labels.** `spot: 18.9`, never `state: "elevated"`. If the module
   computes an interpretation for its own standalone use, expect the pipeline to drop it — that is
   the design working, not a bug.
3. Register it in the relevant spec dict in `scripts/pipeline/_fetch.py` (`_MACRO_SCRIPTS`, or
   inside `_fetch_l4` / `_fetch_l5`).
4. Add the fields you want surfaced to the allow-list in `scripts/pipeline/_evidence.py`.
   Anything not allow-listed will not appear.
5. Run `scripts/.venv/bin/python scripts/serenity_harness.py validate` — it will fail if a
   judgment-shaped key slipped in.

See [Contributing](../../CONTRIBUTING.md) for the full checklist.

## Dependency note

`scripts/requirements.txt` lists `finvizfinance`, `finviz`, `sec-edgar-downloader`, and
`sec-analyzer`, and mentions a CFTC API in a comment. **No module imports any of them.** They are
leftovers from earlier iterations — harmless, but do not read requirements.txt as a source map.

---

**Next:** [Filings and SEC](Filings-and-SEC.md) · [Back to index](README.md)
