---
name: serenity-discovery
description: >-
  Serenity's lens for FINDING the mispriced node — generating a US-listed
  ticker the market has structurally under-priced, before any analysis runs.
  Use whenever the user asks "뭐 사", "what should I buy", "AI 관련주 / X 테마
  관련주", "X vs Y", or any pick-me-a-name / compare-these-names request; whenever
  a supply-chain or bottleneck map turns up a high-growth chain leaning on a
  small concentrated supplier; whenever a known winner prompts "the next $X / who
  benefits / who's the cheaper sibling"; whenever a whole ecosystem has re-rated
  but one critical node stayed flat; whenever an industrial-policy blueprint,
  10-K competitor list, activist write-up, or sum-of-parts story names a
  controller the market hasn't aggregated; and whenever the real winner turns out
  foreign and you need the US-listed route. Trigger even when the user never says
  "discover" — the job is finding the ticker, not screening one already named.
---

# serenity-discovery — finding the mispriced node

This lens *generates* a ticker; it does not screen one already in hand. The pipeline `analyze`s a ticker — it cannot find one. Discovery is pure agent work: WebSearch + SEC reading + chain-tracing + deduction. When you finish, you hand the surfaced US-listed ticker(s) to `analyze` (or a cohort to `discover` first).

Everything here rests on **R3** (stated once in CLAUDE.md): *value lives where attention structurally can't reach — coverage and price pool on the large visible end-node and thin down-chain, out to the un-re-rated analog, and lag the causal signal. A node is mispriced exactly to the degree the market can't see it. But the same un-seenness that mispriced it makes YOU wrong too — so a hidden find is a LEAD, DEDUCED until confirmed, never conviction.* This document cites R3; it does not re-derive it.

## The backbone — how a discovery run actually flows

```
0  Does this even escalate to discovery?  (the quantified gate, below)
1  Pick the axis:  VERTICAL (trace money down a chain to the unpriced input)
                or HORIZONTAL (transfer across from a winner to its un-re-rated sibling)
2  Run the axis to the smallest-MC, least-covered node the chain structurally needs
3  Reconstruct any A→C link no filing draws  (the small-cap's own mouth, spec-match,
   warrant/stake filings, paid share reports)
4  Resolve to a US-listed vehicle  (the fidelity-ordered ladder — never stop at "inaccessible")
5  Tag every link CONFIRMED or DEDUCED
6  Cohort? → `discover` to isolate the laggard → hand the chosen name to `analyze`
7  Pre-commit to the node's EARLIEST observable signal (its timed-entry trigger)
```

The default failure this backbone exists to break: **re-analyzing the incumbent everyone already sees.** Attention saturates the visible end-node; the alpha is definitionally where attention can't reach. A frame that names where attention *does* reach is the map of where to *not* look.

## When discovery fires — the quantified gate

Discovery does **not** fire on every name. Without a numeric trigger it either never fires (you keep re-analyzing the visible target) or fires on every tangential supplier (free association). It fires when mapping a target's chain reveals a high-growth chain whose key input is **concentrated (top-3 supplier share > 70%)** sitting in a supplier with **market cap < 1/10 of the target.**

Both thresholds isolate the asymmetry that pays: >70% concentration means a genuine chokepoint, not a fragmented commodity; MC < 1/10 of the demand leaning on it means the repricing hasn't caught up — and the smaller the node relative to that demand, the more violent the re-rate when attention arrives. When it trips, **stop analyzing the target; run the discovery moves on the down-chain node.**

> Picture: a high-growth AI name whose substrate input is ~60-70% controlled by a sub-$1B supplier — AXTI/InP, a ~$700M node feeding a multi-trillion buildout (DB `2004936335702753729`) — trips both thresholds and escalates from "analyze the target" to "discover the node."

## The two axes

**Most misses come from running only one axis.** If you've only traced down, you skipped the cheaper sibling; if you've only transferred across, you skipped the deeper input. Name both explicitly every run.

