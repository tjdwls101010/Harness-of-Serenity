---
ticker: NBIS
as_of: 2026-07-26
layer: compute-buyer (neocloud — demand node, not semiconductor supply)
archetype: Evolution
stage: 3 (inflection-early)
gates: "blocked: financing structure — EDGAR 403 all session"
tier: UNRESOLVED
conviction: not assigned — gate 3 unproven
vehicle: not assigned until the gate resolves
held: yes
---

# NBIS — the gate that decides this name could not be opened

**TLDR:** UNRESOLVED, and that is the honest output, not a dodge. The revenue ramp is one of the most extreme in the cohort — 50.9 → 399 M/quarter in four quarters. But real FCF is −$3.76B, SBC is 15.7% of revenue, and there is a $9.37B cash pile whose *origin* decides the entire thesis. Whether that cash is customer-funded or self-minted is exactly what the Evolution archetype's gate 3 asks, and SEC EDGAR returned 403 to every request this session. I will not guess it in either direction.

## Structural position (Evolution — and note it is NOT a chokepoint)

NBIS is a neocloud: an AI compute capacity provider. It is on this map as the **demand node**, not as semiconductor supply. It does not own a physical chokepoint; it *buys* from the chokepoints. Forcing it down the bottleneck funnel would mis-frame it from the first move.

The correct archetype is Evolution: a datable step-change (hyperscaler capacity overflow) made a category fundable, and the question is who owns the position as it forms. Its gates:

1. **The datable step-change — pass.** Hyperscaler capex is accelerating (three of four, GOOG +25.9% QoQ, ~$139.0B combined in the latest quarter). Overflow demand into neoclouds is real, and the revenue trajectory confirms it landed here.
2. **Owning the emerging standard — partial.** Capacity is capacity. There is no standard being owned; the differentiation is execution and cost of capital.
3. **Strategic backstop — BINARY, and BLOCKED.** See below.

## Gate 3 — why it is blocked, and why that blocks everything

The doctrine on this gate is unambiguous: a contracted, customer-funded backlog (a prepayment, an above-market strategic equity round, asset-backed debt secured on an offtake) clears it. A buildout funded by an at-market ATM or serial dilution does **not** — that name carries the de-risking story without the de-risking, and grades down.

Two neoclouds wearing an identical "we have a hyperscaler contract" headline can sit on opposite sides of that line. **The line, not the headline, is the call.**

Settling it requires the financing structure from the filings: ATM size and whether it is live, convertible terms, prepayment language, whether any debt is non-recourse and secured on an offtake. `serenity_filings.py` and direct requests to both `data.sec.gov` and `www.sec.gov` returned **HTTP 403** — retried with an explicit identity and again outside the sandbox. IP-level block at SEC's end.

Three disciplines apply and I am holding all three:
- **A silent filing is not a funded confirmation.** Absence of a disclosed ATM is not evidence of contracted capital. Both calls need positive evidence; absence proves neither.
- **A fat balance sheet built from at-market issuance is not a floor.** $9.37B of cash cannot be credited until it is netted against the shares it cost and the SBC it funds.
- **Aim the scepticism hardest at the name you like** — and this is a held position with a spectacular growth chart, which is precisely when the gate matters most.

So: gate 3 is **UNPROVEN**, conviction is capped there, and the name is not tiered.

## Numbers (pipeline, 2026-07-26)

MC $47.67B · EV $48.31B · price $187.77 · 52-week $50.00–$299.86 · 50-day $226.92 · 200-day $139.95
Revenue TTM $878M · GM 72.1% · **OM −32.1%** · cash $9,373M · net debt +$1,295M · total assets $12,431M · book value $28.27
**EV/Rev 55.0×** — by far the highest in the cohort
Forward P/E, 2-year P/E and PEG all **null** — no earnings to anchor on
Short 0.3% of float · beta 1.40 · **IV30 159.4, IV rank 92.1**, typical daily move 7.9%
**SBC 15.7% of revenue · real FCF −$3,764.4M**
Insider flow: 21 sells, 0 buys, $156.8M sold in 12 months.

Revenue: 50.9 → 100.7 → 146.1 → 227.7 → **399.0** M/quarter (roughly 8× in four quarters).
Operating margin: −236.4 → −101.3 → −89.1 → −109.8 → **−32.1** — improving fast, still deeply negative.

Step 0a: total assets $12,431M against cash $9,373M is internally coherent (this is a cash-dominated balance sheet, as expected for a name that has raised a lot). No collision or stale-period signature. The integrity question here is not whether the number is right — it is **where the cash came from**, which is a filings question, not a feed question.

## Valuation — the lens cannot be run, and saying so is the finding

The archetype calls for an asset-financed lens: a unit model from revenue/GPU-hr → $/MW-year → itemised COGS → gross profit/MW → **levered IRR after financing**. That lens is explicitly a *financing* lens — the levered IRR is the whole point, because a thin gross margin on a prepaid, debt-funded asset is a financing artifact rather than an economics verdict.

`Lens: NOT RUN — the levered-IRR denominator requires the financing terms (prepayment %, debt cost, recourse), and those terms were unobtainable (EDGAR 403).`

I could compute an EV/Rev of 55.0× and call it expensive. That would be the wrong lens applied confidently, which is worse than no lens: the standalone multiple is exactly the consensus read this archetype is built to defeat. **A named-but-unrun lens is not a verdict.** No priced/cheap/pass call is issued.

What *can* be said without the filings: 72.1% gross margin is genuinely high for compute capacity and is the strongest single number here; −$3.76B real FCF and 15.7% SBC are genuinely heavy; and 55× EV/Rev leaves no margin for execution error.

## Cycle stage — 3

Operating margin improving from −236% to −32% on 8× revenue is a real inflection. It is stage 3, not 4 — FCF has not converted, and the stage-3→4 migration *is* the hold thesis for this archetype. Holding through capex-burn ugliness is the thesis; capitulating into it is the error. But that only holds if gate 3 is clean, which is unknown.

## Downsides

- **Gate 3 unproven.** If the build is ATM-funded, the de-risking story is unsupported and the name grades down hard. *Not priced in, and not resolvable this session.*
- **Dilution mechanics.** 15.7% SBC on revenue is very heavy; combined with −$3.76B real FCF, the share count is a live variable. *Not priced in.*
- **55× EV/Rev.** Prices execution as a base case. *Partly priced in* — the name is 37.4% off its high.
- **It is not a chokepoint.** In a hyperscaler capex pause, the demand node takes the hit before the physical bottlenecks do. *Not priced in.* This is also why it should not be sized like the equipment and inspection names.

## Rating

**UNRESOLVED — no tier, no rating, no vehicle.** This is not a hold-by-default and not a sell-by-default. It is a name whose single decisive fact was unavailable.

**The action item is concrete and small:** when EDGAR is reachable, run the `serenity-filings` subagent on the most recent 10-Q and any 8-K/424B, and answer exactly three questions — (1) is there a live at-market ATM, and how large relative to market cap; (2) is any capacity funded by customer prepayment or by debt secured on an offtake, non-recourse to the parent; (3) what did the $9.37B cash cost in shares. Those three answers tier this name in about ten minutes.

Comparatively: NBIS is the *demand* end of this whole map. Every layer in `_sectormap.json` sits upstream of it, and several of them — packaging equipment, test, inspection — capture the same buildout with positive operating margins, positive FCF and no financing question at all.

NFA.
