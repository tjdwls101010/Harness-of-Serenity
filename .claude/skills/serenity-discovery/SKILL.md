---
name: serenity-discovery
description: >-
  Serenity's lens for FINDING the mispriced node — generating a US-listed ticker
  the market has structurally under-priced, BEFORE any pipeline analyze runs.
  Use whenever the user asks "뭐 사", "what should I buy", "AI 관련주 / X 테마
  관련주", "X vs Y", or any pick-me-a-name / compare-these-names request; whenever
  a supply-chain or bottleneck map turns up a high-growth chain leaning on a
  small, concentrated supplier; whenever a known winner prompts "the next $X /
  who benefits / who's the cheaper sibling"; whenever a whole ecosystem has
  re-rated but one critical node stayed flat; whenever an industrial-policy
  blueprint, a 10-K competitor list, an analyst write-up, an activist memo, or a
  sum-of-parts story names a controller the market hasn't aggregated; and
  whenever the real winner turns out foreign and you need the US-listed route.
  Trigger EVEN WHEN the user never says "discover" — the job here is FINDING the
  ticker, not screening one already named. Lean toward triggering: a pick / a
  compare / a "who benefits" almost always wants this lens first.
---

# serenity-discovery — finding the mispriced node

This is the half of the funnel `analyze` can't do. It reads a ticker; it can't *find* one — finding is pure agent work, WebSearch + SEC reading + chain-tracing. Your deliverable is a **US-listed ticker the market has structurally under-priced**, every inferred link labeled, ready to hand to the gates.

Everything you surface is a lead, deduced-until-confirmed — the un-seenness that mispriced a hidden node is the same un-seenness that makes *you* wrong about it, so this lens runs the hard DEDUCED/CONFIRMED rail off that. The always-on invariants — US-listed output only, never a number from memory, web for narrative only — bite here at the output and the labeling; apply them where each one fires below.

---

## When discovery even fires — the quantified escalation trigger

Discovery does NOT fire on every name in a chain, or you'd free-associate a supplier-of-a-supplier forever. It fires when mapping a target's chain reveals a high-growth chain whose key input is **concentrated (top-3 supplier share > 70%)** in a node with **market cap < 1/10 of the target.** That pair is the operating gate: a node that's both a genuine chokepoint (concentration, not a fragmented commodity) *and* radically smaller than the demand leaning on it is the leveraged mispricing this whole toolkit exists to surface — the smaller the node relative to the demand it gates, the more violent the re-rate when attention finally arrives. When it trips, **stop analyzing the visible target and run the discovery moves on the down-chain node.** A ~$700M substrate-feedstock duopoly (~60-70% share, demand running ~2x supply) feeding a multi-trillion AI buildout trips both thresholds at once — that's the cue to stop reading the target and go down a layer.

---

## Two axes — most misses come from running only the first

There are exactly two finding-axes, and the default failure is re-analyzing the incumbent everyone already sees — attention pools on the visible end-node (R3). Naming both axes is itself the discipline; a frame that lists where attention *does* reach is the map of where to *not* look:

- **Vertical** — trace the money flow *down* a chain to the deepest input nobody prices.
- **Horizontal** — transfer *across* from a name that already won to its not-yet-re-rated sibling one generation out.

If you've only traced down, you skipped the cheaper sibling; if you've only transferred across, you skipped the deeper input. Run both, then hand the smallest-MC / least-covered node the chain structurally depends on to `analyze`.

### Vertical — trace the chain down

Follow money flow *down* from the end-product: end-product `->` integrator/OEM `->` major components `->` sub-components `->` raw materials `->` equipment `->` feedstock/chemicals. At each layer, the layer-questions — how many suppliers? lead time for new capacity? geographic concentration? % of end-product cost? substitutes? — are not a checklist for its own sake; each one is a direct probe of **concentration** (what makes a node a chokepoint) and **substitutability** (what makes the chokepoint durable). Skip them and you'll mistake a fragmented commodity layer for a bottleneck. The deepest layers carry the thinnest coverage and the most mispricing, because analysts covering the end-product rarely look past the major components — so mispricing compounds with depth.

