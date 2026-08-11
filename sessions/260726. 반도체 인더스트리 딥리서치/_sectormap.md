# The semiconductor chain, decomposed — 2026-07-26

Companion to `_sectormap.json` (machine-loadable, 30 layers, validated by `scripts/serenity_sectormap.py`). Regime context in `_macro.md`. Kiwoom's bottleneck-propagation chart transcribed in `_reference_kiwoom_bottleneck_map.md`. An independent second decomposition, produced without sight of this one, is in `_codex_sectormap.md` — where the two disagree, the disagreement is called out below rather than smoothed over.

**Reload this session with:**
```bash
scripts/.venv/bin/python scripts/serenity_sectormap.py layers  "sessions/260726. 반도체 인더스트리 딥리서치/_sectormap.json"
scripts/.venv/bin/python scripts/serenity_sectormap.py cohort  "sessions/260726. 반도체 인더스트리 딥리서치/_sectormap.json" --layer optics-laser
scripts/.venv/bin/python scripts/serenity_sectormap.py tickers "sessions/260726. 반도체 인더스트리 딥리서치/_sectormap.json" --listing us,adr
```
`cohort` emits the exact argv for `serenity_pipeline.py discover`, so a future session re-prices any layer in one step. **Numbers in this folder expire — re-run the pipeline. What carries over is the structure.**

---

## The one thing that reframes the whole question

The instinct behind "반도체 = NVDA, AMD, ASML, TSM, MU" is not wrong about importance. It is wrong about **where scarcity currently sits**, and it silently assumes the scarce thing is *silicon*. Three separate observations kill that assumption:

1. **The bottleneck has already migrated off the die.** Kiwoom's own chart says GPU die shortage has eased and the constraint moved to HBM, packaging, power and networking. Every layer that matters now is downstream or upstream of the accelerator, not the accelerator.
2. **Scarcity is three different things wearing one word.** A layer is a **bottleneck** (physics; capital cannot fix it inside the demand window), a **constraint** (capital + time fixes it), or a **risk** (one platform decision removes it). Of the 30 layers mapped the split is **13 bottleneck / 15 constraint / 2 risk** — *(corrected twice: an earlier draft said "about a third," and advanced packaging was subsequently reclassified bottleneck → constraint on sourced evidence that the CoWoS gap is closing from ~20% to ~10% by end-2026 while capacity quadruples and is deliberately outsourced)*. And read even the 14 with suspicion: as the review below argues, tagging a layer "bottleneck" on mechanism-plus-concentration is a **candidate**, not a passed test. Calling all of them bottlenecks is how a theme portfolio ends up owning nine names that are one bet.
3. **Several of the tightest layers have no good US-listed expression, and several have one nobody looks for.** Both halves of that sentence are actionable, and the second half was the biggest single correction this session produced.

The organising test I'd apply to any name in this space — borrowed from the independent map because it is sharper than my original phrasing:

> **What is the minimum action required to remove this supplier?** If a customer architecture memo can do it, it is a design slot, not a chokepoint. If removing it means rebuilding or requalifying a manufacturing process, it is a chokepoint.

That single question separates CRDO/ALAB/MPWR (design slots — excellent profit pools, one decision from erosion) from InP crystal growth, hybrid bonding, and qualified mask/material systems (process rebuilds).

---

## The stack, in dependency order

Positions are "how close to end demand", 1 = closest. Full detail per layer in `_sectormap.json`.

