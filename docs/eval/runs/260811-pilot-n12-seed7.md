# Serenity harness — reproduction eval report

- cases: 12 | seed: 7 | model: `opus` | entry-type dist: {'fear_dip': 3, 'event': 1, 'discovery': 7}

**Pooled reproduction rate: 95%** (53/56 in-scope checks met)

Pooled across distinct moves, so it conflates them — usable as a coarse dashboard number and for spotting gross regressions, not as a claim about any single move.

## Per-move reproduction

| signature move | rate | met / in-scope |
|---|---|---|
| archetype_named | 100% | 12 / 12 |
| lens_run | 92% | 11 / 12 |
| recursive_bottom_hop | insufficient n (<12) | 3 / 4 |
| second_order_and_sibling | insufficient n (<12) | 3 / 4 |
| bear_and_falsifier | 100% | 12 / 12 |
| priced_in_decomposed | 100% | 12 / 12 |

## Instrument health

- mechanical pre-pass: 12/12 cases scored by the live hook (`verdict_gate.py --explain`), which overrides the judge on lens_run and bear_and_falsifier.
- judge/hook disagreements: **1** — IQE/lens_run: judge=1 hook=0
- archetype labels: 12/12 cases carry a fixed `archetype`, so their chokepoint scope is stable across passes.

## Per-case

| ticker | archetype | entry | archetype_named | lens_run | recursive_bottom_hop | second_order_and_sibling | bear_and_falsifier | priced_in_decomposed | note |
|---|---|---|---|---|---|---|---|---|---|
| AXTI | chokepoint | discovery | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Same structural insight, reached independently and in places deeper than the key |
| AAOI | chokepoint | discovery | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | Every signature move mechanically RUN and in places harder than the key (5-name  |
| IQE | chokepoint | discovery | ✓ | ✗ | ✓ | ✓ | ✓ | ✓ | Same structural insight (asset-value + restructuring-binary trade) reached indep |
| CPSH | chokepoint | discovery | ✓ | ✓ | ✗ | ✗ | ✓ | ✓ | Different-but-defensible: honest data-integrity gate and genuinely hard forked-l |
| SNAP | disruption | discovery | ✓ | ✓ | – | – | ✓ | ✓ | Different-but-defensible process, but it misses the thesis's actual insight — ev |
| RDDT | disruption | event | ✓ | ✓ | – | – | ✓ | ✓ | Different-but-defensible: same bullish-the-dip call and every signature move str |
| NBIS | evolution | discovery | ✓ | ✓ | – | – | ✓ | ✓ | Same structural insight reached with a different instrument — normalized peer ta |
| NBIS | evolution | discovery | ✓ | ✓ | – | – | ✓ | ✓ | Different-but-defensible route to the same core insight (NBIS is the balance-she |
| MRVL | falling_knife | fear_dip | ✓ | ✓ | – | – | ✓ | ✓ | Same structural insight, reached independently and extended past the key in plac |
| VLN | data_error | fear_dip | ✓ | ✓ | – | – | ✓ | ✓ | Different-but-defensible on direction (premise-inversion to a resolved low-float |
| EWY | macro | fear_dip | ✓ | ✓ | – | – | ✓ | ✓ | Same structural insight, independently reached — prove-the-math fear-dip on a ch |
| AEHR | cycle_meta | ranking | ✓ | ✓ | – | – | ✓ | ✓ | Same structural insight: lands AEHR on the key's exact rung (#2 — hyperscaler-qu |

## Doctrine deltas (recurring misses → GENERALIZE an existing principle)

No move was missed in ≥2 cases — no doctrine delta warranted (per-miss patching guard).

### Monitoring items — 82 one-off miss(es)

Each appeared in exactly ONE case, so none warrants a doctrine change (the per-miss-patching guard). Read them for texture, not for action.
- $smtoy never surfaced — sumitomo stays a competitor stat, the co-chokepoint's us-listed otc line is left unresolved and the comparative ranking stays in the dependent layers
- 'too early, re-enter at a dated future window for better returns' (the amkr h1-2027 move) — answer names the 8-12mo window and its late edge but converts it to a small position now rather than a dated
- 5–10% operating-margin threshold as the generalizable winners/losers rule — key names steel/basic chemicals/flat glass as the actual damaged set
- advertiser brand-safety mechanism — subreddit isolation means ad budgets rotate toward reddit during war while meta/x see pullback (would have repaired the weak take-rate gate)
- analog-transfer reasoning (inp niche telecom -> photonics bottleneck; toto fine ceramics -> memory) absent
- benchmark's own material walk-back ('amazon added alchip for additional design support while marvell retains a position') — the strongest sympathy-vs-real-damage evidence; answer substitutes jpm's reb
- blended gross-margin mix inflection — 43% automotive vs ~69% new-vertical gm re-mixing the blend above street; the answer holds 62% gm as a static input and never runs the mix math
- capacity optionality — the aixtron aix 2800g4-tm fleet is natively dual-capable gaas/inp and reconvertible at ~$0.5-1.5m/reactor; answer priced the fleet at historical cost and treated upside as pure 
- celestial ai acquisition as the structural upgrade making mrvl a real avgo competitor — never mentioned
- ceo's direct 'purchase orders in hand for the entirety of next year's forecast' — answer uses jpm's secondhand po count instead
- chain-sibling ranked is same-layer peers (mxl/smtc/indi/amba, adi-gmsl, ti-fpd-link), never cross-layer (ip/foundry <-> chip <-> tier-1 module <-> oem)
- content×volume÷mc divided by a hand-typed mc flagged unverified instead of --from-run
- …and 70 more — full list in `scored.json` under each case's `scores.missed_signature_moves`.

## What this run can and cannot claim

**How thesis age is handled:** these cases are months old and the pipeline loads current data, so a blind run can see how the setup resolved. The sampler is not biased toward recent theses — the curated gold cases are fixed and old by construction, so that option does not exist for the archetype floor. Instead the blind prompt states the data-timing gap neutrally so every case is answered under the same conditions, and the rubric scores decomposition METHOD rather than directional agreement: a harness that reaches a different verdict because the setup has since resolved passes any item whose method ran properly.

**Uncontrolled variance, named:** disclosure is not the same guard as blinding. A run that already knows how a name resolved can reason backwards from the outcome and still truthfully report that it used current data. That inflates the chain-trace and lens rows specifically, and it grows with thesis age — so it concentrates on the curated chokepoint cases, which are the oldest and the ones the archetype floor exists to protect. Treat a per-move number on those two rows as an upper bound.

**Can:** gross regressions and breaks (visible well below the power threshold); the pooled cross-move number above as a coarse dashboard reading; a running trend across successive doctrine edits, which is where this instrument earns its keep.

**Cannot:** a per-move before/after claim at this n. Any row above showing `insufficient n` is suppressed for that reason, and rows above the floor are still only reliable against swings of roughly 30-40 points. Treat a single-run per-move delta as a monitoring item, never as evidence a doctrine edit worked.
