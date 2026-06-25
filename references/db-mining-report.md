# DB Mining Report — Serenity Methodology Fidelity & Corrections

Source corpus: `data/analysis_Serenity.db` (table `tweets`): 1,435 posts + 169 subscriber theses + 2 replies (1,606 total), 2025-07 → 2026-06. This report cross-validated the legacy monolith doctrine against the real corpus.

**Headline:** the legacy doctrine is high-fidelity — every major doctrine CONFIRMED, often near-verbatim (the archetype trichotomy and cycle-stage table are reverse-engineered straight from his posts). Three corrections below are load-bearing.

---

## A. THREE CORRECTIONS (must be applied to the harness)

### A1. Voice bug — "asymmetric upside" ban is WRONG
The legacy doc bans reciting "asymmetric upside" as a forgery tell. **False.** He says **"asymmetrical upside"** 10×, and "asymmetrical [long/bet/moonshot]" ~35× — it is one of his most authentic markers (he spells it the `-al` variant).
- "Present asymmetrical upside in 2026" (2006709693012467774); "$NBIS maintains highest asymmetrical upside" (1995084174223651180); "Reddit is an asymmetric long" (2031055797086728366); "$AAOI remains an asymmetrical 1Y high conviction" (2029219794025644382); "binary asymmetrical moonshot pick" (2026934223416734052).
- **Fix:** strike "asymmetric upside" from the forbidden list; ADD "asymmetrical [long/upside/bet]" to the *recurring* voice markers.
- **Genuinely-absent (ban holds):** "we are so early"/"so early" (0), "markets aren't efficient"/"efficient eventually" (0), "not every bottleneck" (0 as spoken). Keep these banned.

### A2. Valuation floor — "no-growth ×15" is a doc invention, not his lens
He NEVER says "no-growth floor" (0) or "×15". His real valuation lens is **EV/Revenue and EV/FCF peer/chain multiple banding** vs sector comps and chain-peers.
- "Fabless semi with 60%+ GM trade at 4x–8x EV/Revenue... $493.5M from $155m as conservative base" (2009637599661510665, VLN); "35× EV/FCF" (1975205333254447126, SNAP).
- **Fix:** re-anchor the floor concept on **peer/sector/chain EV-multiple banding** (the no-growth scalar can stay as ONE deterministic anchor among several, but the *taught lens* is multiple banding). The pipeline should surface raw EV/Rev, EV/FCF; the *banding vs peers* is agent judgment.

### A3. Earnings-quality — GAAP vs non-GAAP / SBC is a stated obsession
Fallacy #8 (2032273412413145111): "Net Income is not the same as GAAP Net Income... non-GAAP $500M... GAAP could be a $150M loss because of SBC." Deserves an explicit earnings-quality gate (sharper than the doc's "real FCF after SBC").

---

## B. UNDER-CAPTURED FIRST-CLASS MOVES (add to doctrine)