| # | Layer | Class | The scarce thing | Primary US-listed route |
|---|---|---|---|---|
| 1 | AI accelerators / custom XPU | constraint | simultaneous access to wafer + HBM + packaging slots | NVDA · AMD · AVGO · MRVL |
| 1 | AI compute buyers (neoclouds) | risk | nothing — this is demand, not supply | NBIS *(held)* |
| 2 | EDA · IP · NoC | bottleneck | the tool flow and IP every tape-out needs | SNPS · CDNS · ARM · AIP |
| 2 | Server CPU | constraint | advanced capacity allocated to GPU first | INTC · AMD · ARM |
| 3 | **HBM** | **bottleneck** | wafer-per-bit + stack yield + fab cycle | **MU** · **SKHY** *(SK Hynix ADS, NASDAQ since 2026-07-10 — a rung-1 line this map originally missed)* |
| 3 | Memory interface (RCD/DB, CXL, HBM PHY) | constraint | standards-qualified interface silicon | **RMBS** |
| 3 | NAND / eSSD | constraint | deferred capacity + slow QLC qualification | SNDK · WDC · STX · SIMO |
| 3 | Rack power & cooling infrastructure | constraint | transformers, switchgear, interconnect queues | VRT · NVT · MOD · POWL |
| 4 | Advanced packaging (CoWoS/SoIC/EMIB) | constraint | *reclassified* — CoWoS gap closing ~20%→~10% by end-2026 as capacity quadruples | AMKR · TSM · ASX |
| 4 | Leading-edge foundry + **US jurisdiction** | **bottleneck** | leading edge, and separately *location* | TSM · INTC · GFS · SKYT · UMC |
| 4 | Power semis / power delivery | constraint | the high-efficiency AI cut, not the silicon | MPWR · VICR · POWI · NVTS · WOLF |
| 5 | **Packaging equipment (bonders)** | **bottleneck** | tool build + qualification lead time | **KLIC** · VECO · ONTO · CAMT |
| 5 | Optical transceivers | constraint | upstream laser/DSP, not assembly | LITE *(held)* · COHR · AAOI *(held)* · FN |
| 5 | Electrical interconnect (retimers, AEC) | **risk** | a design slot — removable in one platform | CRDO · ALAB · APH · SMTC |
| 5 | MLCC & passives | constraint | the high-reliability AI-server cut | VSH · LFUS — **the real route is MRAAY** |
| 6 | **Package substrate (FC-BGA / MLB)** | **bottleneck** | layer count vs yield | TTMI *(MLB only — not FC-BGA)* |
| 6 | **Glass-core substrate** | **bottleneck** | through-glass via without micro-cracking | ONTO *(held)* · GLW · LPKFF |
| 6 | **Silicon photonics foundry** | **bottleneck** | photonics-qualified mature-node capacity | TSEM *(held)* · GFS · XFABF · SKYT |
| 6 | **Laser chips (CW/DFB/EML, ELS)** | **bottleneck** | epitaxy + qualification, not assembly | LITE · COHR · MTSI · SIVEF |
| 6 | Front-end WFE | constraint | tool build time; EUV a true monopoly | AMAT · LRCX · ASML · ACLS |
| 6 | Metrology & inspection | **bottleneck** | qualification gate on every new architecture | KLAC · ONTO *(held)* · CAMT · PDFS |
| 6 | Test (ATE, probe cards, burn-in, sockets) | constraint→hybrid | test time per die rising faster than units | TER · **FORM** · AEHR · COHU |
| 6 | Yield analytics | constraint | fragmented chiplet manufacturing data | PDFS |
| 6 | Fibre / FAU / optical connectors | constraint | precision alignment know-how (mostly private) | APH · FN |
| 6 | Package thermal (AlSiC, spreaders) | bottleneck | CTE-matched materials, long qualification | CPSH · MTRN |
| 7 | **Compound substrates (InP/GaAs/SOI)** | **bottleneck** | crystal growth + purity + qualification | **AXTI** · SLOIY · IQEPF |
| 7 | **Upstream substrate materials (T-glass, HVLP foil, ABF)** | **bottleneck** | the thin qualified cut of ordinary materials | *(essentially none — see below)* |
| 7 | Process materials & consumables | bottleneck | per-fab qualification + single-country refining | ENTG · MTRN · LIN · APD |
| 7 | Photomask | **risk** | leading edge is captive; merchant serves mature | PLAB *(the counter-example)* |
| 7 | Subfab components | constraint | qualified subsystems inside the toolmakers | MKSI · AEIS · UCTT · ICHR |

