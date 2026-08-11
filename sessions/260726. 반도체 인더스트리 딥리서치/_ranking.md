# Semiconductor chain — accumulate ranking, 2026-07-26

**Listing-scope exception:** this cohort is US-listed except for **000660.KS (SK Hynix, KRX)**, added at the user's explicit request. CLAUDE.md's US-listed default is overridden by instruction, not by inference. Its US line, SKHY, is the same underlying and is noted alongside it.

Cohort: 24 names across 30 mapped layers (`_sectormap.json`). Regime: `_macro.md`. Layer reasoning: `_sectormap.md`. Independent cross-check: `_codex_sectormap.md`.

**The question this ranks for is not "what do I buy today."** It is: *which names do I want to be systematically adding to when they are down 30–50%?* That changes the ordering. Structure quality and stage decide membership and weight; the valuation band decides *where* you add, not *whether* the name qualifies.

## Protocol deviation — declared

The Rank-N protocol calls for one `serenity-scorecard` agent per name so each is judged in a fresh context. **The fan-out could not run**: the machine refused new agent processes (`fork failed: Device not configured`) with seven research agents already resident, on two separate attempts. Scorecards were therefore filled **inline in the main thread** from the same pipeline evidence, same schema, same precedence. The cost is real and I am naming it: inline scoring means every name was judged in a context that had already seen the others, so cohort contamination is possible in a way the fan-out is designed to prevent. Tier assignments below were written from each name's own evidence block before the table was ordered, which is the mitigation, not a cure.

Per-name detail files were written for the six positions actually held. The remainder are scored in the table.

## Evidence limits — read first

- **SEC EDGAR returned 403 to every request** (retried with identity, and outside the sandbox). No customer concentration, no country revenue split, and **no financing-structure read**. The funded-vs-dilution gate could not be run on any name. Where it is load-bearing, the name is marked `blocked:` and is NOT tiered.
- Two of four regime pillars (net liquidity, credit) were not returned by the macro pipeline.
- **ADR financials are corrupted in the pipeline.** `analyze ATEYY` returns EV of −$195.34B and `analyze DSCSY` returns −$244.09B, because market cap comes back in USD while the financial statements come back in JPY. Their prices and market caps are usable; **every ratio built on their financials is garbage** and none is quoted here. This is a Step-0a data-integrity hard block, not a valuation.
- All figures are from the pipeline run of 2026-07-26 and **expire**. Re-run before acting.

## The two lenses, applied identically to every name

- **Floor leg** (where it trades if growth stopped): `latest-quarter revenue × 4 × current operating margin × 0.85 tax ÷ shares × 15` → a no-growth EPS at a no-growth multiple.
- **Upside leg** (PEG-fair on consensus): `2-year consensus EPS × min(2y EPS growth %, 40)` → what the name is worth if consensus is right and it re-rates to PEG ≈ 1.

Shares are derived as `market cap ÷ price` from `key_facts`; 2-year EPS is derived as `price ÷ forward_pe_2y`. Both legs are run on every name that carries a verdict. **The gap between the two legs is the accumulate band.**

---

## Tier cut

**Tier 1** = genuine physical bottleneck or qualification gate (not a design slot) · stage 3–4 with margin expansion visible in its own trajectory · no disqualifying insider or dilution signal · a floor leg that leaves room to add. **Tier 2** = one of those four is weak or unresolved. **Tier 3** = structure is real but the name is not inflecting, or valuation leaves no accumulate band. **EXIT/TRIM** = own trajectory is rolling over. **EXCLUDED** = fails a binary gate. **UNRESOLVED** = a hard block this session's evidence could not clear.

---

## The table

