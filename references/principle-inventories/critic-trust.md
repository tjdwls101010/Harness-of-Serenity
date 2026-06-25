# Critic — Trust-Spend Pass (skill-creator's "hold only what the model can't supply")

Principle enforced: a harness must hold ONLY what a competent analyst-LLM cannot supply itself. Words spent re-teaching generic finance/valuation/analysis sense both waste context AND signal distrust — which makes the model reason *smaller*, deferring to the doc instead of using its own judgment. The drafts are, on the whole, unusually disciplined: nearly every item already compresses to a serenity-SPECIFIC edge and self-flags `model_already_knows`. The flags below are the residue that still leaks generic sense, plus a handful of items that are over-narrated even where the kernel is keep-worthy.

Legend: **CUT** = delete the item; **COMPRESS** = keep the serenity-specific kernel, strip the generic scaffolding. Every flag names the doc, the action, and the reason. I have been deliberately conservative about CUT — anything carrying a loss-hardened gotcha, a specific threshold/number, or a non-obvious behavioral resolver is explicitly PROTECTED below, not flagged.

---

## TIER 1 — items the drafts THEMSELVES flag `model_already_knows=yes` (auditor's first stop)

These six are the only items across all four drafts self-tagged `yes`. Each is re-examined: does a serenity-specific edge survive the generic core? If yes → COMPRESS to that edge. If no → CUT.

### 1. draft-claude_md — "Not a financial advisor — analyst posture"
- **Action: COMPRESS (hard).**
- **Reason:** "You are an analyst not an advisor; always give a bear case + risk disclosure" is pure generic posture the model already embodies — spending a full What/Why/Picture block on it is exactly the distrust-tax skill-creator warns against. The ONLY non-generic atom is the empirical sign-off frequency: **`NFI` 136 / `NFA` 18 — present on essentially every call, its absence is a forgery tell.** Collapse to a one-liner under the voice item; the "mandatory bear case" content already lives (better) in R6/V7 and the non-negotiables. Do not spend a standalone principle block on the advisor/analyst distinction.

### 2. draft-claude_md — "Per-type required content (A–E)" — partial
- **Action: KEEP, but watch.** Self-tagged `no`; not a Tier-1 item. Listed here only to note: the *idea* that a stock answer needs valuation + risk is generic; the load-bearing part is the US-listed gate firing at the output layer (C flags foreign-only, D demands a US expression) and the archetype-rotation. Those are specific — keep. No action.

### 3. draft-macro — "Real catalysts vs fake" (`model_already_knows=yes`)
- **Action: COMPRESS.**
- **Reason:** That index inclusion / a mega-contract / a guidance-raised beat move earnings, while a CFO resignation / conference / shutdown / tariff-tweet are noise — a competent analyst-LLM already sorts these. The draft even concedes "the lists are just the forward-revenue test pre-computed." Keep the test (it lives in the governing-test item already) and keep ONLY the two non-obvious handles: **dividend front-running is a *timing* catalyst not a thesis**, and **analyst initiations/upgrades LAG price (a V8/V10 read, never a reason).** Cut the real/fake enumeration down to those two traps; the rest is the model re-deriving the obvious from R1.

### 4. draft-macro — "Short-squeeze setup" (`model_already_knows=yes`)
- **Action: COMPRESS.**
- **Reason:** "High short interest squeezes on good news, traps on broken names" is generic; the draft admits "SI is symmetric in the generic finance sense." The serenity-specific atoms worth keeping: the **>30–40% of float** threshold, and the framing that on a *fundamentally-strong* name the squeeze is a *bonus catalyst layered on a thesis you'd own anyway* (the fundamentals gate decides which case you have). Strip the generic squeeze mechanics; keep the threshold + the "bonus on a name you'd own anyway, gate decides" frame.

