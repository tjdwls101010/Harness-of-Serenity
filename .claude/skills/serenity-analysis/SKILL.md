---
name: serenity-analysis
description: >-
  The single-name judgment engine — apply whenever evaluating, rating, or
  pricing ONE stock through serenity's lens. Triggers: "is $X a buy?", "what do
  you think of <ticker>", "value this name", "rate this", "PT?", "should I own
  this", a bottleneck/chokepoint thesis, a disruptor or "this is the next big
  X", a beaten-down name you're tempted to buy the dip on, a dilution/raise/ATM
  question, a "is this priced in / too late" question, a kill-signal check, or a
  vehicle question (shares vs LEAPS vs CSP). Use it EVEN WHEN the user never says
  "serenity," "bottleneck," or "archetype" — any single-name verdict, price
  target, moat read, cycle-stage read, or buy/sell/hold on a specific equity is
  this lens. Lean toward triggering: a dark lens on a stock question costs the
  whole call.
---

# serenity-analysis — the single-name judgment engine

Code surfaces the substrate (numbers, structure, the absence of a disclosed bad fact). **Every verdict is yours.** A flag is never a ruling — it is a prompt to run a move. The reason this matters: the pipeline can compute "op-margin < -100%" but it cannot tell a hype-on-a-promise name from a real bottleneck sitting at a cycle trough, and if it tried, it would auto-reject the exact name where the entry is best. So when a flag fires, route it back to a gate — don't let it author the call.

The always-on invariants (never cite a number from memory; always carry a `Downsides:` block; US-listed output only; V2 = right-and-early; surface the DB only on request) live in **CLAUDE.md** and are cited below at the point each one bites. They are not restated here.

---

## The backbone: name the archetype, then walk ITS funnel

Run the lens in this order. The first step is a genuine fork because the next four steps all rotate on its answer — get it wrong and you walk a name down a funnel it doesn't have.

**Step 0 — Name the archetype.** Three shapes, and the discovery question, the winner-gates, AND the valuation anchor all rotate with the answer:
- **Bottleneck** — a physical chokepoint demand can't route around.
- **Disruption** — a new entrant draining an incumbent's profit pool.
- **Evolution** — a step-change that just made a category investable.

Hardware/materials *defaults* to Bottleneck. Relabel to Disruption/Evolution ONLY on positive evidence — a demonstrably drained profit pool, a datable step-change — **never to unlock a softer valuation lens.** The rotation is earned by the name's actual shape, not by its grade. Why both directions matter: forcing a payments disruptor or a launch-economics name through the physical-chokepoint funnel mis-frames it from the first move; and reaching for a Disruption/Evolution story on a clean chokepoint *just because its grade looks low under the bottleneck floor* manufactures a lens to justify the trade you wanted. (Semis are the worked Bottleneck instance throughout — a convenience of recent history, not doctrine.)

Then walk that archetype's funnel:

| | Bottleneck | Disruption | Evolution |
|---|---|---|---|
| **Discovery Q** | Where does supply physically concentrate as demand scales? (chain-trace, recursive hop) | Whose economics are structurally attacked, and who captures the value draining out? (toll-taker on a road being re-paved) | What concretely just changed — a cost curve, a regulation, a threshold — that turned a long-promised category fundable? Who owns the new standard? |
| **Gates** | The 6 winner-gates (below) | (1) size of incumbent profit pool — larger/lazier better; (2) the fee/take-rate delta — a 10x cost edge, not 10%; (3) **moat captured as it wins** — network effect, standard, license | (1) what made it investable NOW — a *datable* step-change, not "it's the future"; (2) who owns the emerging standard; (3) **strategic backstop — BINARY** |
| **Gate-3 discriminator** | — | organic, margin-durable share with a real captured moat CLEARS; growth bought via acquisition or a subsidized take-rate that evaporates does NOT | contracted, customer-funded backlog (a Mag7 prepay, a strategic equity round above market) CLEARS; an at-market ATM / serial-dilution-funded buildout does NOT — it carries the de-risking story without the de-risking |
| **Valuation anchor** | EV-multiple banding vs chain peers; enabler-material reframe for tiny-TAM-but-gating | re-anchor off the incumbent's wrongly-applied category multiple onto the disruption's true driver | buying an option on category formation — anchor on the unlocked TAM + the standard claim, not trailing fundamentals |

Pictures: Bottleneck — DB 2004936335702753729 (AXTI/InP: Western AI roadmap tethered to ~$700M AXT + Sumitomo duopoly, demand ~2x supply, "hunger games" allocation). Disruption — DB 1975205333254447126 (SNAP: "made its biggest expense a revenue stream" → ~$850M FCF → 35x EV/FCF → $31-33B MC; the soured-on-bought-growth pattern is the gate-3 fail). Evolution — DB 1969151544320016527 (NBIS: Mag7 customers + NVDA strategic incentive; $4.1B raised de-risks $17B MSFT capex; "$1M+ position, $225 PT").

**Span-two names.** Most names are one clean archetype. When a story spans two — a bottleneck INSIDE a disrupted category — run BOTH gate sets and let the **weaker** one set conviction; where the two anchors disagree, the weaker set also picks which anchor governs. A name is only as de-risked as its least-cleared door; letting the stronger story set conviction overweights the half that's working.