| ticker | tier | rung | gates | one-line why |
|---|---|---|---|---|
| KLIC | 1 | 4 | pass | Bonder supply is the qualification gate on every packaging capacity add; OM −27.7%→+15.9% over five quarters at only 6.3× EV/Rev |
| TER | 1 | 4 | pass | Test time per die rises faster than unit volume; OM 19.7%→37.2%, revenue 686→1,283 M/q |
| TSEM | 1 | 3→4 | pass | **$1.3B of 2027 SiPho revenue contracted + $290M customer prepayments** against $1,622M TTM revenue; GM 20.4%→26.8%, OM 9.2%→15.6%, 1 insider sale in 12 months. Best-evidenced Tier 1 in the cohort |
| BESIY | 1 | 4 | conditional: ADR liquidity unverified | Hybrid bonding — the step HBM4-class stacking runs through; OM 27.2%→43.5%, revenue 144→250/q. Rung-1 ADR |
| ONTO | 2 | 3 | pass | Inspection is the qualification gate on new package architectures; steady 21.7% growth, no insider selling, but not inflecting hard |
| GFS | 2 | 3 | pass | Cheapest structural name in the cohort at 4.1× EV/Rev; GM 22.4%→27.6% on flat revenue — an early margin inflection, plus a US-jurisdiction footprint |
| MKSI | 2 | 3 | conditional: $3.77B net debt | The broadest "complexity tax" on process steps, at 6.4× EV/Rev — but the leverage is a live problem in a hike-tail regime |
| CRDO | 2 | 4 | conditional: design-slot risk | Best consensus upside in the cohort, OM 20.4%→35.7% — but it is a design slot removable in one platform decision, at 28.7× EV/Rev |
| LITE | 2 | 4 | conditional: 10.8% annual dilution | Textbook stage-4 (OM −15.4%→+21.8%), but SBC is 10.8% of revenue, real FCF −$281.9M, net debt +$2.09B, and it sits at PEG-fair already |
| 000660.KS | 1 | 4 | conditional: cycle-stage | **HBM share leader, sold out into 2027**, revenue 3× and OM 42.2%→71.5% in five quarters, −41.1% off its high, zero insider selling. Trades at ~9.8× annualised peak-quarter earnings with a floor leg 54% ABOVE spot. Non-US listing, included at explicit user request; SKHY is the same underlying |
| MU | 1 | 4 | conditional: cycle-stage | **Upgraded from Tier 2.** Same peak-margin caveat, but at ~9.2× annualised peak-quarter earnings with a floor leg 63% above spot — the market has already discounted a large normalisation. My earlier Tier 2 generalised from SNDK's arithmetic, which does not transfer |
| FORM | 3 | 3→4 | pass | Probe cards are a genuine hybrid bottleneck, but 2-year consensus EPS growth is only 14.5% and the price already implies far more |
| AAOI | 3 | 3 | conditional: no margin inflection | Revenue ramping 99.9→151.1/q, but operating margin has been NEGATIVE in all five quarters and gross margin is flat ~30% — the ramp is not converting |
| AXTI | 3 | 3 | conditional: moat-vs-hostage unresolved | The recursive bottom hop under lasers, and GM went −6.4%→+29.6% — but 31.8× EV/Rev, $78.1M insider selling across 31 sales with zero buys, and the China footprint cuts both ways |
| SNDK | 3 | 4→5 | conditional: peak-cycle margins | 78.4% gross and 70.0% operating margin are not a durable state, and **the floor leg computed on those margins equals today's price exactly** — ~15.0× annualised peak earnings versus 9.2× for MU and 9.8× for SK Hynix. Within memory, this is the one priced for permanence |
| RMBS | 3 | 3 | pass | High-quality standards toll at 80% gross margin, but revenue has been flat five quarters — quality without inflection |
| ENTG | 3 | 3 | conditional: ~$3.3B net debt | Consumables scale with wafer starts, but revenue is flat and the balance sheet is levered |
| CAMT | 3 | 3 | pass | Same layer as ONTO, flat revenue five quarters and flat margins — ONTO is the better expression of the identical thesis |
| SLOIY | 3 | 3 | conditional: ADR execution | Photonics-SOI wafers one hop below the silicon-photonics foundry — participates whichever foundry wins; ADR tradeability is the constraint |
| SIVEF | 3 | 2 | conditional: OTC execution | CW laser for CPO, the most-discussed name in the thesis DB; foreign micro-cap, OTC spread paid on every tranche of a scale-in |
| LPKFF | 3 | 2 | conditional: OTC execution | LIDE glass-core via drilling — a genuine tool chokepoint at micro-cap scale; liquidity, not the thesis, is the binding problem |
| IQEPF | 3 | 2 | conditional: OTC execution | Compound-semi epiwafers, the hop between substrate and laser die |
| XFABF | 3 | 3 | conditional: OTC execution | Specialty foundry with photonics and MEMS; a smaller, cheaper TSEM analog |
| AMKR | EXIT/TRIM | 5 | fail: own trajectory | Revenue rolled over 1,987→1,888→1,685/q with gross margin 16.7%→14.2%, against **$1.009B of insider selling** on a $16.1B cap. The NVIDIA US-packaging headline is real; the trajectory contradicts it |
| VICR | EXIT/TRIM | 5 | fail: own trajectory | GM 65.3%→55.2% and OM 32.2%→15.0% while revenue went sideways, against **$373.8M of insider selling across 99 sales** on a $9.6B cap |
| PLAB | EXCLUDED | 5 | fail: no economic capture | Revenue flat five quarters, gross margin 36.9%→31.3%, operating margin 26.4%→20.1%, 44 insider sales and zero buys. A concentrated layer whose listed merchant captures none of the AI economics |
| WOLF | EXCLUDED | — | fail: V2 binary | Negative gross margin (−17.4%). If it is anything it is a replacement-cost turnaround, and the bear case is dilution, not demand |
| NBIS | UNRESOLVED | 3 | **blocked:** financing structure | Revenue 50.9→399 M/q in four quarters is extraordinary, but real FCF is **−$3.76B**, SBC is 15.7% of revenue, and the $9.37B cash pile cannot be sourced without filings. The funded-vs-dilution gate IS the thesis here and EDGAR was down |
| ATEYY | UNRESOLVED | — | **blocked:** data integrity | Rung-1 ADR for the HBM-test share leader. Pipeline returns EV of −$195.34B from a USD/JPY mismatch — no ratio is trustworthy until reconciled |
| DSCSY | UNRESOLVED | — | **blocked:** data integrity | Rung-1 ADR for the grind/dice near-monopoly; highest gross margin of any tool name checked. Pipeline returns EV of −$244.09B from the same currency mismatch |