### The recursive hop — and the three tests that stop it

When you hit a bottleneck, ask "what does *this* company depend on?" and trace one hop further — but each hop must EARN the next by passing all three tests, or you stop:

1. **Does concentration rise?** Recompute supplier count / geographic share one layer down. *More* concentrated → you're climbing toward the chokepoint; *more* fragmented → you already passed it.
2. **Does the end-use demand a higher grade?** The deeper input often splits into a fat commodity tier and a thin high-spec tier only the end-use can accept — a distinct, far tighter monopoly. This is the most transferable test: quartz, photoresist, medical-grade polymers, aerospace alloys all hide a tighter monopoly in their high-spec cut, because "the commodity is abundant" is *exactly* the reasoning that makes the market miss the thin qualified tier.
3. **Is the dependency captive?** A supplier that *looks* vertically integrated but still single-sources one outside input is captive to that source — unmask it and the "integrated" name is really a pass-through to the deeper bottleneck.

**Stop hopping the moment concentration stops rising or a real substitute appears** — that layer *is* the bottleneck. Without these three the recursive hop degenerates into free association: you can always name *a* supplier-of-the-supplier infinitely and end up on an irrelevant commodity. The tests are a gradient-ascent stopping rule — concentration-rising means you're still climbing; its reversal means you've crested. The whole AI buildout leans on a ~$700M substrate, but only a laser-grade 6N-purity variant qualifies (~80% one country's output) — research stops at "substrate," the move lived one hop deeper in the purity tier.

### Horizontal — transfer from a proven winner ("the next $X"), done right

The single most frequent discovery move, and the one most often done wrong. It is NOT "find a cheaper lookalike" — that buys a value trap, because a name cheap-relative-to-the-winner is cheap either because attention hasn't reached it (exploitable) or because its fundamentals are broken (deserved), and only the last step separates the two. Five steps:

1. **Strip the winner to its structural ROLE, not its product** — "the EML-laser bottleneck for *current-gen* optics," not "a laser company." Working from the role is what makes the move sector-blind (R2): a payments rail re-rating under a reg shift, or the clear #2 in a launch market, decomposes identically.
2. **Name the architecture shift** that spawns a *next-gen* version of that role — a new interconnect standard, a settlement-rail change, a packaging shift — and the role it creates.
3. **Name the supplier filling that role per orthogonal slice** — current-gen vs next-gen, customer A vs B, scale-up vs scale-out. Each slice is a candidate.
4. **Rank the cohort by how re-rated each already is** and isolate the laggard — the one the ecosystem's move hasn't reached.
5. **Test whether the lag is exploitable.** A coverage gap, sub-$1B MC, a foreign OTC line, ticker/segment-naming confusion = exploitable. Broken fundamentals = the lag is *deserved*, skip it.

The incumbent is already priced — re-analyzing it is wasted motion; the return lives in the sibling one architecture-step out that *shares the role*. A $55B transceiver winner is fully priced, so the move lived in the only pure US transceiver fab one architecture-step out at ~$7B, sharing the same hyperscaler demand — laggard isolated, leverage intact. (This is the generative twin of thesis-inheritance: inheritance *validates* a pattern on a name you already hold; this *generates* the name.)

---

## Reconstruct the link nobody disclosed — the A→C trap

The highest-alpha link is usually the one no filing names, and that's by design: disclosure is asymmetric. A US filer's 10-K names its peers and major suppliers for risk-factor and competition reasons, but the small-cap two hops down — the one whose design win is the actual thesis — has no disclosure obligation and every incentive to stay quiet about a marquee customer. So the link that matters most is structurally the one you must **reconstruct, not retrieve.** The trap: **A→B is public and B→C is public, but nobody draws A→C** — each leg is individually visible and individually boring; only the synthesis is alpha, and synthesis is exactly what a separated-data-point market never does. Rebuild the confidential link from four sources:

1. **The small-cap's own transcripts** — it names its design wins and end-customers even when the customer won't name it.
2. **End-customer keynote → spec-match** — a hyperscaler/OEM discloses a part's specs at a launch; match those specs to the only supplier that can hit them.
3. **Warrant / strategic-investment filings** — an agreement's implied volumes, or an equity stake taken at diligence, reveal a supply contract the income statement hasn't printed yet.
4. **Paid market-share / channel reports** — third-party share data names suppliers no SEC document does.

This is OSINT, not lookup, and it transfers wholesale — a payments rail, an energy interconnect, a defense BOM each hide their real dependency the same way. "3-4 hyperscalers buy all the capacity" gets reconstructed from the small-cap's *own* disclosure, never the hyperscalers'.

**Defense / national-security specialization.** Classified or sensitive programs structurally suppress the customer name on *both* sides, so the link is never in any filing — but the prime's new-program specs (ruggedization, temperature range, edge-AI) and the small-cap's "unnamed leading defense customer" press release each leak one half. Spec-match the two — it's the confidential-link move where disclosure is *legally* constrained, not merely strategic.

---

## Five tacit techniques — reading documents for the omission

- **SEC competitor-list mining.** Read a known winner's 10-K competitor list as a pre-vetted *discovery* pool — smaller, earlier names in the same chain, vetted by the filer's own counsel as genuinely competitive. Almost no one reads a 10-K for the filer's *rivals*, so this free diligence sits unused. Caveat: a *named* competitor is by definition visible enough to be named — the list is a starting pool, not the endpoint; the reconstructed confidential link above is the higher prize.
- **The analyst-report gap — read for the omission.** Read institutional reports for the supplier clearly in the chain but NOT on the list. The names *on* the page are already priced into every one of them; the chain-position the analyst left blank is a direct readout of where attention hasn't reached. A competent reader stops at the named names — the edge is treating the gap as the signal.
- **The re-rating anomaly.** A whole ecosystem up hundreds of percent but one *critical* node still flat/small = the candidate. But ask *why* it hasn't moved before you buy it — a flat node can be flat because it's broken (deserved) or because nobody's looking (exploitable), and conflating the two is how you buy a falling knife dressed as a gem. The anomaly *generates* the candidate; the why-test *qualifies* it. A name owning 100+ MOCVD reactors while its whole ecosystem re-rated, still priced for bankruptcy on a tiny debt load — the "why" there was a coverage gap plus balance-sheet fear, not a capacity flaw.
- **Second-order beneficiary.** From a catalyst, trace who supplies the supplier that just maxed out. The market prices the obvious beneficiary (the company that reported) and stops; the supplier-of-the-supplier is a separate data point nobody connects, so its forward revenue moves before its price does. The move is mechanical — when a node maxes out capacity, its own inputs become the new constraint, and demand has nowhere to go but down one more layer. A transceiver maker's demand blowout `->` the epi-reactor makers it must now buy from go from afterthought to bottleneck.
- **Convergence-find.** List the obvious players in a theme, then ask "which single company do *most* of these rely on?" A node multiple visible players all depend on is, almost by construction, a chokepoint — yet the market prices each player separately and never aggregates the shared dependency into the node's value. **Read it both directions:** the same shared node is both the alpha *and* the tail risk — a "diversified" basket that all leans on one island foundry cluster or one country's refining is secretly one bet. (The bear-case / hidden-single-point-of-failure reading of this same fact is macro's; convergence-find is the alpha side.)

---

## Three document-mining triggers — names the market hasn't aggregated

- **Government-blueprint mining (candidate generation only).** A published industrial-policy blueprint or supply-chain impact-analysis is a free, pre-vetted, often *ranked* list of a chain's controllers — sometimes with explicit control percentages no screen will hand you, because the government already did the expensive diligence: which nodes are critical and who controls them. Almost no one reads it as a *screen for names*. Mine it for the names only — the catalyst/floor read of the same document (datable lagged repricing, chokepoint-validation) is macro's. An AlSiC pure-play (~25% Western share) surfaces as a DoD-relevant thermal material straight out of a defense blueprint, named before any screen would find it.
- **Sum-of-parts / hidden-stake unlock.** A name whose value is unlocked by a **subsidiary stake worth more than the parent's entire market cap** — or any hidden holding the market hasn't aggregated — is a discovery candidate. The market prices a parent off its operating P&L and routinely ignores a non-core stake buried on the balance sheet or in a subsidiary's separate listing — a separated-data-point failure at the corporate-structure level. The discovery edge is *spotting that the stake exists at all* and that an activist or a credible SOP write-up has put a clock on it — that write-up is itself the datable catalyst. (This is convergence-find inverted: instead of the node many names share, you find the value one name *hides*. Quantifying the gap — value the stake standalone, blend, the gap to parent MC is the unlock — is analysis's job, not this lens's.)

---

## Label EVERY link — and never let a DEDUCED node carry CONFIRMED conviction

This is a rule, not a principle — sizing real capital on an unconfirmed inference is the catastrophic, irreversible error this lens is most exposed to. The reconstruction and transfer moves are powerful *precisely because* they infer links no filing states, which is exactly why they can be silently wrong. So tag every link **CONFIRMED or DEDUCED.** A physics/spec deduction ("only this material meets that spec, so they must buy it") is a lead, not a thesis: tag it DEDUCED and **size NOTHING on it** until a filing, press release, or conference confirms it. Aggressive deduction *generates* candidates; confirmation *earns* conviction — never let a DEDUCED node carry a CONFIRMED node's conviction, because the deduction has no external check, so its error mode is silent. Both real misses happened this way: a supplier deduced from materials physics was the *wrong* vendor once the customer named its actual one at a trade show; an "unnamed leading customer" pinned to a hyperscaler simply never was. Converting a free option (a lead) into a leveraged bet on a guess is the specific way this lens blows up.

---

## Discipline — passing the gates is the bar, not "sounding good"

You'll run *tens* of candidates and reject most. **Sounding "good" — a real clean chokepoint — is NOT the bar; passing the Winner Gates is** (the gates live in serenity-analysis; this lens only hands off to them, and the power-law bar there is brutal — V6). Discovery's generative moves are seductive: finding a clean chokepoint *feels* like the work is done, which is the exact moment you stop applying the bar and start rationalizing — and founder's-attachment to a name *you* discovered is the specific bias that lets a sounds-good candidate skip the gates. Don't fall in love with a name because you found it.

---

## Ranking a cohort and converging into the winner

When the transfer or a theme hands you a cohort rather than one name, rank for *capital*, not curiosity:

- **Order by how DE-RISKED each is relative to the proven leader — NOT by which is cheapest.** Cheapest-first inverts the risk you're paid for: the cheapest cohort member is often cheapest *because* it's least de-risked, so price-ranking systematically buys the worst odds. A transfer thesis is a hypothesis until execution confirms it, so rank by de-risk-relative-to-leader.
- **Time entry to the leader's move.** An analog stays buyable while the leader has *already* re-rated but the laggard's gap to it persists — and that gap persists for *coverage* (attention-lag) reasons, not fundamental ones, so it's still buyable after the leader has moved.
- **As execution data arrives and one name pulls ahead, CONSOLIDATE** — sell the laggards *into* the winner rather than nursing the basket. The alpha was always going to concentrate in one name; a diversified basket just bleeds slowly toward that outcome.

### Routing through `discover`

`discover TKR1 TKR2 …` runs the pipeline's triage comparator across the cohort — a per-name health · momentum · catalyst · valuation read for ranking names against each other, never a grade (it's the comparator CLAUDE.md describes; the divergence between it and your structural read is the gap *you* resolve, most useful precisely where it disagrees with you). Workflow: feed the generated cohort to `discover` to isolate the laggard, then hand the chosen name to `analyze`.

```bash
scripts/.venv/bin/python scripts/serenity_pipeline.py discover TKR1 TKR2 …
```

---

## Track the signal the moment you find the node

A discovery is a hindsight story unless it converts into a *timed entry* — and the conversion is naming, in advance, the **earliest publicly observable signal** for *this specific node*, because the raw-material spot leads the equity. Earnings confirmation is the *end* of the propagation chain; by then the move is mostly done. So the instant you finish finding a node, pre-commit: write down "what is the earliest observable signal that confirms/denies this?" — a moved input price (read it directly: the spot, the utilization rate, the margin math) with a still-flat equity is your timed-entry gap. Watch *that*, not earnings. (The full propagation chain and the named data sources are macro's; this lens only applies it to the name you just found.)

---

## US-listed resolution ladder — never stop at "inaccessible"

Discovery keeps surfacing foreign winners, and "foreign → inaccessible → drop it" silently discards capturable return — a foreign micro-cap's own US OTC line tracks the local listing tick-for-tick. The ladder is ordered by **fidelity**, so you descend a rung only when the higher one genuinely doesn't exist:

1. **The name's OWN US line first** — a US OTC ticker or unsponsored ADR of the *exact* company. Highest fidelity, a pure-play, not a diluted basket.
2. **Else the most-concentrated US ETF** — chosen by liquidity *and* expense. And name an options vehicle (deep, liquid chain) separately from a low-cost shares vehicle when they differ.
3. **Else the nearest US-listed analog** in the same hop — a proxy.
4. **Else leave it as a map node** — name the foreign winner *honestly*, then route the capital to the accessible chokepoint *downstream* of it.

Run whatever the ladder yields through `analyze` (use `discover` to compare a generated cohort first). **Never silently bury the truth that the best pure-play is foreign** — naming it even at rung 4 keeps the analysis honest and preserves the map for when a US line later appears.

### ETF = thematic vehicle, read via NAV composition

For an ETF, company-level bottleneck/margin analysis is meaningless — it's not a company. Treat it as a *thematic vehicle* and analyze the underlying via its US-listed constituents. The discovery-specific question is **NAV composition: what % of the ETF's NAV is actually the name you want**, because a thematic ETF can be only fractionally the exposure you're after — ignore this and you buy a basket that's mostly *not* your node. When a holding company is ~90% of an ETF's NAV and itself ~90% one memory maker, that ETF is a usable proxy for that one node — the NAV read is what makes rung 2 precise. (Whether to then express it as shares or a compressed-IV LEAP is an *instrument* decision driven by the IV tier — that's analysis's territory, not this lens's.)

---

## The up-listing catalyst — depressed trailing float handed to forward-priced buyers

A foreign small-cap **up-listing onto a US exchange** (crossing the ~$1B MC / index-mandate thresholds) is a forced-buying catalyst, and the re-rate is *directional*, not just a lag — two mechanisms compound. (a) Index-mandate inclusion forces passive buying regardless of price. (b) The buyer base's valuation *horizon changes*: local markets price off *trailing* revenue; US institutions price ~12mo *forward* — so the listing hands a depressed trailing-priced float to forward-priced buyers, and the same cash flows get re-priced on a basis they were never priced on locally. That directional re-rate is invisible to anyone treating the up-list as a mere liquidity event.

The loss-hardened part: **a hostile local-media piece during the up-list window is the shake-out handing over that float, NOT a bear signal.** The natural read of bad press during a transition is "exit," but a coordinated bearish flood is often the accumulation tell — someone wants retail to paper-hand the float before the institutional bid arrives. (This is an accessibility/discovery event, not a regime read; macro points here.)

---

TLDR: discovery = find the US-listed node attention can't reach. Two axes — trace down + transfer across; gate the recursive hop on rising-concentration; reconstruct the A→C link nobody filed; label every inferred link DEDUCED and size nothing on it until CONFIRMED; run the cohort through `discover` to isolate the laggard; walk the fidelity-ordered US ladder when the winner's foreign — then hand the name to `analyze`. Sounding good isn't the bar; the gates are.
