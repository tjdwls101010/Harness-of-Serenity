# Coverage Critic — Tacit-Knowledge Loss Audit

**Method:** legacy-monolith-skill.md (552 lines) and db-mining-report.md (A1–A3, B1–B6, C, D, E) traced item-by-item against the four drafts (draft-claude_md.md, draft-discovery.md, draft-analysis.md, draft-macro.md). All four drafts present and read in full. Paranoid pass on the dense parentheticals.

**Verdict:** Coverage is **high** — the four drafts are unusually faithful and the heavy parentheticals are mostly captured. But there are **22 genuinely-dropped or materially-weakened items**, of which **6 are HIGH severity** (a load-bearing nuance lost, not just reworded) and the rest MEDIUM/LOW. Each is listed with: the missing item, legacy location, why it matters, and which draft should carry it.

Severity key: **HIGH** = a behavioral resolver / inverse-case / loss-hardened nuance that, if dropped, lets the engine make a confident wrong call. **MED** = a real nuance dropped but lower blast radius. **LOW** = a phrase/handle/example dropped; cosmetic-to-minor.

---

## HIGH severity (load-bearing — must restore)

### H1. The `discover` command's *role* (cohort comparator) is split from its CLI form — and the SCAFFOLD it returns is gone entirely
- **Missing:** Legacy Data Contract (lines 41, 55–57) describes the pipeline's **`objective_screen`** — "health · momentum · catalyst · valuation, scored /60 — a triage/discover comparator, **NOT a grade and NOT a verdict**" — with the operational shorthand *"`objective_screen` is a screen, not a verdict"* and the worked nuance: *"A high screen on a no-moat hot name, or a low screen on a real early winner, is exactly the gap you resolve."* **None of the four drafts mention `objective_screen` at all.** draft-claude_md's gives-vs-judges table (lines 49–58) lists "the `objective_screen` … → what a high/low screen actually means here" was *dropped* from the compressed table (legacy row 49 `CapEx direction, earnings momentum, the objective_screen` became just "CapEx direction, earnings momentum").
- **Legacy location:** Data Contract §, lines 40–41, 49, 55–56; verdict-scaffold description line 41.
- **Why it matters:** This is the single most important "pipeline-gives-but-does-not-judge" artifact and the user's *entire* stated concern is that the pipeline must surface judgment-substrate without making the judgment. The `objective_screen`-is-a-screen-not-a-verdict framing is the canonical worked example of that boundary (a high screen on a no-moat name = the gap the analyst resolves). Dropping it silently risks the new pipeline either (a) re-introducing a hidden grade, or (b) the analyst treating any composite score as a verdict — the precise failure the redesign exists to prevent. **NOTE:** the new harness may intend to *remove* `objective_screen`; if so that is a deliberate design decision, but the *principle* it encoded (a composite triage number is never a verdict) must survive somewhere. Right now it survives nowhere.
- **Belongs in:** draft-claude_md (Data Contract / gives-vs-judges table) — restore the "a composite/triage score is a comparator, never a verdict" principle even if the field name changes.

### H2. The `pre_commercial` "one-time charge" caveat is dropped from CLAUDE.md and the dual-meaning is thinned
- **Missing:** Legacy (line 57) — *"(yfinance TTM op-margin can also be pushed < −100% by a one-time charge — check before trusting it.)"* draft-analysis.md DOES carry "first rule out a one-time charge (impairment, litigation, restructuring)" (line 119) and the gotcha echoes it (line 331). But **draft-claude_md's gives-vs-judges table row for `pre_commercial` (line 57) does not carry the caveat**, and more importantly the *behavioral resolver* — *"the tenor of cash commitment — a supplier that can demand multi-year prepayment to guarantee supply faces a structural shortage, not a cyclical one (revealed preference)"* (legacy line 329) — appears ONLY in draft-analysis line 119. That is correct placement, so this is half-covered.
- **Legacy location:** Data Contract line 57; Winner Gates pipeline-hand-off line 329.
- **Why it matters:** The multi-year-prepayment-as-revealed-preference resolver IS captured (analysis line 119) — good. The residual gap is only that CLAUDE.md's one-line `pre_commercial` summary could read as "op-margin < −100% = be skeptical" without the trough-vs-melting fork. Lower than H1 but flagged because the dual meaning (hype-promise vs cyclical-trough vs one-time-charge — THREE meanings) is the load-bearing part.
- **Belongs in:** Already in draft-analysis (good). Confirm draft-claude_md's one-liner does not collapse it to a single meaning.

