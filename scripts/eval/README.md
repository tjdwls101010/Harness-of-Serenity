# Serenity reproduction-eval harness (plan §5)

Measures whether the harness **reproduces Serenity's method** on real past cases, and turns each
miss into a *generalized principle* — never another case-specific rule (the per-miss-patching病인
§0 of the design-review plan names). WF4 found the harness reproduces the framework but skips
signature moves; this makes that check repeatable instead of one-off.

## Why this is user-triggered only

The eval reads `data/analysis_Serenity.db` — his real theses — as an **answer key**. That is exactly
the N8 / `serenity-db-discipline` use: the DB is touched only on an *explicit* request to
cross-validate or measure, never in routine analysis. So there is no automatic cadence and no hook
that runs this. You run it deliberately: after a doctrine edit, or on a periodic audit.

The split is deliberate: everything deterministic (sampling, the rubric, the report) is free and
lives in `scripts/serenity_eval.py`; only the blind-run + judge spends tokens, and that is the
workflow you trigger.

## The four steps

```bash
PY=scripts/.venv/bin/python

# 1. SAMPLE — stratified, SEEDED. Same seed → same cases (a true before/after around a doctrine edit);
#    a different seed → a different subset. Each case carries a blind prompt + the hidden answer key.
$PY scripts/serenity_eval.py sample --n 8 --seed 7 > cases.json

# 2. BLIND-RUN + JUDGE — the token-spending middle. Two fidelity modes (below). Produces scored.json.

# 3. (implicit in step 2) each answer is scored against the rubric:
$PY scripts/serenity_eval.py rubric        # the signature-move checklist + the feedback rule

# 4. REPORT — aggregate → markdown + a prioritized doctrine-delta list.
$PY scripts/serenity_eval.py report --results scored.json > eval-report.md
```

### Step 2, mode A — workflow (fast, parallel)

Trigger the workflow, passing the sampler output as `args`:

```
Workflow({ scriptPath: "scripts/eval/serenity_eval_workflow.js", args: <the parsed cases.json> })
```

It pipelines each case: blind-run → judge, and returns `{ cases: [...with .scores] }`. Write that to
`scored.json`, then run step 4.

**Fidelity caveat:** a workflow `agent()` is a subagent — it reasons from CLAUDE.md + skills but does
**not** fire the `UserPromptSubmit`/`Stop` hooks (the WF4 confound). So mode A measures the
*doctrine's* reproduction, which is most of the method. The hooks are backstops whose effect (e.g. the
`Lens:` driver line) still shows up in the answer, so the judge can still see it when it's present.

### Step 2, mode B — `claude -p` per case (full harness, incl. hooks)

For a run that exercises the *entire* harness (hooks included), blind-run each case as a fresh
top-level session in the project dir, collect the answers, then judge them (a judge agent per case,
or one batched judge) against `serenity_eval.py rubric` + the case's `thesis_text`. Slower and more
tokens, but it's the faithful measure when a hook's behavior is what you're checking.

## The feedback rule (the whole point)

`report` ends in a **doctrine-delta** list: every move missed in ≥2 cases. For each one, the fix is to
**generalize an EXISTING principle** — name the `R#` / `V#` / `NN#` / skill-section that should already
have triggered it, and widen its *trigger* or its *why*. Do **not** add a case-specific rule for the
miss: that grows the spine and still won't cover the 17th case (§0). A one-off miss (1 case) is a
**monitoring item**, not a delta.

## Scoring METHOD, not numbers

The pipeline loads *current* market data, so figures will differ from the thesis date. That is
expected — the eval scores whether the harness reached the same **structural insight** and ran the
same **moves** (archetype, lens-with-arithmetic, recursive bottom hop, 2nd-order + sibling, bear +
falsifier, priced-in decomposition), not whether a number matches. That is why the rubric is
move-based and the judge is told to ignore number drift.

## Side benefit — measuring the §1/§2 dedup

Run a baseline (`--seed 7`) **before** the CLAUDE.md/skills dedup, then re-run the same seed after. A
drop in a per-move rate is salience the dedup cost; no drop means the redundancy was genuinely
redundant. This is why the plan orders the eval (§5) *before* the docs dedup (§1/§2).
