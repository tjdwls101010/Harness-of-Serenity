# Harness of Serenity — remediation plan, 2026-08-10

**The code layer (00–03, 07) was implemented 2026-08-11. Read `08-amendments-260811.md` alongside this file** — four items below are factually wrong or unimplementable as written (02.6's premise, 02.2's numeric bar, 03.3 layer 3, 03.5's schema field), and the phases as written omit a toolchain phase without which nothing could be verified at all.

Read this file first. It carries the diagnosis, the binding constraints every downstream file inherits, and the phase order. Each phase file is self-contained enough to open alone in a fresh session; this file is what tells you which one to open.

## What this plan answers

The owner asked two questions: **did Serenity's tacit knowledge actually get into this harness**, and **do the three authoring frames — principle over rail, interface over document, dense information — hold up?**

The honest answer to the first is that **nobody can currently tell**, and the reason is measurable rather than philosophical. The reproduction eval that would answer it ran once at n=6 and its own authors recorded the result as "inside the noise floor… detects only GROSS regressions." Worse, an audit of the eval as an instrument found that 16% of its sampled tickers return empty pipeline data and that the 12 hand-curated archetype-labeled gold theses are never actually sampled. So the instrument is not merely imprecise, it is partly measuring nothing.

The answer to the second is that the frames hold up better than most harnesses achieve and are breaking in five specific, traceable ways — but a finding arrived that outranks both questions:

> **The harness's most carefully-designed reproducibility mechanism produced output matching its own schema in zero of seven real cases, and every automated check reported green.**

All seven scorecards in `sessions/260726. 반도체 인더스트리 딥리서치/` carry a `tier:` field that `serenity-scorecard.md:64` explicitly forbids ("a scorecard that carries a tier is inviting itself to rank, and it can't see the cohort"), write `archetype: Bottleneck` where the schema pins a lowercase `chokepoint` enum, use free text where `stage` is an int 1–5, and omit `type` / `session` / `date` / `data_as_of` / `mc` / `gate_strength` entirely. Meanwhile `serenity_harness.py validate` reports 15/15 green, and the committed hook-fixture suite is at 19/22 while six documentation files claim 22/22.

That reframes the whole exercise. Before asking whether the doctrine captures him, establish that the doctrine we already have is honored on the execution path and that a failure to honor it is visible. A harness whose self-check reports green while its output ignores its own schema cannot be improved by adding better doctrine — the addition would be equally unobserved.

## The five root causes

Thirty-seven findings survived adversarial verification (eleven high severity). They collapse into five mechanisms. Full detail per finding: `99-appendix-findings.md`.

| | Root cause | Findings | Phase |
|---|---|---|---|
| **RC1** | Hooks verify shape, never meaning — in all three directions: shaped-but-empty content passes, correct-but-differently-shaped content is flagged, and content that should be checked never enters the check | 9 | 02 |
| **RC2** | Nothing enforces a file's schema at write time — so sessions, scorecards, and sector-map cohorts have already drifted in the wild | 4 | 03 |
| **RC3** | The self-check verifies that things *exist*, not that they *work* — `validate` is green while the fixtures it is supposed to guard are red | 4 | 01 |
| **RC4** | Closed-list doctrine ships without a generative test — five lists where the kill-signal list's own "define the kill by this principle, not the list, so you catch the #10 that isn't enumerated" was not applied | 5 | 06 |
| **RC5** | The eval was never audited as an instrument — nine bugs, one decision: build fast, never turn the lens on the lens | 9 | 04 |

Severity concentrates in RC1, RC5 and RC3. **RC4 — the widest pattern by count, and the one that most directly answers the "principle over rail" question — contributes zero high-severity findings**, because in every case the raw evidence still reaches the model whether or not the derived flag fires. That is worth stating precisely: the closed lists are currently *annotations*, not *filters*. Any future refactor that starts filtering on them converts five low findings into five high ones at a stroke.

## Binding constraints — these govern every phase

These are not preferences. A change that violates one is wrong regardless of how well it fixes its target.

**C1 — Code loads facts; Claude judges.** No score, grade, archetype tag, regime label, or verdict may be computed in code. This is the invariant the whole harness rests on: a judgment baked into code drifts silently run-to-run, and one bad criterion among a hundred inverts a call invisibly. It binds hardest exactly where this plan adds code — the lens CLI must never accept a ticker or an archetype and must never emit valuation vocabulary (see `03-interface-layer.md`).

**C2 — Principle over rail.** Every instruction written or edited must carry a *why* strong enough that the model could re-derive the rule and handle a case the author never enumerated. Each work item in this plan therefore states **the 16th case it must survive** — the specific unenumerated situation that proves the fix generalized rather than merely patched. A fix that only appends an item to a list has failed its own test; the template for the correct form is already in `serenity-analysis/SKILL.md:214`.

**C3 — Interface over document.** Prefer expressing a rule in a signature — a CLI's argument space, a hook's input, a schema, an agent's `tools:` — over prose, *where the rule is about what is valid*. A signature is re-read for free on every use, including inside subagents that never load CLAUDE.md and after every compaction. The boundary matters as much as the opportunity: **when to reach for something, and why this project chose it, stay prose.** Moving those into a signature loses them.

**C4 — Dense information.** Every sentence must carry something a capable model could not derive from general competence. Cut restatement, argument for a claim already made, and narration of what comes next. This binds the plan's own prose and every doctrine edit it authorizes.

**C5 — CLAUDE.md is not cut for size.** Length limits are advisory. Content that genuinely belongs always-on stays, and no work item may propose deletion on length grounds. Structural and precedence work — making explicit which of two directives governs — is in scope and is the correct form of the fix. Where prose genuinely should leave CLAUDE.md, the destination is a signature (C3), which relocates rather than deletes.

**C6 — Absorption discipline for anything the corpus audit surfaces.** A move found in the corpus but missing from the doctrine is fixed by *widening the trigger or the why of an existing root or value*, naming which one should already have fired. New standalone rules are prohibited. The reason is recorded in the harness's own spec: bloat's root cause is per-miss patching, and the commit history shows four consecutive rounds of exactly that. A doctrine claim found in the doctrine but *absent* from the corpus is kept only if independently useful, and is then catalogued in the provenance layer as harness augmentation rather than his method.

## Phase order and why it is this order

The owner's original sequencing was "fix the measurement instrument first, then the doctrine." The audit's synthesis refined it: **that lock is narrower than it looks.** It protects judgment-prose changes from being made unmeasurably. It does not apply to code with its own fast verification loop — a hook fix is verified by feeding it a crafted payload and reading the output, a validator fix by running it. And there is a second reason code work loses nothing by going first: before the eval works, there is no valid before/after comparison to preserve.

```
01 Honest self-check   -> the only phase with no prerequisite; everything downstream is
                          untrustworthy until validate can go red
02 Hook contract       -> RC1; verified by fixtures, needs 01's honest baseline
03 Interface layer     -> RC2 + the approved lens CLI; code only, doctrine wiring deferred to 06
04 Measurement         -> RC5; the instrument that makes 06 verifiable
05 Corpus audit        -> answers "was his tacit knowledge captured", and supplies the real
                          gold cases 06's generalizations need
06 Doctrine            -> RC4 + salience/precedence + wiring 03's interfaces + absorbing 05's
                          findings; every change measured against 04's baseline
07 Residual checks     -> the two the owner selected from the audit's honest residual
```

Phases 01–03 are code and may run in one session or several. **04 must complete and produce a trusted baseline before any 06 work begins.** 05 should precede 06 because it supplies both the content (which principles need widening) and the verification material (real corpus cases exercising the generalization points — the reason RC4's fixes are otherwise unverifiable, since the current gold set contains no permitting-risk case, no non-neocloud funded-vs-dilution case, and no fifth-liquidity-channel case).

## What would make this worse

Three specific risks, each with the constraint that neutralizes it. These come from the audit's own synthesis and are repeated in the relevant phase files.

**Patching the hooks one regex at a time.** Each fix is cheap in isolation, which is exactly what makes the pile dangerous — and the audit caught this in miniature, since one proposed fix (an alias list for company names) is itself a closed list that will still miss a ticker's first mention. *Constraint:* before adding a bespoke pattern, ask whether the gap fits an existing structural category. If it does not, **leave it uncovered and document it as an accepted hook-layer limit.** Agree a ceiling on exception clauses beyond which a fix requires redesign rather than another clause.

**RC4 fixes landing as a literal 7th gate or a 5th drain.** Appending one more enumerated item reproduces the failure being fixed, just longer. *Constraint:* reject any RC4 draft that only appends; require the generative-sentence form, checked against the kill-signal list's wording as the template.

**The lens CLI creeping from "verify arithmetic" into "characterize the result."** A subcommand-per-driver CLI is precisely the shape that accretes a "which lens applies here" convenience feature, at which point judgment has moved into code. *Constraint:* the argument surface never accepts a ticker or an archetype, and the output never contains valuation vocabulary — enforced by a fixture, the way the harness already enforces its other seam invariants.

## Files

| File | Phase | Prerequisite |
|---|---|---|
| `01-honest-self-check.md` | make `validate` capable of going red | none |
| `02-hook-contract.md` | RC1 — the shape/meaning gaps, both directions | 01 |
| `03-interface-layer.md` | RC2 + lens CLI + generators (code only) | 01 |
| `04-measurement-instrument.md` | RC5 — a baseline whose numbers mean something | 01 |
| `05-corpus-audit.md` | 1,792 posts → move inventory → A/B/C + provenance | 04 (recommended) |
| `06-doctrine.md` | RC4 + salience + interface wiring + 05's absorptions | 04 and 05 |
| `07-residual-checks.md` | filings-subagent compliance; prose-growth tripwire | 01 |
| `99-appendix-findings.md` | all 37 verified findings, verbatim | — |
| `08-amendments-260811.md` | **READ WITH THIS.** Where implementation found the plan wrong or unimplementable | — |