### VERTICAL — trace the money down

Follow the flow down from the end-product: end-product → integrator/OEM → major components → sub-components → raw materials → equipment → feedstock/chemicals. Analysts covering the end-product rarely look past the major components, so **mispricing compounds with depth** — coverage tracks proximity to the visible end-node, not where value structurally concentrates.

At each layer ask the layer-questions — and treat them as probes, not a checklist: *how many suppliers? lead time for new capacity? geographic concentration? % of end-product cost? substitutes?* Every one is a direct probe of **concentration** (what makes a node a chokepoint) and **substitutability** (what makes the chokepoint durable). Skip them and you mistake a fragmented commodity layer for a bottleneck.

> Picture: traced the Western AI roadmap down past "substrate" to InP feedstock, where a ~$700M AXT + Sumitomo duopoly (~60-70%) sits with demand ~2× supply (DB `2004936335702753729`, AXTI).

**The recursive hop — and its three earning-tests.** When you hit a bottleneck, ask "what does *this* company depend on?" and trace one hop further — but each hop must EARN the next by passing all three, or you stop. Without the tests the hop degenerates into free association: you can always name *a* supplier-of-the-supplier, infinitely, onto an irrelevant commodity. The tests are a gradient-ascent stopping rule.

1. **Does concentration rise?** Recompute supplier count / geographic share one layer down. *More* concentrated → climbing toward the chokepoint. *More* fragmented → you've already passed it.
2. **Does the end-use demand a higher grade?** A deep input often splits into a commodity tier and a thin high-spec tier only the end-use can accept — a distinct, far tighter monopoly. This is the most transferable test (quartz, photoresist, medical-grade polymers, aerospace alloys all hide a tighter monopoly in their high-spec cut), because "the commodity is abundant" is exactly the reasoning that makes the market miss the thin qualified tier.
3. **Is the dependency captive?** A supplier that *looks* vertically integrated but still single-sources one outside input is captive to that source — unmask it and the "integrated" name is really a pass-through to the deeper bottleneck.

**Stop hopping when concentration stops rising or a real substitute appears** — that layer is the bottleneck.