---

## Lens lines — the arithmetic, run on both legs

Each name gets both legs. The floor is where it trades if growth stops; the upside is PEG-fair on consensus. **Accumulate band** is the zone between the floor and the midpoint to today's price.

**KLIC** — $101.33
`Lens (floor): 242.6 × 4 × 0.159 × 0.85 ÷ 52.3M × 15 = $37.60` (−63%)
`Lens (upside): 4.24 × 26.4 = $111.94` (+10%)
Read: on consensus, KLIC is roughly *fairly* valued — the upside leg is thin. The thesis is that consensus underrates a packaging-capex cycle where bonder lead time gates every capacity add. That makes it a Tier 1 to **accumulate into weakness**, not to chase. Band **$38–69**.

**TER** — $349.92
`Lens (floor): 1282.5 × 4 × 0.3715 × 0.85 ÷ 156.6M × 15 = $155.17` (−56%)
`Lens (upside): 10.29 × 40.0 = $411.60` (+18%)
Read: the best floor-to-price ratio of any Tier 1, on the strongest margin expansion. Band **$155–253**.

**TSEM** — $233.37 *(held)*
`Lens (floor): 413.6 × 4 × 0.1561 × 0.85 ÷ 113.0M × 15 = $29.13` (−88%)
`Lens (upside): 5.83 × 40.0 = $233.20` (−0%)
Read: **already exactly at PEG-fair on 2-year consensus.** The business is inflecting cleanly and the insider record is the cleanest in the cohort, but the price has caught up. Hold, do not add here. Band **$29–131**.

**BESIY** — $256.25
Floor leg cannot be run: the pipeline mixes a USD market cap with EUR financials, so a computed EPS would be wrong. What survives: revenue 144.1→249.9 per quarter and operating margin 27.2%→43.5%, both from the same statement basis, so the *trajectory* is sound even where the *ratio* is not.
`Lens (relative): EV/Rev ≈ 28× — the most expensive tool name checked, against the fastest margin expansion`
Read: Tier 1 on structure, and explicitly **not** on a run valuation. Do not size before reconciling the currency basis and the ADR's real spread.

**ONTO** — $272.62 *(held)*
`Lens (floor): 1030.6 × 0.1675 × 0.85 ÷ 49.7M × 15 = $44.29` (−84%)
`Lens (upside): 9.95 × 38.3 = $381.08` (+40%)
Read: a real +40% consensus gap with no insider selling and IV rank 84.6. The best risk-adjusted *add* among the holdings. Band **$44–158**.

**GFS** — $53.53
`Lens (floor): 1634 × 4 × 0.1102 × 0.85 ÷ 548.7M × 15 = $16.74` (−69%)
`Lens (upside): 2.51 × 32.4 = $81.32` (+52%)
Read: cheapest structural name in the cohort at 4.1× EV/Rev, with margins inflecting on flat revenue — which is the shape that precedes an earnings inflection. Band **$17–35**.

**MKSI** — $329.18
`Lens (floor): 1078 × 4 × 0.1438 × 0.85 ÷ 67.5M × 15 = $117.12` (−64%)
`Lens (upside): 15.38 × 30.8 = $473.70` (+44%)
Read: good gap, but the floor leg ignores that **EV exceeds market cap by $3.73B**. In a regime pricing a 36% hike probability, that leverage is the bear case. Band **$117–223**.

**CRDO** — $213.15
`Lens (floor): 437 × 4 × 0.3566 × 0.85 ÷ 186.5M × 15 = $42.61` (−80%)
`Lens (upside): 9.07 × 40.0 = $362.80` (+70%)
Read: the largest consensus gap in the cohort. Discounted to Tier 2 not on numbers but on **class** — a retimer is a design slot, and $478.7M of insider selling across 81 sales is not a rounding error. Band **$43–128**.

**LITE** — $762.99 *(held)*
`Lens (floor): 808.4 × 4 × 0.2172 × 0.85 ÷ 77.8M × 15 = $115.11` (−85%)
`Lens (upside): 18.34 × 40.0 = $733.60` (−4%)
Read: **at or slightly through PEG-fair on consensus.** Superb operating trajectory, but the 10.8% annual dilution and −$281.9M real FCF mean the equity is being paid for partly by shareholders. Hold; do not add here. Band **$115–439**.

**SNDK** — $1,436.56
`Lens (floor): 5950 × 4 × 0.6998 × 0.85 ÷ 148.1M × 15 = $1,433.86` (−0%)
`Lens (upside): 214.41 × 40.0 = $8,576.40` (+497%)
Read: **both legs are the same warning.** A no-growth floor computed on *current* margins lands within $3 of the spot price — the market is already capitalising 70% operating margins as permanent. And a +497% upside leg is not a target, it is proof that the 2-year consensus EPS of $214.41/share is a peak-cycle extrapolation. The absurd verdict is a cue to distrust the lens inputs, never a license for the trade.

