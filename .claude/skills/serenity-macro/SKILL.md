---
name: serenity-macro
description: >-
  The macro/regime/catalyst lens — sets the AGGRESSION DIAL and runs the
  forward-revenue CATALYST test that gate every single-name call. Use this
  whenever the question is about the market environment, a regime read, or
  whether an event is real: "장 어때 / 지금 들어가도 되나 / 시장 어떤지", risk-on vs
  transition, "should I be aggressive or defensive". Use for ANY catalyst,
  headline, or event read — earnings beat/guidance, index inclusion,
  M&A/mega-contract, executive order / regulation / new law, tariffs, export
  controls, sanctions, rate cuts/hikes or Fed/Polymarket odds, short squeezes,
  prediction markets, government shutdowns, analyst upgrades — even when the
  user only names the headline and never says "macro" or "catalyst". Use when a
  name or sector is selling off and you must judge fear-dislocation vs structural
  break (sympathy selloff, TACO/cross-fire dip, tax-loss season, "is this the
  bottom"). Use for geopolitics, war/conflict, policy persona, reshoring,
  subsidies/grants, liquidity drains, "is this trade too crowded", seasonal
  (Nov–Dec/January) timing, and "this looks diversified" basket / hidden
  single-point-of-failure reads. Trigger when a question is macro AND something
  else (a supply-chain or discovery ask wrapped in a macro trigger) — run this
  lens first and let the downstream names inherit its setting. Lean toward
  triggering: a regime read that conditions a name almost always wants this lens.
---

# serenity-macro — the aggression dial and the catalyst gate

This lens runs *before and around* any single name. It does two jobs: read the **regime** into a posture (how aggressive the hunt, how loud the go), and run the **forward-revenue catalyst test** on every event. Everything else is one of those two specialized to a recurring case.

> Always-on from CLAUDE.md, NOT restated here: never cite a number from memory · US-listed only · V2 falsification · bear-case-mandatory. What this lens adds: the macro-specific number bridge and two macro-local hard rules (bidirectional rate-routing; YOUR-bearishness-only-on-forward-revenue). Bodies owned elsewhere, only pointed to: the US-listed resolution ladder + foreign up-listing catalyst (serenity-discovery); the IV→vehicle and the geographic moat-vs-hostage *net-the-two* read (serenity-analysis).

## THE BACKBONE — run in dependency order

```
1. REGIME read    → set the aggression dial (do this FIRST, every macro turn)
2. CASCADE locate → where on the Hyperscaler-CapEx → ... → raw-material spine?
3. CATALYST test  → does the event change FORWARD REVENUE?  (the one test)
4. ROUTE / SIZE   → fundamental change = size to it; entry-only = trade the dip
```

The order is load-bearing — each step conditions the next. The same name is a buy in one regime and a pass in another, so resolving the regime first stops you sizing a thesis correctly in isolation but wrong for the tape. When a question is macro **AND more** ("관세 때문에 뭐 사" is macro + supply-chain + discovery), walk the union in this dependency order, regime first (CLAUDE.md owns the routing precedence) — macro isn't a separate question you answer and stop, its job is conditioning everything after it.

---

## STEP 1 — REGIME → AGGRESSION

The pipeline gives the raw gauges — it does **not** label the regime or a risk level; that classification is a judgment, so it's yours (the code-loads-facts boundary holds for macro too: never quote a regime you didn't read off a sourced gauge). Read the gauges into a posture: Risk-On → lean aggressive on conviction; Transition → raise the bar. They live in code precisely because a recalled regime read mis-marks the whole book (number bridge below).

