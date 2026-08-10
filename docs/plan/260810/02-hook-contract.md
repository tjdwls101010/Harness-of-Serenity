# Phase 02 — the hook contract: close the shape/meaning gaps in both directions

**Prerequisite:** Phase 01 (every fix here is verified against the fixture suite, which must be honest first).

**The root cause, stated once:** `verdict_gate.py` and `evidence_discipline.py` are, by their own docstrings, structural pattern-matchers over the final message string. That choice is *correct* — a Stop hook cannot judge whether an argument is right, and a hook that tried would be judgment in code (C1). But structural checking has three symmetric failure directions, and all three are live:

- **shaped-but-empty passes** — content that matches the pattern regardless of what it says;
- **correct-but-differently-shaped is flagged** — a genuine answer nagged for notation;
- **never enters the check** — trigger vocabulary too narrow to see the answer at all.

The third is the worst, because it is silent on both sides: the model isn't told, and the developer sees a green hook.

Findings covered: F08 (also touched in Phase 03), F12, F13, F14, F17, F18, F19, F20, F04-lens-regex.

---

## The ceiling rule — read before writing any regex

This phase's failure mode is a pile of cheap patches. The audit demonstrated it in miniature: one proposed fix (seed the regex with a company-name alias list) is *itself* a closed list that still misses a ticker's first-ever mention. Adding it would have converted an RC1 finding into an RC4 finding.

So: **before adding a bespoke pattern, ask whether the gap fits an existing structural category** — a marker (a token that must be present), a label (a section header whose body must be non-trivial), or a threshold (a magnitude that changes severity). If it fits, extend that category. If it does not — if the honest fix would require part-of-speech tagging, or semantic judgment, or an unbounded name list — **leave it uncovered and write it down as an accepted hook-layer limit** in the hook's docstring.

An accepted, documented limit is strictly better than a clause that appears to cover the case and doesn't, because the limit tells a future reader where the guarantee ends. Agree a ceiling now (a small number of exception clauses per hook) past which a fix requires redesign rather than another clause.

---

## 2.1 — Stop gating the entire contract on one literal token

`verdict_gate.py:52-54` returns early unless the message contains `TLDR`/`TL;DR`. Verified: a message reading *"Bottom line: … PT $250, 12 months, LEAPS as the vehicle. Rating: overweight, high conviction. $NVDA is the name."* — cashtag, price target, vehicle, rating, priced-in language, zero NFI/NFA — produces **empty output**. No hard block, no soft nudge, nothing. Every downstream check is dead behind that one `if`.

Enter the gate on `finance_signal OR the TLDR token`, and make TLDR-presence its own independent soft requirement. `finance_signal` is already computed further down the same function; this is a reordering, not new detection.

**The 16th case:** any opener that isn't the literal token — "Quick take:", "Short version:", a Korean equivalent, or an answer that simply forgets. The contract must not depend on the model remembering the one word that turns the contract on.

## 2.2 — Close the label-as-content loophole

Verified end-to-end, with a real archive folder so even the `Saved:` branch cleared: a message containing `Downsides: none that matter` / `Falsifier: can't think of one, pretty confident honestly` / `Lens: EV/Rev N/A × N/A ÷ N/A = still good` produces **completely silent output**. The word "Falsifier" contains `falsif`; `Downsides:` matches `\bDownside`; the Lens line has an operator and an `=`. Every check is satisfied by the label while the body explicitly negates it.

This is the deepest risk in the whole hook layer, because a structural check teaches the model to produce the structure. Left alone, the gate actively trains compliance tokens.

The fix stays structural, no semantics: reject a `Downsides:`/`Falsifier:` line whose remainder after the label is below a minimum length or matches an explicit null-set (`none`, `n/a`, `없음`, `can't think of`), and reject a `Lens:` line whose operands are placeholders rather than numbers. Requiring the operands to be numeric is the sharper of the two — it is checkable, unambiguous, and it is what "the arithmetic ran" actually means.

**The 16th case:** a legitimately empty bear case. It exists — a clean-kill verdict can genuinely have no upside leg. Handle it by requiring the model to *say why* it is empty rather than by accepting a bare "none": a one-clause reason clears the length bar and is exactly the content the check should be buying.

## 2.3 — Accept `/` as division in the `Lens:` marker

`lens_marker` requires one of `×÷*` between `Lens:` and `=`. A correctly-run asset-value-turnaround lens — `Lens: replacement-cost-per-unit — $4.2B rebuild cost / 12 reactors = $350M per reactor vs $280M peer comp` — contains only `/` and gets nagged. The doctrine writes this driver with a slash in CLAUDE.md's own non-negotiable #10 (`replacement-cost/unit`), and the voice mandate makes `/` far more natural than `÷`. The hook is flagging its own notation.

Accept a bare `/` flanked by numeric or currency tokens, preserving the exclusion for ratio *names* (`EV/Rev`). If that distinction proves fragile, prefer over-accepting: a soft nudge that under-fires once on a genuine top-down answer is far cheaper than one that misfires on correct arithmetic, because the second teaches the reader to ignore the hook.