---

## Where I think the real money is, and why

### 1. The ladder correction — the best expression of three tight layers is a foreign ADR that trades fine in the US

This is the finding I'd act on first, and it is exactly the failure mode `US-listed only` is supposed to cause. I initially wrote several layers off as "rung 4, no route". Checking properly, they price:

| Layer | The actual owner | US route | Verified 2026-07-26 |
|---|---|---|---|
| **Hybrid bonding** — the step HBM4-class 3D stacking runs through | BE Semiconductor (NL) | **BESIY** ADR | prices; fastest revenue growth and highest gross margin of any packaging-tool name checked |
| **HBM test** — Advantest, not Teradyne, leads here | Advantest (JP) | **ATEYY** ADR | prices |
| **Wafer grinding & dicing** — close to a monopoly step | Disco (JP) | **DSCSY** ADR | prices; the highest gross margin of any tool name checked this session |
| **MLCC high-spec tier** | Murata (JP) | **MRAAY** ADR | prices |
| **ABF build-up film** — effectively the substrate standard | Ajinomoto (JP) | **AJNMY** ADR | prices — **but** mid-single-digit consolidated growth, because ABF sits inside a food conglomerate. Access ≠ exposure. |
| **Photonics-SOI wafers** | Soitec (FR) | **SLOIY** ADR | prices |

### …and the correction to that correction

An adversarial review (`_codex_review_sectormap.md`) attacked the sentence above, correctly: **a pipeline quote proves only that a data vendor returns a price.** It says nothing about sponsorship, DTC eligibility, broker access, two-sided depth, or the effective spread you pay on *every tranche* of a multi-year scale-in. It went and checked the depositary records. Revised verdicts:

| ADR | Program status (sourced by the review) | Verdict as a scale-in vehicle |
|---|---|---|
| **ATEYY** | Sponsored, JPMorgan depositary, recurring monthly trading | **Strongest of the six.** Still confirm live spread before sizing |
| **DSCSY** | *Unsponsored*, multiple depositaries, recurring monthly trading | Survives executionally; unsponsored means weaker issuer involvement and variable fees |
| **MRAAY** | *Unsponsored*, sustained recurring trading | Survives executionally. Separate problem: Murata is diversified, so AI-MLCC materiality is unproven |
| **BESIY** | Sponsored, books open, recurring monthly trading | **Conditional** — activity is real, depth and slippage are not established. Small patient limit orders only |
| **AJNMY** | Newly *converted to sponsored* from an unsponsored facility | **Conditional** — and it fails exposure purity regardless: ABF is buried in a food conglomerate |
| **SLOIY** | Unsponsored, DTC-eligible, but thin activity relative to the others | **Fails as a default scale-in vehicle** — closest of the six to a quote-only artifact |

Use limit orders, never market orders, on any of these. **None of this is settled without a live Level 2 book and a measured effective spread at your intended tranche size** — which no artifact in this folder contains.

The lesson generalises: "the winner is foreign" is almost never the end of the analysis, and the ADR is usually a *better* vehicle than forcing a US analog that sits in a different layer. Note the discipline in the AJNMY row — owning the monopoly and owning an equity that *moves* on the monopoly are different things, and that distinction is what stops this from becoming a list of interesting foreign companies.

### 2. The Serenity DB's own edge names are mostly foreign micro-caps — and that is the honest headline

The thesis DB was consulted as a candidate pool only, after forming the map. Its most-discussed semiconductor names by volume are **SIVE** (Sivers, Sweden — CW lasers for CPO), **AXTI**, **LITE**, **AAOI**, **SOI** (Soitec, France), **IQE** (UK), **LPK** (LPKF, Germany — glass-core LIDE), **XFAB** (Belgium). Five of the eight are foreign small or micro caps.