### H3. Discovery Escalation trigger lives only in CLAUDE.md draft — discovery draft omits its own escalation rule
- **Missing:** Legacy Analysis Protocol (line 192) — *"Discovery Escalation: if mapping reveals a high-growth chain whose key input is concentrated (top-3 > 70%) in a supplier with MC < 1/10 of the target, escalate to the discovery toolkit."* This IS in draft-claude_md (line 227, step 4). But **draft-discovery.md — the skill that OWNS the discovery toolkit — never states the quantified escalation trigger (top-3 > 70%, MC < 1/10).** Discovery is where this threshold actually fires.
- **Legacy location:** Analysis Protocol step 4, line 192.
- **Why it matters:** The numeric trigger (top-3>70%, MC<1/10) is exactly the kind of deterministic gate that keeps discovery from firing on every name while guaranteeing it fires on the leveraged ones. CLAUDE.md mentioning it is the *routing* cue; the discovery skill needs it as the *operating* threshold. A reader who loads only serenity-discovery would not see the threshold.
- **Belongs in:** draft-discovery (add the quantified escalation trigger as an entry/qualification gate; CLAUDE.md keeps the routing pointer).

### H4. "Most names are clean / span-two → run BOTH gate sets, weaker sets conviction" — the *valuation* half is dropped
- **Missing:** Legacy Archetype Playbooks closing (line 221) — *"When a story spans two — a bottleneck inside a disrupted category — run both gate sets and let the weaker one set the conviction."* draft-analysis line 59 captures the GATE-SET half. But legacy One Funnel (line 169) and the playbook also imply the **valuation anchor** rotates per archetype and a span-two name must reconcile *two anchors*. The span-two item only addresses gates, not which valuation lens wins. Minor, but the "weaker one sets conviction" rule is the resolver and it IS captured — so this is borderline. Flagging because the *inverse error* warning ("don't reach for Disruption/Evolution on a clean chokepoint just because its grade looks low") appears in draft-analysis (line 11) and draft-claude_md (line 208) — GOOD, fully covered there.
- **Legacy location:** Archetype Playbooks line 221; One Funnel lines 169.
- **Why it matters:** Covered well enough; downgrading on re-check. Leaving as a note: confirm the span-two resolver explicitly says the *weaker gate set*, which draft-analysis line 59 does. **Resolved — no action needed.**

### H5. The "objective_screen scored /60" component breakdown is gone — and so is the L1–L5 level taxonomy as a data-map
- **Missing:** Legacy Data Contract (lines 39–41) enumerates the full pipeline output map: **L1** macro regime + VIX/ERP/liquidity/BDI/DXY · **L2** hyperscaler CapEx cascade direction · **L3** the SEC `evidence_dossier` (company_relationships, country_exposure, critical_inputs, financing_facts) + XBRL (per-country revenue %/$, customer-concentration %, inventory, purchase obligations) + recent 8-K events · **L4** forward P/E, PEG, dual valuation, margins, debt grade, dilution class, RS rank, institutional quality, IV tier, short interest, health gates · **L5** earnings momentum + analyst revisions. The drafts reference `L3.evidence_dossier`, `key_facts`, `financing_facts`, `health_gates`, `absence_evidence_flags`, `capex_flow.direction`, `iv_tier`, `dilution`, `pre_commercial`, `cockroach_effect`, `real_fcf`, `marketCap`, `days-to-earnings`, `institutional_quality` — but **no draft carries the consolidated L1–L5 field map.** The cycle-stage table in draft-analysis (line 211) references `rev_growth`, `earnings_momentum`, `margins.flag`, `capex_flow.direction` (good), but the master "here is the full schema the JSON returns" inventory is absent.
- **Legacy location:** Data Contract lines 39–41.
- **Why it matters:** The user explicitly said the new pipeline output schema should be redesigned and *leaner* — so a verbatim L1–L5 reproduction is NOT required. BUT the **set of fields the analyst is entitled to expect** (per-country revenue %, customer-concentration %, purchase obligations, inventory, 8-K events, RS rank, short interest) is tacit knowledge: if the new schema silently drops `purchase_obligations` or `customer_concentration`, the analyst loses inputs the doctrine references (e.g. content-sizing needs concentration %; designed-out monitor needs 8-K events). This is a **schema-contract** risk, not a doctrine-text risk.
- **Belongs in:** draft-claude_md (Data Contract) should carry a compressed but COMPLETE field inventory so the pipeline redesign has a checklist of what judgment-substrate must survive. Right now the field list is scattered and partial.