### 5. draft-macro — "Net liquidity = Fed balance sheet − TGA − RRP" (`model_already_knows=yes`)
- **Action: COMPRESS to a fragment.**
- **Reason:** The formula and "read it directionally not as a point estimate" is standard macro literacy — the model knows it. But the formula is *pipeline-computed*, so the only thing that needs saying is the data-contract fact (it comes from code, interpret don't recompute) plus its membership in the four regime pillars. Drop the standalone block; fold "net liquidity is one of the four pillars, pipeline-computed, read directionally" into the four-pillars item. Do not spend a Why-paragraph teaching what TGA/RRP are.

### 6. draft-analysis — "Forward P/E is PEG" (`model_already_knows=yes`)
- **Action: KEEP (do NOT cut), tighten only.**
- **Reason:** Although self-flagged `yes`, this is a borderline mis-flag: the *specific* claim — "judge P/E *relative to growth*; 30–40× at 60%+ is CHEAP on PEG and the biggest winners lived there; 12× at 5% is a trap; AVOID = above sector comp at *decelerating* growth" — carries the serenity inversion (high absolute multiple ≠ reject) plus concrete number anchors. A generic LLM knows PEG exists but does NOT reliably apply "high absolute P/E is where the winners live" under pressure; it reaches for the absolute multiple. PROTECTED as a specific-threshold item. Only trim: don't re-explain what PEG *is*; lead straight with the inversion + the two number anchors.

---

## TIER 2 — items self-flagged `no` but that LEAK generic sense (the real work)

These restate competent-analyst sense with too little serenity-specific edge surviving, OR over-narrate a thin kernel. Ordered by confidence.

### 7. draft-analysis — "Sanity-band the upside against supply-shock base rates"
- **Action: COMPRESS.**
- **Reason:** "Calibrate a target against historical base rates, present a band not a forecast" is generic forecasting hygiene the model already practices. The keep-worthy atom is the *specific reference set* he bands against — **rare-earth / specialty-gas / PGM / memory-supercycle shocks, where concentrated supply + inelastic demand produced multi-hundred-to-thousand-percent moves.** Keep that named base-rate set as the calibration anchor; cut the generic "use a band not a point estimate" lecture around it.

### 8. draft-macro — "Post-liquidation entry — wait for exhaustion, then quality snaps back" AND "Fear-Dislocation is the best buying environment"
- **Action: MERGE + COMPRESS (two items → one).**
- **Reason:** These overlap heavily and both spend a Why-paragraph re-deriving why forced selling overshoots and self-limits — which a competent analyst-LLM already understands. The serenity-specific edge is thin but real: **fear-elevated-fundamentals-intact is named the *single best* environment (not merely "a" buyable one)** — that superlative is the behavioral nudge that keeps you buying when the tape feels worst. Merge the two into one item carrying (a) the superlative framing and (b) the "wait for forced-seller exhaustion *first*" discipline; cut the redundant mechanics-of-margin-calls narration that appears in both.

### 9. draft-macro — "Competitor launch or fumble — apply the test to the category"
- **Action: COMPRESS to one line.**
- **Reason:** "A rival's delay/failure shifts demand-share to the names that shipped" is something the model derives instantly from R1 the moment R1 is stated. The only specific instruction is "run the forward-revenue test on the *category*, one level up, not just the named company." That single sentence is the whole item — the What/Why/Picture triple is three sentences spent on one. Collapse to a one-liner appended to the governing-test or proxy-read-through item.

### 10. draft-macro — "Proxy read-through" vs "The cascade chain, in order" vs "Hyperscaler CapEx is THE leading indicator"
- **Action: COMPRESS (consolidate overlap).**
- **Reason:** Three adjacent items all restate the same spine — demand propagates down a fixed chain, an upstream print is a downstream demand signal, position before the read-through is priced. The *ordered cascade* (Hyperscaler CapEx → neocloud → semis → memory → substrates/optics → raw materials) and the *CapEx-is-the-load-bearing-pillar* superlative are the specific, keep-worthy atoms. "After a major report ask which names it validates" (proxy read-through) is the generic corollary the model re-derives from the spine. Keep the ordered spine + the CapEx superlative as ONE dense item; fold proxy-read-through into it as a single clause rather than a standalone block. (The DB pictures differ but the doctrine is one thing said three times.)

### 11. draft-macro — "Classify every macro event: fundamental vs entry-only" + "The other five transmission channels"
- **Action: COMPRESS the framing, PROTECT the channel specifics.**
- **Reason:** The meta-item ("identify the transmission pathway, decide fundamental-vs-entry, that classification IS the move") is the generic skeleton — a smart analyst already knows a macro event either changes the numbers or only the price. What it CANNOT supply is the *pre-classified verdict per channel*: export-controls→monopoly = structural (size); tariff/TACO, algo-misparse, tax-harvest = entry-only; credit-stress = structural-for-survivors. Keep the six channels with their pre-baked fundamental/entry tags (that's the cached work). Compress the meta-framing paragraph that precedes them to one sentence — don't spend a full block teaching the fundamental-vs-entry axis the model owns.

### 12. draft-discovery — "Tacit technique — SEC competitor-list mining"
- **Action: KEEP, tighten only (do NOT cut).**
- **Reason:** Borderline. "A 10-K lists competitors" is generic, but the *use* — reading a known winner's competitor list as a pre-vetted *discovery* candidate pool, and the caveat that a *named* peer is by definition visible-enough-to-be-named so it's a starting pool not the endpoint — is a non-obvious reframe (everyone reads 10-Ks for the filer, not its rivals). PROTECTED as a non-obvious technique. Trim the Why-paragraph; the reframe is one sentence.

---

## TIER 3 — over-narration flags (kernel is keep-worthy; the WORD COUNT is the violation)

Not cuts — these carry real edge, but spend a competent-analyst's worth of words re-explaining the obvious half before reaching the specific half. Skill-creator's "density" mandate applies: strip the generic lead-in.

- **draft-claude_md — the two big verbatim tables (gives-vs-judges, 10-Values):** KEEP both (they are the cited index the rest of the harness references — load-bearing infrastructure, not generic sense). No cut. But the surrounding Why-prose re-derives "code should do deterministic work, judgment is the analyst's" more than once across the Data-Contract section — say the boundary philosophy ONCE, let the table carry the rest.
- **draft-macro — "Net liquidity" / "Four drains":** Four-drains KEEPS (the convergence ladder 1=noise / 2=tighten / 3+=cut-leverage is a specific, non-obvious resolver — PROTECTED). Net-liquidity compresses per #5 above.
- **draft-analysis — "Revenue quality + earnings quality":** KEEP — the GAAP-vs-non-GAAP/SBC gate ("$500M non-GAAP can be a $150M GAAP loss") and the normalized-peer-table requirement are specific and loss-hardened. The generic "contracted > recurring > speculative" ladder is *almost* model-known but the "at equal multiples the higher-quality dollar is cheaper" framing earns its place. Trim only the generic earnings-momentum sentence.

---

## EXPLICITLY PROTECTED — do NOT let any downstream cutter touch these

Flagged here because a naive trust-spend pass would wrongly classify them as "generic finance" — they are NOT. Each carries a serenity-specific edge, a loss-hardened gotcha, a hard threshold, or a non-obvious behavioral resolver:

- **Every Section-5 loss-hardened gotcha (draft-analysis):** DEDUCED≠CONFIRMED, limited-float round-trip (7× on ~1% float → IPO-price collapse at unlock), tax-harvest-persists-through-November, data-error mispricing (the −$82M ticker-collision), prototype≠production, mis-classified-character (17%-in-a-day "safe compounder"). All loss-hardened, all specific.
- **All the kill-signal STRUCTURE reads:** kill #8 dilution (premium-convert vs at-market-ATM, the circular self-justification loop, net-the-cash-before-crediting), kill #9 designed-out INVERSION (severing the soft intermediary above a hard-layer name is BULLISH), wrapper NAV-premium. These are exactly the non-obvious resolvers the model would get *wrong* by default (it reads "customer cancels supplier" as uniformly bearish, "buyback" as friendly).
- **Funding-structure / R4 cluster:** funded-vs-dilution, tranche-carve-out-doesn't-launder, silent-filing-isn't-funded-confirmation, ATM-near-MC tell. The single most loss-hardened content; the dilution trap is *designed to look like* funding.
- **Hard thresholds/numbers (keep verbatim):** >30–40% SI; top-3>70% & MC<1/10 discovery-escalation trigger; <6mo/>5% funding-floor; op-margin<−100% pre_commercial; <30%/65–100%/100%+ CSP IV-tier ladder; no-CSP-inside-7-days-to-earnings; >90% prediction-market-priced gauge; net-liquidity convergence 1/2/3+ ladder; PEG anchors 30–40×@60% / 12×@5%; 4×–8× EV/Rev, 35× EV/FCF, ~65 unmodeled margin points.
- **Behavioral resolvers the model lacks:** tier-1-buys-on-open-market = structurally (not cyclically) sold out; multi-year-prepayment-tenor = structural-not-cyclical shortage; jurisdiction/FDI-screening predicts non-realization of pricing power BEFORE name-specific evidence; architecture-identity check before a single-spec commoditization claim; equipment-first-then-pure-play rotation; the bottom-up content×volume÷MC sizing move (with DEDUCED tag) — the read "nobody else runs."
- **The voice forgery list (draft-claude_md):** the un-banned "asymmetrical" (~35×), the genuine-zeros ban list ("we are so early" 0, "efficient eventually" 0), the verified hedge-stack counts. These are corpus-empirical, un-guessable, and a forged voice is the fastest credibility kill — PROTECTED in full.
- **The DEDUCED/CONFIRMED discipline, US-listed resolution ladder, and the V2-falsification invariants:** rules, irreversible-error class, not principles to re-derive. Keep verbatim.

---

## CROSS-DRAFT NOTE
The discovery draft is the cleanest — its own closing "Notes on cuts" already pre-empts the generic-supply-chain-intuition tax, and I found nothing in it to CUT (only the competitor-list tighten, #12). Macro is where the leak concentrates (catalyst lists, squeeze, net-liquidity, the three-way cascade overlap) because it touches the most textbook-macro surface area. CLAUDE.md's only real spend is the advisor/analyst block (#1). Analysis is dense and almost entirely specific — its self-flagging is accurate except the borderline PEG mis-flag (#6, keep).
