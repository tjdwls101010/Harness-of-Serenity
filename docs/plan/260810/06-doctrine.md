# Phase 06 — doctrine: close the rails, fix precedence, wire the interfaces

**Prerequisites:** Phase 04 must have produced a trusted baseline. Phase 05 should have run, because it supplies both the content (which principles need widening) and the verification material (real corpus cases exercising the generalization points).

**This is the only gated phase.** Everything before it is code with its own fast verification loop. These are judgment-prose changes, which is exactly the class the "fix the instrument first" decision exists to protect — a doctrine edit made without measurement is a guess that looks like progress.

**Every edit in this phase inherits C2, C4 and C5:** carry a re-derivable why, cut anything a capable model already knows, and never delete for length.

Findings covered: F03, F05, F06, F25, F26, F28, F01/F02 (as sets), plus the wiring deferred from Phase 03 and the absorptions from Phase 05.

---

## The RC4 rule — read before writing any of 6.1

Five closed lists ship without a generative test. The template for the correct form already exists two lines from one of them, in `serenity-analysis/SKILL.md:214`:

> **The 9 kill signals (+ the principle that spots a 10th)** … Define the kill by this PRINCIPLE, not the list, so you catch the #10 that isn't enumerated.

That is the only list in the harness that teaches its own extension. Every fix below must reach that form.

**Reject any draft that only appends an item.** A seventh gate, a fifth drain, a broadened-but-still-closed region set — each reproduces the exact failure being fixed, just longer, and it will feel like progress because the specific case that prompted it is now covered. The test is not "is the new case covered," it is "would the model handle the case *after* the new one." Check every draft against the kill-signal wording as the literal template.

**Why these are low-severity today, and the condition that changes that.** In all five cases the raw evidence still reaches the model regardless of whether the derived flag fires — the full `company_relationships` prose passes through whether or not a Mag7 name matched, and the full geographic breakdown is emitted whether or not a region matched. That property is incidental, not designed as a backstop. **Any future change that starts *filtering* on these flags rather than merely *annotating* converts five low findings into five high ones at once.** Write that down where a future editor will hit it.

## 6.1 — The five closed lists

**The six winner gates** (`serenity-analysis/SKILL.md:66-77`) are stated as "clears ALL six" with no extension principle. A domestic HALEU or rare-earth-separation name can clear all six cleanly — it monetizes, has pricing power, a strong balance sheet, TAM headroom, allocation control, broad demand — then have its NRC license stall for years and never ramp. Gate 3 is explicitly *balance-sheet* survival. Fold the regulatory pathway into gate 3 ("can the balance sheet **and the regulatory pathway** last to monetization?") **and** add the generative disclaimer. The disclaimer is the part that matters; the permitting clause is one instance.