1. **IV/Vega LEAP-on-a-thematic-ETF** — EWY is his #11 ticker (77 posts). He buys **$EWY 2028 LEAP calls** for Samsung/SK Hynix exposure, reasons through ETF NAV ("SK Square ~90% NAV is SK Hynix") AND IV/Vega expansion ("2028 OTM leap value may double from Vega expansion alone"; "My $EWY leaps hit triple digit returns"). The doc's "ETF = thematic vehicle" badly under-captures this. → first-class entry/vehicle move.
2. **Options mechanics depth** — full CSP-laddering keyed to IV tiers (1972367879858470974): "<30% not worth it... 65-100% sweet spot... 100%+ danger zone", beta-sized margin, "never write puts on stocks you're not comfortable buying."
3. **Normalized peer-comparison tables** — he manufactures apples-to-apples comparisons (1995084174223651180 neocloud margins normalized to same H100s/4yr dep/85% util; "means nothing if accounting is not normalized" — fallacy #7). A core analytical artifact.
4. **Prove-the-math fear-fade** — his single most repeated quantitative pattern: fade coordinated bear narratives with hard margin math. "a 50% increase in energy costs shaves ~0.7% off SK Hynix margins" (2030667380855083222). Elevate.
5. **Sum-of-parts / hidden-stake unlock** — values names on a subsidiary stake worth more than the parent's MC (2067100222778704207 WUS/Kunshan via Palliser; 2007071108831338685 NBIS Clickhouse SOP). Doc has no SOP move — add.
6. **Self-deprecating post-mortem / loss-confession** — real voice element ("Weekend Reflections — every position I'm down on + lessons", 1979685872800010548).

---

## C. VOICE SIGNATURE (verified counts)

- `NFI`/`NFA` 136/18 (ubiquitous sign-off) · `probably` 217 · `imo` 56 · `lol` 58 · `feels like` 49 · `my guess` 20.
- `->` arrow chains 255 · `TLDR` 93 (TLDR-sandwich confirmed).
- Rating vocab: "Strong Buy" 18, "Avoid" 20, "swing trade" 25, "re-rate/rerate" 47, "tax harvest" 16.
- Genuine epithets (rare, use ≤once): "money printer" 13, "holy grail" 5, "free real estate" 4 (CSPs), "dilution machine" 2. Confirmed verbatim signature: **"The biggest signal of whether the AI trade continues is hyperscaler spending."**
- Iconic one-offs (real, rare): "Float & fundamentals > lines on a chart", "bottleneck within a bottleneck", "follow the money", "hunger games" (substrate allocation).

---

## D. VALIDATION GOLD-SET (12 self-contained theses — for WF4 reproduction tests)

Format: `id | date | tickers | archetype | the call + logic + PT/timeframe`

1. **2004936335702753729 | 2025-12-28 | AXTI,SMTOY,LITE,GOOGL | BOTTLENECK (purity-tier recursive hop).** InP chokepoint: Western AI roadmap tethered to $700M AXT + Sumitomo duopoly (~60-70%); demand ~2× supply; "hunger games" allocation. Tests: chain-trace to feedstock, demand>supply gate, enabler-material reframe.
2. **2029219794025644382 | 2026-03-05 | AAOI,LITE,FN | BOTTLENECK + content-sizing.** "3x by next year." AAOI only pure US transceiver fab; at $7.1B MC H2-2027 $4.35B ARR leapfrogs LITE ($55B) FY26; 3-4 hyperscalers buy all capacity. PT 3x/1Y. Tests: content×volume÷MC, monetization gate, made-in-America moat.
3. **2027318568728273305 | 2026-02-27 | IQE,LITE | BOTTLENECK + asset-value turnaround.** IQE ($179M) owns 100+ MOCVD reactors vs LandMark 27-30 ($3.8B); priced for bankruptcy on £45M debt ("pennies to hyperscalers"); Lazard review. Downside: dilution. Tests: transfer-from-winner, survival gate, capacity-optionality, DEDUCED restructuring bet.
4. **1995084174223651180 | 2025-11-30 | NBIS,CRWV,IREN | EVOLUTION/asset-financed + levered-IRR.** Normalized H100 margins NBIS 38.1%>IREN 35.8%>CRWV 30.6%; IREN 9.3% MSFT GM is "wrong lens — 15-20% levered IRR." CRWV killed on $1.3B debt interest. Tests: levered-IRR substitution, normalized peer table, dilution/debt kill.
5. **1975205333254447126 | 2025-10-06 | SNAP | DISRUPTION/margin-inversion.** "Made biggest expense a revenue stream" — monetize Memories storage + cut $190M GCP OPEX → ~$850M FCF → 35× EV/FCF → $31-33B MC. PT +50-100%/12-18mo. Tests: OPEX-flips-to-revenue re-anchor, FCF-multiple valuation.
6. **2031055797086728366 | 2026-03-10 | RDDT | DISRUPTION/catalyst (contrarian).** "Asymmetric long, bullish during war": captures crisis search/engagement; subreddit isolation protects ad spend; Q1 guidance sandbagged pre-Iran. Tests: catalyst=forward-revenue test, second-order engagement, falsifiable.
7. **2009637599661510665 | 2026-01-09 | VLN | DATA-ERROR mispricing.** Ticker collision (Valens vs Velan) → phantom $82M inventory burn — mathematically impossible ($136.7M assets − $93.5M cash = $43.2M room); + CES robotics pivot 69% GM. PT ~$493M base (320%). Tests: data-error gotcha, prove-the-math on filing, dilution-cap on warrants.
8. **2006301094394335399 | 2025-12-31 | MRVL | Falling-knife / mechanism check.** Benchmark/Information "displacement" rumors physically impossible mid-cycle (30-38mo redesign; SerDes embedded in I/O ring); CEO "POs in hand." PT $231 from $85/2Y at 30× on $20B rev. Tests: is-headline-bad-math, physics-trumps-rumor, sympathy-vs-real-damage.
9. **2030667380855083222 | 2026-03-09 | EWY (SK Hynix/Samsung) | MACRO fear-fade with math.** Oil/LNG/Helium KOSPI fears are "bad math": 50% energy spike = -0.7% SK Hynix / -2.4% Samsung OP vs 58-70% margins; helium "almost no chance." "If margins were actually threatened, the selloff would be justified." Tests: prove-the-math fear-dip, narrative-flood-as-tell, KRW second-order, EWY LEAP vehicle.
10. **1969151544320016527 | 2025-09-20 | NBIS | EVOLUTION + strategic-floor + macro stack.** "$1M+ position, $225 PT": Mag7 customers + NVDA strategic incentive to prop GPU-lenders; $4.1B raised de-risks $17B MSFT capex; 3x rate cut marks up far-out earnings. Tests: strategic-backstop floor, funded-de-risking, multi-channel macro→micro.
11. **2016921538780680402 | 2026-01-30 | CPSH | BOTTLENECK/enabler-material (early-cycle).** AlSiC pure-play (~25% Western share) ~$100M MC; tiny-TAM defense material maybe → AI thermal at Rubin 2000W+ (2027-28); DoD contract floor. "Toto toilet ceramic → memory" analog. Tests: stage-1 guess, enabler-material option, defense-floor downside.
12. **2033763395032519112 | 2026-03-17 | AEHR,POET,AAOI,SNDK,NVDA | CYCLE-STAGE framework (meta).** Explicit 5-stage map w/ named exemplars + allocation logic (#4 mid-cycle most weight, <2% to #1). Tests: can harness place a name in the right cycle stage and size conviction accordingly?

(Spread: 4 bottleneck, 2 disruption, 2 evolution/asset-financed, 2 falling-knife/data-error, 1 macro-fade, 1 cycle-meta.)

---

## E. COVERAGE STATS

- **Top tickers** (post count): SIVE 266 (tagging artifact), LITE 247, NVDA 238, AXTI 207, NBIS 200, AAOI 171, TSM 138, COHR 128, MRVL 125, IREN 123, GOOGL 120, MU 111, META 111, AMZN 110, MSFT 109, SNDK 102, IQE 93, INTC 86, AVGO 85, HOOD 80, EWY 77, RDDT 77, RKLB 72.
- **Post types:** single-name (1 ticker) ~26%, focused thematic/comparison (2-7) ~51%, ranking list-posts (≥8) ~13%, pure macro (0 ticker) ~11%. → maps to Type B / C-D / E / A.
- **Themes:** photonics 295, hyperscaler 235, laser 193, bottleneck 177, memory 168, substrate 121, space 109, InP 97, transceiver 82, neocloud 74, robotics 62, defense 55, dilution 55, monopoly 53, NAND 51, HBM 44, quantum 43 (almost always *avoid*), made-in-america 30, stablecoin 22.
- Cadence ramps over time (2025-09: 78 → 2026-03: 316). Methodology most densely expressed in 2026 H1.