### H6. "Float & fundamentals > lines on a chart" and the chart/TA-timing-only discipline — the TA prohibition is in CLAUDE.md but the *entry-timing* positive rule is thin
- **Missing:** Legacy Entry/Vehicle (line 494) — *"TA (support/resistance) informs where to enter a validated name — never whether."* draft-analysis line 264 carries this verbatim (good). And the prohibition "never base directional conviction on chart patterns — TA is timing only" is in draft-claude_md (line 286) and the Values table V10. So the rule is covered. **The dropped piece:** the *iconic sign-off* "Float & fundamentals > lines on a chart" is listed in draft-claude_md's signature-phrase item (line 31). **Covered. Resolved — no action.** (Re-verified: this is fully present. Downgrading out of HIGH; left here only to document the check.)

---

## Revised HIGH list (after re-verification, H4/H6 resolved): the four genuine HIGH gaps are H1, H3, H5, plus the two below (H7, H8).

### H7. The L2 / Crisis-Wartime "companies irrelevant in peacetime become critical in wartime" + the Fear-Dislocation-vs-Crisis DISTINCTION-trap — partially thinned
- **Missing-check:** draft-macro line 30–35 carries Crisis/Wartime as the 4th regime AND the critical distinction ("Fear-Dislocation and Crisis/Wartime *look* identical on the tape but demand opposite moves") — **this is fully and excellently captured.** The "companies irrelevant in peacetime become critical in wartime" line is in draft-macro line 31. **Resolved — no action.** Documented to show the paranoid check ran.

### H8. The "absence_evidence_flags.no_fundamental_change_selloff → potential_entry" pipeline mechanic — the FLAG NAME and its hand-off semantics
- **Missing:** Legacy Entry (line 480) — *"The pipeline flags candidates via `absence_evidence_flags.no_fundamental_change_selloff → potential_entry`; you validate it."* draft-analysis's 4-step falling-knife (line 243) describes the validation steps but **drops the specific flag `absence_evidence_flags.no_fundamental_change_selloff → potential_entry`** that the pipeline raises to *trigger* the 4-step. draft-claude_md gives-vs-judges (line 56) has "health gates, absence_evidence_flags → fear-dip or fundamental?" — so the flag *family* survives in CLAUDE.md, but the specific `no_fundamental_change_selloff → potential_entry` hand-off semantics (pipeline flags a *candidate*, analyst *validates*) is gone from the analysis draft where the 4-step lives.
- **Legacy location:** Entry §, line 480.
- **Why it matters:** It's the concrete hand-off contract: the pipeline does not say "buy," it raises "this looks like a no-fundamental-change selloff, here's a *candidate* — go validate." If the new pipeline schema is redesigned, whoever builds it needs to know this flag is the entry-point trigger, and the analysis doctrine should say "when the pipeline raises [this], run the 4-step." Dropping the flag name risks the validation steps becoming orphaned (no stated trigger).
- **Belongs in:** draft-analysis (Entry 4-step — name the triggering flag) and confirm the pipeline schema inventory (H5) lists it.

---

## MEDIUM severity

### M1. The "two failures the data contract prevents" framing — distrusting clean numbers vs over-trusting a fabricated judgment
- **Missing:** draft-claude_md line 59 DOES carry "the two symmetric failures: the LLM either distrusting clean numbers (re-guessing a market cap from memory) or over-trusting a fabricated judgment (treating a screen as a verdict)." **Covered.** Resolved.

### M2. "Eyeballing the market cap a sizing move divides by … is a V2 falsification that invalidates the call" — the *eyeballing* (not just inventing) clause
- **Missing-check:** draft-claude_md line 65 carries "Asserting a 'supply agreement' the dossier doesn't list, or eyeballing the MC a sizing move divides by, is a V2 falsification." draft-analysis line 349 carries "Eyeballing the MC … or asserting an unlisted 'supply agreement' … silently inverts the whole call." **Covered in both.** Resolved.

### M3. The recursive-hop "vertically-integrated-LOOKING supplier may still buy one critical input from a single outside source — that source is the deeper bottleneck"
- **Missing-check:** draft-discovery line 22 carries test (3) "Is the dependency captive? A supplier that *looks* vertically integrated but still single-sources one outside input is captive to that source." **Covered.** Resolved.