> Picture: a ~$700M substrate the whole AI buildout leans on is cut from a feedstock — but only a laser-grade 6N-purity variant qualifies (~80% one country's output). Research stops at "substrate"; the +500% lived one hop deeper, in the purity tier (DB `2004936335702753729`).

### HORIZONTAL — transfer from a proven winner ("the next $X")

The most frequent discovery move — and done right it is **NOT** "find a cheaper lookalike" (that buys a value trap; see the gotcha). It is a five-step decomposition. The incumbent is already priced (R3), so the return lives in the sibling one architecture-step out that *shares the structural role*. Decomposing by **role, not product** is what makes the move sector-blind — a payments rail re-rating under a regulatory shift, or the clear #2 in a launch market, decomposes identically.

1. Strip the winner to its **structural role**, not its product — "the EML-laser bottleneck for *current-gen* optics," not "a laser company."
2. Name the **architecture shift** that spawns a *next-gen* version of that role — a new interconnect standard, a settlement-rail change, a packaging shift — and the role it creates.
3. Name the supplier filling that role **per orthogonal slice**: current-gen vs next-gen, customer A vs B, scale-up vs scale-out — each slice is a candidate.
4. **Rank the cohort by how re-rated each already is** and isolate the laggard — the one the ecosystem's move hasn't reached.
5. **Test whether the lag is exploitable**: a coverage gap, sub-$1B MC, a foreign OTC line, or ticker/segment-naming confusion = exploitable; broken fundamentals = the lag is *deserved*, skip it.

> Picture: AAOI from LITE (DB `2029219794025644382`) — role = "pure US transceiver fab"; shift = next-gen optics ramp; laggard isolated = AAOI at $7.1B vs LITE $55B; exploitability = sub-scale MC with leverage to the same hyperscaler demand. Same move on MOCVD reactor capacity: IQE from a LandMark comp (DB `2027318568728273305`).

**Rank a cohort by de-risk, not by cheapest — then consolidate.** Cheapest-first inverts the risk you're paid for: the cheapest member is often cheapest because it's *least* de-risked, so price-ranking systematically buys the worst odds. Order by how de-risked each is **relative to the proven leader**, and time entry to the leader's move — the laggard's gap persists for *coverage* reasons (attention lag), not fundamental ones, so it stays buyable *after* the leader has already re-rated. As execution data arrives and one name pulls ahead, **consolidate — sell the laggards into the winner** rather than nursing the basket (a diversified basket's alpha was always going to concentrate in one name). Use `discover` to compare the cohort side-by-side before committing.

## Reconstruct the link nobody disclosed — the A→C trap

The highest-alpha link is usually the one **no filing names.** A 10-K surfaces only the large-caps a US filer *chose* to name (for risk-factor and competition reasons) — never the small-cap two hops down whose design win is the actual thesis, because that small supplier has no disclosure obligation and every incentive to stay quiet about a marquee customer. So the link that matters most is structurally the one you must **reconstruct, not retrieve.**

Why the market leaves it unpriced: **A→B is public and B→C is public, but nobody draws A→C.** Each leg is individually visible and individually boring; only the synthesis is alpha, and synthesis is exactly what a separated-data-point market doesn't do. This is OSINT, not lookup, and it transfers wholesale — a payments rail, an energy interconnect, a defense BOM each hide their real dependency the same way. Rebuild from four sources:

1. **The small-cap's own transcripts** — it names its design wins and end-customers even when the customer won't name it.
2. **End-customer keynote → spec-match** — a hyperscaler/OEM discloses a part's specs at a launch; match those specs to the only supplier that can hit them.
3. **Warrant / strategic-investment filings** — an agreement's implied volumes, or an equity stake taken at diligence, reveal a supply contract the income statement hasn't printed yet.
4. **Paid market-share / channel reports** — third-party share data names suppliers no SEC document does.

> Picture: AAOI (DB `2029219794025644382`) — "3-4 hyperscalers buy all capacity" reconstructed from the *small-cap's* own disclosure, not the hyperscalers'. Also the confidential-BOM archetype (SpaceX-style: pin the unnamed supplier by spec-matching the end-customer's published part specs).

The defense / national-security specialization of this move — where disclosure is legally constrained, not merely strategic — lives in `references/tacit-techniques.md`.

## Resolve to a US-listed vehicle — the fidelity ladder

Discovery keeps surfacing foreign winners. The answer is **never just "inaccessible, move on"** — that reflex throws away capturable returns (a foreign micro-cap's own US OTC line tracks the local listing tick-for-tick — the +1900% you'd skip by stopping early). Walk the ladder **IN ORDER**; it's ordered by fidelity, so descend only when the higher rung genuinely doesn't exist:

1. **The name's own US line** — a US OTC ticker or unsponsored ADR of the *exact* company (a pure-play, highest fidelity — not a diluted basket).
2. **The most-concentrated US ETF** — chosen by liquidity *and* expense; name an options vehicle (deep, liquid chain) separately from a low-cost shares vehicle when they differ.
3. **The nearest US-listed analog** in the same hop (a proxy).
4. **Leave it as a map node** — name the foreign winner honestly, then route the capital to the accessible chokepoint *downstream* of it.

Run whatever the ladder yields through `analyze`; use `discover` to compare a generated cohort first. **Never silently bury the truth that the best pure-play is foreign** — naming it honestly even at rung 4 keeps the analysis truthful and preserves the map for when a US line later appears.

> Picture: "a foreign micro-cap's own US OTC line tracks the local listing — the +1900% you'd have skipped." Rung-2 instance: EWY (DB `2030667380855083222`) — SK Hynix / Samsung accessed via the most-concentrated US ETF.

**ETF = thematic vehicle, read via NAV composition.** An ETF isn't a company — company-level bottleneck/margin analysis is meaningless. The only discovery question is "does this basket actually hold the node I found, and at what weight?" A thematic ETF can be only *fractionally* the exposure you want, so ignoring NAV composition risks buying a basket that barely is the name. (Whether to then express it as shares or a Vega-LEAP is an *instrument* decision keyed to the IV tier — that's analysis's territory, not discovery's.)

> Picture: EWY — "SK Square ~90% NAV is SK Hynix" is the NAV-composition read that makes EWY a usable proxy for the SK Hynix node (DB `2030667380855083222`).

**The up-listing catalyst.** A foreign small-cap **up-listing onto a US exchange** (crossing the ~$1B MC / index-mandate thresholds) is a forced-buying catalyst, and the re-rate is *directional*, not just a lag. Two mechanisms compound: (a) index-mandate inclusion forces passive buying regardless of price, and (b) the buyer base's valuation horizon *changes* — local markets price off *trailing* revenue, US institutions price ~12mo *forward*, so the listing hands a depressed trailing-priced float to forward-priced buyers. That directional re-rate is invisible to anyone treating the up-listing as a mere liquidity event.

## More finding-moves — the tacit techniques

Six pattern-finders Serenity reaches for, each a different way to point at the un-reached node. Reach for whichever the situation fits; the full catalogue with why + picture lives in **`references/tacit-techniques.md`** (load it when you need a finding-move and the axes above haven't surfaced the node):

- **SEC competitor-list mining** — a winner's 10-K competitor list is free, pre-vetted diligence on the chain.
- **Analyst-report gap** — read for the *omission*: the supplier in the chain but not on the list.
- **Re-rating anomaly** — ecosystem up hundreds of %, one critical node still flat. Always ask *why*.
- **Second-order beneficiary** — trace who supplies the supplier that just maxed out.
- **Convergence-find** — which single company do *most* of the obvious players rely on? (Also the hidden single-point-of-failure check.)
- **Government-blueprint mining** — an industrial-policy blueprint is a pre-vetted, often ranked controller list, sometimes with explicit control %.

**Sum-of-parts / hidden-stake unlock** is a seventh trigger: a name whose value is unlocked by a **subsidiary stake worth more than the parent's whole market cap**, or a hidden holding the market hasn't aggregated, is a discovery candidate — the market prices the parent off its operating P&L and ignores a non-core stake (a separated-data-point failure at the corporate-structure level). An activist (e.g. Palliser) or a credible SOP write-up surfacing the stake is itself the datable catalyst. This is convergence-find inverted — instead of the node many names share, you find the value one name *hides*. (The valuation mechanic — value the stake standalone, blend, gap-to-parent-MC — belongs to analysis.) Picture: WUS / Kunshan stake via Palliser (DB `2067100222778704207`); NBIS / Clickhouse (DB `2007071108831338685`).

## Once the node is found — pre-commit to its earliest signal

A discovery is a hindsight story unless it converts into a **timed entry**, and the conversion is naming, *in advance*, the earliest leg of the propagation chain for *this specific node*. Earnings confirmation is the *end* of the chain — by then the move is mostly done. So the instant you finish finding the node, write down the spot/utilization signal you'll watch: a moved input price with a still-flat equity is your timed-entry gap. (The full propagation chain and named data sources — LME/Fastmarkets/Argus, TrendForce/DRAMeXchange — are owned by macro; discovery only *applies* it to the name in hand.)

> Picture: read the energy/helium spot and SK Hynix margin math directly rather than waiting for the KOSPI-fear narrative to resolve in earnings (DB `2030667380855083222`, EWY).

## The `discover` comparator — what it hands back, and what it does NOT

```
python3 scripts/serenity_pipeline.py discover TICKER1 TICKER2 …
```

It runs the pipeline's triage layer on each name and returns a **side-by-side comparator** — a per-name triage read (health · momentum · catalyst · valuation substrate) for ranking a cohort *against each other*. It is a **comparator, not a grade and not a verdict.** The whole reason it hands a comparator rather than a ranked verdict is the project's core boundary: code surfaces decision-substrate, the embodied analyst makes the call. A composite triage number is a relative-ordering aid across a cohort, never an absolute judgment on one name — treat it as a verdict and you re-introduce the hidden grade this harness was built to remove, and a no-moat name screens "good" on momentum exactly when you most need your own gates.

**The comparator is most useful precisely where it DISAGREES with your read** — a high triage on a no-moat hot name, or a low one on a real early winner, is the gap YOU resolve, not the answer. Run the cohort through `discover` to isolate the laggard, then hand the chosen name to `analyze`.

## Gotchas — the traps that cost real runs

- **"Cheaper lookalike" is a value trap.** A name cheap-relative-to-the-winner is cheap either because attention hasn't reached it (exploitable) or because its fundamentals are broken (deserved). Only step 5 of the transfer separates the two. The whole transfer move collapses into a falling-knife buy if you skip it.
- **The re-rating anomaly cuts both ways.** A flat node can be flat because it's broken (deserved) *or* because nobody's looking (exploitable). The anomaly *generates* the candidate; the **why-test qualifies it**. Conflating the two buys a falling knife dressed as a gem. (IQE was priced for bankruptcy on £45M debt — the "why" was a coverage gap + balance-sheet fear, not a capacity flaw: DB `2027318568728273305`.)
- **Don't fall in love with a name because you found it.** You'll go through *tens* of candidates and reject most. Sounding "good" (a real chokepoint) is NOT the bar — passing the Winner Gates is. Finding a clean chokepoint *feels* like the work is done, which is exactly when you stop applying the brutal power-law bar and start rationalizing. A chokepoint that can't monetize, can't price, or won't survive to the ramp is a fascination, not an investment. (Hand the name off to the gates; don't grade it here.)
- **A *named* competitor is, by definition, already visible enough to be named.** The SEC competitor list is a *starting pool*, not the endpoint — the confidential reconstructed link is the higher prize.
- **The convergence-find is also a tail-risk readout.** A "diversified" set of names that all lean on one node is secretly *one bet*. Read it in both directions — the same shared node is both the alpha and the single-point-of-failure.
- **Hostile local media during an up-list window is the shake-out, not a bear signal.** The natural read of bad press during a transition is "exit" — but a coordinated bearish flood is often the accumulation tell (someone wants retail to paper-hand the float before the institutional bid arrives).

## Invariants — never violated

- **Label every link CONFIRMED or DEDUCED — and never let a DEDUCED node carry a CONFIRMED node's conviction.** The reconstruction and transfer moves are powerful *because* they infer links no filing states — which is exactly why they can be wrong, and R3's un-seenness gives the deduction no external check, so its error mode is silent. A physics/spec deduction ("only this material meets that spec, so they must buy it") is a **lead, not a thesis**: tag it DEDUCED and size NOTHING on it until a filing, press release, or conference confirms it. Aggressive deduction *generates* candidates; confirmation *earns* conviction. This is an invariant because sizing real capital on an unconfirmed inference is a catastrophic, irreversible error — it converts a free option into a leveraged bet on a guess. (Written in real misses: a supplier deduced from materials physics was the *wrong* vendor once the customer named its actual one at a trade show; an "unnamed leading customer" pinned to a hyperscaler simply never was. DB `2027318568728273305` carries an explicit DEDUCED tag on its turnaround bet.)
- **Recommend only what the user can buy.** Every name handed off must resolve to a **US-listed, pipeline-analyzable** vehicle (common stock, ADR, or ETF) via the fidelity ladder. If the real winner is foreign, name it honestly *and* route to the accessible vehicle — never silently drop the truth that the best pure-play is foreign, and never recommend a name the user can't buy without flagging it US-inaccessible.
- **Discovery finds; it does not judge.** Discovery surfaces the node and the substrate to judge it; it hands the name to the Winner Gates, valuation, and timing lenses. It references them — it never duplicates their verdict here.
