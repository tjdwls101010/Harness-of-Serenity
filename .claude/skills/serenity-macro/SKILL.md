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

This lens runs *before and around* any single name. It does two jobs: it reads the **regime** into a posture (how aggressive the hunt, how loud the go), and it runs the **forward-revenue catalyst test** on every event. Everything else is one of these two specialized to a recurring case.

> Loaded every turn from CLAUDE.md, so NOT restated here: never cite a number from memory · US-listed only · V2 falsification · bear-case-mandatory. This skill adds only the *macro-specific* number bridge and two macro-local hard rules (bidirectional rate-routing; YOUR-bearishness-only-on-forward-revenue). Bodies owned elsewhere and only pointed to: the US-listed resolution ladder + foreign up-listing catalyst (serenity-discovery); the IV→Vega vehicle and the geographic moat-vs-hostage *net-the-two* read (serenity-analysis).

## THE BACKBONE — run in dependency order

```
1. REGIME read    → set the aggression dial (do this FIRST, every macro turn)
2. CASCADE locate → where on the Hyperscaler-CapEx → ... → raw-material spine?
3. CATALYST test  → does the event change FORWARD REVENUE?  (the one test)
4. ROUTE / SIZE   → fundamental change = size to it; entry-only = trade the dip
```

The order is load-bearing because each step conditions the next: the same name is a buy in one regime and a pass in another, so resolving the regime first stops you from sizing a thesis correctly in isolation but wrong for the tape. When a question is macro **AND more** ("관세 때문에 뭐 사" is macro + supply-chain + discovery), walk the *union* of lenses in this dependency order — regime first — and let every downstream name inherit the setting. Don't treat macro as a separate answerable question you answer and stop; its real job is conditioning everything after it.

---

## STEP 1 — REGIME → AGGRESSION

**Read the dial; don't re-derive it.** The pipeline computes `regime` + `risk_level` and the four pillars — interpret them into a posture. Risk-On → lean aggressive on conviction. Transition → raise the bar. The gauges come from code precisely *because* a recalled regime read mis-marks the whole book (see number bridge); your job is the interpretation, not the recompute.

**The four regime pillars — hyperscaler CapEx direction is THE load-bearing one.** ① hyperscaler CapEx direction · ② net liquidity (= Fed balance sheet − TGA − RRP, pipeline-computed, read *directional* not as a point estimate) · ③ credit conditions · ④ VIX structure (contango vs backwardation). For any AI-adjacent book **CapEx direction is load-bearing**: increasing = tailwind, flat/declining = reassess everything downstream. *Why it dominates:* the entire CapEx cascade (semis → memory → substrates → raw materials) is downstream of hyperscaler spend, so its direction is the one signal that validates or invalidates the largest cluster of theses at once — it moves forward revenue for the whole chain, not sentiment. Reading VIX *alone* gives a fear spike with no fundamental read — you'd buy a dip the cascade is actually turning against. Combine the pillars; elevated VIX by itself is insufficient. (Net liquidity is named with its three parts so you can attribute a swing to a TGA refill vs an RRP drain rather than treating "liquidity" as an opaque mood — but it comes from code: interpret, don't recompute.)
> Verbatim serenity signature (DB-confirmed): **"The biggest signal of whether the AI trade continues is hyperscaler spending."**

**Fear-Dislocation is the BEST buying environment — but wait for forced-seller exhaustion first.** Fear elevated, fundamentals intact → the single best buying environment (V1): the supply-chain thesis is unchanged, the price is gifted. Naming it the *best* (not merely "a buyable" one) is the deliberate behavioral nudge — it keeps you buying when the tape feels worst, exactly when instinct says wait, because the market reacts to sentiment faster than to structure and this is the maximal gap between price and unchanged structure. **Operationally: wait for forced selling (margin calls, redemptions) to exhaust, THEN enter** — forced selling is price-insensitive and overshoots, so entering before it exhausts is catching the knife mid-cascade. Quality snaps back *first* because it's what the remaining real buyers want.