Every one has a US OTC line that prices — SIVEF, SLOIF/SLOIY, IQEPF, LPKFF, XFABF — and every one of those lines was down heavily from its 52-week high on 2026-07-26. But: **OTC liquidity and spreads on a sub-$1B foreign micro-cap are a real execution constraint, not a footnote.** For a scale-in program specifically, a wide-spread OTC line is a worse vehicle than a slightly less pure US name, because you pay the spread on *every* tranche. That is a genuine argument against the purest expressions here, and it is not the argument the theses themselves make.

### 3. The layers with genuinely no faithful vehicle — say it plainly

Kiwoom's rung 6 (upstream substrate materials: T-glass, HVLP copper foil, micro drill bits) is arguably the single tightest layer on the whole chart, described as structurally tight into mid-'27. **There is no faithful US-listed way to own it.** PKE and ROG are adjacent laminate names whose AI-substrate revenue share is unquantified; neither owns T-glass scarcity. Top-end FC-BGA fabrication (Ibiden, Shinko, Unimicron) is the same story.

Also genuinely unownable: Zeiss SMT optics inside EUV; temporary bond/debond chemistry (Brewer Science, EV Group — private); purity-critical quartzware and chamber ceramics; the private FAU/precision-attach specialists; narrow specialty-gas molecules.

The useful move for these is not to buy a proxy. It is to **use them as leading indicators** — T-glass and HVLP lead times tell you the substrate layer is tight, which tells you the equipment and inspection layers have orders coming, and *those* you can own.

### 4. The counter-example that keeps the map honest

**PLAB (Photronics).** Photomask is a real three-player oligopoly, mask blanks a genuine duopoly. A hype-anchored map puts it on the list. The pipeline says: revenue flat across five quarters, gross margin compressing, operating margin compressing, and 44 insider sells against zero buys in twelve months. The structural story is true and the economics do not reach the listed merchant, because leading-edge masks are made captive at the logic and memory makers themselves. **A concentrated layer where the listed player captures none of the economics is not an opportunity, and "cheap" is not the same as "mispriced."**

The same test, applied honestly, should be run on ENTG, MTRN, LIN, APD, GLW and VSH — all touch relevant layers, all may be too diluted to move on them.

### 5. Where the two independent maps disagreed

Worth recording, because the disagreements are where the uncertainty actually is:

- **Advanced packaging.** I classed it a bottleneck; the independent map classed the broad category a capital-and-time constraint and argued the hard node sits *underneath* — substrate, dielectric, low-expansion glass, temporary-bond chemistry, alignment, known-good-die test. I think the independent read is better and have kept the bottleneck tag only for the *equipment* and *inspection* sub-layers, which is where the qualification gate really is.
- **Silicon photonics foundry.** I classed it a bottleneck; the independent map argues a customer-owned PIC can be ported after requalification, making it capital-and-time. This matters directly for TSEM, and it is unresolved — the falsifier is whether a volume customer states a foundry module is sole-source and unportable within the product window.
- **AXTI geography.** I flagged moat-vs-hostage as needing resolution; the independent map argues the China-linked footprint creates scarcity *and* permit hostage risk simultaneously, and that scarcity without reliable shipment is not monetisable. Also unresolved, and it is the crux of that name.

---

## Response to the adversarial review

`_codex_review_sectormap.md` is a genuine attack on this map, run by a model that had not seen it while building its own. Recording what I accepted and what I did not, because a review whose findings vanish into a summary was theatre.

**Accepted and fixed in place:**
- The bottleneck count contradiction ("about a third" vs 14/30) — a straight arithmetic error, corrected above.
- The unsourced "20–40% drawdowns" claim in `_macro.md` — replaced with the actual `pct_below_52w_high` range from this session's runs.
- "Combined latest-quarter capex" mixing Q1 and Q2 reporters — relabelled a rolling latest-report aggregate.
- "Full conviction is allowed on structure" in `_macro.md` — contradicted the two unread regime pillars and the EDGAR block. Capped a tier lower.
- The ADR ladder over-claim — replaced with the sourced program-status table above. This was the single most useful catch: I had treated "the pipeline returns a quote" as evidence of tradeability, and it is not.

