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

Mode-A subagents run in the **real** project directory, so the blind-run prompt carries one explicit exception to CLAUDE.md's archive rule: write no files. Without it an n=12 pass leaves twelve junk folders in the live archive and twelve `INDEX.md` lines, with parallel cases racing on the same index. Nothing is lost by it — no hooks fire in mode A, so nothing scores the `Saved:` mark, and mode B measures the archive step properly in a disposable worktree.

**Fidelity caveat:** a workflow `agent()` is a subagent — it reasons from CLAUDE.md + the skills but does **not** fire the `UserPromptSubmit`/`Stop` hooks. The blind-run stage therefore tells the agent to Read `./CLAUDE.md` and load the matching skill explicitly, so a change in that content actually registers in the score. This is the right mode for the four doctrine-content items (`archetype_named`, `recursive_bottom_hop`, `second_order_and_sibling`, `priced_in_decomposed`) — **no hook checks any of them**, so routing them through the expensive hooks-included mode buys exactly zero extra fidelity.

### Step 2, mode B — `claude -p` per case (full harness, incl. hooks)

```bash
$PY scripts/eval/modeb_runner.py --cases cases.json --out answers.json
```

Use this only for confirming the hook-triggered structural items still fire. Each case runs in its own throwaway git worktree so `CLAUDE_PROJECT_DIR` resolves to a private tree: mode B produces real verdicts, and CLAUDE.md's archive rule plus `verdict_gate`'s `Saved:` nudge push every one of them toward writing into the **real** `sessions/` and appending to the **real** `INDEX.md`. Parallelise for wall-clock and two runs interleave on the same index.

The runner snapshots the real `sessions/` before and after and fails loudly if anything under it changed. `--dry-run` exercises the whole isolation path without spending a token.

## Freezing a standing sample

`report` can only apply the chokepoint scope split mechanically for cases that carry an `archetype`. The twelve gold cases have one; the random remainder does not, and those cases are reported separately as scope-unstable.

**Why this step is not optional at large n.** Growing n buys statistical power for the four always-in-scope rubric rows and **none at all** for the two chokepoint-scoped ones: their stable in-scope N stays at the four curated chokepoint cases no matter how big the draw gets. Those two — `recursive_bottom_hop` and `second_order_and_sibling` — are the moves the harness's own retrospective calls the weakest-reproduced, which is most of what a larger n is being bought for. So an unlabelled n=100 is, for the rows that matter most, an n=4.

**The standing sample, as it exists today:**

```bash
scripts/.venv/bin/python scripts/serenity_eval.py sample --n 100 --seed 7 --only-labeled
# -> n=63, 63/63 labelled, all seven archetypes, chokepoint 17
```

**It is a census, not a seeded sample, and the `--seed` in that command does nothing to it.** 74 labelled cases exist and `--n 100` asks for more than that, so every one is taken; seeds 7, 99 and 12345 produce identical membership and differ only in ordering. That is the right shape for a regression panel — you want the same cases every time — but it means the panel supports statements about *itself*, not about the corpus. It is not a random draw from the thesis DB and cannot carry prevalence or representativeness claims. Say "the standing panel scored X", never "the harness reproduces X% of his method".

`--only-labeled` restricts the pool to cases carrying a label, and that is what makes the sample a **fixed point** rather than a moving target. Without it, excluding a non-thesis pushes the draw deeper into the pool and pulls in fresh unlabelled cases, which need another labelling round, which excludes more, which pulls in more. Measured on the first attempt: 26 exclusions caused 57 of 100 cases to come back unlabelled. With the pool restricted, the sample settles immediately and is reproducible by a command instead of by committing a blob of cases.

n=63 rather than 100 is the honest price of dropping the non-theses and the wrong-subject cases, and it is still a good trade: **chokepoint is 17**, above the `--n-floor` of 12, so the two chokepoint-scoped rubric rows report a real percentage for the first time. Those are the moves the retrospective calls weakest-reproduced, and an unlabelled n=100 would have left them at an effective n=4.

**Redoing the pass from scratch** (only needed if the DB grows or the vocabulary changes):