**Crisis/Wartime is a 4th regime — structural ROTATION, not buy-the-dip.** ⚠️ GOTCHA. When active conflict / a sustained geopolitical crisis / a structural policy shift (sanctions, trade-war escalation) creates a *durable* sector rotation — not a temporary fear spike — treat it as a distinct regime **the pipeline won't flag**. The action is *rotate the portfolio* (capital actively into defense / energy / national-security, out of civilian/consumer names lacking crisis resilience), NOT "buy the dip." The trap is that Fear-Dislocation and Crisis/Wartime **look identical on the tape** (everything red) but demand opposite moves: in one the thesis is unchanged so you *add to your existing names*; in the other the thesis-set itself rotated, so adding to peacetime names is buying into a structurally impaired cohort. Collapsing the two means you "buy the dip" on a name whose category just lost its forward revenue. (A sudden conflict pops small caps but isn't a TAM increase — not a multi-x or a long hold *unless* the war structurally shifts the category.)

---

## STEP 2 — CAPEX CASCADE: THE TRANSMISSION SPINE

**The chain, in fixed order — and the proxy read-through it generates.** Demand moves down the physical chain in this order:

```
Hyperscaler CapEx → neocloud deals → semiconductors → memory → substrates/optics → raw materials
```

Everything in this lens reads off positions on this spine. **The cascade's alpha:** after any major report the reporting company's numbers are public but the supply-chain *implications* are not yet priced — locate the names one-to-three hops down and position *before* the read-through prices. *Why the gap is tradeable:* the market prices the reporting name's beat instantly but takes days-to-quarters to re-price the suppliers it structurally implies, because no analyst covers both the reporter and the three-hops-down node. Without the ordered spine you treat each report as isolated news instead of a demand signal for everyone beneath it. (A foundry blowout confirms downstream GPU/substrate/memory demand before those names move; a hyperscaler CapEx raise validates the neocloud tier and component tier before those names move.)

**Earliest signal = the raw-material spot, not the equity.** Information propagates in a fixed order: supply-chain derivative signals (commodity spot, procurement, utilization) → paid industry reports → public news → repricing → earnings confirmation. Earnings confirmation is the *end* of the chain — anchoring on the print structurally guarantees you're late. A spot move with no equity move *yet* is the gap; the equity is the last domino, not the first. **Named sources:** LME / Fastmarkets / Argus (metals), TrendForce / DRAMeXchange (memory), spot indices (specialty gases, PGMs). (A NAND spot move on DRAMeXchange with memory equities still flat = the forward leg the market hasn't priced. serenity-discovery *applies* this to time an entry; the chain + sources are owned here.)

Two cascade patterns carry traps — see **references/cascade-and-spof.md** for the **overflow / tier-1-buys-on-open-market sold-out tell** (⚠️), the **sympathy-selloff real-vs-association split** (⚠️), the **strategic-incentive cohort floor**, and the **hidden single-point-of-failure** read (⚠️). Pull that file whenever you're locating supply-chain read-throughs, judging why a peer dropped, or stress-testing a "diversified" basket.

---

## STEP 3 — THE CATALYST GATE: "does this change forward revenue?"

**One test sits over every headline, drop, and catalyst: does this change forward revenue?** Yes → reality moved, re-rate. No → only sentiment/mechanics moved → that's the opportunity (or noise). This is R1 (always-loaded) specialized to events — carry the test and you adjudicate a catalyst the lists never named, so lead straight into the cases rather than re-teaching the axiom. (An earnings *beat* alone is execution — forward revenue unchanged; a beat *with a guidance raise* is real — forward revenue moved up.)

The real/fake enumeration (index inclusion / mega-contract / EO / guidance-raised beat / export-control monopoly = REAL; CFO resignation / conference / shutdown / tariff-tweet = noise) is just R1 pre-applied — a competent analyst re-derives it the moment R1 is stated, so spending a block re-sorting it is the distrust-tax. **Keep only the four handles the test alone misses:**