**AXTI** — $47.23
`Lens (floor): 26.924 × 4 × (−0.0589) = negative — no floor exists; operating margin is still below zero`
`Lens (upside): 0.78 × 40.0 = $31.20` (−34%)
Read: consensus 2-year EPS implies a price *below* spot at a PEG-fair multiple. 31.8× EV/Rev on a 21% gross-margin substrate maker, with the crystal-growth footprint in a jurisdiction that cuts both ways. IV30 173.6% — if owned at all, sell puts, do not buy shares.

**AMKR** — $64.96
`Lens (floor): 1684.7 × 4 × 0.0595 × 0.85 ÷ 247.8M × 15 = $20.63` (−68%)
`Lens (upside): 2.57 × 20.9 = $53.71` (−17%)
Read: PEG-fair is *below* spot, on a trajectory that has rolled over, against $1.009B of insider selling. Both legs point the same way.

---

## The memory call — the most important judgment here, and it is contrarian

MU and SNDK screen as the two cheapest names in the entire cohort: MU at forward P/E 12.5 one-year and **6.0** two-year with 84.0% revenue growth and 72.6% gross margin; SNDK at 21.5 and **6.7** with 151.4% revenue growth. On PEG they are absurd — 0.02 and 0.01. Every screen in existence says buy.

I do not think they are the right names for a **multi-year accumulate program**, and the reason is not valuation, it is the denominator.

The doctrine on this is explicit: an expanding margin is *not* by itself a late-cycle sell — you flip only when the price index actually rolls over. So I sourced it rather than guessing. TrendForce, dated:

- 3Q26 conventional DRAM contract prices: **+13–18% QoQ** — still rising, but this follows a 1Q26 in which DRAM industry revenue rose **81% QoQ**. The second derivative has turned hard.
- 3Q26 NAND: **+10–15% QoQ**, described as *"a noticeably slower pace than in previous quarters."*
- The 3Q26 note attributes the moderation to *"weaker demand from consumer applications and the impact of a higher comparison base."*

> ### CORRECTION — a load-bearing claim of mine was not sourced
>
> An earlier version of this section asserted that **HBM contract prices were expected to shift into year-over-year decline**, and used it as a pillar of the bear case. **That claim does not survive.** It came from a search-engine *summary*, not from a primary source; when the underlying TrendForce 3Q26 article was actually fetched it gave **no HBM price direction at all**. A dedicated research agent then looked for it independently and reported: *"I found NO source stating HBM contract prices turn YoY negative. Do not rely on it."*
>
> This is precisely the failure mode the doctrine names — a web snippet standing in for a number, inverting a call while looking authoritative. Retracted.
>
> The sourced evidence in fact runs the **other** way on HBM supply: the shortfall is **widening** — roughly 5% (2025) → 6% (2026) → 9% (2027) — with no supply/demand balance projected until 2Q28. That is a bull argument, and it is now on the record against my own call.

**What survives, and the better bear argument that replaced it.** The deceleration is real and sourced. And there is a stronger, dated bear point I did not have before: from 3Q26, **US CSP multi-year LTAs contractually CAP pricing** — increases now come only from non-LTA customers and from incremental supply sold outside the LTAs. So the very contracts that de-risk 2026–27 *revenue* also cap the *price* upside, exactly as consensus extrapolates from an +81% quarter.

Against that, the sold-out horizon passes the funded test cleanly, which I must credit: Micron's 2026 HBM is fully sold under 3–5 year LTAs backed by roughly **$22B of customer prepayments**. That is third-party capital at risk, not a company selling stock — the discriminator resolves *bullish*.

Two consequences:

1. **Prices are still rising, so kill signal #6 has not fired.** Not an exit. MU stays Tier 2.
2. **The bear case is now about the price *ceiling*, not a price *decline*** — LTAs capping realised pricing into a consensus that extrapolates peak margins. Weaker than what I originally claimed, and I am saying so rather than quietly restating it.

Now put that against SNDK's own numbers: gross margin went 22.5% → **78.4%** and operating margin −2.5% → **70.0%** in five quarters. A 70% operating margin in NAND is not a business quality, it is a shortage. The floor-leg arithmetic above capitalises exactly that margin at a no-growth 15× and lands at $1,433.86 against a $1,436.56 price. **The market is already paying for permanence.** If margins normalise even halfway toward the 22–30% these businesses print mid-cycle, that floor halves.

So: for a program whose entire premise is adding on every drawdown, memory is the worst possible fit — because the drawdown you would be averaging into is a *margin* drawdown, where the earnings fall with the price and the multiple never actually gets cheap. That is the classic late-cycle value trap, and the 0.01 PEG is its disguise.

**The bull case I owe against my own call** — and it is stronger than it was an hour ago: the HBM shortfall is widening rather than closing, no balance is projected until 2Q28, the sold-out book is customer-prepaid, and eSSD started its cycle roughly a year after DRAM so it sits earlier on its own curve. If AI inference structurally re-rates memory into a permanently tighter balance, these margins are the new normal, the 2-year EPS is real, and I will have passed on the cheapest large caps in the market.

**Revised falsifier, dated:** the ~October 2026 TrendForce 4Q26 guide. **If it prints single-digit or negative QoQ for conventional DRAM, the deceleration thesis is confirmed. If it prints another double-digit rise, this call is wrong** and memory goes to Tier 1. Watch that guide, not the earnings print.