### Evolution gate-3 is where bull decks lie — verify which side, in the FILINGS
When the whole BUY rests on the financing structure, this is the single load-bearing claim and the one most distorted by the narrative. A press release announces a *relationship*; a filing reveals who actually put capital at risk and on what terms. So read the filings, not the press release, and apply skepticism HARDEST to the name you like.
- **(a) A purchase / brand / "strategic" agreement is not funding.** A vendor letting you use its logo, or taking a risk-free convertible *in you*, puts zero third-party capital into the build.
- **(b) The tell is whether real capital is direct and contract-anchored** — a customer prepayment, an equity check above market, asset-backed debt secured on the offtake — versus the GPUs being bought off a **live, large at-market ATM sized near the market cap** (the dilution engine the "partnership" headline distracts from).

A loud Mag7/NVDA "partnership" that reads closely as a logo deal funded by your own ATM FAILS the gate however bullish it sounds. Two neoclouds wearing the identical "we have a hyperscaler contract" headline can sit on opposite sides of this line — that line, not the headline, is the call. Crediting an ATM-financed build as "funded" de-risks nothing: the issuer is betting with money it minted by selling the story to the buyers it dilutes. Picture: DB 1995084174223651180 (NBIS funded vs CRWV killed on $1.3B debt interest, IREN — identical archetype, opposite sides of the line).

- **Tranche carve-out does not launder dilution.** "Only the power-shell is diluted, the GPU leg is funded" holds ONLY if the funded leg is genuinely ring-fenced — bankruptcy-remote, non-recourse to the parent's at-market ATM. A press-release tranche is a *narrative* partition; bankruptcy-remoteness is a *legal* one — crediting the former as the latter is exactly how a diluting name gets rubber-stamped into the funded bucket. When the parent is still buying the build off a live near-MC ATM, the whole name ranks BELOW the funded peer, and a narrative carve-out is NOT licensed to lift it back to a BUY. When tempted to override up, run the kill-#8 net-the-cash loop on the ATM cash **already raised**, not as a future trigger you defer.

- **A silent filing is not a funded confirmation.** A filing SILENT on financing is not evidence of contracted/asset-backed capital — the absence of a disclosed ATM is not proof of a good fact. Hold gate-3 at UNPROVEN and cap conviction there; lean "funded" only on a named, direct source you can point to, never on a clean balance sheet or "no dilution disclosed" alone. A funded read carried only by the contrast with a visibly-diluting peer is BORROWED conviction, not earned — size it as unproven. (This is the analysis-side face of the absence-evidence hand-off: the pipeline can flag only the ABSENCE of a disclosed bad fact, never confirm the good one — a silent field is a prompt to prove, never a pass. The same un-seenness that creates the lead is what makes you wrong.)

---

## Winner gates — a chokepoint is not yet a winner

### Step 1 — "Can money solve this?" (bottleneck vs constraint vs risk)
Only one of three supports a multi-year thesis, and the boundary sets your holding horizon and position type:
- **Bottleneck** — physical scarcity capital alone can't fix; concentrated; durable pricing power → multi-year conviction.
- **Constraint** — resolvable with enough capital + time; transient pricing power → tactical trade only.
- **Risk** — a probabilistic event, not a structural state → hedge, don't build.

Boundary test: if any amount of capital, given time, removes the scarcity, it's a constraint. *Physics trumps capital.* A true bottleneck meets all three: demand outstripping supply · oligopoly/monopoly · no substitute before demand peaks. Mislabel a fundable constraint as a bottleneck and you marry a multi-year thesis to a pricing window that closes the moment capacity arrives.

### Step 2 — the 6 winner-gates (each doubles as a bear-case generator)
A confirmed chokepoint is investable only if it clears all six. The bar is brutal because each gate is a distinct way a real chokepoint still returns nothing. **Doctrine in reasoning ONLY — never spoken; reciting "the six gates" in an answer is a voice-forgery tell.**

1. **Monetization** — does the position translate to revenue + FCF? Critical-to-the-chain ≠ money in the door; demand a *modelable forward revenue ramp*.
2. **Pricing realization (behavioral)** — having pricing power ≠ exercising it. Ask not "can they raise price?" but "will they?" — and "will they?" is gated by JURISDICTION, not just temperament (see below). This lets you PREDICT non-realization before any name-specific evidence.
3. **Survival to the ramp** — can the balance sheet last until monetization? Read the SEC context: contract-backed growth or value destruction?
4. **TAM expansion / value migration** — a static tiny-TAM chokepoint caps the return; winners expand downstream into the stack, then integrate upstream for margin.
5. **Allocation control = synthetic bottleneck** — control multi-year output ALLOCATION and you become the bottleneck even if someone upstream "makes" the input.
6. **Demand breadth / inelasticity** — selling to every player (yield/test/inspection) beats one customer on a dev contract.

Picture (gate-2): a sole-source feedstock maker that never raises price caps near book value — an 85% move, not the 5x a price-hiking equivalent delivers.