**The 16th case:** the additive lens. Sum-of-parts — a stake value **plus** an operating value against parent MC — is doctrine (`serenity-analysis` §2, "Sum-of-parts / hidden-stake unlock") and has no multiply or divide at all. Any operator list will keep snapping. The durable fix is Phase 03's lens CLI emitting the line itself; until then, add `+`/`−` and accept that the marker checks "an arithmetic expression is present," not "a specific operator is present."

## 2.4 — Fix the false fires, each in its own category

Four verified false fires. Group them so the fix is one decision each, not four patches.

**A dev/coding answer citing a real cashtag hard-blocks.** *"TL;DR: fixed the verdict_gate cashtag regex so a `$NVDA`-style example now round-trips through the new fixture"* returns `decision: block` demanding a financial disclaimer. `evidence_discipline.py` already solved this with its `_META` guard; port that concept into `verdict_gate.py` so the cashtag-only path of `finance_signal` is suppressed when the message carries obvious dev context and no other finance signal is present.

**`evidence_discipline`'s dev suppression is defeated by its own override vocabulary.** *"refactor how `serenity_pipeline.py` computes the valuation multiples so PEG doesn't divide by zero"* fires the full pipeline-first reminder. `_MARKET_ANCHOR` treats `valuation` / `earnings` / `dividend` / `PT` as proof of a market ask, but those are field names the pipeline *fetches* — they appear in every prompt about the pipeline's code. Drop pure field names from the override; require a cashtag or a Korean market phrase, so the override means "there is also a concrete market ask here," not "this prompt names a field."

**The Lens nudge fires on macro-only calls naming no company.** *"regime reads risk-on … overweight semis, underweight defensives"* is asked for a single-company driver computation. Gate the Lens nudge on `single_name`, not the broader `valuation_verdict`.

**A verdict with no cashtag and no listed vocabulary is invisible to both hooks.** *"should I load up on Nvidia here?"* → no input nudge; the reply *"TLDR: Nvidia is a screaming buy right now … I'd load up here"* → no output gate. This is the one to leave uncovered per the ceiling rule: catching it honestly needs proper-noun-plus-verb detection, and any alias list will miss the first mention of a name. **Document it in the hook docstring as a known limit** and note the compensating control — CLAUDE.md is always loaded, so the doctrine is in context whether or not the hook fires.

**The 16th case for the whole group:** the harness's own development. This repo talks about tickers, valuation, and dilution constantly *as subject matter*. Any hook that cannot distinguish talking about a market from making a market call will be trained away by its own false fires.

## 2.5 — Give `data_integrity_guard` magnitude tiering and one cash field

Verified against a live `analyze MU`: `key_facts.totalRevenue` = $90.27B versus `fundamental_inputs.debt_and_cash.total_revenue` = $37.38B — a 142% gap — logged at exactly the same severity as AAPL's benign 12% gap in the same session. Micron's real scale matches the $37B figure and the $82.8B total-assets line in the same payload, so the larger number is implausible on its face. A gap that size is no longer a denominator-choice question; it is the ticker-collision / stale-figure class the doctrine calls "itself the mispricing."

Give check #6 the magnitude tiering check #1 already has. Separately, checks #5 and #7 draw "cash" from two different pipeline fields that diverged by $26.5B on AAPL and $16.4B on MU in the same run — both stayed under threshold by coincidence of scale, not by reconciliation. Pick one field consistently, or diff the two against each other the way check #6 already diffs the two revenue fields.

**The 16th case:** the small-cap where a 142% gap is *not* obvious from scale. Tiering by magnitude is the generalization; naming Micron is the example.

## 2.6 — Extract the structural checks into one shared module

`serenity_eval.py:59-66` and `:79-83` reimplement the `Lens:` and Downsides/falsifier checks that `verdict_gate.py:96-146` already performs, with different bars. The eval's judge can score `lens_run = 1` on an answer that would fail the live hook, so the measured reproduction rate can diverge from what a real user actually gets.

Pull `lens_marker`, the Downsides/falsifier detection, and the bear-leg/bull-leg detection into a small module imported by both. This pays down RC1 and RC5 at once and is a prerequisite for Phase 04's deterministic pre-pass, so it is best done here rather than there.

**The 16th case:** any future check added to one and forgotten in the other. One definition, two consumers, is the structural answer.

---

## Exit criteria

1. A fixture exists for **every** verified failure above — each one written as a stdin payload under `.claude/hooks/tests/`, with the expected outcome recorded. The suite goes from 22 to roughly 32–35 fixtures. Every payload in this file was verified by direct execution; reuse the exact strings.
2. `run_fixtures.py` green, `validate` green, and both observed going red when a fix is reverted.
3. The shared structural module exists and `verdict_gate.py` imports it, with no duplicated regex remaining in `serenity_eval.py`.
4. Each accepted limit is written in the relevant hook's docstring, naming what it does not catch and why the honest fix was declined.
