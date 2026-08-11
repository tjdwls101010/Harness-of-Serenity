# Eval runs

Committed output from `scripts/serenity_eval.py`. One pair of files per run under `runs/`: the markdown report, and the scored JSON it was generated from. Both are needed — the report is what you read, the JSON is what a later run gets compared against, and re-deriving the JSON means re-spending the tokens.

How to run one is in `scripts/eval/README.md`. What the numbers can and cannot claim is printed inside every report, so it travels with the artifact instead of living only here.

## What is here

| run | n | seed | model | pooled | what it is |
|---|---|---|---|---|---|
| `260811-pilot-n12-seed7` | 12 | 7 | opus | 95% | **A pilot, not a baseline.** See below. |

## The pilot is not a baseline, and the distinction matters

Phase 04's deliverable (exit criterion 6) is *a baseline* — a run whose numbers you are willing to compare a later run against. This is not that, for two reasons worth stating rather than leaving to be rediscovered:

- **Its case set is the twelve curated gold cases only**, because `--n 12` is exactly the archetype floor. That makes it maximally diverse per token and ideal for proving the wiring fires end to end, but it is not the mode-A n≈60–100 the power arithmetic in §4.8 calls for. Two rows are already suppressed as `insufficient n`, which is the instrument correctly refusing to make a claim.
- **Its blind-run prompts predate the final ones.** The data-timing note moved from the mode-A wrapper into `_blind_prompt` mid-session, so mode B would inherit it. A comparison run must be answered under identical prompts; this one would not be.

What it *does* establish: the whole path works on real cases — sampler → forced-include → blind run → judge → mechanical pre-pass → scoped aggregation → report, with the archive untouched throughout.

## What the pilot found, which is the actual return on running it

Two production bugs in `verdict_gate.py` that **no fixture covered**, both on the harness's most doctrine-central check, both found by running real answers rather than by review:

1. **A blank line after a bolded section header hid the section.** `**Downsides:**\n\n- real bullet` measured a body of `**`, failed the length bar, and nudged a correctly-formatted answer for having no Downsides block. Every existing fixture happened to be written in the tight form, so all of them passed while the shape a model actually emits was broken.
2. **The `Lens:` check read only the first occurrence.** A model that runs the lens properly routinely writes a bold header first (`**Lens: RUN, both legs —**`) or states the formula before substituting into it, and puts the arithmetic below. Measuring occurrence one scored a fully computed forked lens as "no lens run" — the same unanchored-first-match defect already fixed for section headers and never applied here.

Both are fixed, both have fixtures verified to redden when the fix is reverted, and fixing them moved this run's own numbers: pooled 91% → 95%, `lens_run` 75% → 92%, judge/hook disagreements 3 → 1.

That last part is the point. The eval's structural scores come from running the production hook, so a hook bug corrupts the measurement in the same motion that it corrupts production — and the one surviving disagreement (IQE, judge said the lens ran, the answer contains zero `Lens:` lines) is the pre-pass doing exactly what it was built for.