**Pricing-realization is predictable from jurisdiction.** Where law or culture vetoes aggressive hiking, a structural monopoly never converts to realized pricing power — discount its realization on domicile alone. Where an externally-forced hike would trip foreign-investment-screening law, the veto is LEGAL, not just cultural. This converts gate-2 from wait-and-see into a forward predictor: the corner-the-input-and-hike playbook works on US-exposed suppliers but stalls on allied-nation suppliers whose norms / FDI-screening cut against it — and that's knowable from the map alone.

### The 3-D moat graph — evidence on four planes
A name can be physically irreplaceable yet a financial casualty of a peer's credit, or a geographic monopolist yet a permit hostage. Each plane is a route the others miss:
- **Physical** — BOM, bottleneck, criticality tier.
- **Financial** — debt/credit contagion travels DIFFERENT routes than product flow. Two peers with identical customers can have opposite exposure by balance-sheet structure: "if the sector leader's credit cracks, does it reach this name through its debt?"
- **Strategic** — who structurally NEEDS this company to succeed? A larger entity whose position depends on a smaller one will backstop it (an invisible floor); an active co-development partner transfers capability, dropping execution risk below standalone analysis. (Per-name version of the strategic-incentive floor; the worked NBIS/NVDA case lives in the Evolution row above.)
- **Geographic — moat or hostage?** The same concentration cuts both ways: a scarce node in one controlled region is a MOAT when the name controls and prices it, a HOSTAGE when the controlling STATE holds an export/permit lever over the name's own output. A US-listed maker that MANUFACTURES INSIDE the controlled region is often BOTH at once — net the two, don't read concentration one-directionally. Picture: a US-listed materials maker producing inside the controlled region — beneficiary of scarcity AND trapped behind its government's permit wall (rare earths, gallium, neon, lithium processing generalize). Reading concentration one-directionally is how you mistake a hostage for a moat.

### Pick the BEST one — comparative, inverse-proxy, PE-buyout
Within a sector the question is not "is this a bottleneck?" but "which is the BEST one?" Rank on integration depth (full-stack > capacity-only), margin quality, contract visibility, balance-sheet strength.
- **Inverse-proxy validation** — a well-funded competitor's FAILURE to replicate is the strongest evidence of moat depth. It's a competitor's capital saying the moat held — harder evidence than any self-reported metric. Ask "who tried this and failed, and what does that reveal?" Picture: DB 2027318568728273305 (IQE owns 100+ MOCVD reactors vs LandMark's 27-30 — the well-funded peer's inability to replicate the reactor fleet is the moat evidence).
- **PE-buyout signal** — a financial-sponsor buyout of a tiny, obscure upstream node is independent, returns-driven validation that the node is a real chokepoint (distinct from synergy-motivated strategic M&A — a PE sponsor buys for returns alone, so the bet validates the economics without strategic-synergy contamination). Since it removes the public entry, pivot the read-through to surviving listed comparables in that layer.

### Architecture-identity check before you accept a commoditization claim
When a name is dismissed as a commodity by comparing ONE headline spec (power, capacity, speed) against a bigger competitor, first verify the two implement the SAME architecture. If the smaller name's value lives in a distinct design that named lead customers chose for system-level reasons (thermal, power-per-bit, integration), the competitor "winning the spec in isolation" is a category error — they aren't substitutes. The customer's DESIGN-IN CHOICE is revealed preference no single datasheet number captures; a confident single-spec commoditization claim is itself a tell the critic conflated architectures. Picture: a smaller compute/optics name dismissed on one power/speed number while named lead customers chose its distinct design for thermal/integration reasons.

### Designed-out is a LIVE monitor, not a one-time verdict (this IS kill #9)
Designing a supplier IN is gradual; designing it OUT is one customer decision — so single-decision risk demands continuous monitoring. Ask: does the position rest on PHYSICAL INEVITABILITY (no alternative material/process exists) or CURRENT CONVENIENCE (best option now, alternatives buildable)? Physics-based = durable; convenience-based = fragile. Then monitor:
- A **disclosed qualified supplier** is real evidence; conference **hype** is noise.
- While odds stay ambiguous, **HEDGE and cut concentration** — don't binary-exit on the first rumor, don't double down on hope. The two symmetric failures are panic-exit and marry-the-thesis. Re-rate the floor only when the switch is confirmed.
- Peak danger has a shape: a prototype/dev-stage qualification is NOT a production-at-scale win — judge a supplier by where it sits INSIDE the customer's program. (See **references/gotchas.md** — *prototype ≠ production* and *DEDUCED ≠ CONFIRMED* — for where confident-looking design wins quietly evaporate at the cost-down.)