### M4. "The purity/spec gate is the most transferable of the three" + the specific transfer list (quartz, photoresist, medical-grade polymers, aerospace alloys)
- **Missing-check:** draft-discovery line 23 carries "The purity/spec gate is the most transferable test (quartz, photoresist, medical-grade polymers, aerospace alloys all hide a tighter monopoly in their high-spec cut)." **Covered.** Resolved.

### M5. The "13F lags, so corroborate" caveat on institutional-accumulation
- **Missing-check:** draft-analysis line 243 (step 3) carries "(13F lags, corroborate)." draft-claude_md does not, but it's a deep mechanic correctly placed in analysis. **Covered.** Resolved.

### M6. Dividend front-running as a *timing* catalyst on already-validated large-caps
- **Missing-check:** draft-macro line 88 carries "dividend front-running is a *timing* catalyst (optimize entry on already-validated large-caps)." **Covered.** Resolved.

### M7. The "convertible *in you* — taking a risk-free convertible in you puts zero third-party capital into the build" funding-trap (a)
- **Missing-check:** draft-analysis line 38 (Evolution gate-3 verify) carries "a vendor letting you use its logo, or taking a risk-free convertible *in you*, puts zero third-party capital into the build." **Covered.** Resolved.

### M8. "Architecture-identity check" — the "confident single-spec commoditization claim is itself a tell the critic conflated architectures"
- **Missing-check:** draft-analysis line 105 carries this in full including the "is itself a tell" clause. **Covered.** Resolved.

