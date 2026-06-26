---
name: serenity-analysis
description: >-
  The single-name judgment engine — gate, value, time, and rate ONE stock through the
  supply-chain lens. Load it whenever a question lands on a specific equity, EVEN IF the
  user never says "serenity," "bottleneck," or "archetype": "is $X a buy / should I own
  this / what do you think of <ticker>", "value / price / rate this name", "PT?", "fair
  value", "is it too late / already priced in", "moat?", "how early is this". Also any
  bottleneck/chokepoint thesis, a disruptor or "the next big X" claim, an evolution /
  step-change / "this just became investable" name, a beaten-down quality name you're
  tempted to buy the dip on (falling-knife check), a dilution / raise / ATM / convertible
  / buyback structure read, a cycle-stage or "where in the cycle" read, a kill-signal /
  "should I cut this" check, a head-to-head where the verdict lands on ONE name ("X vs Y,
  which do I own"), a "rate / grade this" ask, and any vehicle question (shares vs LEAPS vs
  CSP vs covered call). A bare ticker routes straight here. Lean toward triggering — a
  single-name verdict run without this lens costs the whole call.
---

# serenity-analysis — the single-name judgment engine

This is steps 2–5 of the funnel on ONE name: name the archetype, run the gates, read the cycle, pick the valuation lens, set entry/vehicle/kill. The pipeline already handed you the facts (run `analyze TICKER` first — the gives-vs-judges split, the never-cite-from-memory and V2 rules, the 6 roots, and the always-on invariants all live in CLAUDE.md; this skill is the situational depth that bites once the JSON is in front of you). Everything below is a verdict the code refuses to make for you.

**The filing's words are a tool-call away.** `analyze` ships the deterministic XBRL numbers (country %, customer-concentration %, inventory, purchase obligations) but NOT the relationship prose. The moment a verdict turns on *who* the named customers/suppliers are, the critical-input sourcing, or the financing STRUCTURE (the funded-vs-dilution gate, kill-#8's raise terms) — invoke the **`serenity-filings` subagent** (via the Task tool) to read the 10-K/10-Q/8-K and return those facts verbatim. Don't infer a counterparty or a raise term from memory when the subagent can pull it from the filing; a DEDUCED link stays DEDUCED until it does.

---

## 0 — Name the archetype FIRST (it rotates everything downstream)

Before you value anything, name the *kind* of opportunity, because the discovery question, the winner-gates, AND the valuation anchor all rotate with it:

- **Bottleneck** — a physical chokepoint demand can't route around (no alternate material/process) — *or a jurisdiction/location* one (a US-only fab, a single-country processing step). When customers or sovereigns fund peers to **replicate** the footprint, the footprint IS the scarce node and the integrated owner is the chokepoint, not an overflow valve — so before demoting a vertically-integrated name to "second source," ask whether its scarce attribute is location, not component-share.
- **Disruption** — a faster entrant draining an incumbent's profit pool (take-rate → cents, T+2 → instant, closed rail → open). You're finding the toll-taker on a road being re-paved, not tracing a chain.
- **Evolution** — a datable step-change that just turned a long-promised category fundable; now someone owns the emerging standard.