### SECOND CORRECTION — I over-generalised from SNDK

Running the identical floor arithmetic across all three memory names, rather than one, inverts part of the conclusion:

*(A list, not a table — the `rankdiff` parser reads any tier-shaped table in this file.)*

- **MU** — ~**9.2×** annualised peak-quarter earnings · floor leg **+63%** vs spot · **−26.6%** off its 52-week high
- **SK Hynix (000660.KS)** — ~**9.8×** · floor leg **+54%** · **−41.1%** off its high
- **SNDK** — ~**15.0×** · floor leg **+0%** · **−39.0%** off its high

`Lens: MU no-growth floor — 41.46 × 4 × 0.8037 × 0.85 ÷ 1,129.4M × 15 = $1,504.50` (+63% vs $920.95)
`Lens: SKH no-growth floor — 52.58조 × 4 × 0.7153 × 0.85 ÷ 709.85M × 15 = ₩2,702,073` (+54% vs ₩1,759,000)
`Lens: SNDK no-growth floor — 5950 × 4 × 0.6998 × 0.85 ÷ 148.1M × 15 = $1,433.86` (+0% vs $1,436.56)

The "market is pricing peak margins as permanent" finding is **true of SNDK and false of the other two.** MU and SK Hynix trade at roughly nine-and-a-half times *peak-quarter* earnings, which already embeds a large normalisation; SNDK trades at fifteen, which does not. I built the general claim on the one name whose arithmetic I had run first — a straightforward reasoning error, and the reason the same lens has to be run on every name rather than one exemplar.

**Consequence: MU upgraded Tier 2 → Tier 1 (conditional), SK Hynix enters at Tier 1 (conditional), SNDK stays Tier 3.** The cycle-stage condition applies to all three; the valuation gap between them does not.

**How much conviction the deceleration argument deserves now:** less than when I wrote it. One of the two legs was retracted, and the surviving leg — LTA price caps against peak-margin extrapolation — is an argument about the *ceiling*, not about a decline. Read the memory call as "do not treat the 0.01 PEG as a green light for a scale-in," not as "memory is about to break."

---

## What actually changes about the portfolio

Current holdings: NBIS, TSEM, LITE, ONTO, SK Hynix, AAOI.

**The single biggest structural observation:** four of the six sit in the *same* two layers — optical interconnect (LITE, AAOI) and the silicon/inspection layer serving it (TSEM, ONTO) — and NBIS is the demand node that buys from all of them. That is not six positions. Read one hop down, it is close to **one bet on the optical-interconnect buildout**, which is exactly the hidden single-point-of-failure the macro lens warns about. A CPO-versus-pluggables architecture decision, or a single hyperscaler's optical roadmap slipping, hits four of six at once.

Per name:

- **TSEM** — hold, stop adding. Cleanest insider record in the cohort and a real margin inflection, but the lens puts it exactly at PEG-fair. Re-add under ~$131.
- **LITE** — hold, stop adding. Best operating trajectory of anything here, but at/through PEG-fair, and the 10.8% dilution means the share count is working against you between now and then. Re-add under ~$439.
- **ONTO** — **the one holding worth adding to.** +40% consensus gap, zero insider selling, and the inspection layer is a qualification gate rather than a design slot. IV rank 84.6, so sell puts rather than buy shares.
- **AAOI** — the weakest holding on evidence. Revenue is ramping but operating margin has been negative in all five quarters and gross margin is flat at ~30%, while LITE in the same layer went from −15.4% to +21.8%. Same demand, one converting it and one not. Do not add until gross margin moves; IV 141.4% makes covered calls the sensible way to hold it.
- **SK Hynix** — **CORRECTED. A rung-1 US line exists and I missed it.** SK Hynix listed ADSs on NASDAQ as **SKHY** on 2026-07-10 (424B4, CIK 0002120882; 177.9M ADSs at $149.00; cornerstone demand ~$7B). I had tested SKHYY, HXSCL and SKHYF, all of which returned nothing, and wrongly concluded no line existed — I never tested the four-letter ticker. Verified live: **SKHY $154.57, MC $1,097.2B, forward P/E 6.3 (1y) / 3.8 (2y), revenue +49.0%, gross margin 68.3%, −20.7% from its 52-week high.**
  Two traps on it: **1 ADS = 1/10 of a common share**, so the position size is not what a KRX-share instinct will tell you; and it adds **zero diversification** to a holder of the KRX line — it is the same underlying, not a second position. Its real use is if you ever want the exposure inside a US account. As a first-time US filer it now has fresh English-language disclosure worth reading for LTA and prepayment terms once EDGAR is reachable.
- **NBIS** — **UNRESOLVED, and that is the answer.** Real FCF −$3.76B and SBC at 15.7% of revenue against a $9.37B cash pile whose origin cannot be verified with EDGAR down. Whether that cash is customer-funded or self-minted is the entire thesis, and I will not guess it in either direction. Resolve it from the filings before adding a dollar.

**What the portfolio is missing** — every one of these is a layer it has no exposure to at all: packaging equipment (KLIC), test (TER), hybrid bonding (BESIY), the complexity tax (MKSI), and the US-jurisdiction foundry (GFS).

---

