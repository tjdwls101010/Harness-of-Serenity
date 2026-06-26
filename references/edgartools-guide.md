# edgartools Build Spec (verified vs installed edgartools==5.35.1)

Build spec for `scripts/serenity_filings.py` (thin deterministic CLI) and the `serenity-filings` subagent. SEC is IP-blocked in the build env (403) — everything below is verified by offline introspection of the installed package, not live calls. The user's machine can hit SEC.

## API by job (verified)
- **Identity (required):** `from edgar import set_identity; set_identity("Name email@x.com")` — or env `EDGAR_IDENTITY` set BEFORE import. `get_identity()` to verify.
- **Company:** `c = Company("NVDA")` (ticker or CIK). `.cik .name .tickers .get_exchanges() .industry .shares_outstanding .public_float .not_found`. Bad id → raises `CompanyNotFoundError`/`ValueError` OR `.not_found==True` (check both).
- **Latest / range:** `c.latest("10-K")` → Filing; `c.latest("10-Q", 3)` → list. `c.get_filings(form="8-K").head(5)`; `filing_date="2025-01-01:"` / `":end"` / `"a:b"` / `(a,b)`; `form=["10-K","10-Q"]`. EntityFilings: `.head/.tail/.latest/.filter/[i]/.to_pandas`. `get_by_accession_number("0000320193-23-000106")`. ALWAYS `.head(n)` before iterating (bare load = everything).
- **10-K sections (TenK only):** `tk = c.latest("10-K").obj()` → `tk.business` (Item1) · `tk.risk_factors` (1A) · `tk.management_discussion` (Item7, NOT `.mda`) · `tk['Item 7']` · `tk.auditor` · `tk.subsidiaries` (Ex-21) · `tk.financials`. **TenQ lacks** `.business/.risk_factors/.management_discussion` → use `tq['Item 2']` (MD&A) / `tq['Item 1A']`. Items: 10-K/Q use `"Item 1A"`; 8-K uses dotted `"Item 1.01"`.
- **8-K (CurrentReport/EightK):** `ek = c.get_filings(form="8-K").latest().obj()` → `ek.items` (`['Item 2.02',...]`) · `ek.structure` · `ek['1.01']` (subscript, works with/without "Item ") · `ek.has_press_release` → `ek.press_releases[0].to_markdown()` · `ek.has_earnings` → `ek.earnings`. Codes: 1.01 Material Agreement · 2.02 Earnings · 5.02 Officer change · 8.01 Other · 9.01 Exhibits.
- **Standardized numbers (each may be None — guard!):** `fin = c.get_financials()` → `.get_revenue(offset=0) .get_net_income() .get_operating_income() .get_free_cash_flow() .get_total_assets() .get_total_liabilities() .get_stockholders_equity() .get_capital_expenditures() .get_operating_cash_flow() .get_financial_metrics()`. Values in actual dollars. `.income_statement().to_dataframe()` (on the statement, not Financials).
- **Raw XBRL (segments/geo/concentration):** `xb = c.latest("10-K").xbrl()` (None if none — check). `xb.statements.income_statement().to_dataframe(view="detailed")` (views: standard/detailed/summary). Query: `xb.query(include_dimensions=False)` → FactQuery: `.by_concept(regex) .by_label .by_value(callable) .by_dimension(axis[,member]) .by_statement_type .by_date_range .by_period_key .to_dataframe(*cols) .first .count`. SEGMENT/GEO: `xb.query(include_dimensions=True).by_concept("RevenueFromContractWithCustomer").by_dimension("StatementBusinessSegmentsAxis").to_dataframe()`. Notes/disclosures: `xb.notes()`, `xb.disclosures()` → `.title`, `.to_dataframe()`/`.render()`. Multi-year: `XBRLS.from_filings(c.get_filings(form="10-K").head(3))`.
- **Text for LLM:** `filing.text()` (str) · `filing.markdown(include_page_breaks=True)` · section accessors above · `obj.to_context(detail="minimal|standard|full")` (~100/300/800 tok — a routing summary, NOT full text) · `filing.search("phrase"[, regex=True])` → matching excerpts. No built-in token chunker — chunk at section boundaries.