**Two forks preempt archetype-naming — run them on the raw evidence FIRST:**
- **Step 0a — data-integrity.** Before reasoning from any figure, sanity-check it: Total Assets ≥ Cash + Inventory + the other lines, and no single line (esp. inventory) implausible vs MC or the business model (>3–4 months' COGS for a fabless name is a flag). A ticker-collision / stale / mis-tagged number is ITSELF the mispricing — prove the identity on `key_facts`/XBRL before it drives the read. If the pipeline returned the line null because EDGAR was blocked, that's a *load-bearing gap*, not "proceed without it" — pull it via the `serenity-filings` subagent or the 10-Q press release.
- **Step 0 (preempted) — falling-knife / mechanism-check.** When the entry is a **drop on a displacement / loss / cancellation headline**, don't tag the structural archetype and band the multiple — litigate the *one falsifiable mechanical claim* the headline rests on. (a) Test physical feasibility on the engineering timeline — mask set, embedded IP/SerDes, qualification cycle; an embedded-IP / long-lead fact can make near-term displacement *impossible* (the inverse of second-source fragility). (b) Split **immediate displacement** (often physically impossible → price only if real) from **future-gen diversification** (usually legitimate). (c) Treat a downgrade/retraction sequence as a discrete sentiment-vs-fundamental point. (d) Content-size from the **single-project floor** ("one anchor program alone justifies the price, the rest is free"), not only the full-portfolio target that already reads "priced."

Hardware/materials defaults to **Bottleneck**; relabel to Disruption/Evolution **only on positive evidence** — a *named* drained profit pool, a *datable* step-change — never to escape a floor that returns an ugly number. The inverse error costs exactly the same: don't reach for a disruption story on a clean physical chokepoint just because its grade looks low. The rotation is earned by the name's actual economics, not its screen. Get this wrong and you walk the name down a funnel it doesn't have, mis-framed from the first move (forcing a payments name or a launch-economics name through the chokepoint funnel is the canonical failure). Semis are the worked Bottleneck instance everywhere here — a convenience of recent history, not doctrine.

**Span-two names:** most names are one clean archetype. When a story genuinely spans two (a chokepoint *inside* a disrupted category), run BOTH gate sets and let the **weaker** one set conviction — a name is only as de-risked as its least-cleared door. Where the two anchors disagree, the weaker gate set also picks which one governs.

### Bottleneck — gates & anchor
*Discovery Q:* where does supply physically concentrate as demand scales? *Anchor:* EV-multiple banding vs chain peers; when the input is tiny-TAM but gating, the enabler-material reframe (below). Gates: monetization · pricing-realization · survival · TAM-expansion · allocation-control · demand-breadth (the six, below).

### Disruption — gates & anchor
*Discovery Q:* whose economics are structurally attacked, and who captures the value draining out? Gates: **(1)** size of the profit pool under attack — larger and lazier is better; **(2)** the fee/take-rate delta — a 10x cost advantage, not 10%; **(3)** the moat captured *as it wins* (network effect, a standard, a regulatory license). **Gate 3 is the discriminator** — without a captured moat the disruption is competed away; organic margin-durable share-capture clears it, growth *bought* via acquisition or a subsidized take-rate that evaporates does NOT. *Anchor:* the market mis-applies the incumbent's category multiple — re-anchor on the disruptor's true driver (assets-on-platform × yield + take-rate for money-movement; the OPEX line that just flipped to a revenue line for a margin-inversion), but earn floor-N/A by *demonstration* and a real number, never the label.
*Crisis/regime sub-case:* when the live regime is a conflict/crisis, ask whether an attention/engagement-monetized name is a **forward-revenue beneficiary** (crisis-driven high-intent search & discussion traffic; advertisers rotating TOWARD brand-safe isolated inventory) — that's a catalyst that changes forward revenue (R1), not just a fear-dip to size into. Pair it with the **stale-guidance sandbag** check: guidance issued *before* a dated event is a pre-baked beat, falsifiable at the next print.

### Evolution — gates & anchor
*Discovery Q:* what concretely just changed — a cost curve, a regulation, a technical threshold — that made this fundable NOW, and who controls the new standard? Gates: **(1)** the datable step-change (not "it's the future"); **(2)** who owns the emerging standard / reference design the category converges on; **(3)** a strategic backstop — **BINARY and the discriminator.** A contracted, customer-funded backlog (a Mag7 prepay, a strategic equity round above market) clears it; a buildout funded by its own at-market ATM / serial dilution does NOT — that name carries the de-risking *story* without the de-risking, and grades DOWN. *Anchor:* you're buying an option on category formation — anchor on the TAM the step-change unlocks and the name's claim on the standard, defended with a real driver number, not trailing fundamentals.

### Evolution gate-3 — verify which SIDE of funded you're on (the one fact you can't take from the bull deck)
This is R4 at the neocloud — apply it to the financing STRUCTURE. The neocloud-specific tells that flip "funded" to "dilution":
- **A purchase / brand / "strategic" agreement is not funding.** A vendor letting you use its logo, or taking a risk-free convertible *in you*, puts zero third-party capital into the build.
- **The tell is whether real capital is direct and contract-anchored** — a customer prepayment, an equity check above market, asset-backed debt secured on the offtake — versus the GPUs being bought off a **live, large at-market ATM sized near the market cap** (the dilution engine the "partnership" headline distracts from). A loud Mag7/NVDA "partnership" that reads closely as a logo deal funded by your own ATM FAILS the gate however bullish it sounds.

Two neoclouds wearing the identical "we have a hyperscaler contract" headline can sit on opposite sides of this line — *that line, not the headline, is the call.*

Two follow-on traps on the same line:
- **A tranche carve-out does not launder dilution.** "Only the power-shell is diluted, the GPU leg is funded" holds ONLY if that funded leg is genuinely ring-fenced — bankruptcy-remote, non-recourse to the parent's at-market ATM. A press-release tranche is a *narrative* partition; bankruptcy-remoteness is a *legal* one. When the parent is still buying the build off a live near-MC ATM, the whole name carries the overhang — it ranks BELOW the funded peer, and a narrative carve-out is NOT licensed to lift it back to a BUY. When you feel that override-up tempting you, run the kill-#8 net-the-cash loop on the ATM cash *already raised*.
- **A silent filing is not a funded confirmation.** Absence of a disclosed ATM is not evidence of contracted capital — both the funded call and the dilution call need *positive* evidence; absence proves neither. Hold gate-3 at UNPROVEN and cap conviction there; lean "funded" only on a named, pointable source. A funded read carried only by the contrast with a visibly-diluting peer is *borrowed* conviction, not earned — size it as unproven (the same un-seenness that creates the lead makes you wrong, R3).

---

## 1 — Winner gates & moat (a chokepoint is not yet a winner)

**First, classify the limitation — "can money solve this?"** Only one of three supports a multi-year thesis. **Bottleneck:** physical scarcity capital alone can't fix → multi-year conviction. **Constraint:** resolvable with enough capital + time → tactical trade only. **Risk:** a probabilistic event, not a structural state → hedge, don't build. If any amount of capital, given time, removes the scarcity, it's a constraint — *physics trumps capital.* A true bottleneck meets all three: demand outstripping supply · oligopoly/monopoly · no substitute before demand peaks. Mislabel a fundable constraint as a bottleneck and you marry a multi-year thesis to a pricing window that shuts the moment capacity arrives.

**The 6 winner gates** — a confirmed chokepoint is investable only if it clears ALL six; each doubles as a bear-case generator, and each is a distinct way a real chokepoint still returns nothing (necessary-not-sufficient per V6; reasoning-only, never spoken).

1. **Monetization** — does the position translate to revenue + FCF? Critical-to-the-chain ≠ money in the door; demand a modelable forward revenue ramp.
2. **Pricing realization (behavioral)** — having pricing power ≠ exercising it. Ask not "*can* they raise price?" but "*will* they?" — and "will they?" is gated by **JURISDICTION**, not just temperament, which lets you *predict* non-realization before any name-specific evidence: where law or culture vetoes aggressive hiking, a structural monopoly never converts; where an externally-forced hike would trip foreign-investment-screening law, the veto is LEGAL. The corner-the-input-and-hike playbook works on US-exposed suppliers and stalls on allied-nation ones — knowable from the map alone. A sole-source feedstock maker that never raises price caps near book (an 85% move, not the 5x a price-hiking equivalent delivers).
3. **Survival to the ramp** — can the balance sheet last to monetization? Read the SEC context: contract-backed growth or value destruction?
4. **TAM expansion / value migration** — a static tiny-TAM chokepoint caps the return; winners expand downstream into the stack, then integrate upstream for margin.
5. **Allocation control = synthetic bottleneck** — control multi-year output *allocation* and you ARE the bottleneck even if someone upstream "makes" the input.
6. **Demand breadth / inelasticity** — selling to every player (yield/test/inspection) beats one customer on a dev contract.

### The moat graph — physical · financial · strategic · geographic
Gates get evidence on four planes; each is a route the others miss.
- **Physical** — BOM, bottleneck, criticality tier.
- **Financial** — debt/credit contagion travels DIFFERENT routes than product flow. Two peers with identical customers can have opposite exposure by balance-sheet structure: *if the sector leader's credit cracks, does it reach this name through its debt?*
- **Strategic** — who structurally NEEDS this company to succeed? A larger entity whose position depends on a smaller one will backstop it (an invisible floor); an active co-development partner transfers capability, dropping execution risk below standalone analysis. (Macro maps the same dependency as a cohort-level flow; here it's per-name.)
- **Geographic — moat or hostage?** The same concentration cuts both ways: a scarce node in a controlled region is a MOAT when the name controls and prices it, a HOSTAGE when the controlling STATE holds an export/permit lever over the name's own output. A US-listed maker that MANUFACTURES INSIDE the controlled region is often BOTH at once — net the two, don't read concentration one-directionally (rare earths, gallium, neon, lithium processing all generalize). Reading it one way is how you mistake a hostage for a moat.

### Comparative + inverse-proxy + PE-buyout
Within a sector the question isn't "is this a bottleneck?" but "which is the BEST one?" — rank on integration depth (full-stack > capacity-only), margin quality, contract visibility, balance-sheet strength. **Inverse-proxy:** a well-funded competitor's FAILURE to replicate is the strongest moat evidence there is — a rival's capital saying the moat held, harder than any self-reported metric (*who tried this and failed, and what does it reveal?*). **PE-buyout signal:** a financial-sponsor buyout of a tiny obscure upstream node is independent returns-driven validation that it's a real chokepoint (distinct from synergy-motivated strategic M&A) — and since it removes the public entry, pivot the read-through to surviving listed comparables in that layer.

### Architecture-identity check (before accepting any commoditization claim)
When a name is dismissed as a commodity by comparing ONE headline spec (power, capacity, speed) against a bigger competitor, first verify the two implement the SAME architecture. If the smaller name's value lives in a distinct design that named lead customers chose for system-level reasons (thermal, power-per-bit, integration), the competitor "winning the spec in isolation" is a category error — they aren't substitutes. The customer's DESIGN-IN choice is the revealed preference no single datasheet number captures; a confident single-spec commoditization claim is itself a tell the critic skipped the architecture check.

### Designed-out = a LIVE monitor (this IS kill #9)
Designing a supplier IN is gradual; designing it OUT is one customer decision. Ask: does the position rest on PHYSICAL INEVITABILITY (no alternative exists) or CURRENT CONVENIENCE (best option now, but alternatives could be built)? Physics-based = durable; convenience-based = fragile. But this is MONITORED, not answered once: watch leaks and OEM/CES disclosures for a second source qualifying (a *disclosed* qualified supplier is real evidence; conference *hype* is noise). While odds stay ambiguous, HEDGE and cut concentration — don't binary-exit on the first rumor, don't double down on hope. Re-rate the floor only when the switch is confirmed. And judge the supplier by where it sits INSIDE the customer's program: a prototype/dev-stage qualification is NOT a production-at-scale win (see *prototype ≠ production* below) — that's where confident-looking design wins quietly die at the cost-down.

### `pre_commercial` is a hand-off, not a ruling
The objective layer can raise `pre_commercial` (op-margin < −100%): operating losses exceed revenue, so there's no commercial business to value yet — a story priced on a promise. It is NOT a cap and NOT a verdict, just the cue to be skeptical, routed straight back to the gates. The flag has *at least three* meanings only judgment separates, so don't let it auto-reject:
- Override the skepticism only on a moat you can *show* (a named design-win, a sole-source part) — and first rule out a one-time charge (impairment, litigation, restructuring) dragging trailing op-margin below the line on a genuine business.
- Don't slam to AVOID when a real revenue ramp is keeping it alive — a ramp holds it OFF avoid without earning a bull override UP.
- The same flag fires on a real bottleneck at a cycle TROUGH (capacity intact, margins about to inflect) — so it raises a **Cycle fork** (melting legacy vs cyclical trough) you resolve on revenue/margin *trajectory* and the designed-out monitor, never the snapshot. One behavioral resolver when trajectory is ambiguous: the **tenor of cash commitment** — a supplier that can demand MULTI-YEAR PREPAYMENT to guarantee supply faces a structural shortage, not a cyclical one (revealed preference, louder than any order-book number).

---

## 2 — Valuation (a multiple is meaningless until divided by the demanded denominator, R5)

**The floor is EV/Rev + EV/FCF peer/chain MULTIPLE BANDING** — band the name's EV/Rev and EV/FCF against sector comps AND chain-peers (NOT a "no-growth ×15" scalar — he never said that; the scalar may stay as one deterministic anchor among several, but it isn't the lens). The pipeline surfaces raw EV/Rev and EV/FCF; the banding is your judgment. Present the floor (where it trades if growth stopped) BEFORE the upside — the GAP is the asymmetry, and a name near its floor with visible catalysts is the ideal setup. (Pre-revenue: floor inapplicable — say so, make the growth case primary, apply a larger uncertainty discount.)

**Forward P/E IS PEG** — judge the multiple relative to growth, never by absolute level. The inversions that flip the naive read: a HIGH absolute P/E isn't a reject — **30–40x at 60%+ growth is CHEAP on PEG, and the biggest winners lived there**; a LOW P/E can be a trap — **12x at 5% is expensive**. <15x at 50% growth *screams* (PEG ~0.3 — paying a third of the growth rate). Avoid = above sector comp at DECELERATING growth, regardless of narrative. Build a custom peer set when there's no clean comp. Under pressure you'll reach for the absolute number — the inversion is the edge that stops you rejecting the names that compound and buying the value traps.

**Value accretes toward the scarcest node** — benchmark a name's multiple against the OTHER LAYERS of its chain, not only its own history. The irreplaceable input should out-multiple the assembler it enables; a SCARCER node priced BELOW the node depending on it is the mispricing (buy the scarce node). The inverse — a convenience node priced above its irreplaceable input — is a kill/avoid flag. Set the correct ordering from a mature analog chain, then find a younger chain where the market inverted it (the market inverts young chains because attention pools on the visible end-node).

### Bottom-up content × volume ÷ MC — the load-bearing DEDUCED move
On a design-win component supplier feeding a COUNTABLE end-unit below a megacap, this is the *whole call.* Size the scarce node bottom-up, from one unit of end demand: estimate the supplier's $ or % CONTENT per downstream unit (per robot, per ASIC, per TPU pod), × the end-product's projected unit volume → "implied revenue from customer Y alone," ÷ TODAY'S market cap. The same BOM slice is already priced inside a $70B megacap but *triples* a $2.5B microcap's ARR — so you buy the small-MC leg with leverage to it, not the diversified incumbent.

- **The trigger to run it is the moment you catch yourself reaching for the supplier's own PEG / P-S / trailing multiple and starting to write "priced" / "the easy money's been made."** That top-down read IS the consensus lens on a countable design-win supplier — concluding from it re-derives the exact mistake the gap is built on. Nobody else runs the bottom-up version (they model the supplier off its own historicals — which is *why* the gap exists), and it's the only move that turns a chokepoint-find into a price target.
- The content number is load-bearing and almost always confidential (triangulate from a CEO value-capture quote, a design-win disclosure, a chain map) — so tag it **DEDUCED** and size nothing on the multiply-out until a filing/transcript/conference confirms the per-unit figure (the deduced-until-confirmed rule applies; the same un-seenness that mispriced it makes you wrong). Treat the ratio as a candidate-SIZER, not a pass — a fat ratio does NOT bypass the gates.
- Divide by the CURRENT pipeline-sourced `marketCap` — a wrong MC silently inverts the call (the never-eyeball-the-MC invariant in CLAUDE.md applies here). "Already re-rated / graduated out of the small-MC window" is legitimate ONLY when the bottom-up ratio on today's verified MC says so — never inferred from the dilution/concentration/ATM gates while the sizing math goes unrun. If you wrote the verdict without actually dividing content × end-volume by today's MC, the move did not run: the gates cap conviction, they do not author the priced-vs-cheap call.

### When the framework breaks — re-anchor, don't fake precision
Strategic monopolies, policy-mandated demand, paradigm-shift growth, and disruptors all resist P/E and P/S — this is where R5's re-anchor discipline bites (the absurd verdict is a candidate to re-examine the lens, never a license for the trade; re-anchoring is earned by demonstration and a real checkable number, per CLAUDE.md). The per-archetype recipes that ARE this lens's depth: **Strategic monopoly** (a substrate maker priced at commodity multiples) → anchor on subsidy scale, policy-mandated TAM floor, the strategic value of irreplaceability. **Disruptor** → name the legacy multiple the market wrongly applies, then re-anchor on the disruption's driver. **Stablecoin / float-yield or pre-scale name** → the no-growth floor is N/A, so say so and substitute the float-yield driver, don't print the "overvalued" verdict the floor fabricates.

### Lens-mismatch — the capital structure picks the metric
Check the lens fits BEFORE judging profitability — the wrong one manufactures a false verdict.
- **Asset-financed capacity buildout** (neocloud, data-center, anything prepaid-and-debt-funded): gross margin reads alarmingly thin yet is the wrong lens — a single-digit gross-margin contract is a high-teens-to-20%+ **levered IRR** once customer prepayment and cheap financing are layered in. A thin gross margin on a prepaid debt-funded asset is a *financing artifact*, not an economics verdict. **Naming the lens isn't the verdict — build the unit model** (revenue/GPU-hr → $/MW-year → itemized COGS → gross profit/MW → normalized margin → levered IRR *after* financing) and **fan to the 2–3 normalized siblings**: the alpha here is cross-name margin normalization + capital-structure disqualification (a peer whose debt interest eats the IRR fails), not standalone banding. Carry a **bull falsifier** (utilization / adoption-% / execution) beside the bear — this archetype's risk is delivery, not direction.
- **Margin-inversion** (an OPEX line flips to a revenue line — storage, compute, logistics, payments float): don't retreat to EV/Rev or declare EV/FCF N/A on a *trailing*-negative print — the thesis IS the forward-FCF inflection. Build the pro-forma — COGS line × %-addressable → OPEX saved; users × adoption% × ARPU → new recurring revenue → **net FCF delta** — and band that pro-forma FCF at growth-tech ~25–35×. Size the inversion specifically AND build the upside leg, not only the SBC/dilution bear.
- **Asset-value turnaround** (revenue/margin melting but the balance sheet holds hard, redeployable physical assets — fabs, reactors, GW capacity): value on **replacement cost** + a pure-play comp **per unit of physical capacity** (reactor count, MOCVD systems, MW), NOT EV/Rev or gross margin. The distressed income statement is the *source* of the mispricing, not the disqualifier — a low GM is expected; the bear is dilution / failure-to-restructure. A hardware/materials name trading near or below tangible-asset replacement value triggers this lens *before* the pricing-realization gate.
- **Vertically-integrated name spanning several chain stages:** don't stamp the scarcest node's multiple on the whole company (that overshoots — the chain-multiple read RANKS nodes, it doesn't price a conglomerate); blend each stage's standalone multiple by its revenue share so the name prices BETWEEN the extremes.

### Enabler-material reframe — TAM is a floor, not a ceiling
For a tiny-TAM input that physically GATES a huge deployment, its current TAM is a FLOOR not a ceiling. Price it as an option on the gated end-market — willingness-to-pay is set by the COST OF NOT HAVING IT (a $100 part that strands a $20B buildout commands orders of magnitude more than its commodity spot), not the input's price. Consensus systematically UNDER-values these by anchoring on input TAM; that gap is the asymmetry.

### Sanity-band the upside against supply-shock base rates
Calibrate a chokepoint's plausible magnitude against a SPECIFIC named base-rate set — **rare-earth · specialty-gas · PGM · the memory supercycle** — where concentrated supply + inelastic demand produced multi-hundred-to-thousand-percent moves. Without an external base rate a chokepoint upside is just a number you wanted; that named history is what separates a credible 5–10x target from fantasy, and keeps a re-anchored driver honest.

### Revenue & earnings quality
At equal multiples the higher-quality dollar is cheaper: contracted (especially customer-funded CapEx) > recurring > speculative. **The GAAP-vs-non-GAAP / SBC gate:** non-GAAP "Net Income" is NOT GAAP net income — a $500M non-GAAP figure can be a $150M GAAP LOSS once SBC is counted; verify which is quoted before trusting any earnings number (the related tell: reported FCF positive but real FCF after SBC negative = optical illusion). SBC is the most common way a promotional name shows profit it doesn't have. **Normalized peer tables:** before ranking peers, normalize to the same assumptions (same GPU gen, same depreciation schedule, same utilization) — an un-normalized comparison silently ranks accounting choices instead of economics and "means nothing if accounting is not normalized."

### Sum-of-parts / hidden-stake unlock
A name can be worth more than its market cap on a single asset. When a subsidiary stake or a hidden holding (a tracked sub, an equity holding in another listed name, a spin-out) may exceed the parent's whole MC: surface the stake, value it STANDALONE, blend against the operating business, compare to the parent's MC — the gap is the unlock. The market prices the consolidated headline and routinely ignores a stake worth more than the whole, because attention pools on the operating story not the balance sheet.

### Funding price floor
A recent (<6mo), significant (>5% of MC) strategic investment priced ABOVE market is a SOFT floor — a sophisticated counterparty did diligence there and will defend it in normal tape. Probabilistic; broad distress overrides it. (Same fact as kill-#8's premium-priced raise, read on the valuation side rather than the dilution-structure side.)

---

## 3 — Cycle stage (an evaluation lens — how early & de-risked — never a sizing one)

Read cycle stage from the name's OWN revenue/margin evidence, not the category label you filed it under, and re-read each quarter since names migrate. The two reads that matter most:

**Magnitude peaks early; the thesis de-risks late — and they don't peak together.** MAGNITUDE peaks at stage 2 (qualified, not yet repriced) — exactly where binary designed-out risk is live and the thesis unproven. By the confirmed ramp, earnings de-risk the thesis quarter after quarter but most magnitude is already priced. So an early name is high-asymmetry/low-certainty and a confirmed-ramp name is lower-magnitude/earnings-validated — SAY which you have, or you'll demand confirmed-ramp certainty at stage-2 prices (and never buy) or pay stage-2 magnitude on a stage-4 name (priced-in disappointment).

**Stage migration IS the hold thesis.** A name migrates 2→3→4, and that migration is why a thesis survives an ugly stretch: a capital-burning buildout is a 2/3, and once spend converts to FCF it's a 4 — holding through the capex-burn ugliness is the whole thesis, not capitulating into it. Timing: a bottleneck two years out is dead money now — flag the entry window ~8–12 months BEFORE an inflection, re-enter closer to the ramp; a stage-5 revenue cliff is an exit call regardless of how good the story was. Migration also picks WHICH NODE to hold across a phase transition: through a qualification/capex phase that precedes volume, own the **equipment/tool supplier FIRST** (paid DURING the build, its P&L inflects 2–3 years earlier), then rotate to the **pure-play volume producer** once the theme crosses qualification→volume (tools don't capture downstream volume economics).

### The pull-forward trigger most miss
Because price is set 8–12mo ahead, an inflection arriving EARLIER than the Street modeled re-rates immediately — the *compression of the date*, not mere re-confirmation, is the tradeable event. Sharpest instance: a **dated sold-out horizon** ("sold out until 2027") PLUS an announced **contract-price hike that exceeds the Street's modeled increase** is forward revenue at a FATTENING margin you can clock before the print — the above-consensus slice is near-100%-drop-through profit (a NAND +100% against a 33–38% model is ~65 unmodeled margin points). Enter while the forward P/E still prices it like slow-growth commodity.
- **Discriminator:** verify the sold-out is FUNDED demand — a sold order book, a customer-prepaid allocation, a tier-1 buying the input on the open market — NOT the name itself selling stock into the open market (the identical "open market" phrase flips from buy-signal to dilution-kill depending which side the company sits).
- **The reflex this beats:** a cheap multiple on a commodity/memory bottleneck whose margins are ALREADY EXPANDING reads as "peak-cycle value trap — don't pay up." An EXPANDING margin is NOT by itself a late-cycle sell. Flip to "late-cycle value trap" only when the spot/contract index is actually ROLLING OVER (kill #6) — the *price of the input* turning down, not merely the margin being high.

*(The full 5-stage table — guess-the-bottleneck · qualified-no-ramp · inflection-early · inflection-mid · end/structural, each bound to pipeline fields — is the deep catalogue; the two reads above are what you carry every time.)*

---

## 4 — Entry / vehicle / kill / conviction

### Falling-knife discrimination — the 4-step (run BEFORE responding)
The pipeline raises `absence_evidence_flags.no_fundamental_change_selloff → potential_entry` — it does NOT say "buy"; it flags "this drop has no disclosed fundamental cause, here's a candidate" and hands it to you (absence-of-bad-news is all the code can see; confirming the dip is safe is yours). V1 alone catches knives. When the flag fires (or any name you'd own drops hard), run all four first:
1. **Identify the mechanism** — mechanical/sentiment (MM hedging / option-pinning, algo misreading a one-time tax charge, margin-liquidation cascade, sector contagion by association, tax-loss harvesting, retail panic) OR a real fundamental change? Tell: mechanical drops reverse when the switch flips, and their magnitude is disconnected from real news.
2. **Prove the math** — does the scary headline actually hit the numbers? If it's BAD MATH (an energy spike denting <2% on a 60%-margin oligopoly; a "displacement" physically impossible mid-cycle), the gap between fundamentals and price IS the trade.
3. **Institutional-accumulation tell** — in a true fear-dip institutions accumulate INTO the drop (IO% rising, dark-pool prints) while retail panic-sells (13F lags, corroborate).
4. **Clear the kill signals** — if a real one fired (designed-out, dilution, sector-price crash, CapEx cancellation, restatement), it is NOT a fear-dip; step aside.

**Prove-the-math fear-fade** (his single most-repeated quantitative pattern): fade a coordinated bear narrative with hard MARGIN math — compute exactly how much the scary input moves the number; if trivial, the gap is the trade. Coordinated bear floods rely on the reader NOT doing the arithmetic ("if margins were genuinely threatened, the selloff would be justified" — so quantify the threat instead of feeling it; e.g. a 50% energy-cost spike shaving ~0.7% off a 58–70%-margin memory maker).

### The V1 guardrail — applied to the knife
V1's right-and-early, made operational: even when the discrimination says "buy," fear overshadows fundamentals short-term. Scale in slowly, never on margin in a high-fear tape, expect to bleed before vindication. The repeated, confessed mistake is conviction-without-the-right-vehicle: catching the knife with *shares* instead of getting paid to wait. Being structurally right doesn't stop a high-fear tape going lower first — the failure isn't the thesis, it's expressing a correct thesis with the wrong vehicle so you can't survive the bleed.

### IV picks the vehicle (this is the single home for the IV→vehicle decision)
Let IV choose:
- **Compressed IV + high conviction → LEAPS** (cheap leverage + IV-expansion tailwind); also the move on low-IV sector/index ETFs you believe are directionally up. On a **thematic ETF**, a long-dated OTM LEAP can DOUBLE on Vega expansion alone — reason through the ETF's NAV composition to confirm the exposure (e.g. a holding co that's ~90% one underlying gives you that underlying through the ETF).
- **Elevated IV (the fear-dip default) → cash-secured puts:** sell a put at a strike you'd happily own (assignment = bought at target + premium; no assignment = paid to wait). The fat premium IS the fear's volatility harvested; CSP > knife-catching shares whenever IV is elevated.
- **CSP-laddering by IV tier:** <30% IV not worth it; 65–100% the sweet spot; 100%+ the danger zone — beta-size the margin, never write puts on stocks you're not comfortable buying.
- **Extreme IV → covered calls** on names you already own.

Rules: only on names that pass the full framework; **NEVER sell CSPs with earnings inside ~7 days** (check days-to-earnings FIRST — inside that window default to shares or wait; gap risk is uncompensated by the premium); size leverage by beta; TA informs WHERE to enter a validated name, never WHETHER. The vehicle is how you get paid to wait through the V1 bleed — selling elevated IV harvests the very fear mispricing the name.

### The 9 kill signals (+ the principle that spots a 10th)
A kill signal isn't "the price dropped" — it's anything that BREAKS a load-bearing assumption OR FLIPS the risk asymmetry so downside now structurally exceeds upside. Response falls out of which kind: a broken core assumption → the thesis is gone (exit, no trim); a mechanical, quantifiable, recoverable pressure → reduce/hedge and wait. Define the kill by this PRINCIPLE, not the list, so you catch the #10 that isn't enumerated. The nine recurring instances:
1. **MC/valuation disconnect** — no revenue/earnings path anchors the price → exit, no partial trim. *(Acute case: **wrapper NAV-premium** — a vehicle holding illiquid private positions trading at many multiples of underlying NAV; the premium is itself the kill however good the holdings; with no float/options to short, the move is DON'T BUY, then expect violent reversion to NAV.)*
2. **Suspicious fundamentals** — restatement, auditor change, rev-rec anomaly → exit immediately.
3. **Meme trap** — price fully decoupled from any thesis → trim to zero.
4. **Lockup expiration** — insider incentive to sell into the unlock → reduce/hedge, model the overhang.
5. **Inverse Cathie Wood** — ARKK accumulation as a hype-peak warning → tighten discipline, re-examine the bear case (not auto-exit).
6. **Sector-collapse signal** — the chain's leading indicator crashes (NAND/DRAM spot, fab utilization) → reassess the WHOLE chain.
7. **CapEx cancellation** — a downstream customer cancels/delays CapEx; if >20% of the forward model, the thesis may be broken.
8. **Dilution** — read the STRUCTURE (below).
9. **Designed-out** — the live monitor in §1 (below).

### Kill #8 — dilution: read the STRUCTURE before calling it a kill (both directions)
The true kill is SERIAL, value-destroying ATM — management that habitually prints stock into the open market to fund the burn → exit on the PATTERN, not the first raise. A single raise is a capital-markets event whose structure decides everything: **instrument** (a premium-priced convertible >> an at-market ATM), **coupon** (0% >> 9%), **use-of-proceeds** (a named contract-backed build >> general runway), and whether it's already priced in. Contract-funded / 0%-coupon / pre-announced dilution is often a BUYABLE DIP. The pipeline flags only the quant; the kill-vs-buyable call lives in the 8-K/424B structure it can't read. The read runs BOTH directions:
- **Price the raise against spot** — when a sophisticated counterparty (convertible, PIPE, strategic round) pays ABOVE market, that premium is a conviction floor above spot (a front-runnable bullish anomaly, inverse of the default "raises come at a discount").
- **Invert the buyback's friendly reputation** — a buyback funded by ISSUING DEBT and sized to roughly offset annual stock-comp is not a return of capital; it masks SBC dilution and quietly flips the balance sheet to net debt. Reconstruct as-if-cash FCF to tell it from a real buyback paid out of surplus.
- **The circular self-justification loop** (one tell inside this kill): management dilutes retail off a live ATM to hoard cash, then points to that cash pile to claim a higher "deserved" MC and awards itself SBC out of the proceeds. That is value RELOCATED from new buyers to insiders, not created — a fat balance sheet BUILT FROM at-market issuance is NOT a floor. **Net the cash against the shares it cost and the SBC it funds before crediting a dollar;** cash raised off a live ATM is a red flag, not an asset.

### Kill #9 — designed-out: scope WHICH LAYER the cut lands on (the inversion)
Responds per the §1 monitor (confirm → exit; ambiguous rumor → hedge/cut not binary-exit; watch hardest at the cost-down). But scope WHICH layer before reading it as bearish: soft layers (packaging, assembly, integration) get in-sourced relatively easily; the hard physical/IP layer (the light source, the substrate, the irreplaceable material) can't just be spawned. So a customer severing a ONE-HOP INTERMEDIARY ABOVE your hard-layer name — cutting the *packager*, not you — is often BULLISH for you: they now buy the hard input direct, a higher-margin tier-1 relationship, and demand re-routes TOWARD you. The default "customer cancels supplier = chain-wide bearish" INVERTS when the cut concentrates value into the hard layer it depended on.

### Conviction dynamics — strengthen · erode · inherit · post-mortem
Conviction is a continuous variable (a mark on confirming-evidence − the live falsifier, R6); manage it.
- **Strengthening:** a high-conviction name drops with NO kill signal → asymmetry rose; re-check EVERY kill signal, and if all clear and the cause is mechanical, scale up ONE tier — NOT blind averaging-down (one ambiguous kill and you don't escalate).
- **Erosion:** no kill fires but no catalyst materializes either; at ~2x the expected catalyst timeline force a re-examination — if the thesis holds but urgency faded, downgrade to watch-only; if you can't re-articulate it with fresh conviction, exit (zombie theses dilute focus).
- **Inheritance:** when a thesis wins, its transferable pattern (formation, sector dynamics, customer profile, margin structure) is a HYPOTHESIS for similar names — but each must INDEPENDENTLY pass the gates; inheritance accelerates discovery, never bypasses validation.
- **Post-mortem** (every loss): classify — (A) right thesis/wrong timing → adjust horizon; (B) partially wrong → find the blind spot; (C) fully wrong → what evidence did you misread; (D) process error (wrong vehicle, ignored kill, wrong timeframe) → fix the process.

---

## 5 — Loss-hardened gotchas (every one a must-keep)

- **DEDUCED ≠ CONFIRMED.** A supplier link deduced from materials physics FEELS like fact but can be the wrong vendor — the real one shows up named at a trade show; an "unnamed leading customer" you pin to a specific buyer is often simply not that buyer. R3 in practice: the reconstruction/transfer moves infer links no filing states, so they're wrong often enough to size losses. Confirm via filing/press/conference before sizing conviction on a deduced link.
- **Limited-float round-trip.** Within ~6–12mo of IPO/SPAC, price tracks TRADABLE float, not fundamentals — a name can run 7x on ~1% of float actually trading, then collapse to the IPO price on unlock. A thin tradable float lets a little buying move price grotesquely, so a post-unlock drop is MECHANICAL, not a fear-dip — don't buy it as one.
- **Tax-harvest timing.** A November dip in a down-YTD quality name is partly harvest selling that PERSISTS through November — buying it means buying into continued forced selling. Wait for December (it exhausts, then mean-reverts in January); don't read it as a clean fear-dip.
- **Data-error mispricing.** "Prove the math" assumes the reported numbers are real — a ticker-collision / stale / mis-tagged figure (a balance sheet showing −$82M cash when the truth is +$93M net) is ITSELF the mispricing. The fear-fade math is only as good as its inputs; verify the actual filing, because the gap between the artifact and the real number can be the entire trade (and trusting the feed blindly inverts a buy into a "broken balance sheet" pass).
- **Prototype ≠ production.** A demo-stage qualification reads like a production win but routinely DIES at the mass-production cost-down — demo-locked designs get re-optimized out of the BOM. Judge a supplier by where it sits INSIDE the customer's program (prototype vs production-at-scale), and watch OEM/CES for a second source. The failure is inheriting production-win conviction from a prototype.
- **Mis-classified character.** You inherit a name's volatility/stage from its category label — but a "safe compounder" can move 17% in a day. Read cycle stage from the name's OWN revenue/margin evidence, not the archetype you filed it under.

---

## 6 — Building the answer (Type B)

Structure it as a TLDR-sandwich: open with a one-to-two-line `TLDR:` carrying verdict + directional bias; render the funnel as scorecard bullets with causal chains inline as `->` arrows. Required content, in order:

- **Structural position BY ARCHETYPE** — supply-chain node for a bottleneck; drained profit pool for a disruption; emerging-standard claim for an evolution.
- **Forward revenue trajectory.**
- **Valuation with the LENS NAMED** — EV-multiple banding floor-first for a has-revenue physical name; for an asset-financed / pre-scale / disruptor name, compute the floor first and declare it N/A ONLY when it demonstrably fabricates an absurd verdict, then substitute a driver-based anchor DEFENDED with a real checkable number (a levered IRR from prepayment + financing terms, a contracted-customer-funded backlog $, a sanity-banded TAM); for a design-win component supplier the lens is the bottom-up content × end-volume ÷ MC, run *before* calling it priced. Naming the lens is what stops a disruptor self-declaring "the framework breaks" as a free pass out of valuation discipline.
- **Winner-gates verdict** (the archetype's gates).
- **Cycle stage.**
- **Priced-in assessment.**
- A short **`Downsides:`** block (2–4 casual labeled bullets, each tagged priced-in / addressed).
- **Rating with conviction + vehicle** (shares / LEAPS / CSP / CC).

**Close comparatively** — rank the name against its alternatives even on a single-ticker ask (*"strong, but X in the same chain is more compelling / faster"*), so the power-law instinct is audible: a name is only a buy relative to the best alternative in its chain. (The `Downsides:` block, the explicit bear case / falsifier, and the US-listed output gate are always-on invariants from CLAUDE.md surfacing here — honored at this layer, defined there.)