## Build order for a scale-in program

Not buy recommendations at spot — a sequence, with the band each becomes interesting in.

1. **ONTO** — add on weakness, band $44–158. The only current holding with a real gap.
2. **TER** — start, band $155–253. Best floor-to-price of the Tier 1s.
3. **KLIC** — start small, band $38–69. Best structure, thinnest consensus upside, so this one specifically wants patience.
4. **GFS** — start, band $17–35. Cheapest structural name, margins turning.
5. **TSEM** — **upgraded: add on weakness.** The $290M of customer prepayments and $1.3B contracted 2027 book are documented reasons my upside leg's consensus input is stale. Band wider than the lens's $29–131 suggests; do not wait for $131.
6. **LITE** — hold, resume below $439. NVIDIA's $2B with capacity-access rights makes that level more likely to hold.
6. **BESIY** — research first. Best layer on the map; resolve the ADR spread and the currency basis before sizing.
7. **MKSI, CRDO** — Tier 2 for named reasons (leverage; design-slot class). Bands above.
8. **MU** — **upgraded to a genuine accumulate candidate.** At ~9.2× annualised peak earnings with the floor leg 63% above spot, the margin normalisation is already largely priced. Still governed by the dated TrendForce falsifier, so stage the entry rather than front-loading it.
9. **SK Hynix (000660.KS)** — already held; hold and add on further weakness, not at spot. Bear leg is −64% on a mid-cycle normalisation, which is what the staging is for. Shares only — no IV feed on the KRX line, so no CSP ladder. **SKHY is the same underlying and adds no diversification.**
10. **SNDK** — the one memory name to leave alone. Priced for permanence at ~15× peak earnings.

**Vehicle note.** IV rank is elevated across almost the entire cohort — ONTO 84.6, KLIC 94.6, MKSI 96.4, TER 87.7, TSEM 96.0, RMBS 96.5, FORM 94.9, AXTI 70.1, NBIS 92.1. In the 65–100% IV zone the doctrine is cash-secured puts at strikes you would happily own, not shares. That is the right instrument for this whole exercise: you get paid to wait for the band instead of catching the knife. **Check days-to-earnings before writing any of them** — never inside ~7 days.

---

## Post-delivery corrections — seven research agents reported after the ranking was written

Their sourced findings changed four calls. Recorded as corrections rather than folded in silently.

**1. AXTI — moat-vs-hostage is RESOLVED, and it resolves toward hostage.** I left this open as the crux of the name. The evidence: AXT's China plants require **MOFCOM export permits with roughly a 60-business-day cycle, and those permits directly capped Q4'25 revenue**. That is a state holding a lever over *this name's own shipments* — the positive evidence the doctrine requires before demoting a merchant chokepoint from moat to hostage. Scarcity you cannot reliably ship is not monetisable. **Stays Tier 3, now for a proven reason rather than an open question.**