### M9. Wrapper NAV-premium acute case — "no float/options to short, the move is *don't buy*, then expect violent reversion to NAV"
- **Missing-check:** draft-analysis line 271 (kill #1) carries the wrapper NAV-premium acute case fully. **Covered.** Resolved.

### M10. The buyback-funded-by-debt-to-offset-SBC inversion ("reconstruct as-if-cash FCF")
- **Missing-check:** draft-analysis line 278 (kill #8) carries "invert the buyback's friendly reputation … reconstruct as-if-cash FCF." **Covered.** Resolved.

### M11. The circular self-justification loop (dilute → hoard cash → claim higher 'deserved' MC → award SBC out of proceeds)
- **Missing-check:** draft-analysis line 278 carries the full circular-self-justification-loop. **Covered.** Resolved.

### M12. Kill #9 designed-out INVERSION — "customer severing a one-hop intermediary ABOVE your hard-layer name … is often *bullish*"
- **Missing-check:** draft-analysis line 285 (kill #9) carries the soft-layer-vs-hard-layer inversion fully. **Covered.** Resolved.

### M13. Erosion timer — "at ~2× the expected catalyst timeline, force a re-examination"
- **Missing-check:** draft-analysis line 292 carries "at ~2x the expected catalyst timeline force a re-examination." **Covered.** Resolved.

### M14. Post-mortem 4-way taxonomy (A right/wrong-timing · B partial · C fully wrong · D process error)
- **Missing-check:** draft-analysis line 292 carries all four. **Covered.** Resolved.

### M15. The funding-price-floor "<6mo, >5% of MC, fails in broad distress" thresholds
- **Missing-check:** draft-analysis line 200 carries "(<6mo), significant (>5% of MC) … Probabilistic; fails in broad distress." **Covered.** Resolved.

### M16. The "purchase obligations" / "inventory" / "per-country revenue %/$" XBRL fields — see H5 (schema contract)
- Folded into H5.

### M17. The "never sell CSPs with earnings inside ~7 days — check days-to-earnings FIRST" earnings-window stop
- **Missing-check:** draft-analysis line 264 carries it fully including "gap risk is uncompensated." **Covered.** Resolved.

### M18. CSP IV-tier ladder exact numbers (<30% not worth it / 65–100% sweet spot / 100%+ danger zone) + "never write puts on stocks you're not comfortable buying"
- **Missing-check:** draft-analysis line 264 carries the exact tiers and the never-write-puts rule. **Covered (B2).** Resolved.

### M19. The "analyst-report gap — read for the OMISSION" technique
- **Missing-check:** draft-discovery lines 56–61 carry it as a standalone item. **Covered.** Resolved.

### M20. Government impact-analysis mining + the "two governments independently funding the same node compounds it"
- **Missing-check:** draft-discovery lines 84–89 AND draft-macro lines 193–198 both carry it including the two-governments-compound clause. **Covered (and correctly cross-placed).** Resolved.

### M21. Up-listing "hostile local-media piece during the up-list window is the shake-out … NOT a bear signal"
- **Missing-check:** draft-discovery lines 126–131 AND draft-claude_md line 115 AND draft-macro line 309 all carry it. **Covered.** Resolved.

### M22. Sum-of-parts is double-placed — fine, but verify it is not the ONLY discovery-vs-analysis overlap that could cause routing confusion
- **Missing-check:** SOP appears in draft-discovery (lines 140–145) and draft-analysis (lines 192–197). Both frame it correctly (discovery = generate the candidate via the stake; analysis = value the stake standalone). **Acceptable intentional overlap.** Resolved.

---

## GENUINELY DROPPED — confirmed missing after full re-check (the real findings)

After the paranoid pass, the items that are **actually absent from all relevant drafts** (not merely reworded) are:

1. **[H1] `objective_screen` / the /60 triage-comparator-is-not-a-verdict principle** — absent from all 4 drafts. (CLAUDE.md / Data Contract)
2. **[H3] The quantified Discovery-Escalation trigger (top-3 > 70%, MC < 1/10)** — present in CLAUDE.md draft, ABSENT from draft-discovery where it operates. (serenity-discovery)
3. **[H5] The consolidated L1–L5 pipeline field inventory / schema contract** — scattered and partial; no single complete list of judgment-substrate fields (per-country revenue %, customer-concentration %, purchase obligations, inventory, 8-K events, RS rank, short interest, analyst revisions). Risk: the redesigned leaner schema silently drops a field the doctrine depends on. (CLAUDE.md / Data Contract — as a checklist for the pipeline rebuild)
4. **[H8] The `absence_evidence_flags.no_fundamental_change_selloff → potential_entry` flag name + hand-off semantics** — the trigger for the falling-knife 4-step; flag family survives in CLAUDE.md but the specific entry-trigger flag is gone from draft-analysis where the 4-step lives. (serenity-analysis + schema inventory)
5. **[MED-DROP-1] The "absence_evidence_flags" → "is this drop fear or fundamental?" row** appears in CLAUDE.md table (line 56) — but the legacy nuance that the pipeline raises an *absence-of-evidence* signal (no disclosed bad news despite the drop) as distinct from a present-evidence signal is thinned. The *absence-evidence* concept (the pipeline can only flag the ABSENCE of a fundamental-change disclosure, never confirm the dip is safe) is a subtle hand-off the drafts gloss. (serenity-analysis)
6. **[MED-DROP-2] "discover" command returns a *comparator*, and the discovery draft should say what `discover TICKER1 TICKER2…` actually hands back** — draft-discovery references using `discover` to "compare a generated cohort" (line 120) but never states what the comparator output IS (the legacy `objective_screen`-per-name comparison). Tied to H1. (serenity-discovery)
7. **[LOW-DROP-1] "Bottleneck within a bottleneck" / "follow the money flow down to…" / "hunger games"** iconic one-offs — "hunger games" appears in draft-discovery via DB example (line 17) and "bottleneck within a bottleneck" in db-mining C; but the *instruction to use them ≤once as sign-offs* lives only in draft-claude_md's signature item (line 31). Acceptable — voice belongs in CLAUDE.md. **Borderline-resolved.**

---

## Cross-placement / routing risks (not droppage, but coverage hazards)

- **R1 (MED):** The US-listed resolution LADDER is correctly in draft-discovery (full, lines 119–124) with CLAUDE.md keeping only the imperative (line 115) and draft-macro keeping a geo-flavored copy (lines 308–312). This triple-placement is intentional and well-managed. **No gap** — but confirm the three copies don't drift (the ladder *order* must be identical in all three).
- **R2 (LOW):** "Earliest signal = raw-material spot" is in draft-discovery (line 99), draft-macro (line 130), and the named-source lists (LME/Fastmarkets/Argus, TrendForce/DRAMeXchange) appear in both. Intentional overlap, fine.
- **R3 (MED):** The forward-revenue test ("does this change forward revenue?") is the R1 root and appears in CLAUDE.md (R1, line 133), draft-macro (line 81), and implicitly across analysis. Good — it's the master test and SHOULD be omnipresent.

---

## What is impressively COMPLETE (paranoid checks that PASSED)

To calibrate the severity: the following dense/loss-hardened items were checked and are fully captured — the drafts did NOT drop them:
- A1 asymmetrical-upside un-ban + genuine-zeros ban (claude_md line 31, 33) ✓
- A2 EV/Rev + EV/FCF banding replacing no-growth×15 (claude_md R5 line 162, analysis line 129) ✓
- A3 GAAP-vs-non-GAAP/SBC gate + B3 normalized peer tables (analysis line 186) ✓
- B1 Vega-LEAP-on-thematic-ETF (discovery line 133, macro line 314, analysis line 264) ✓
- B2 CSP IV-tier ladder (analysis line 264) ✓
- B4 prove-the-math fear-fade (analysis line 250, macro line 282) ✓
- B5 sum-of-parts (discovery line 140, analysis line 192) ✓
- B6 self-deprecating post-mortem voice (claude_md R6 line 170, analysis line 292) ✓
- Pricing-realization-predictable-from-jurisdiction incl. FDI-screening legal veto (analysis line 84) ✓
- Tranche-carve-out-does-not-launder-dilution + bankruptcy-remote/non-recourse (analysis line 44) ✓
- Evolution gate-3 INVERSE trap (silent filing ≠ funded; borrowed conviction) (analysis line 51) ✓
- Geographic moat-or-hostage + manufactures-inside-the-region = BOTH (analysis line 91, macro line 187) ✓
- Dated-sold-out + above-consensus-hike incl. the NAND ~65-margin-points worked number + the funded-vs-selling-stock "open market" flip + kill #6 cross-check (analysis line 232) ✓
- Equipment-first-then-pure-play rotation (analysis line 225) ✓
- Magnitude-peaks-early/thesis-de-risks-late (analysis line 218) ✓
- Mis-classified-character "safe compounder moves 17% in a day" gotcha (analysis line 338) ✓
- Data-error VLN ticker-collision +$93M-net gotcha (analysis line 324, claude_md line 67) ✓
- Limited-float round-trip 7×-on-1%-float gotcha (analysis line 310) ✓
- Rate-regime never-vibe-it/never-delete-it two hard stops (macro line 154, claude_md line 427-equiv R-routing) ✓
- Four-drains convergence ladder (macro line 232) ✓
- Hidden single-point-of-failure / convergence-find dual-read (discovery line 78, macro line 264) ✓
- Crowded-but-right ≠ wrong (macro line 214) ✓
- YOUR-bearishness-only-on-forward-revenue-change discriminator (macro line 289) ✓
- Priority order V7>V2>V9>V1>V3/V4>V10>V5/V6>V8 verbatim (claude_md line 194) ✓
- A>D>B>C>E question-shape tiebreak (claude_md line 220) ✓
- Strategic-incentive-floor / overflow tier-1-buys-on-open-market tell (macro line 48, line 63) ✓
- Sympathy-selloff real-vs-association split (macro line 70) ✓
- Inverse-proxy + PE-buyout-validation signal (analysis line 97) ✓
- Enabler-material TAM-is-a-floor reframe (analysis line 171) ✓
- Sanity-band against supply-shock base rates (analysis line 178) ✓
- Confidential-link A→C trap + four reconstruction sources (discovery line 28) ✓
- Transfer-from-winner 5-step + de-risk-not-cheapest cohort rank + consolidate (discovery line 35, 42) ✓
- DEDUCED/CONFIRMED discipline (discovery line 112, analysis gotcha line 302) ✓

---

## SUMMARY

- **Items genuinely dropped (need restoration):** 6 — of which **4 HIGH** (H1 objective_screen-is-not-a-verdict, H3 discovery-escalation threshold missing from discovery skill, H5 consolidated schema field-contract, H8 no_fundamental_change_selloff trigger flag) and **2 MEDIUM** (absence-evidence hand-off semantics thinned, discover-comparator output unstated).
- **Items verified PRESENT despite paranoid suspicion:** ~35 (listed above) — the drafts are high-fidelity.
- **Overall tacit-knowledge-loss severity: MEDIUM.** No catastrophic doctrine loss; the four HIGH gaps cluster on ONE theme — the **pipeline-output contract** (what the JSON surfaces, what the `objective_screen`/triage layer is, what flags trigger which analyst move). That is exactly the seam the user is redesigning, so it is the highest-leverage place to be precise. Recommend: before finalizing the pipeline schema, restore a single authoritative "judgment-substrate field + flag inventory" in CLAUDE.md's Data Contract (covering H1/H5/H8) and push the quantified discovery-escalation trigger (H3) into draft-discovery.