1. **TAM-changing vs flow-only — the third cell the binary split misses.** ⚠️ GOTCHA. A catalyst can be *entirely real* (real event, real inflows) yet *not raise addressable revenue* — that's neither noise nor a re-rate, it's a **bounded, short-term trade**. The binary real/fake split silently buckets a flow-only catalyst as "real" and tempts you to hold a pop like a re-rate, bleeding the gain back when the flow rotates out. Forward *revenue* changing is the hold license; mere inflows changing is only a horizon-bounded trade. **Match the horizon to which kind it is.** (A sudden conflict is a real tailwind but not a TAM increase — small caps may pop, but no multi-x and no long hold unless the war structurally shifts the category.)

2. **Dividend front-running is a *timing* catalyst** — optimize entry on already-validated large-caps, never a thesis.

3. **Analyst initiations/upgrades LAG price** — a V8/V10 read, never a reason. Treating an upgrade as a catalyst inverts cause and effect: the upgrade is the lagging confirmation that the move already happened. (An upgrade *after* a 20% run is confirmation, not a reason to chase.)

4. **Prediction-market gauge — >90% priced = the event is noise; a surprise is not.** When a market (e.g. Polymarket) prices an event **>90%**, it's already priced — the actual occurrence is noise, and any retail panic on the news is a buy. A *surprise* outcome (low prior, it happened) is NOT priced — real repositioning required. "Priced in" is usually a vibe; a prediction-market number makes it *checkable* — it tells you mechanically whether the occurrence carries new information (low prior) or none (≥90% prior).

**Competitor launch or fumble — run the test one level up at the category.** A rival shipping/delaying/failing doesn't change the named company's numbers directly, but it redistributes the *category's* forward revenue toward the names that didn't fumble — run the forward-revenue test one hop up at the category, not just the named company.

**Short-squeeze setup — the threshold and the "bonus on a name you'd own anyway" frame.** Extreme short interest (**>30–40% of float**) on a *profitable, growing* name makes a squeeze a **bonus upside catalyst layered on a thesis you'd own anyway**; the same SI on a broken name is a falling-knife dressed as a squeeze. SI is symmetric in the generic sense (don't re-teach mechanics) — the serenity edge is the threshold + the framing: the **fundamentals gate**, not the SI number, tells the two cases apart.

**Regulation cuts both ways — read the CLAUSES for mechanically-compelled buyers/sellers.** ⚠️ GOTCHA. A new legal framework is often the *biggest* catalyst — it changes what a business is *allowed to be*, the most durable forward-revenue change there is. It can re-rate a whole **category** (a stablecoin/payments law turning an issuer into quasi-infrastructure) or cap a model as a structural **headwind** (a DTC/clinical-access rule). Ask: one name or the whole category? tailwind or headwind? **When you suspect the headwind side, read the actual clauses for who is mechanically COMPELLED to buy or sell**, and trade that against the consensus narrative when they conflict. The market trades the *framing* ("safety," "consumer protection" — often masking an incumbent-chokepoint motive) while the *clauses* mechanically force the flows the narrative hides. (A stablecoin reserve mandate → read the clause → the largest holder is a *forced seller* of liquid assets it must post as collateral; trade that against the bullish "regulatory clarity" narrative.) The mechanically-compelled flow is the truth; the narrative is the misdirection.

---

## STEP 4 — MACRO → MICRO: classify every event, then route