**2. LITE — a genuine funding price floor I did not have.** On **2026-03-02 NVIDIA invested $4B, $2B each into Lumentum and Coherent, each with a multi-billion purchase commitment plus future capacity-access rights**; the reported consequence is non-NVDA EML lead times pushed past 2027. That is a sophisticated counterparty putting capital at risk (~3.4% of LITE's market cap) inside the last six months, and it is simultaneously moat evidence and a soft floor. It does not change the valuation arithmetic — the upside leg is still −3.9% — so **LITE stays Tier 2 and "stop adding" stands**, but the *quality* of the business underneath that call is better than I scored it, and the re-add level is more likely to hold.

**3. KLIC's "most levered to advanced packaging" claim is not evidenced — CAMT and ONTO are.** The equipment agent's correction is fair and I accept it: **CAMT disclosed roughly 70% of Q1'26 revenue from advanced packaging** (~50% AI) and **ONTO reports packaging at >50% of 2026 revenue**, while **KLIC's packaging revenue share is undisclosed** in anything sourced — it is a pure-play by *product category*, not by verified revenue share. Worse for the thesis: **concentration at the bonder hop is FALLING**, not rising — AMAT has invested in Besi, ASML is reportedly evaluating entry, Korean makers are pushing in. A layer being de-monopolised while I tag it a bottleneck is the exact error the review warned about.
**Consequence:** KLIC's structural case is weaker than written. It keeps Tier 1 on its own margin trajectory (OM −27.7%→+15.9% is its own evidence), but the "cleanest bottleneck on the map" framing is withdrawn. **ONTO's case strengthens** — inspection captures the packaging ramp without having to pick the bonder winner, and its packaging share is actually disclosed. That reinforces ONTO as the best add.
This also softens **BESIY**: hybrid-bonding backlog is up 105% YoY, but if AMAT and ASML are entering, the monopoly framing has a clock on it.

**4. The substrate-materials layer is even tighter than mapped — and still unownable.** Now sourced: **Ajinomoto ABF >95% share** with a ~30% price increase notified for Q3-2026 and no meaningful new capacity until the 2030s; **Nittobo ~90% of certified T-glass**, no new capacity before mid-2027; **Mitsui Kinzoku >40% of AI-server HVLP copper foil** against a 28–39% industry shortfall through 2028; **micro drills a two-supplier duopoly** where Unimicron and GCE just took strategic stakes in Topoint — customers funding their own supplier's capacity, which is the replication-funding tell. Meanwhile **the CoWoS gap is CLOSING, ~20%→~10% by end-2026**. Both halves confirm the map's structure: the packaging headline is a fundable constraint, the durable chokepoints are two layers below it, and none has a clean US line.
**One contrarian catch worth acting on:** the 2026 laminate/CCL price spike is **not purely AI demand** — an April-2026 strike at SABIC's Jubail complex took offline the line supplying ~70% of electronic-grade PPE/PPO resin. Any CCL/PCB margin re-rate read as structural AI pull is partly a repairable-plant artifact. **That is a direct warning on TTMI, ROG and PKE**, all of which I listed as substrate-adjacent routes.

**New names surfaced, not scored:** **ESI** (Element Solutions — IC-substrate and RDL via-fill plating chemistry; the cleanest pick-and-shovel on the substrate layer), **ASMVY** (ASMPT ADR — the TCB bonder leader, which I had wrongly put at rung 3; bookings +71.6% QoQ), **SKHY** (above), **LWLG** (pre-revenue, no volume revenue guided before 2027 — lottery sliver at most), **CIEN**, **NDSN**, **PENG**. Also flagged and worth noting: **optical isolators** are an unmodelled chokepoint — Granopt cut Faraday-rotator capacity in April 2026, lead times went from weeks to 6–9 months, and the TGG garnet feedstock is exposed to China's January-2026 rare-earth controls. **No US pure-play exists**; it is a rung-4 map node and a leading indicator for the whole 1.6T ramp.

**5. TSEM — the single most consequential finding of the session, and it upgrades a holding.** Sourced from company press releases (a legitimate CONFIRMED channel even with EDGAR down): **$1.3B of 2027 silicon-photonics revenue already under contract, plus $290M of customer prepayments for capacity reservation**, >50 active photonics customers, and named **Marvell** (>5M coherent PICs shipped, joint PR 2026-06-18) and **NVIDIA** (1.6T module SiPho, 2026-02-05) relationships. Against TTM revenue of $1,622M, one product line has >80% of the company's current total revenue contracted for 2027 — with customers' own cash reserving the capacity.

That prepayment is the funded-gate discriminator, cleared with cash rather than a partnership headline, and it is revealed unportability: nobody prepays for a fungible process. **My "stop adding — it's at PEG-fair" call rested on a two-year consensus EPS of $5.83, and I explicitly named "consensus revised up materially" as its falsifier. That falsifier is now live.** Revised to **add on weakness with a wider band than the lens implies** — the lens's own input looks stale, and when a documented fact contradicts my input I don't get to keep quoting the output. Tier 1 confirmed and now the best-evidenced Tier 1 in the cohort.
Also correcting a widely-repeated capacity fact: the **Intel New Mexico 300mm corridor is dead or in mediation** (Tower disclosure 2026-02-11). Most published TSEM capacity tables still credit it. Sole-source status remains honestly unproven — Tower redirected the stranded NM customers to Fab 7 Japan, which proves portability *within* Tower, not across foundries.

**6. VICR's EXIT/TRIM is confirmed from an independent angle.** I called it on collapsing margins and $373.8M of insider selling. Now add: **VICR is conspicuously absent from NVIDIA's 800VDC silicon partner list while publicly disputing the architecture.** Two unrelated evidence streams pointing the same way is about as good as this gets. Note the flip side — that partner list has **fourteen names**, which is itself the tell that the power-semi device layer is content growth, not a chokepoint.

**7. 800VDC — my "constraint" tag was WRONG for the transition itself.** It is a datable step-change: NVIDIA published the architecture (4→2 conversion stages, ~83%→92%+ efficiency, ~45% less copper), TI unveiled a complete reference architecture with NVIDIA at GTC on 2026-03-16, and Vertiv/Schneider/Eaton/Delta committed commercial product for H2-2026 timed to Kyber. Production programs with dated availability, not announcements. **But** there are two forking reference designs — NVIDIA's own, and OCP "Mt Diablo"/Diablo 400 co-authored by Google, Meta and Microsoft, which NVIDIA did *not* co-author. Nobody owns the standard alone, so the correct read is **Evolution = content-per-rack re-rate, not scarcity rent**. Suppliers qualified into *both* capture the union.

**8. CPSH should come off the map as an AI-thermal name.** Its filings name AlSiC baseplate end markets as IGBT modules for rail, subway, EV/HEV, wind and HVDC grid — **no AI-package or 2000W-class datacenter disclosure exists.** I had it as DEDUCED; it is weaker than that. Keep at most a sliver on the indirect link (800VDC pulls IGBT/SiC baseplate volume), never as an AI-package pure-play. There is **no US-listed pure-play for AI package thermal** — the depth players are Indium Corporation (private) and T-Global (Taiwan), and TIM1/TIM2 is described as the most stubborn remaining bottleneck in 3D IC packages. Real bottleneck, no vehicle.

**9. A genuinely new bottleneck node with a buyable owner: liquid-cooling quick-disconnects.** Certification-gated with **only four certified suppliers — Stäubli, Eaton, CPC and Parker-Hannifin**. Two are listed: **DOV** (owns CPC/Colder Products; launched Everis DC full-flow connectors 2026-07-22) and **PH**. Both bury it inside a diversified industrial, which is exactly why it is under-covered. This is the tightest node in the entire cooling stack, and the rest of cooling — CDUs, cold plates — is visibly commoditising (Ecolab/CoolIT at ~29× EBITDA, Flex/JetCool, Trane/LiquidStack, Google naming Envicool ~25% of its 2026 CDU orders).

**10. WOLF's exclusion is confirmed, and the reason is better than the one I gave.** I excluded it on negative gross margin. The structural reason is worse: **SiC substrate is DE-concentrating** — SICC 27.6% plus TanKeBlue 18.2%, both Chinese and Big-Fund backed, against Wolfspeed's 24.9%. Anyone buying SiC as a chokepoint is on the wrong side of the concentration vector. Same warning applies to any neon-shortage revival: China is now the largest neon producer, so the 2022 trade has inverted.

**11. Uninvestable chokepoints worth knowing as indicators.** **High-purity quartz for CZ crucibles: Spruce Pine, North Carolina is 85–90% of global semiconductor-grade supply, two private operators.** The highest single-location concentration found anywhere in this exercise, and completely uninvestable. **EUV mask blanks: AGC + Hoya ~90–93%, Hoya alone >75% and the only vendor with validated High-NA blanks.** And the deepest still-rising hop in materials: **electronic-grade WF6 — two Japanese producers, ~25% of global capacity, ceasing permanently on 2026-07-01**, with China having controlled the tungsten feedstock while deliberately leaving WF6 itself off the dual-use list. Moat-side expression: **ALM** (Almonty, Nasdaq, US-redomiciled tungsten).

**12. Server-CPU capture is NOT x86 — it is Arm.** Arm crossed roughly **50% of hyperscaler CPU compute** (Computex 2026), up from ~15–18% in mid-2024, with datacenter royalties **+100% year-over-year**. Intel itself said on its Q1-2026 call that the datacenter CPU:GPU ratio could tighten to 1:1 in agentic workloads from today's 1:4–1:8. My map routed this layer to INTC/AMD/ARM without ranking them; **ARM is the capture mechanism**, and the under-covered adjacency is DDR5 channel expansion (12→16 with Diamond Rapids/Venice) driving RCD content — where **RMBS is the US-listed pure-play** because Montage is China-listed and inaccessible.

**More names surfaced, none scored:** **Q** (Qnity — the DuPont electronics spin, ~2/3 semiconductors, S&P 500 but analytically unmapped as a pure-play), **ON** (East Fishkill 300mm bought outright from GF — arguably the most under-covered US 300mm asset), **ALM**, **DOV**, **PH**, **SITM** (timing; comms/DC revenue +158% y/y, 1.6T modules take a higher-ASP oscillator), **SMTC** (CONFIRMED 2026-03-12 in NVIDIA's 1.6T DR8 OSFP — but read it as a content *transfer* event on the DSP-less fork, not growth), **KN**, **IQEPY** (the better-quoted IQE line vs the IQEPF I had).

**One caveat on SLOIY that cuts against my own enthusiasm:** Soitec's Smart Cut is a genuine IP chokepoint and photonics-SOI has effectively one qualified volume supplier — but **FD-SOI demand is RF and automotive-levered, not AI-datacenter-levered.** Right moat, wrong end market for this theme. Combined with the review's finding that SLOIY is the weakest of the six ADRs as a scale-in vehicle: **best thesis, worst vehicle.** Leave it a map node.

**Unchanged by all of this:** the portfolio-concentration finding, the ONTO/LITE/AAOI verdicts, and the build order — except that ONTO's case is stronger, KLIC's is more qualified, and **TSEM moves from "stop adding" to "add on weakness."**

## Deltas vs prior ranking

None. `sessions/INDEX.md` contained no prior entries; this is the first ranking in the archive. Future sessions should diff against this one — `_sectormap.json` is machine-diffable via `scripts/serenity_sectormap.py diff`.

---

## The falsifiers, collected

*(Deliberately a list, not a table — the `rankdiff` parser reads any tier-shaped table in this file.)*

- **"Memory is late-cycle for accumulation"** breaks if 4Q26 conventional DRAM contract prices are still rising AND HBM contract prices are not in year-over-year decline.
- **"KLIC / TER / BESIY are Tier 1"** breaks if advanced-packaging capacity adds stop being tool-gated — bonder lead times compressing while packaging output keeps rising.
- **"ONTO is the best holding to add"** breaks if a competing inspection modality is qualified into a named customer's packaging flow.
- **"AAOI is the weakest holding"** breaks if gross margin moves above ~30% and operating margin crosses zero.
- **"Trim AMKR / VICR"** breaks if revenue re-accelerates for two quarters with margin expansion and insider selling stops.
- **"Stop adding TSEM / LITE"** breaks if two-year consensus EPS is revised up materially — both calls rest entirely on that estimate being right.
- **The whole map** breaks if hyperscaler capex direction turns. It is the load-bearing pillar under every layer here.

**NFA.**
