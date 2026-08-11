# Eval Harness

Measuring whether the harness actually reproduces the method — not whether it produces
well-formatted output, and emphatically not whether the method makes money.

## The question it answers

Everything in [Testing and Validation](Testing-and-Validation.md) checks structure: does the
pipeline emit the right keys, do the hooks fire on the right inputs, does judgment stay out of the
data layer. All of it can pass while the harness quietly fails at its actual job.

The failure mode that motivated this: an earlier review found the harness reproducing the
*framework* — the right sections, the right vocabulary, the right shape — while skipping the
signature moves that carry the insight. It named the archetype. It did not trace the chain to its
recursive bottom hop. The output looked right and was analytically hollow.

That is invisible to a structural test, because a hollow answer and a good one have identical
structure. So the eval asks a different question:

> Given only the situation an analyst faced — with their conclusion withheld — does the harness
> reach the same **structural insight**, by running the same **moves**?

## The deliberate design constraints

Three choices shape the whole thing.

**It grades moves, not numbers.** The pipeline loads *current* market data, so figures from a run
today will not match a thesis written eight months ago. That drift is expected and the judge is
explicitly told to ignore it. What is scored is whether the same analytical operations ran.

**It is user-triggered only.** No hook runs it, no cadence schedules it. It reads the thesis DB as
an answer key, which is fenced behind an explicit cross-validation request — see
[Concepts](Concepts.md#the-thesis-db). Automating it would violate the rule that makes the
measurement meaningful.

**The expensive part is isolated.** Sampling, the rubric, and reporting are pure Python — no
tokens, no network, no model. Only the blind-run and judging middle spends anything. You can
inspect exactly what will be measured before paying for a run.

## The four steps

```bash
PY=scripts/.venv/bin/python

# 1. SAMPLE — seeded, stratified, free
$PY scripts/serenity_eval.py sample --n 8 --seed 7 > cases.json

# 2. BLIND RUN + JUDGE — the only step that spends tokens
#    (mode A or B below) → scored.json

# 3. RUBRIC — inspect what the judge scores against
$PY scripts/serenity_eval.py rubric

# 4. REPORT — aggregate, free
$PY scripts/serenity_eval.py report --results scored.json > eval-report.md
```

### Step 1 — Sampling

`sample` draws a stratified, seeded sample from the thesis DB.

| Flag | Default | Effect |
| --- | --- | --- |
| `--n` | `8` | Number of cases (the twelve gold cases are a floor, not part of the count) |
| `--seed` | `7` | Same seed → same cases |
| `--min-len` | `400` | Minimum thesis length in characters |
| `--gold` | `scripts/eval/gold_set.json` | The curated, archetype-labeled cases force-included first |
| `--no-gold` | off | Random draw only — leaves the sample archetype-blind |
| `--resolution-cache` | `scripts/eval/ticker_resolution_cache.json` | Committed cache of resolution answers |
| `--no-network` | off | Resolve from the cache only; a miss drops the candidate and is reported |

Sampling happens in two passes. **The twelve curated gold cases are force-included first**, then
the remainder of `--n` is filled from the seeded random draw. That ordering is what guarantees an
archetype floor: the DB carries no archetype labels for the general pool, so the random half cannot
be stratified on that axis, and before the floor existed only one of the twelve ever appeared in an
n=25 draw — leaving the two chokepoint-scoped rubric rows with an in-scope N of whatever chance
supplied.

For the random remainder, eligibility is: type `post` or `subscriber` (replies excluded), length
clears `--min-len`, a primary ticker exists, the thesis does not *disclaim* that ticker, and the
ticker **resolves** to a real security. Resolution is `marketCap` or `sector` non-null, plus an
explicit ETF branch — both fields are null for an ETF by construction, so the naive predicate would
reject every one. Gold cases bypass the gate entirely; it exists to keep unresolvable garbage out
of the random draw, not to second-guess a hand-picked case.

Candidates are then bucketed by **entry type** — `fear_dip`, `event`, `discovery`, `ranking` — via
a keyword heuristic, drawn round-robin, preferring deeper theses and avoiding ticker repeats. Gold
cases pin their own `entry_type` where the heuristic mis-frames them, because that field selects
the prompt template and therefore decides what question each case actually asks.

Each case carries a `blind_prompt` reconstructing the *situation* — ticker, date, setup — with the
conclusion removed, plus the answer key: `thesis_text`, and for a gold case `archetype`,
`gold_label` and `gold_tests`. **All of those go to the judge only.** A leak into `blind_prompt`
would fail nothing; it would quietly inflate every score, which is why it is asserted per case in
`scripts/tests/test_serenity_eval.py`.

`archetype` is persisted at sample time rather than re-derived by the judge each pass. That is what
stops a borderline case from flipping `n/a`↔`0` between two scorings of the *identical* answer — a
false regression with zero underlying change, which no increase in n removes.

> Resolution answers are cached to a committed file. That is what makes a sample reproducible on a
> fresh clone with the network down, and what stops its composition from depending on yfinance's
> mood that afternoon. Entries never expire on their own: a ticker that resolved once does not stop
> being a real company, and an automatic refresh would reintroduce the drift the cache removes.

### Step 2 — Blind run and judge

Two modes, trading fidelity against speed.

**Mode A — the workflow (parallel, faster):**

```
Workflow({ scriptPath: "scripts/eval/serenity_eval_workflow.js", args: { n: 8, seed: 7 } })
```

Each case runs through a two-stage pipeline. Stage one gives an agent only the `blind_prompt` and
instructs it to read `CLAUDE.md`, identify the question type, load the matching skill, run
`serenity_pipeline.py analyze <TICKER>`, and answer in full form. Stage two hands a judge the
rubric, the hidden `thesis_text`, and the stage-one answer, and requires a structured score.

**Fidelity caveat:** a workflow agent is a subagent, so the `UserPromptSubmit` and `Stop` hooks do
**not** fire. Stage one compensates by explicitly instructing the agent to read `CLAUDE.md` and
load the skill — but that is a reconstruction of what the hooks would have injected, not the real
thing.

That caveat costs less than it appears to. **No hook checks archetype naming, chain depth,
second-order actors, or priced-in decomposition** — `verdict_gate` touches only the `Lens:` token,
the Downsides/falsifier phrasing, and the `Saved:` mark. So routing those four doctrine items
through the expensive hooks-included mode buys zero extra fidelity, which is the whole argument for
running mode A at high n and mode B at low n rather than one uniform pass.

**Mode B — `claude -p` per case (full harness, slower):**

```bash
scripts/.venv/bin/python scripts/eval/modeb_runner.py --cases cases.json --out answers.json
```

Each case runs in its own throwaway git worktree with `CLAUDE_PROJECT_DIR` pointed at it. That
isolation is not optional: mode B produces real verdicts, and CLAUDE.md's archive rule plus
`verdict_gate`'s `Saved:` nudge push every one of them toward writing into the **real** `sessions/`
and appending to the **real** `INDEX.md`. Parallelise for wall-clock and two runs interleave on the
same index. The runner snapshots the real `sessions/` before and after and fails loudly if anything
under it changed; `--dry-run` exercises the entire isolation path without spending a token.

> A bare worktree is not enough. `scripts/.venv` is gitignored with zero tracked files, so a
> worktree has no interpreter and every `analyze` call inside it fails — producing answers built on
> no data at all. The runner symlinks the venv, and verifies it by *executing* the interpreter
> inside the worktree rather than checking that the link exists.

### Step 3 — The rubric

Eight items, defined once in `scripts/serenity_eval.py` and mirrored exactly in the workflow's
schema so `report` can aggregate either.

| Item | Scope | Measures |
| --- | --- | --- |
| `archetype_named` | all | Named the archetype off the name's own economics, without escaping to a softer lens than it earns |
| `lens_run` | all | The valuation lens was **run** — driver arithmetic shown, each input traced, both legs if forked. *A named-but-not-run lens, or a bare top-down multiple, scores 0.* |
| `recursive_bottom_hop` | chokepoint only | Traced the chain to the true scarce substep beneath the headline node |
| `second_order_and_sibling` | chokepoint only | Surfaced a second-order allocation effect **and** ranked a chain sibling |
| `bear_and_falsifier` | all | Explicit bear case **and** a falsifier |
| `priced_in_decomposed` | all | Decomposed what is versus is not priced in — not a restatement of consensus multiples |
| `missed_signature_moves` | free text | Moves the answer key used that the harness missed |
| `notes` | free text | Same structural insight / weaker version / different but defensible |

Scoring is 1, 0, or `n/a`; the reproduction rate is the mean of in-scope binary items with `n/a`
excluded.

**Scoping matters, and it is not the judge's call.** The two chokepoint-only items are skipped for
disruption and evolution names — a disruptor legitimately has no recursive bottom hop, and scoring
it there manufactures a miss, inflating the failure rate and pointing doctrine work at a
non-problem. `report` applies that split **mechanically** from each case's persisted `archetype`.
The judge is told explicitly not to re-derive it, because a judge re-deciding scope from
unstructured text on every pass is how the identical answer scored differently twice.

**Two items are scored by the production hook, not by the judge.** `lens_run` and
`bear_and_falsifier` are exactly what `verdict_gate` already checks, so `report` runs the live hook
over each answer via `verdict_gate.py --explain` and lets its verdict override the judge's. A judge
can score `lens_run = 1` on an answer the real hook would have blocked; that measures the judge.
Sharing the hook itself — rather than extracting its patterns into a module both sides import —
means the two cannot drift, and the hook's own fixture suite regression-covers the eval's oracle for
free. Where the hook returns `null` for a check it did not apply (a macro-only answer names no
company to run a driver line on), that maps to `n/a`, never to 0.

### Step 4 — The report

`report` aggregates into markdown: a pooled reproduction rate, a per-move table, an **instrument
health** block, a per-case grid, a **doctrine deltas** section, and a plain statement of what the
run can and cannot claim.

| Flag | Default | Effect |
| --- | --- | --- |
| `--n-floor` | `12` | Below this many in-scope cases, print "insufficient n" instead of a percentage |
| `--no-hook` | off | Skip the mechanical pre-pass and use judge scores for the two hook-owned items |

**Read the instrument-health block first.** It reports how many cases the live hook actually scored,
how often the hook and the judge disagreed, and how many cases lack an archetype label. If it says
the mechanical pre-pass is *unavailable*, every number below it is a weaker measurement than the
report normally makes — a `verdict_gate.py` predating `--explain` ignores argv and prints ordinary
hook output, which is valid JSON, so the contract's own key is demanded rather than a successful
parse.

## The feedback rule

This is the most transferable idea in the project, and it is enforced by the report's structure
rather than left to discipline:

> For every **recurring** miss (a move dropped in ≥ 2 cases), the fix is to **generalize an
> existing principle** — name the root, value, or skill section that should already have covered
> it, and widen its trigger or sharpen its rationale. Do **not** add a case-specific rule. A
> one-off miss is a monitoring item, not a change.

The reasoning: patching per miss is how a methodology document bloats without improving. Each
patch covers the case that prompted it and not the next one, and after enough of them the document
is long enough that nothing in it is salient. Generalization keeps the document the same size while
extending its reach.

So the report separates recurring misses (which warrant a doctrine change) from one-off misses
(which explicitly do not), and says so:

> *"No move was missed in ≥2 cases — no doctrine delta warranted (per-miss patching guard)."*

## Using it to check a doctrine change

The eval doubles as a regression test on the methodology itself. Run the same seed before and
after an edit:

```bash
$PY scripts/serenity_eval.py sample --n 8 --seed 7 > cases.json
# ... run and score, both before and after the doctrine change ...
$PY scripts/serenity_eval.py report --results scored_before.json
$PY scripts/serenity_eval.py report --results scored_after.json
```

A drop in a per-move rate after a deduplication edit means the removed text was carrying salience,
not redundancy. No drop means the redundancy was genuinely redundant.

The design record contains a worked example: a documentation consolidation measured 72% before and
70% after — inside the noise floor at n = 6, and recorded as such rather than claimed as an
improvement or a regression.

## Interpreting a number

Some honesty about what a reproduction rate is and is not.

- **The n you need is larger than the n you will run.** At α = 0.05 two-sided and 80% power,
  detecting a 50%→70% shift needs ≈90 in-scope cases; 60%→90% needs ≈29; only a ≈40-point swing
  drops to ≈20. This is why per-move percentages are suppressed below `--n-floor` and why the
  report states its own limits on every run: the previous measurement (n=6, 72%→70%) was called a
  single stochastic judge flip by its own authors and still got quoted afterwards.
- **A judge is a model.** Scoring is an LLM comparing two texts against a rubric. It is
  reproducible in structure, not in the sense that two judges would agree perfectly — which is why
  the two items a deterministic hook can score are taken away from the judge entirely, and why the
  hook/judge disagreement count is printed rather than hidden.
- **The corpus is one analyst.** It measures reproduction of one method, not analytical quality in
  general.
- **It measures method, not direction.** These theses are months old and the pipeline loads current
  data. If a setup has since resolved and the harness therefore reaches a *different* verdict, that
  is a pass on every item whose method ran properly.
- **It is not a backtest.** Nothing here measures whether the method makes money. No performance
  claim is made anywhere in this repository, and the eval provides no basis for one.

What the design *can* claim, stated plainly because the report prints it too: gross regressions,
the pooled cross-move number as a coarse dashboard reading, and a running trend across successive
doctrine edits. A per-move before/after at any n this instrument will realistically run is not on
that list.

What it is genuinely good for: catching the specific failure where a harness produces
correctly-shaped output that skipped the moves carrying the insight. That failure is invisible to
every other check in the repository.

---

**Next:** [Troubleshooting](Troubleshooting.md) · [Known Limitations](Known-Limitations.md) ·
[Back to index](README.md)