**Four regime pillars — hyperscaler CapEx direction is THE load-bearing one.** ① hyperscaler CapEx direction · ② net liquidity (= Fed balance sheet − TGA − RRP, pipeline-computed, read *directional* not as a point estimate) · ③ credit conditions · ④ VIX structure (contango vs backwardation). For any AI-adjacent book, CapEx direction decides the most theses at once: increasing = tailwind, flat/declining = reassess everything downstream — the whole cascade (semis → memory → substrates → raw materials) hangs off hyperscaler spend, and its direction is a forward-*revenue* move, not sentiment. Named with its three parts, net liquidity lets you attribute a swing to a TGA refill vs an RRP drain instead of treating "liquidity" as an opaque mood. Combine the pillars — elevated VIX *alone* is a fear spike with no fundamental read, and leaning on it solo buys a dip the cascade is actually turning against. Beyond the four pillars the pipeline also surfaces ERP (equity risk premium — what you're paid over the real rate to hold stocks; thin ERP = priced for perfection), DXY (the dollar — a rising dollar tightens global liquidity and pressures ex-US and commodity names), and BDI (Baltic Dry — physical-trade throughput, a real-economy demand read); fold these in as supporting reads, not pillars.

> *"The biggest signal of whether the AI trade continues is hyperscaler spending."*

**Fear-Dislocation is the BEST buying environment — but wait for forced-seller exhaustion first.** Fear elevated, fundamentals intact → buy when the tape feels worst (V1), because the market reacts to sentiment faster than to structure and that's the fattest gap between price and unchanged structure. But forced selling (margin calls, redemptions) is price-insensitive and overshoots, so entering before it exhausts is catching the knife mid-cascade. Wait for the forced sellers to finish, *then* enter; quality snaps back first because it's what the remaining real buyers want.

**Crisis/Wartime is a 4th regime — rotate the cohort, don't buy the dip.** ⚠️ GOTCHA. Active conflict, a sustained crisis, or a structural policy shift (sanctions, trade-war escalation) can create a *durable* sector rotation — not a fear spike — that the pipeline won't flag. Fear-Dislocation and Crisis/Wartime look **identical on the tape** (everything red) but demand opposite moves: in one the thesis is unchanged so you *add to your names*; in the other the thesis-*set* rotated, so capital moves actively into defense / energy / national-security and out of civilian/consumer names lacking crisis resilience. Collapse the two and you "buy the dip" on a name whose whole category just lost its forward revenue. (A sudden conflict popping small caps is usually flow, not a TAM increase — not a multi-x or a long hold *unless* the war structurally shifts the category.) **Beyond rotating the cohort, ask whether a *specific* name is a crisis forward-revenue BENEFICIARY** — an attention/engagement-monetized platform whose high-intent search & discussion traffic spikes in conflict (advertisers rotating *toward* brand-safe isolated inventory), or a defense/energy name with a freshly-funded program. That's a name to *add*, not a dip to fear; hand it to the analysis archetype step, which runs the forward-revenue-beneficiary check (R1) and the stale-guidance-sandbag read on it.

---

## STEP 2 — CAPEX CASCADE: THE TRANSMISSION SPINE

Demand moves down the physical chain in a fixed order:

```
Hyperscaler CapEx → neocloud deals → semiconductors → memory → substrates/optics → raw materials
```

Everything in this lens reads off positions on this spine. **The cascade's alpha:** the reporter's beat prints instantly, but the three-hops-down supplier it structurally implies re-rates on a days-to-quarters lag — because no analyst covers both the reporter and that node. So locate the names one-to-three hops down and position *before* the read-through prints. (A foundry blowout confirms downstream GPU/substrate/memory demand before those names move; a hyperscaler CapEx raise validates the neocloud and component tiers before those names move.)

**Earliest signal = the raw-material spot, not the equity.** Information propagates in a fixed order: supply-chain derivative signals (commodity spot, procurement, utilization) → paid industry reports → public news → repricing → earnings confirmation. The print is the *end* of the chain — anchor on it and you're structurally late. A spot move with no equity move *yet* is the gap. Named sources: **LME / Fastmarkets / Argus** (metals), **TrendForce / DRAMeXchange** (memory), spot indices (specialty gases, PGMs). A NAND spot move on DRAMeXchange with memory equities still flat = the forward leg the market hasn't priced. (Discovery *applies* this to time an entry; the chain + sources are owned here.)

### Overflow + the sold-out tell ⚠️ GOTCHA
When hyperscaler capacity is full, demand overflows to alternatives (neoclouds, specialized compute) — sudden revenue acceleration the market hasn't priced. The reflex reads "leader sold out" as bullish for the *leader* — but the leader is already priced for it; the un-priced move is the displaced #2/#3 demand cascading to the next merchant down. The confirmation supply has nowhere left to go: **the tier-1 leader itself buying the scarce sub-component on the open market** (vs internal allocation) = *structurally* sold out, not cyclically tight — revealed preference louder than any order-book number, and the discriminator between cyclical tightness (resolves with capex) and physics-bound shortage. Buy the un-allocated #2/#3 underneath, never the sold-out leader.

### Sympathy selloff — split real damage from pure association ⚠️ GOTCHA
A peer drops on a peer's bad print. Run the mechanism check across the peers (R1, on a selloff) and split **real counterparty damage** (a customer/supplier whose forward revenue actually takes the hit — may be real; re-rate) from **pure association** (sold off only for sharing a theme, no revenue link — mechanical, usually round-trips in 1–2 sessions). Get it wrong and you either buy a name whose real customer just vanished, or pass on a free round-trip. Displacement rumors that are physically impossible mid-cycle = association, not damage. (Run on a single name you'd own, the full 4-step is serenity-analysis's falling-knife.)

### Strategic-incentive floor — map the cohort backstop flow
When a hyperscaler's core demand is threatened by customer in-housing, it may backstop alternative consumers to defend its own revenue — a price floor that lives in the *backer's* incentive, not the name's balance sheet, so it never shows up on a screen. At the macro level read it as a *flow*: when a threatened larger entity defends a consumer tier, the whole tier's downside is propped, not just one name. (The per-name "who structurally NEEDS this company" moat-plane is serenity-analysis's job — map the flow here, let analysis value the individual moat.)

### Hidden single-point-of-failure ⚠️ GOTCHA
A set of US-listed names that — one hop down — all lean on the **same node** (one region's supply chain: a single-island foundry cluster, one country's refining; or one driver: hyperscaler CapEx, one commodity, one policy line) is secretly *one bet*. The list *looks* diversified, but the diversification is an illusion when they converge a hop down — a single event (an island quake, an export ban, a CapEx cut) takes the whole "diversified" book at once. Surface the shared chokepoint when evaluating a theme and name it in the bear case. This is the tail-risk face of the same node discovery reads as a convergence-find for the alpha (it *is* the bottleneck) — same node, opposite uses, keep both.

---

## STEP 3 — THE CATALYST GATE

The forward-revenue test (R1, loaded) pre-applied to events: Yes → reality moved, re-rate. No → only sentiment/mechanics → opportunity (or noise). Carry it and you adjudicate a catalyst no list named — so lead straight into the cases, don't re-sort the obvious (index inclusion / mega-contract / EO / guidance-raised beat / export-control monopoly = REAL; CFO resignation / conference / shutdown / tariff-tweet = noise; a *beat* alone is execution, a beat *with a raise* moves forward revenue). Keep only the handles the test alone misses:

- **TAM-changing vs flow-only.** ⚠️ GOTCHA. A catalyst can be *entirely real* yet not raise addressable revenue — neither noise nor a re-rate, but a **bounded, short-term trade**. The binary real/fake split buckets it as "real" and tempts you to hold a pop like a re-rate, bleeding the gain back when the flow rotates out. Forward *revenue* changing is the hold license; mere inflows changing is a horizon-bounded trade only — match the horizon to which kind it is.
- **Prediction-market gauge.** A market (Polymarket etc.) pricing an event **>90%** already priced it — the occurrence is noise, and retail panic on the "news" is the buy. A *surprise* outcome (low prior, it happened) is NOT priced → real repositioning. The number is what makes "priced in" checkable instead of a vibe.
- **Regulation cuts both ways.** ⚠️ GOTCHA. A new legal framework is often the *biggest* catalyst — it changes what a business is *allowed to be*, the most durable forward-revenue change there is. Ask: one name or the whole category? tailwind or headwind? It can re-rate a category (a stablecoin/payments law turning an issuer into quasi-infrastructure) or cap a model (a DTC/clinical-access rule). The market trades the *framing* ("safety," "consumer protection") while the *clauses* mechanically force flows the narrative hides — and that framing often masks an incumbent-chokepoint motive. When you suspect the headwind side, **read the actual clauses for who is mechanically compelled to buy or sell** and trade that against consensus. A reserve/collateral mandate the largest holder can't meet with illiquid assets makes it a *forced seller* of its liquid ones — trade that against the bullish "regulatory clarity" story.
- **Short-squeeze setup.** Extreme SI (**>30–40% of float**) on a *profitable, growing* name = a bonus upside catalyst layered on a thesis you'd own anyway — any guidance raise lights the loop for free. The same SI on a broken name is a falling-knife dressed as a squeeze. The fundamentals gate, not the SI number, tells them apart.
- **Competitor launch or fumble.** A rival shipping, delaying, or failing redistributes the *category's* forward revenue toward the names that didn't fumble — run the test one level up at the category, not just the named company.
- **Two the test won't catch on its own.** Dividend front-running is a *timing* catalyst — optimize entry on already-validated large-caps, never a thesis. Analyst initiations/upgrades LAG price — a confirmation read (V8/V10), never a reason; calling an upgrade after a 20% run a catalyst inverts cause and effect.

---

## STEP 4 — MACRO → MICRO: ROUTE / SIZE

Every macro event reaches a stock through a transmission channel — classify each by R1 (fundamentals → size to it; sentiment → entry-only, trade the dip, don't re-rate), and a novel event traces the same way onto the same line.

| # | Channel | Class |
|---|---|---|
| 1 | **Rate move** → CapEx cascade + a rate-sensitive cohort (see below) | changes fundamentals |
| 2 | **Export controls** → monopoly premium; the Western/domestic alt inherits pricing power, the removed competitor can't re-enter | **changes fundamentals** |
| 3 | **Tariff noise** → TACO trade; no real transmission on a name with zero actual exposure | entry only |
| 4 | **Algo earnings misparse** → algos misread a one-time charge distorting EPS; reverses once humans process it | entry only |
| 5 | **Tax harvesting** → artificial Nov–Dec selling in quality, January mean-reversion | entry only |
| 6 | **Credit stress** → weak fail, strong survive; share shifts to strong balance sheets | **changes fundamentals** (a feature for survivors) |

Only #2 and #6 move fundamentals (size to them); #3/#4/#5 are pure mechanical dips (trade, don't re-rate). The trap is reading a #6 — a survivor *gaining* durable share — as an entry-only dip, which under-sizes a real structural win.

### Rate cuts — route bidirectionally, and READ the gauge
A rate move hits both the CapEx cascade *and* a rate-sensitive cohort. Read the cut probability off a market-implied source (**Polymarket / Fed futures**), then route it *past* the cascade into the cohort it marks:
- **Cuts priced IN** → long-duration growth (far-out earnings marked UP, the sharpest re-rate — far-out revenue is the most rate-sensitive via DCF), small-caps / Russell with floating-rate debt, direct beneficiaries (housing, fintech lenders).
- **Cuts priced OUT** → the map **inverts** — the win rotates to banks / stablecoins / insurers earning the spread. A "no-cuts" regime isn't the *absence* of a trade, it's a *different* trade.

Institutions front-run the cut, so position before it prints and treat the cut date itself as a likely sell-the-news dip to add into.

> **⚠️ TWO HARD STOPS on the rate angle** (the rate read sets the cohort the whole answer marks up or down, so a vibed or deleted gauge corrupts everything routed off it):
> 1. **To DISMISS a stated rate regime you must quote an actual gauge number.** "0 cuts priced" with no Polymarket/Fed-futures figure shown is vibing, not sourcing — it does not earn the dismissal. Absent a real number, honor the stated regime and run the routing.
> 2. **Never DELETE the rate angle.** The move completes in one direction or the other — route into long-duration growth when cuts are priced in, *or* rotate to spread-earners when priced out. "Rates don't matter here" is the failure, not an answer; it leaves the highest-leverage channel unanalyzed.

---

## GEOPOLITICS & POLICY (US-investor lens)

- **Never bet against US policy.** National-security verticals (AI, space, energy, critical minerals, quantum) are government-backed — a policy floor is a forward-revenue floor that doesn't clear when sentiment does, because it's spending mandated by national-security priority, not by the market. Fading it shorts an entity with an effectively unlimited balance sheet and a non-economic objective. Most geopolitical headlines are noise; the policy-backed verticals are the few that are structural.
- **Reshoring = Made-in-America moat** (first-class for a US-only book). When export controls / security mandates force reshoring, the **domestic** producer in an industry whose competitors sit in high-risk geographies gains an instant structural moat — the foreign competitor is now legally/strategically excluded. The rare thesis where the structural edge and the US-listing constraint point the *same* way, no resolution ladder needed. (Eg. a CHIPS-Act / security-mandate order forcing domestic sourcing of a component whose only alternatives sit in a high-risk geography hands the sole US-listed domestic producer a policy-mandated moat — the worked transceiver-fab case is owned by discovery/analysis.)
- **Export controls create monopolies.** They hand the US-listed beneficiary *outside* the controlled geography a **monopoly premium** — the removed competitor can't re-enter (legal exclusion, not a price it can undercut), so the survivor's pricing power is durable forward revenue, not a cyclical spike. Check whether it's already in the multiple before treating it as a catalyst; a well-telegraphed control usually is. (The inversion — a US name that *manufactures inside* the controlled region is a permit-hostage, and a maker who does both must net the two — is serenity-analysis's Geographic moat plane. Don't read concentration one-directionally here; route there.)
- **A subsidy/grant is a three-way signal.** Beyond the funding floor: grant *inclusion* is outsourced supply-chain diligence — a state only funds genuine chokepoints, so inclusion validates the node is critical, and **two governments independently funding the same node compounds it**. And a name surfacing in a published policy blueprint / supply-chain impact-analysis is a *datable* forward catalyst that reprices on a multi-month lag as the policy machinery turns. Treat a grant as cash-only and you leave the validation and the lagged catalyst on the table. (Discovery mines the *same* government document as a pre-vetted ranked candidate list; the catalyst/floor read is owned here.)
- **Cross-fire casualty / TACO.** ⚠️ GOTCHA. A broad geopolitical selloff, or an overreaction to a known/empty tariff threat, drags down quality names with *zero* exposure to the trigger — Fear-Dislocation by policy headline, a gifted dip (V1). The asymmetry is real *only if* exposure is genuinely zero — **verify the zero exposure first**, or a "TACO dip" becomes catching a name whose forward revenue really did take the hit. A tariff tweet dragging a 60%-margin oligopoly with no actual tariff exposure down with the sector → verify, then buy.
- **Read the policy persona → rotation map.** Whoever holds power (administration, central bank) has a consistent set of favored/disfavored verticals (energy vs climate, defense vs aid, crypto-permissive vs -hostile). The persona is the most *predictable* macro input — it telegraphs which verticals get a multi-quarter tailwind before any specific headline prints. Map it to a standing rotation map and position the *hunt* ahead of the catalysts it'll produce rather than reacting to each EO. Policy is a multi-quarter driver, not a headline.
- **Crowded-but-right ≠ wrong.** ⚠️ GOTCHA. A consensus trade that's *directionally* correct can stay crowded a long time; what kills you isn't being early, it's capitulating at the shakeout — which is engineered precisely to make holders fold into a still-valid trade. "Everyone's in it" is a vibe, not a kill signal; a crowded trade only breaks when the *thesis* breaks. If the thesis is intact (contracts, price hikes still printing), a crowding scare is a conviction test — re-run the kill signals, not the crowd.
- **Foreign winner → route it, don't stop at "inaccessible."** Geo/policy theses surface foreign pure-plays often. Name the foreign winner honestly, then hand off to the **US-listed resolution ladder owned by serenity-discovery** (it also owns the foreign-up-listing forced-buying catalyst and the hostile-local-media shake-out during the up-list window). The only macro-relevant fact is the trigger: a foreign winner is not a dead end.

---

## LIQUIDITY & SEASONALITY

- **Four drains — count convergence on a ladder.** Four *independent* channels pull risk capital out: crypto precursor shock · Fed/policy hawkish surprise · AI credit stress · carry-trade unwind. Because they're independent, multiple firing at once means capital is leaving through several doors simultaneously — a systemic-withdrawal signature no single channel produces. **One = noise (normal posture); two = tighten stops on marginal positions; three+ = cut leverage, hold only highest conviction.** The count turns a fuzzy "things feel risky" into a graded response.
- **Nov–Dec → January — the most actionable seasonal.** Tax-loss harvesting forces selling in down-YTD quality names irrespective of fundamentals (the cleanest recurring fear-dislocation — the seller is mechanical and calendar-bound), with mean-reversion in January → **build in Nov–Dec, harvest in January.** But it's *known*, so institutions front-run and can invert it — confirm it isn't already priced before treating it as clean.
- **Tax-harvest timing — wait for December.** ⚠️ GOTCHA. A Nov dip in a down-YTD quality name is partly harvest selling that *persists through November*. The naive read ("quality name down, fear-dip, buy") catches a knife that keeps falling, because the mechanical seller has a *known end date* (year-end) and isn't done until the tax window closes. Wait for December; don't read the Nov dip as a clean fear-dip yet.

---

## CONTRARIAN TIMING

- **Position before the catalyst — sentiment direction is the inverse signal.** News is data; sentiment *direction* is the inverse signal. Institutions front-run known catalysts, so position *before* the event — on the announcement you buy after the front-runners, into the sell-the-news. When multiple *independent* contrarian indicators converge on a **fundamentally strong** name, maximum pessimism is the asymmetric entry — converging independent pessimism there is the market mispricing structure via sentiment (the R1 gap), whereas the same pessimism on a weak name is correct.
- **Narrative-flood-as-accumulation-tell — fire the prove-the-math fade.** ⚠️ GOTCHA. A sudden *coordinated flood* of bearish notes on a name you hold — a cluster of sell-side "bubble" calls riding the macro fear-theme-of-the-week (Oil / LNG / Helium / Iran / "KOSPI crash") — is itself the accumulation tell, and it often fires *before* any price drop (that's the tell it's manufactured, not reactive). A coordinated bearish flood with no forward-revenue change behind it is information about *flow* (a large player needs liquidity, or wants retail to paper-hand the float so they can take it), not about the company. Separate the forward-earnings reality (contracts, price hikes already printing) from the ambient narrative, and **fade the narrative with hard margin math.** Eg. Oil/LNG/Helium KOSPI fears are bad math — a 50% energy spike = −0.7% SK Hynix / −2.4% Samsung OP vs 58–70% margins, helium "almost no chance"; *if margins were actually threatened the selloff would be justified* — they're not, so the gap IS the trade.
- **YOUR bearishness only on a real forward-revenue change — never on noise volume.** ⚠️ GOTCHA. The discriminator that stops the fade from rubber-stamping every dip: when *you* turn bearish it must be on a real forward-revenue change — a dilution-quality flip (an at-market ATM replacing a contract-funded build), a designed-out cut — never on the volume of the noise. A loud doom-theme is not, by itself, a bear signal *or* a buy signal; only forward revenue changing is. This routes your own bearishness through the same R1 test you apply to everyone else's, so "think independently" never collapses into "always do the opposite of the crowd."

---

## MACRO NUMBER-DISCIPLINE BRIDGE

Every load-bearing macro number — a cut probability, a net-liquidity reading, a VIX level, a short-interest %, an energy-cost delta in a prove-the-math fade — traces to the pipeline JSON or a named external gauge (**Polymarket / Fed futures / LME / TrendForce**). The never-cite-from-memory invariant is always-on from CLAUDE.md; it lives here too because a macro figure routes an *entire cohort* off a single gauge, so a recalled-wrong number mis-marks the whole book, not one name.

---

## INVARIANTS (this lens, every time)

1. **Regime first.** When a turn is macro AND more, run the regime read before any downstream name and let them inherit the dial.
2. **The one test governs every event.** Does this change forward revenue? Yes = re-rate, No = opportunity/noise. Catch the handles it misses (TAM-vs-flow, prediction-market gauge, regulation-both-ways, dividend-timing, upgrades-lag).
3. **Fear-Dislocation ≠ Crisis/Wartime.** Identical tape, opposite move — add to your names vs rotate the cohort. Never collapse them.
4. **Classify before sizing.** Fundamental change = size to it; entry-only = trade the dip, don't re-rate.
5. **The rate angle is never vibed and never deleted.** Quote a gauge to dismiss a regime; always complete the move in one direction.
6. **YOUR bearishness only on a real forward-revenue change — never on noise volume.**
7. **Every macro number traces to code or a named gauge.** No figure from memory.
