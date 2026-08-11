# Serenity reproduction-eval harness

Measures whether the harness **reproduces Serenity's method** on real past cases, and turns each recurring miss into a *generalized principle* — never another case-specific rule (the per-miss-patching pattern §0 of the design-review plan names). The point is repeatability: a one-off finding that the harness "skips signature moves" is an anecdote; a number you can re-run after a doctrine edit is an instrument.

## Why this is user-triggered only

The eval reads `data/analysis_Serenity.db` — his real theses — as an **answer key**. That is exactly the N8 / `serenity-db-discipline` use: the DB is touched only on an *explicit* request to cross-validate or measure, never in routine analysis. There is no cadence and no hook that runs this. You run it deliberately, after a doctrine edit or on a periodic audit.

The split is deliberate: everything deterministic (sampling, the rubric, the report) is free and lives in `scripts/serenity_eval.py`; only the blind-run and the judge spend tokens, and that is the part you trigger.

## Read this before trusting a number

An eval is the one place in this repo where a bug does not show up as red — it shows up as a *number*, and a number gets quoted. Three things were measuring nothing until 2026-08-11, and knowing them is what makes the current output readable:

- **16% of the n=25/seed=7 draw returned empty pipeline data.** SIVE, ASHM and XFAB do not resolve at all; `APPL` is a typo for AAPL in the source post and yfinance resolves it to an unrelated mutual fund — the harness's own ticker-collision gotcha, turned on the eval. Those cases had no facts to build a `Lens:` line from and scored near-zero for reasons unrelated to doctrine quality.
- **Eleven of the twelve archetype-labeled gold theses were never sampled.** The sampler stratifies on entry-type, an axis orthogonal to archetype, so nothing guaranteed a draw contained a chokepoint case at all — while the two chokepoint-scoped rubric rows are the ones the retrospective calls the weakest-reproduced moves.
- **The judge re-decided scope on every pass.** A borderline case could flip `n/a`↔`0` between two scorings of the *identical* answer: a false regression with zero underlying change, which no increase in n removes.

`sample` now resolves every ticker, force-includes all twelve gold cases, and persists `archetype`. `report` prints an **Instrument health** block — read it first. If it says the mechanical pre-pass is unavailable or that cases are unlabeled, the numbers below it are weaker than they look.

## The four steps

```bash
PY=scripts/.venv/bin/python

# 1. SAMPLE — seeded and offline-reproducible. The twelve curated cases are force-included, then the
#    remainder is filled from the seeded draw. Each case carries a blind prompt + the hidden answer key.
$PY scripts/serenity_eval.py sample --n 25 --seed 7 > cases.json

# 2. BLIND-RUN + JUDGE — the token-spending middle. Two fidelity modes, below. Produces scored.json.

# 3. (implicit in step 2) each answer is scored against the rubric:
$PY scripts/serenity_eval.py rubric

# 4. REPORT — aggregate → markdown + a prioritized doctrine-delta list.
$PY scripts/serenity_eval.py report --results scored.json > eval-report.md
```

`sample` writes resolution answers to `scripts/eval/ticker_resolution_cache.json`, which is committed. That is what makes `--no-network` reproduce a sample on a fresh clone with yfinance down — and what stops the sample composition from depending on the network's mood that afternoon. Delete an entry to re-resolve it; entries never expire on their own, because a ticker that resolved once does not stop being a real company and an automatic refresh would reintroduce the drift the cache exists to remove.

### Step 2, mode A — workflow (fast, parallel)

```
Workflow({ scriptPath: "scripts/eval/serenity_eval_workflow.js", args: { n: 25, seed: 7 } })
```

It pipelines each case blind-run → judge and returns `{ meta: {...model}, cases: [...with .scores] }`. Write that to `scored.json`, then run step 4.

**Fidelity caveat:** a workflow `agent()` is a subagent — it reasons from CLAUDE.md + the skills but does **not** fire the `UserPromptSubmit`/`Stop` hooks. The blind-run stage therefore tells the agent to Read `./CLAUDE.md` and load the matching skill explicitly, so a change in that content actually registers in the score. This is the right mode for the four doctrine-content items (`archetype_named`, `recursive_bottom_hop`, `second_order_and_sibling`, `priced_in_decomposed`) — **no hook checks any of them**, so routing them through the expensive hooks-included mode buys exactly zero extra fidelity.

### Step 2, mode B — `claude -p` per case (full harness, incl. hooks)

```bash
$PY scripts/eval/modeb_runner.py --cases cases.json --out answers.json
```

Use this only for confirming the hook-triggered structural items still fire. Each case runs in its own throwaway git worktree so `CLAUDE_PROJECT_DIR` resolves to a private tree: mode B produces real verdicts, and CLAUDE.md's archive rule plus `verdict_gate`'s `Saved:` nudge push every one of them toward writing into the **real** `sessions/` and appending to the **real** `INDEX.md`. Parallelise for wall-clock and two runs interleave on the same index.

The runner snapshots the real `sessions/` before and after and fails loudly if anything under it changed. `--dry-run` exercises the whole isolation path without spending a token.

## Freezing a standing sample

`report` can only apply the chokepoint scope split mechanically for cases that carry an `archetype`. The twelve gold cases have one; the random remainder does not, and those cases are reported separately as scope-unstable.

The fix is not more code — it is that the standing regression sample is **inspected once by a human and frozen**, not re-drawn every run. During that pass: fill `archetype` in for each unlabeled case, and eyeball the blind prompts for the cases a regex will always lose to (rhetorical anchoring — "not X, but something like it" is a normal way to write, and the disclaim guard only catches the obvious form). Commit the result. That one fixed cost is what buys a stable in-scope N for every future audit.

## What the numbers can and cannot claim

`report` prints this on every run rather than leaving it to the reader, because the previous measurement (n=6, 72%→70%) was called a single stochastic judge flip by its own authors and still got quoted afterwards as though it meant something.

At α=0.05 two-sided and 80% power, detecting a 50%→70% shift needs ≈90 in-scope cases; 60%→90% needs ≈29; only a ≈40-point swing drops to ≈20. So per-move percentages are **suppressed below `--n-floor`** (default 12) and printed as "insufficient n" instead. What survives is real and useful: gross regressions, the pooled cross-move number as a coarse dashboard reading, and a running trend across successive edits.

## The feedback rule (the whole point)

`report` ends in a **doctrine-delta** list: every move missed in ≥2 cases. For each one, the fix is to **generalize an EXISTING principle** — name the `R#` / `V#` / `NN#` / skill-section that should already have triggered it, and widen its *trigger* or its *why*. Do **not** add a case-specific rule for the miss: that grows the spine and still won't cover the 17th case. A one-off miss is a **monitoring item**, not a delta.

## Scoring METHOD, not numbers or direction

The pipeline loads *current* market data and these theses are months old, so figures will differ from the thesis date. That is expected. The stronger version of the same rule: if the setup has since **resolved** and the harness therefore reaches a different verdict — "already re-rated, look elsewhere" — that is a **pass** on every item whose method was run properly. The eval measures whether his method was reproduced, not whether his call was right. All three blind-prompt templates are date-anchored so the question is at least asked in the world the thesis was written in.