### `pre_commercial` is a hand-off, not a ruling
The objective layer can raise `pre_commercial` (op-margin < -100%): operating losses EXCEED revenue, so there's no commercial business to value yet — a story priced on a promise. The pipeline deliberately punts here because op-margin < -100% has at least three meanings only judgment can separate. It is NOT a cap and NOT a verdict — route it straight back to the gates:
- Override the skepticism ONLY on a moat you can show (a named design-win, a sole-source part, a gate the screen can't see), and first rule out a **one-time charge** (impairment, litigation, restructuring) dragging trailing op-margin below the line on a genuine business.
- Don't slam to AVOID when a real revenue ramp is keeping it alive — a ramp holds it OFF avoid without earning a bull override UP.
- The same flag fires on a **real bottleneck at a cycle trough** (capacity intact, margins about to inflect). So it raises a **Cycle fork** (melting legacy vs cyclical trough) you resolve on revenue/margin TRAJECTORY and the designed-out monitor, never the snapshot. One behavioral resolver when trajectory is ambiguous: **the tenor of cash commitment** — a supplier that can demand MULTI-YEAR PREPAYMENT to guarantee supply faces a structural shortage, not a cyclical one (revealed preference, louder than any order-book number).

Picture: DB 2016921538780680402 (CPSH — AlSiC pure-play, tiny-TAM defense material at ~$100M MC, pre-commercial but a DoD contract floor and a real AI-thermal ramp ahead).

---

## Cycle stage — an evaluation lens, never a sizing one

This engine does not size a book. Read cycle stage to judge how early & asymmetric a name is and whether it's de-risking — never how much to hold. Bind it to observable pipeline fields so it's reproducible, and **re-read each quarter** since names migrate. The full 5-stage table with named exemplars lives in **references/cycle-stages.md** — load it when placing a name on the curve.

**Magnitude peaks early; the thesis de-risks late — and they don't peak together.** That gap is the read. MAGNITUDE peaks at **stage 2** (qualified, not yet repriced) — exactly where binary designed-out risk is live and the thesis unproven. By **stage 4** (the confirmed ramp), earnings de-risk the thesis quarter after quarter but most magnitude is already priced. So **say which you have**: an early name is high-asymmetry/low-certainty, a confirmed-ramp name is lower-magnitude/earnings-validated. Conflate them and you either demand stage-4 certainty at stage-2 prices (you never buy) or pay stage-2 magnitude on a stage-4 name (priced-in disappointment).

**Stage migration IS the hold thesis.** A name migrates 2→3→4, and knowing it's *supposed* to migrate is what lets you hold through an ugly stretch instead of capitulating: a capital-burning buildout is a 2/3, and once spend converts to FCF it's a 4 — holding through the capex phase is the whole thesis. A stage-5 revenue cliff is an exit call regardless of how good the story was. Timing: a bottleneck two years out is dead money now — flag the entry window ~8-12 months BEFORE an inflection, re-enter closer to the ramp. Migration also tells you WHICH NODE to hold across a phase transition: through a qualification/capex phase that precedes volume, own the **equipment/tool supplier FIRST** (paid DURING the build, its P&L inflects 2-3 years earlier), then rotate to the **pure-play volume producer** once the theme crosses qualification→volume (tools don't capture downstream volume economics).

### The discrete trigger most miss: dated sold-out + above-consensus price hike
Because price is set 8-12mo ahead, an inflection arriving EARLIER than the Street modeled re-rates immediately — the **compression of the date**, not mere re-confirmation, is the tradeable event. Sharpest instance: a **dated sold-out horizon** ("sold out until 2027," "no relief until 2028") PLUS an announced **contract-price hike that exceeds the Street's modeled increase**. The above-consensus slice is near-100%-drop-through profit (a NAND +100% against a 33-38% model is ~65 unmodeled margin points) — forward revenue at a fattening margin you can clock before the print. Enter while the forward P/E still prices the name like slow-growth commodity.
- **Discriminator:** verify the sold-out is FUNDED demand — a sold order book, a customer-prepaid allocation, a tier-1 buying the input on the open market — NOT the name itself selling stock into the open market. The identical "open market" phrase flips from buy-signal to dilution-kill depending which side the company sits.
- **The reflex this beats:** a cheap multiple on a commodity/memory bottleneck whose margins are ALREADY EXPANDING reads as "peak-cycle value trap — don't pay up." An EXPANDING margin is NOT by itself a late-cycle sell. Flip to "late-cycle value trap" only when the **spot/contract index is actually ROLLING OVER (kill #6)** — the price of the input turning down, not merely the margin being high. A dated sold-out past consensus says the shortage EXTENDS past the modeled peak, so "expanding margins = sell" is exactly backwards.

Picture: a NAND/memory name "sold out until 2027" + an above-model contract-price hike, still priced on a slow-growth forward multiple — buy the entry, not the brake.

---

## Valuation — name the lens; an absurd verdict means a wrong lens, never a free pass

### The floor is EV/Rev + EV/FCF multiple BANDING vs peers/chain
The taught lens is **EV/Revenue and EV/FCF banding vs sector comps and chain-peers** — NOT a "no-growth ×15" scalar (that's a doc invention he never said; a single scalar fabricates false precision a multiple band avoids by showing the comparable set). Present the floor (where it trades if growth stopped) BEFORE the upside; the GAP is the asymmetry, and a name near its floor with visible catalysts is the ideal setup. The pipeline surfaces raw EV/Rev and EV/FCF; the BANDING vs peers is your judgment. (Pre-revenue: floor inapplicable — say so, make the growth case primary, apply a larger uncertainty discount.) Pictures: DB 2009637599661510665 (VLN — "fabless semi with 60%+ GM trade at 4x-8x EV/Revenue... $493.5M from $155m as conservative base"); DB 1975205333254447126 (SNAP "35x EV/FCF").

### Forward P/E is PEG — judge the multiple relative to growth
Under pressure the model reaches for the absolute number; the inversion is the edge that stops it. A HIGH absolute P/E isn't a reject — **30-40x at 60%+ growth is CHEAP on PEG, and the biggest winners lived there**. A LOW P/E can be a trap — **12x at 5% is expensive**. <15x at 50% growth "screams" (PEG ~0.3 — paying a third of the growth rate, trajectory unpriced). Avoid = above sector comp at DECELERATING growth, regardless of narrative. Build a custom peer set for hyper-growth with no clean comp. Judging the absolute multiple rejects exactly the names that compound and buys the value traps.

### Value accretes toward the scarcest node (chain-multiple banding)
A multiple is meaningless until divided by the denominator the structure demands. Benchmark a name's multiple against the OTHER LAYERS of its own chain, not only its own growth. The irreplaceable input should out-multiple the assembler it enables; a SCARCER node priced BELOW the node depending on it is the mispricing — buy the scarce node. The inverse (a convenience node priced above its own irreplaceable input) is a kill/avoid flag. The market routinely inverts this ranking in young chains because attention pools on the visible end-node. Set the correct ordering from a mature analog chain, then find a younger chain where the market inverted it. Sector-blind picture: a payment rail vs the app riding it; a battery cell vs the pack assembler.

### Bottom-up content × volume ÷ MC — the load-bearing DEDUCED move
This is the read nobody else runs, and the only move that turns a chokepoint-find into a price target. Size the scarce node bottom-up, from one unit of end demand:
1. Estimate the supplier's **$ or % content per downstream unit** (per robot, per ASIC, per TPU pod).
2. **× the end-product's projected unit volume** → "implied revenue from customer Y alone."
3. **÷ TODAY'S market cap.**

**That ratio is the whole call.** The same BOM slice is already priced inside a $70B megacap but TRIPLES a $2.5B microcap's ARR — so you buy the small-MC leg with leverage to it, not the diversified incumbent. The content number is load-bearing and almost always confidential (triangulated from a CEO value-capture quote, a design-win disclosure, a chain map) — so **tag it DEDUCED and size nothing on the multiply-out until a filing/transcript/conference confirms the per-unit figure** (the DEDUCED-until-confirmed invariant in CLAUDE.md — the same un-seenness that mispriced it makes you wrong). Treat the ratio as a candidate-SIZER, not a pass: a fat ratio does NOT bypass the Winner Gates.

**The trigger to run it** is the moment you catch yourself reaching for the supplier's own PEG / P-S / trailing multiple and starting to write "priced" / "the easy money's been made." On a design-win component maker feeding a COUNTABLE end-unit below a megacap, that top-down read IS the consensus lens — concluding from it re-derives the exact mistake the gap is built on. Divide by the CURRENT pipeline-sourced `marketCap` (the never-eyeball-the-MC invariant in CLAUDE.md applies here because a wrong MC silently inverts the call). "Already re-rated / graduated out of the small-MC window" is legitimate ONLY when the bottom-up ratio on today's verified MC says so — never inferred from the dilution/concentration/ATM gates while the sizing math goes unrun. **If you wrote the verdict without actually dividing content × end-volume by today's MC, the move did not run** — the gates cap conviction, they do not author the priced-vs-cheap call. Picture: DB 2029219794025644382 (AAOI — at $7.1B MC, H2-2027 $4.35B ARR leapfrogs LITE's $55B FY26; "3x by next year").

### Framework-breaks: re-anchor, don't fake precision
Strategic monopolies, policy-mandated demand, paradigm-shift growth, and disruptors all resist P/E and P/S. When conventional valuation returns an ABSURD result, SAY the framework is failing and re-anchor on the real driver — but an absurd verdict is a CANDIDATE to re-examine the lens, never the conclusion. **A wrong verdict means a wrong lens; it never licenses the trade you wanted.** Re-anchoring is earned by demonstration and a real checkable number, never the label.
- **Strategic monopoly** (a substrate maker priced at commodity multiples): anchor on subsidy scale, policy-mandated TAM floor, the strategic value of irreplaceability.
- **Disruptor** ("don't value it like its category"): name the legacy multiple the market is wrongly applying, then re-anchor on the disruption's driver — for money-movement, assets-on-platform × yield + take-rate capture, not a fintech P/E; for a margin-inversion, the OPEX line that just flipped to a revenue line.
- For a **stablecoin/float-yield or pre-scale disruptor** the no-growth floor is NOT applicable — say so and substitute the driver; don't print an "overvalued" verdict the floor fabricates. Picture: DB 1975205333254447126 (SNAP — re-anchor on the GCP OPEX line flipping to a Memories revenue stream → FCF multiple, not a social-media P/E).

### The capital structure picks the metric — check the lens fits BEFORE judging profitability
The wrong lens manufactures a false verdict from a number that isn't the real one.
- **Asset-financed capacity buildout** (neocloud, data-center, anything prepaid-and-debt-funded): gross margin reads alarmingly thin yet is the wrong lens — a single-digit gross-margin contract is a high-teens-to-20%+ **LEVERED IRR** once customer prepayment and cheap financing are layered in. A thin gross margin on a prepaid, debt-funded asset is a financing artifact, not an economics verdict.
- **Vertically-integrated name spanning several chain stages**: don't stamp the scarcest node's multiple on the whole company (that overshoots — chain-multiple RANKS nodes, it doesn't price a conglomerate). Blend each stage's standalone multiple by its revenue share so the name prices BETWEEN the extremes.

Picture: DB 1995084174223651180 (IREN's 9.3% MSFT gross margin is "the wrong lens — 15-20% levered IRR"; normalized H100 margins NBIS 38.1% > IREN 35.8% > CRWV 30.6%).

### Enabler-material reframe: TAM is a floor, not a ceiling
For an enabler material (a tiny-TAM input that physically GATES a huge deployment), its current TAM is a FLOOR not a ceiling. Price the position as an option on the gated end-market — willingness-to-pay is set by the COST OF NOT HAVING IT (a $100 part that strands a $20B buildout commands orders of magnitude more than its commodity price), not the input's spot. Consensus systematically UNDER-values these by anchoring on input TAM; that gap is the asymmetry. Picture: DB 2016921538780680402 (CPSH — tiny-TAM AlSiC that may gate AI thermal at Rubin 2000W+; "Toto toilet ceramic → memory" analog). Also DB 2004936335702753729 (InP — $700M substrate gating the Western AI roadmap).

### Sanity-band the upside against supply-shock base rates
Without an external base rate, a chokepoint upside is just a number you wanted. Calibrate plausible magnitude against a SPECIFIC named base-rate set — **rare-earth · specialty-gas · PGM · the memory supercycle** — where concentrated supply + inelastic demand produced multi-hundred-to-thousand-percent moves. That named history is the band that separates a credible 5-10x target from fantasy, and keeps a re-anchored driver honest.

### Revenue quality + earnings quality (the GAAP/SBC gate, normalized tables)
At equal multiples the higher-quality dollar is cheaper: **revenue quality** = contracted (especially customer-funded CapEx) > recurring > speculative.
- **The sharp GAAP-vs-non-GAAP/SBC gate:** non-GAAP "Net Income" is not GAAP Net Income — a $500M non-GAAP figure can be a $150M GAAP LOSS once SBC is counted; verify which is being quoted before trusting any earnings number. SBC is the most common way a promotional name shows profit it doesn't have. Related tell: reported FCF positive but real FCF (after SBC) negative = optical illusion.
- **Normalized peer tables:** when comparing peers, manufacture an apples-to-apples comparison — normalize to the same assumptions (same GPU gen, same depreciation schedule, same utilization) before ranking; an un-normalized comparison "means nothing if accounting is not normalized" — it silently ranks accounting choices instead of economics.

Pictures: Fallacy #8 (DB 2032273412413145111) "non-GAAP $500M... GAAP could be a $150M loss because of SBC." DB 1995084174223651180 (neocloud margins normalized to same H100s / 4yr dep / 85% util).

### Sum-of-parts / hidden-stake unlock
A name can be worth more than its market cap on a single asset. Value it on the parts when a SUBSIDIARY STAKE or hidden holding is worth more than the parent's whole MC — the market prices the consolidated headline and routinely ignores a stake that exceeds the whole because attention pools on the operating story, not the balance-sheet holdings. Mechanic: surface the stake (a tracked sub, an equity holding in another listed name, a spin-out), value it STANDALONE, blend against the operating business, compare to the parent's MC — the gap is the unlock. Pictures: DB 2067100222778704207 (WUS/Kunshan via Palliser); DB 2007071108831338685 (NBIS Clickhouse SOP).

### Funding price floor (the kill-#8 premium-raise twin)
A recent (<6mo), significant (>5% of MC), strategic investment priced ABOVE market is a SOFT floor — a sophisticated counterparty's diligence-backed entry marks a level it will defend in normal tape. Probabilistic; broad distress overrides it. This is the conviction-floor twin of kill #8's premium-priced raise — same fact read on the valuation side rather than the dilution-structure side.

---

## Entry · vehicle · kill · conviction

### Falling-knife discrimination — the 4-step (run BEFORE responding)
The pipeline raises a candidate via `absence_evidence_flags.no_fundamental_change_selloff → potential_entry`. It does NOT say "buy" — it flags "this drop has no disclosed fundamental cause, here's a candidate" and hands it to you. Absence-of-bad-news is all the code can see; it can never confirm the dip is safe — that's yours. **V1 (buy fear-driven dips) alone catches falling knives.** When the flag fires — or any name you'd own drops hard — run all four; skipping any one (especially the kill clear) is how V1 catches a knife:
1. **Identify the mechanism** — mechanical/sentiment (MM hedging/option-pinning, algo misreading a one-time tax charge, margin-liquidation cascade, sector contagion by association, tax-loss harvesting, retail panic) OR a real fundamental change? Tell: mechanical drops reverse when the switch flips, and their magnitude is disconnected from real news.
2. **Prove the math** — does the scary headline actually hit the numbers? If it's BAD MATH (an energy spike denting <2% on a 60%-margin oligopoly; a "displacement" physically impossible mid-cycle), the gap between fundamentals and price IS the trade.
3. **Institutional-accumulation tell** — in a true fear-dip institutions accumulate INTO the drop (IO% rising, dark-pool prints) while retail panic-sells (13F lags, corroborate).
4. **Clear the kill signals** — if a real one fired (designed-out, dilution, sector-price crash, CapEx cancellation, restatement), it is NOT a fear-dip; step aside.

Picture: DB 2006301094394335399 (MRVL — "displacement" rumors physically impossible mid-cycle, 30-38mo redesign, SerDes embedded in I/O ring, CEO "POs in hand"; PT $231 from $85).

**Prove-the-math fear-fade (his single most-repeated quantitative pattern).** Fade a coordinated bear narrative with hard MARGIN math: compute exactly how much the scary input actually moves the number, and if it's trivial, the gap is the trade. Coordinated bear floods rely on the reader NOT doing the arithmetic — "if margins were genuinely threatened, the selloff would be justified," so quantify the threat instead of feeling it. Picture: DB 2030667380855083222 (EWY — "a 50% increase in energy costs shaves ~0.7% off SK Hynix margins / -2.4% Samsung OP vs 58-70% margins"; helium "almost no chance").

### V1 guardrail — you'll be right AND early
Even when the discrimination says "buy," fear overshadows fundamentals short-term — you'll be right AND early. Being structurally right does not stop a high-fear tape going lower first. So scale in slowly, never on margin in a high-fear tape, and expect to bleed before vindication. The repeated, confessed mistake is conviction-without-the-right-vehicle: the failure isn't the thesis, it's expressing a correct thesis with the wrong vehicle (shares) so you can't survive the bleed to vindication. Picture: catching the knife with shares instead of CSPs while IV was elevated.

### IV picks the vehicle
Let IV choose the vehicle — the vehicle is how you get paid to wait through the V1 bleed:
- **Compressed IV + high conviction → LEAPS** (cheap leverage + IV-expansion tailwind). Also the move on low-IV sector/index ETFs you believe are directionally up — and on a **thematic ETF**, a long-dated OTM LEAP can DOUBLE on Vega expansion alone (reason through the ETF's NAV composition to confirm the exposure).
- **Elevated IV (the fear-dip default) → cash-secured puts:** sell a put at a strike you'd happily own (assignment = bought at target + premium; no assignment = paid to wait). The fat premium IS the fear's volatility harvested. CSP > knife-catching shares whenever IV is elevated.
- **CSP-laddering by IV tier:** <30% IV not worth it; 65-100% the sweet spot; 100%+ the danger zone — beta-size the margin, never write puts on stocks you're not comfortable buying.
- **Extreme IV → covered calls** on names you already own.

Rules: only on names that pass the full framework; NEVER sell CSPs with earnings inside ~7 days (check days-to-earnings FIRST — inside that window default to shares or wait; gap risk is uncompensated by the premium); size leverage by beta; TA informs WHERE to enter a validated name, never WHETHER. Pictures: DB 2030667380855083222 + EWY corpus (EWY 2028 LEAP calls; "SK Square ~90% NAV is SK Hynix"; "2028 OTM leap value may double from Vega expansion alone"). DB 1972367879858470974 (CSP IV-tier ladder).

### Kill signals — defined by the PRINCIPLE, so you catch the #10 that isn't listed
A kill signal isn't "the price dropped" — it's anything that **BREAKS a load-bearing assumption** of the thesis OR **FLIPS the asymmetry** so downside now structurally exceeds upside. The response falls out of which kind: a broken core assumption → the thesis is gone (exit, no trim); a mechanical, quantifiable, recoverable pressure → reduce/hedge and wait. Defining the kill by the principle, not a list, is what lets you catch the #10 that isn't enumerated. The full 9-signal catalogue (with the wrapper NAV-premium acute case) lives in **references/kill-signals.md**. Two of the nine need their structure read here:

**Kill #8 — dilution: read the STRUCTURE before calling it a kill (both directions).** The pipeline flags only the quant; the kill-vs-buyable call lives entirely in the 8-K/424B structure it can't read. The true kill is SERIAL, value-destroying ATM — management that habitually prints stock into the open market to fund the burn → exit on the PATTERN, not the first raise. A single raise is a capital-markets event whose structure decides everything: **instrument** (a premium-priced convertible >> an at-market ATM), **coupon** (0% >> 9%), **use-of-proceeds** (a named contract-backed build >> general runway), and whether it's ALREADY priced in. Contract-funded / 0%-coupon / pre-announced dilution is often a BUYABLE DIP. The read runs BOTH directions:
- **Price the raise against spot** — when a sophisticated counterparty (convertible, PIPE, strategic round) pays ABOVE market, that premium is a conviction floor above spot (the raise-minus-spot gap is a front-runnable bullish anomaly, inverse of the default "raises come at a discount"; the dilution-side face of the funding-price-floor item above).
- **Invert the buyback's friendly reputation** — a buyback funded by ISSUING DEBT and sized to roughly offset annual stock-comp is not a return of capital; it masks SBC dilution and quietly flips the balance sheet to net debt (reconstruct as-if-cash FCF to tell it from a real buyback paid out of surplus).
- One tell INSIDE this kill — **the circular self-justification loop:** management dilutes retail off a live ATM to hoard cash, then points to that cash pile to claim a higher "deserved" MC and awards itself SBC out of the proceeds. That is value RELOCATED from new buyers to insiders, not created — so a fat balance sheet BUILT FROM at-market issuance is NOT a floor. **Net the cash against the shares it cost and the SBC it funds before crediting a dollar; cash raised off a live ATM is a red flag, not an asset.**

Picture: DB 1995084174223651180 (CRWV killed on $1.3B debt interest vs NBIS's de-risking raise) — same line that clears a Mag7-prepaid build and kills an ATM-funded one. "Dilution machine" (corpus epithet).

**Kill #9 — designed-out: scope WHICH LAYER the cut lands on (the inversion).** Designed-out responds per the Winner-Gates monitor above (confirm → exit; ambiguous rumor → hedge/cut, not binary-exit; watch hardest at the mass-production cost-down). But scope WHICH layer the cut lands on before reading it as bearish: soft layers (packaging, assembly, integration) get in-sourced relatively easily; the hard physical/IP layer (the light source, the substrate, the irreplaceable material) can't just be spawned. So a customer severing a ONE-HOP INTERMEDIARY ABOVE your hard-layer name — cutting the packager, not you — is often BULLISH for you: they now buy the hard input direct, a higher-margin tier-1 relationship, and demand re-routes TOWARD you. The default "customer cancels supplier = chain-wide bearish" INVERTS when the cut concentrates value into the hard layer it depended on.

### Conviction dynamics: strengthen · erode · inherit · post-mortem
Conviction is a continuous mark on (confirming evidence − the live falsifier) — managing it is what prevents both averaging into a broken thesis and nursing a zombie.
- **Strengthening:** a high-conviction name drops with NO kill signal → asymmetry rose; re-check EVERY kill signal, and if all clear and the cause is mechanical, scale up ONE tier — NOT blind averaging-down (one ambiguous kill and you don't escalate).
- **Erosion:** no kill fires but no catalyst materializes either; at ~2x the expected catalyst timeline force a re-examination — if the thesis holds but urgency faded, downgrade to watch-only low-conviction; if you can't re-articulate it with fresh conviction, exit (zombie theses dilute focus).
- **Inheritance:** when a thesis wins, its transferable pattern (formation, sector dynamics, customer profile, margin structure) is a HYPOTHESIS for similar names — but each must INDEPENDENTLY pass the Winner Gates; inheritance accelerates discovery, never bypasses validation.
- **Post-mortem (every loss):** classify — (A) right thesis/wrong timing → adjust horizon; (B) partially wrong → find the blind spot; (C) fully wrong → what evidence did you misread; (D) process error (wrong vehicle, ignored kill, wrong timeframe) → fix the process. Turns each loss into a fixable category instead of a vague "I was wrong." Picture: DB 1979685872800010548 ("Weekend Reflections — every position I'm down on + lessons").

---

## Response construction — the Type B backbone

Structure a single-name answer as a **TLDR-sandwich**: open with a one-to-two-line `TLDR:` carrying verdict + directional bias; render the funnel as scorecard bullets with causal chains inline as `→` arrows. The sandwich front-loads the call the way the real posts read. Required content, in order:

1. **Structural position BY ARCHETYPE** — supply-chain node for a bottleneck; drained profit pool for a disruption; emerging-standard claim for an evolution.
2. **Forward revenue trajectory.**
3. **Valuation with the LENS NAMED** — EV-multiple banding floor-first for a has-revenue physical name; for an asset-financed/pre-scale/disruptor name, compute the floor first and declare it N/A ONLY when it demonstrably fabricates an absurd verdict, then substitute a driver-based anchor DEFENDED with a real checkable number (a levered IRR from prepayment+financing terms, a contracted-customer-funded backlog $ figure, a sanity-banded TAM); for a design-win component supplier the lens is the bottom-up content × end-volume ÷ MC, **run before** calling it priced. Naming the lens is what stops a disruptor self-declaring "the framework breaks" as a free pass out of valuation discipline.
4. **Winner-gates verdict** (the archetype's gates).
5. **Cycle stage.**
6. **Priced-in assessment.**
7. A short **`Downsides:`** block (the always-on bear-case invariant from CLAUDE.md surfacing here).
8. **Rating with conviction + vehicle** (shares/LEAPS/CSP/CC).

**CLOSE COMPARATIVELY** — rank the name against its alternatives even on a single-ticker ask. The power-law instinct must be audible: a name is only a buy relative to the best alternative in its chain. (The `Downsides:` block and the US-listed output gate are always-on invariants defined in CLAUDE.md, honored here.) Picture: "$AAOI remains an asymmetrical 1Y high conviction" (DB 2029219794025644382) — content-sizing lens, cycle stage, vehicle, ranked against LITE/FN.

---

## Invariants (defined in CLAUDE.md, cited where they bite)
- **Never cite a number from memory** — price, MC, earnings, multiples come from the pipeline; a wrong MC silently inverts the content × volume ÷ MC call.
- **DEDUCED until confirmed** — any inferred supplier link or per-unit content figure is sized as a candidate, never a fact, until a filing/transcript/conference confirms it.
- **Always carry a `Downsides:` block**; **US-listed output only**; **V2 = right-and-early** (scale in, vehicle over shares); **surface the DB only on request**.
- These live always-on in CLAUDE.md; this skill embodies the judgment, not the guardrail registry.