**Gate-3's funded-versus-dilution checks** (`:53-62`) sit under a header reading "This is R4 at the neocloud," in GPU and hyperscaler vocabulary throughout. An SMR developer or a gigafactory funding construction off a live at-market ATM while touting a strategic MOU is structurally the identical pattern. The general principle is restated in domain-neutral form elsewhere (CLAUDE.md's R4, and the preceding paragraph in the same skill), so *some* scrutiny would still apply — what is genuinely at risk of non-transfer is the two granular follow-on traps (the tranche carve-out doesn't launder dilution; a silent filing is not a funded confirmation), which have no neutral restatement anywhere. Reframe the header to name the general case first with the neocloud as the worked instance, and de-sector the traps ("the GPU leg" → "the funded leg").

**The four-drain liquidity ladder** (`serenity-macro/SKILL.md:140`) counts named channels, so a regional-banking failure alongside AI credit stress reads as "one channel firing → normal posture" when two independent doors are open. State the generative test: any channel pulling risk capital out through a mechanism distinct from those already firing counts toward the ladder; the four named are the recurring instances, not the ceiling.

**`_MAG7_NAMES`** contains six companies; Tesla is absent, so a battery-materials or custom-silicon supplier disclosing a multi-year Tesla agreement never trips the flag whose stated purpose is surfacing exactly that. Add it, and derive membership from one dated source-of-truth constant so the next membership question does not drift silently.

**`_HIGH_RISK_REGIONS`** contains only Taiwan / China / Hong Kong, and folds two mechanically different risks into one undifferentiated signal — Taiwan is invasion and supply-disruption risk, China is export-control-target risk. A name with 40% Russia revenue never fires at any exposure level. Either track a sourced list, or split into two separately-labelled flags so the signal's meaning travels with it.

## 6.2 — Precedence and routing, without deleting anything (C5)

Three places where two directives can both claim a turn and nothing says which wins. The harness states two precedence chains explicitly and tersely (`V7 > V2 > V9 > …` and `A > D > B > C > E`); these three deserve the same treatment in the same form.

**The three routing reflexes have no firing order.** *"AAOI's ripping to new highs, but with the Taiwan situation heating up, is this too extended to add?"* trips all three at once: (a) price-extreme → run the bearish fade first; (b) countable-end-unit → run `discover` before quoting the subject's own multiple; (c) a known ticker with an active-conflict date → this is an event, run the catalyst test before the single-name read. Each claims priority over the normal B-type read; none states its position relative to the other two. Append the order in the same terse form — resolve whether it is fundamentally an event first, since that determines whether a bearish frame is warranted at all; then the fade; then let the comparator feed the valuation step it already governs.

**The `discover` comparator is placed in two contradictory positions.** CLAUDE.md's reflex (b) requires the comparator table *before* the subject's own multiple is quoted; `serenity-analysis` §6 ties the identical `discover` call to the closing paragraph, *after* Rating. Followed literally, the valuation section quotes the standalone multiple, the rating prints, and the comparator arrives after the verdict it was supposed to author. Make one document own the placement — CLAUDE.md, since it is always loaded and the routing-reflex framing already marks it as pre-empting template order — and rewrite the skill's closing line to be a callback to a ranking that already ran, not a fresh instruction.

**Check 6 is the only pre-answer check with no pointer, no downstream verification, and its worked technique in a skill B-type questions never load.** Non-negotiables 9 and 10 each close with "mechanics live in serenity-analysis §X." Check 6 closes with nothing — and its actual operating procedure (the three-test recursive-hop stopping rule) lives in `serenity-discovery`, which the funnel explicitly frames as the *finding* skill for when you don't have a ticker yet. A bare-ticker question loads `analyze` plus `serenity-analysis` and never sees it. Meanwhile the Stop hook structurally re-checks four other contract items and has no equivalent here. That routing gap is a candidate explanation for the baseline's finding that recursive-bottom-hop and second-order are the weakest-reproduced moves — and it is now testable, which is the point of doing this after Phase 04.

Three parts, all additive: give check 6 the same pointer form its siblings have; add a cross-reference in `serenity-analysis` §1 near gate 5 (allocation control is check 6's second-order content in substance but currently uncredited as such), so the skill a B-type question *does* load carries the depth; and consider extending `verdict_gate` with one more presence-only check — on a chokepoint-scoped answer, flag when no token names a sub-layer beneath the headline node. Weigh that last one against Phase 02's ceiling rule before adding it.

## 6.3 — Wire the Phase 03 interfaces

The tools exist by now; this is the prose that makes them reachable. Keep each pointer to what C3 says prose is for — **when to reach for it and why**, never a restatement of the argument space, which the signature already carries and carries better.

- **The lens CLI** — where the doctrine names the driver list, point at the subcommand space instead of re-enumerating it, and say plainly that the `custom` escape hatch is the supported path for a driver nobody has named. That sentence is what converts the list from a rail to a principle; without it the CLI is just a shorter rail.
- **`new-session`** — one line in the session-archive convention. The convention text stays (it explains *why* the archive exists and why numbers expire); the naming mechanics move to the generator.
- **`scorecard-lint`** — the scorecard agent's own final step self-invokes it before returning, and the Rank-N protocol's Step 1 inlines the field list rather than pointing at the agent file, since the inline-fill path is precisely the one that never loads that file.
- **`serenity_sectormap.py`**, if Phase 03 adopted it — a pointer from CLAUDE.md's type-D bullet and/or `serenity-discovery`'s chain-tracing section.

## 6.4 — Absorb Phase 05's bucket B

Per C6, and per the budget set in Phase 05. Each absorption names the existing root or value whose trigger or why is being widened, and what it now covers that it didn't. No standalone additions except where genuinely nothing should have fired.

---

## Measurement protocol

**Baseline before, re-run after, per change group** — not once at the end of the phase, or a regression in one group hides behind an improvement in another.

And respect what Phase 04.8 established the instrument can honestly claim: gross regressions, a pooled cross-move aggregate, and a trend across edits. **A per-move before/after at achievable n is not a claim this eval supports.** A change whose only evidence is a single per-move percentage moving has not been validated — say so and rely on the judgment, rather than dressing the judgment in a number.

Record each change group's before/after in `harness-spec.md`'s change history, including the ones that showed no measurable effect. A doctrine edit that made no difference is the most useful data this project can collect, because it is the only direct evidence about where the harness is already saturated — and the current spec's honest record of "72% → 70%, inside the noise floor" is the model to follow.

## Exit criteria

1. Every RC4 fix carries a generative sentence, checked against the kill-signal template. No draft that only appends survives review.
2. The three precedence gaps are resolved in the terse form the harness already uses, with no content deleted.
3. Every Phase 03 interface has exactly one doctrine pointer, saying when and why rather than restating the signature.
4. Bucket-B absorptions each name the widened principle; the count is within the Phase 05 budget.
5. Before/after recorded per change group, including nulls.
6. `harness-spec.md` reflects the harness as it now is — the drift this plan repeatedly found starts with a spec that stopped being updated in the same pass.