```bash
PY=scripts/.venv/bin/python
$PY scripts/serenity_eval.py sample --n 100 --seed 7 > cases.json       # who needs a label
# 1. label:  scripts/eval/archetype_label_workflow.js   (fan-out, one archetype per case)
# 2. triage: scripts/eval/thesis_triage_workflow.js     (which of those are theses at all)
# write both into scripts/eval/archetype_labels.json (`labels` + `excluded`), then confirm:
$PY scripts/serenity_eval.py sample --n 100 --seed 7 --only-labeled --no-network \
  | $PY -c "import json,sys; m=json.load(sys.stdin)['meta']; print(m['archetype_labeled'],'/',m['n'])"
```

**Step 3 — subject audit** (`scripts/eval/subject_audit_workflow.js`) is a separate pass again, and skipping it undoes the other two. It asks whether each case's ticker is the company its thesis *argues*, not merely one it mentions. Measured: **19% of the random cases were wrong** — a thesis arguing SIVE filed under AMD, one arguing LITE filed under GOOGL, one whose chokepoint is Macronix/Winbond filed under NVDA. Neither earlier pass caught it, and the reason is exact: the labelling pass described the THESIS (its own reasons read *"despite the AMD tag"*), and the triage asked whether the POST is a scoreable thesis. Neither ever asked whether the SUBJECT is right, so a well-argued thesis about company X tagged with company Y sailed through both. A re-subject target that does not resolve (a foreign code, an unlisted name) is EXCLUDED rather than pinned — swapping a wrong-company question for a no-data one is the same failure in a different costume.

Step 2 is not optional, and the reason is worth knowing before you skip it. The first labelling pass was told *"there is no 'unclear' option"* — so `cycle_meta` silently became the bucket for everything that is not one name's argument, and swallowed **26 posts that are not investment theses at all**: a five-ticker idea-share list of one-liners, a table of 23 tickers' daily moves whose tagged ticker is not in the table, a follower-milestone thank-you note, trade logs, research-in-progress scans. Each of those becomes an answer key for "what's your read on TICKER?", i.e. a guaranteed miss on every rubric row for reasons unrelated to the harness — and a meaningless low score is worse than a missing case, because it reads as a finding. Removing the escape hatch did not make the labels decisive; it relocated the uncertainty into the broadest bucket and made it invisible.

Also eyeball the blind prompts for the cases a regex will always lose to — rhetorical anchoring ("not X, but something like it" is a normal way to write, and the disclaim guard only catches the obvious form).

Then **commit** `archetype_labels.json`. It is frozen from that point: a label that later looks wrong is corrected *in place, by hand, with its `why` updated* — never by re-running the pass, which would move other labels too and break comparability with every run already scored against it. Re-deriving scope at judge time is what let a borderline case flip `n/a`↔`0` between two scorings of the identical answer.

## What the numbers can and cannot claim

`report` prints this on every run rather than leaving it to the reader, because the previous measurement (n=6, 72%→70%) was called a single stochastic judge flip by its own authors and still got quoted afterwards as though it meant something.

At α=0.05 two-sided and 80% power, detecting a 50%→70% shift needs ≈90 in-scope cases; 60%→90% needs ≈29; only a ≈40-point swing drops to ≈20. So per-move percentages are **suppressed below `--n-floor`** (default 12) and printed as "insufficient n" instead. What survives is real and useful: gross regressions, the pooled cross-move number as a coarse dashboard reading, and a running trend across successive edits.

## The feedback rule (the whole point)

`report` ends in a **doctrine-delta** list: every move missed in ≥2 cases. For each one, the fix is to **generalize an EXISTING principle** — name the `R#` / `V#` / `NN#` / skill-section that should already have triggered it, and widen its *trigger* or its *why*. Do **not** add a case-specific rule for the miss: that grows the spine and still won't cover the 17th case. A one-off miss is a **monitoring item**, not a delta.

## Scoring METHOD, not numbers or direction

The pipeline loads *current* market data and these theses are months old, so figures will differ from the thesis date. That is expected. The stronger version of the same rule: if the setup has since **resolved** and the harness therefore reaches a different verdict — "already re-rated, look elsewhere" — that is a **pass** on every item whose method was run properly. The eval measures whether his method was reproduced, not whether his call was right. All three blind-prompt templates are date-anchored so the question is at least asked in the world the thesis was written in.
