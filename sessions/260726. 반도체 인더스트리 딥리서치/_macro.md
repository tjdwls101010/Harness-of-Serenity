# Macro / regime read — as-of 2026-07-26 (pipeline `macro` run this session)

**Source:** `scripts/serenity_pipeline.py macro`, single run, reused verbatim across the whole cohort.

## Raw gauges (pipeline JSON, no memory numbers)

| gauge | value |
|---|---|
| VIX spot | 18.58 |
| VIX structure | contango |
| Fear & Greed | 39.43 |
| FedWatch next meeting | 2026-07-29 |
| FedWatch probabilities | cut **0.0%** · hold **64%** · hike **36%** |
| BDI z-score | +1.67 |
| DXY z-score | +0.14 |
| MSFT capex (2026-Q1) | $30.876B, +3.35% QoQ — **accelerating** |
| GOOG capex (2026-Q2) | $44.924B, +25.93% QoQ — **accelerating** |
| AMZN capex (2026-Q1) | $44.203B, +11.84% QoQ — **accelerating** |
| META capex (2026-Q1) | $18.997B, −11.16% QoQ — **stable** |

Sum of the four latest *reported* quarters ≈ **$139.0B**. **This is not one synchronized quarter** — three of the four report 2026-Q1 and GOOG reports 2026-Q2, so treat it as a rolling latest-report aggregate, not a period industry total. (Correction applied after the adversarial review flagged the period mismatch.)

**Gap flagged:** this run returned no net-liquidity (Fed BS − TGA − RRP), no ERP, no credit-spread gauge. Pillars ② and ③ are therefore **unread** — no conviction is built on them; treated as a monitoring item, not assumed benign.

## Regime classification (agent judgment — the code does not label this)

**Risk-On on the AI cascade, with a hawkish rate overlay. Not a fear-dislocation, not crisis/wartime.**

- **Pillar ① (load-bearing) is a clean tailwind.** Three of four hyperscalers accelerating, GOOG at +25.9% QoQ. This is a forward-*revenue* move for everything downstream of it (semis → memory → substrates → optics → materials), not sentiment. The AI-trade continuation signal is intact.
- **Not a fear-dislocation.** VIX 18.58 in contango = normal term structure, no forced-seller cascade. Fear & Greed 39.43 is mild fear, not panic. So the V1 "buy when the tape feels worst" trigger is **not** currently firing — this is a hunt-and-stage regime, not a back-up-the-truck regime.
- **Not crisis/wartime.** No cohort rotation warranted; the civilian AI-infrastructure cohort keeps its forward revenue.
- **BDI z +1.67** — physical throughput running hot; corroborates real (not just financial) demand in the materials/logistics layers. Supporting read, not a pillar.
- **DXY z +0.14** — neutral dollar; no meaningful ex-US liquidity tightening or commodity-name pressure from FX this run.

## Rate routing (mandatory, bidirectional — hard stop honored)

Cuts are **priced OUT** on a sourced gauge: cut 0.0%, hold 64%, **hike 36%** for 2026-07-29. The move completes in the "priced out" direction:

- Long-duration growth — high-multiple, far-out-earnings names — gets its DCF marked **DOWN**, and the highest-multiple, least-earnings-backed names take it worst. A 36% hike tail is not a background detail; it is a live re-rating risk on exactly the small-cap, story-priced end of the semi chain.
- The rotation winner in a no-cut regime is the spread-earner cohort (banks/insurers/stablecoins) — outside this book's scope, named for completeness.
- **The operational consequence for this session:** the hawkish overlay is the **dip generator**, not a reason to stay out. Structure (accelerating capex) points up; the discount rate points down on multiples. That divergence is what a scale-in program is built to eat. **Sourced, not asserted:** across the 40+ names priced by `discover` this session, `pct_below_52w_high` ran from −14.5% (APH) to −72.2% (SIVEF), with the AI-semi mid-caps clustered around −25% to −45% (SOXX −19.7%, SMH −16.5% at the index level). So the cohort is *already* in a broad drawdown, and the dispersion between index and single names is the size of the opportunity a staged program harvests. Aggressive on *quality of structure*, disciplined on *entry price* — do not pay a fear-free multiple in a hike-tail tape.

## Evidence availability this session — SEC EDGAR IS DOWN FOR US

`serenity_filings.py` and every direct request to `data.sec.gov` / `www.sec.gov` returned **HTTP 403** from this environment on 2026-07-26. Retried with an explicit `--identity` and again outside the sandbox — same 403. This is an IP-level block at SEC's end, not a config error.

Consequences, which every name in this cohort inherits:
- The `filing_evidence.dossier` field comes back **null** on every `analyze` run. That is an outage, not a company that filed nothing.
- **Do not burn time invoking the `serenity-filings` subagent — it will fail.** Note the gap and move on.
- Any gate whose verdict depends on a filing fact — customer concentration %, country revenue %, and above all the **funded-vs-dilution financing structure** (ATM size, convertible terms, prepayment, offtake-backed debt) — must be marked `conditional:` or `blocked:` with the missing fact named. Do **not** infer the financing structure from memory, from a press release headline, or from a web snippet, and do **not** resolve the gate by assuming either side. Absence of a disclosed ATM is not evidence of contracted capital.
- yfinance-sourced `key_facts`, financials, valuation, market-structure and volatility data are all **unaffected** and remain the source of record for every number.

## Aggression dial for the cohort

**Constructive, staged — and capped one tier below full conviction.** *(Corrected after adversarial review: the original text said "full conviction is allowed on structure," which contradicts the two unread regime pillars and the cohort-wide EDGAR block. An unresolved pre-answer check drops conviction a tier, and here two are unresolved.)* Sizing is not front-loaded. Entries scale in on drawdowns rather than at spot, and the vehicle preference tilts toward elevated-IV harvesting (CSPs at strikes you'd own) over knife-catching shares wherever IV is fat.