**Every macro event reaches a stock through a transmission pathway. Identify which and you know whether it CHANGES FUNDAMENTALS (size to it) or is ENTRY-ONLY (trade the dip, don't re-rate).** That classification IS the move, and it generalizes — trace a novel event's path the same way and place it on the same line. The error a macro headline invites is uniform: over-react (re-rate on an entry-only dip) or under-react (treat a fundamental shift as noise) — the fundamental-vs-entry axis is the single decision that prevents both. (Export controls → monopoly premium = *changes fundamentals* (size). Tariff noise on a zero-exposure name = *entry only* (trade the dip).)

### Rate moves — the highest-leverage channel, routed bidirectionally

A rate move hits both the CapEx cascade *and* a rate-sensitive cohort. **READ the cut probability off a market-implied source (Polymarket / Fed futures)**, then route it *past* the cascade into the cohort it actually marks:
- **Cuts priced IN** → long-duration growth (far-out earnings marked UP — the sharpest re-rate, because far-out revenue is most rate-sensitive via DCF), small-caps / Russell with floating-rate debt, direct beneficiaries (housing, fintech lenders).
- **Cuts priced OUT** → the map **inverts**: the win rotates to banks / stablecoins / insurers earning the spread.

Institutions front-run the cut, so position *before* it prints and treat the cut date itself as a likely **sell-the-news dip to add into**. *Changes fundamentals.* (DB 2069151544320016527 (NBIS) — a 3× rate cut marks up far-out earnings, one channel of the multi-channel macro→micro stack on the thesis.)

> **⚠️ TWO HARD STOPS on the rate angle** (loss-hardened — these guard two model-native failures that each corrupt the whole cohort routed off the gauge):
> 1. **To DISMISS a stated rate regime you must quote an actual gauge number.** "0 cuts priced" with no Polymarket/Fed-futures figure shown is *vibing, not sourcing*, and does not earn the dismissal. Absent a real number, **honor the stated regime** and run the routing. (Asserting a rate regime from a macro *feeling* fabricates the entire downstream routing on no evidence.)
> 2. **Never DELETE the rate angle.** The move completes in one direction or the other — route into the long-duration cohort when cuts are priced in, *or* rotate to spread-earners when priced out. A terminated move ("rates don't matter here") is the failure, not an answer — it leaves the highest-leverage macro channel unanalyzed.
>
> If a question states "in a 3-cut regime," you must either honor it and route into long-duration growth, or quote a Fed-futures number that contradicts it. You may NOT reply "rates don't matter for this name."

**The other five transmission channels** — each already classified fundamental-vs-entry — live in **references/transmission-and-policy.md** (#2 export controls, #3 tariff/TACO, #4 algo earnings misparse, #5 tax harvesting, #6 credit stress), together with the full **geopolitics & policy** block, **liquidity & seasonality** (the four-drains ladder + the Nov–Dec→January seasonal and its ⚠️ November-persistence gotcha), and the **contrarian-timing** block (the narrative-flood accumulation tell + the YOUR-bearishness hard rule). Pull that file for any policy / geopolitics / war / sanctions / reshoring / subsidy / rate-cohort / liquidity-drain / crowding / seasonal / contrarian-fade question.

---

## MACRO NUMBER-DISCIPLINE BRIDGE (the one number rule that stays local)

⚠️ **Every load-bearing macro number — a cut probability, a net-liquidity reading, a VIX level, a short-interest %, an energy-cost delta in a prove-the-math fade — must trace to the pipeline JSON or a named external gauge (Polymarket / Fed futures / LME / TrendForce). Never assert a macro figure from recall.** This is the macro *application* of CLAUDE.md's always-on never-cite-a-number-from-memory invariant; it stays local only because a macro figure routes a whole cohort and the failure is macro-specific. A macro answer routes an entire cohort up or down off a single gauge, so a recalled-wrong number silently corrupts everything downstream — unlike a single-name slip, a wrong regime read mis-marks the whole book. (Asserting "0 cuts priced" with no Polymarket/Fed-futures figure shown is vibing, not sourcing — it does not earn a regime dismissal.)

---

## INVARIANTS (this lens, every time)

1. **Regime first.** When a turn is macro AND more, run the regime read before any downstream name and let them inherit the dial.
2. **The one test governs every event.** "Does this change forward revenue?" — Yes = re-rate, No = opportunity/noise. Catch the four handles it misses (TAM-vs-flow, dividend-timing, upgrades-lag, prediction-market gauge).
3. **Fear-Dislocation ≠ Crisis/Wartime.** Identical tape, opposite move — add to your names vs rotate the cohort. Never collapse them.
4. **Classify before sizing.** Fundamental-change = size to it; entry-only = trade the dip, don't re-rate.
5. **The rate angle is never vibed and never deleted.** Quote a gauge to dismiss a regime; always complete the move in one direction.
6. **YOUR bearishness only on a real forward-revenue change — never on noise volume** (the contrarian-fade clamp; full statement in references/transmission-and-policy.md).
7. **Every macro number traces to code or a named gauge.** No figure from memory.