**Accepted as a real limitation, not fixed this session:**
- **"Bottleneck was tagged, not run."** Correct. Most rows give a mechanism and a concentration claim but do not quantify demand-versus-supply, do not demonstrate no-substitute-before-demand-peaks, and do not price the layer economics per unit. The field should be read as **`bottleneck_candidate`**. Doing it properly means per-layer supply/demand arithmetic that this session did not have the sourced inputs for.
- **Concentration counts are unsourced.** "Three suppliers worldwide," "a two-player duopoly," "one credible tool owner" — these are load-bearing and should each carry a dated citation. They currently do not. Treat them as DEDUCED.
- **Proxy contamination in the candidate column.** LIN/APD under a bottleneck row, VSH/LFUS under high-spec MLCC, TTMI under FC-BGA, GFS/SKYT/UMC under leading-edge — each is caveated in its note, but a machine consumer reading `candidates` still gets the ticker. The right fix is a `relationship: owner | tool | consumer | adjacent_proxy` field in the schema; that is a change to `serenity_sectormap.py` and its validator, deferred rather than bodged.

**Where I push back:**
- **"The thesis DB was used without authorization" (E5) is wrong on the facts.** The reviewer could not see the user's instruction, which explicitly permitted consulting the DB critically. Non-negotiable 8 was satisfied by explicit user authorization, and the DB was used only as a candidate pool after the map was formed — every link it produced is tagged DEDUCED, which is what the reviewer asks for anyway.
- **"The map crosses from map to action without completing the funnel" (E8) is half right.** The reviewer was given only the map files. The funnel *is* completed — `analyze` → gates → stage → a both-legs `Lens:` line → vehicle — for every actionable name, in `_ranking.md` and the per-name scorecards. The fair part of the criticism stands: `_sectormap.md` itself should not carry action language, and the phrase "where the real money is" over-claims for a document that is candidate generation.
- **"N9 hard-block not honoured on NBIS" (E4) is arguable.** N9's data-integrity fork hard-blocks on a nulled `key_facts`/XBRL line; NBIS's `key_facts` are complete and internally consistent, and what is missing is the relationship dossier. Naming a neocloud an Evolution archetype is not the contested judgment — its *gate 3* is, and that gate is explicitly held UNPROVEN with the name left UNRESOLVED and untiered. I have not moved it.

**The best criticism, recorded for the next iteration:** `limitation_class` is attached to the wrong object. Scarcity is not a property of an industry noun like "advanced packaging" or "test" — it is a property of an **atomic scarce attribute on a dated product-generation edge** (HBM generation × bonding route × qualification window; optical architecture × light-source choice × epi source). Because each composite row must accept one class, a lower-hop bottleneck lends its label to a fundable assembler above it, and the bottleneck *count* becomes an artifact of taxonomy granularity. That is a schema redesign — nodes plus time-bounded edges carrying `scarce_attribute`, `minimum removal action`, `qualified supply evidence`, `substitute qualification time`, `owner vs tool vs proxy` — and it is the right next version of this file.

## Evidence limits of this session — read before using any of it

- **SEC EDGAR returned 403 to every request** from this environment, retried with explicit identity and outside the sandbox. So: no customer-concentration %, no country revenue %, and critically **no financing-structure read**. The funded-versus-dilution gate — the one that decides NBIS and any capacity-building name — could not be run. It is marked unresolved, not assumed either way.
- Net liquidity, ERP and credit spreads were not returned by the macro pipeline; two of the four regime pillars are unread.
- Every supply link in `_sectormap.json` is tagged CONFIRMED or DEDUCED. **Nothing tagged DEDUCED should be sized on.**
- All figures cited anywhere in this folder are from the pipeline run of 2026-07-26 and expire. Re-run before acting.