## 4 doc-bugs to code around (installed 5.35.1)
1. **`EightK.get()` does NOT exist** → use `ek['8.01'] if 'Item 8.01' in ek.items else None`.
2. **`FactQuery.by_value` takes a CALLABLE**, not `min_value/max_value` → `by_value(lambda v: v>1e9)`; period filtering is `by_date_range`/`by_period_key`, not `by_period`.
3. **No top-level `get_company`** and **`find(form=,ticker=)` invalid** (`find(search_id)` single-arg) → use `Company(t).get_filings(form=...)`.
4. **MD&A is `.management_discussion`** not `.mda`; TenQ lacks named section props.

## Gotchas
- Rate limit 9 req/s default (SEC max 10; over → IP block). `EDGAR_RATE_LIMIT_PER_SEC`. Keep HTTP/1.1 (default) for fan-out.
- Caching on by default; persistent store via `use_local_storage(True)` + `EDGAR_LOCAL_DATA_DIR`.
- `filing.xbrl()` returns None (no XBRL); `XBRL.from_filing()` raises `XBRLFilingWithNoXbrlData` — different failure modes. ALL `get_*` return None (not 0) when absent. Empty query → empty DataFrame, not error. **Treat every return as possibly-None and guard it — annotations lie (edgartools' own lint flags 79 mismatches).**

## serenity_filings.py CLI design (thin, deterministic, JSON-out, NO LLM, NO narrative schema)
Identity from `EDGAR_IDENTITY` env or `--identity`; `use_local_storage(True)`. Every value possibly-null → emit `null`, never invent. Retry once on transient net fail then emit `{"error":"data_unavailable",...}`. No truncation.
**(a) numbers (pipeline):** `company TICKER` · `financials TICKER [--offset N]` · `xbrl-facts TICKER [--form --concept --dimension --statement --latest N]` · `segments TICKER [--axis ...]` · `statement TICKER [--which income|balance|cashflow --view detailed]`.
**(b) text (subagent):** `filings TICKER [--form --since --limit --between]` · `section TICKER [--form --item "Item 1A" | --named business|risk_factors|mda]` · `eightk TICKER [--limit --item 1.01]` · `text ACCESSION [--format text|markdown]` · `context ACCESSION [--detail standard]`.

## CLI-vs-direct split for the subagent
- **Via CLI** (must be byte-stable / cache-friendly): all numbers (financials/xbrl-facts/segments/statement); filing enumeration; a NAMED section or 8-K item already decided.
- **Direct edgartools** (adaptive, next-call-depends-on-last): iterative `ek.items`→pick→`ek[item]`; in-filing `filing.search("supply agreement")`; `xb.notes()/disclosures()` title spelunking; `to_context()` triage; cross-section synthesis.
- Rule: same-inputs-same-output → CLI subcommand; call-sequence-steered-by-what-you-just-read → direct.

## Cheat-sheet to embed in the subagent doc
```python
from edgar import Company, get_by_accession_number, set_identity
set_identity("Serenity chunghun1@naver.com")          # or env EDGAR_IDENTITY before import
c = Company("NVDA")                                     # ticker or CIK
tk = c.latest("10-K").obj()
tk.business; tk.risk_factors; tk.management_discussion  # TenK only; NOT .mda
tk['Item 7']; tk.auditor; tk.subsidiaries
ek = c.get_filings(form="8-K").latest().obj()
ek.items;  body = ek['1.01'] if 'Item 1.01' in ek.items else None   # NO .get()
if ek.has_press_release: ek.press_releases[0].to_markdown()
fin = c.get_financials(); fin.get_revenue(); fin.get_free_cash_flow()  # None-guard each
xb = c.latest("10-K").xbrl()                            # None if no XBRL
xb.statements.income_statement().to_dataframe(view="detailed")
geo = (xb.query(include_dimensions=True).by_concept("RevenueFromContractWithCustomer")
         .by_dimension("StatementBusinessSegmentsAxis").to_dataframe())
for d in xb.disclosures(): d.title                      # concentration / disaggregation
c.latest("10-K").text(); tk.to_context(detail="standard")
```
