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
| `--n` | `8` | Number of cases |
| `--seed` | `7` | Same seed → same cases |
| `--min-len` | `400` | Minimum thesis length in characters |

Eligibility: type is `post` or `subscriber` (replies excluded), length clears `--min-len`, and a
primary ticker is resolvable.

Cases are bucketed by **entry type** — `fear_dip`, `event`, or `discovery` — via a keyword
heuristic, then drawn round-robin across buckets, preferring deeper theses and avoiding ticker
repeats. Seeding means the same seed reproduces the same cases exactly (a true before/after) while
a different seed draws a different subset of comparably deep theses (broader coverage across
rounds).

Each case carries a `blind_prompt` that reconstructs the *situation* — the ticker, the date, the
setup — with the conclusion removed, plus `thesis_text`, which is the answer key.

> The sampler's own metadata states an important honesty caveat: the DB carries no archetype
> labels, so it **cannot** stratify by archetype — naming the archetype is precisely what is being
> tested, so the harness does it, not the sampler. A skew in the entry-type distribution reflects
> the corpus, not a silent cap.

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

**Mode B — `claude -p` per case (full harness, slower):**

Blind-run each case as a fresh top-level session in the project directory, then judge. Slower and
more expensive, but it is the faithful measure — and the only valid one when a hook's behavior is
what you are checking.

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

**Scoping matters.** The two chokepoint-only items are skipped for disruption and evolution names.
A disruptor legitimately has no recursive bottom hop, and scoring it there would manufacture a
miss — inflating the apparent failure rate and pointing doctrine work at a non-problem.

### Step 4 — The report

`report` aggregates into markdown: an overall reproduction rate, a per-move table, a per-case grid,
and — the part that matters — a **doctrine deltas** section.

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

- **Small n.** Runs are typically 6–8 cases. Differences of a few percentage points are noise. The
  per-move breakdown is more informative than the headline number.
- **A judge is a model.** Scoring is an LLM comparing two texts against a rubric. It is
  reproducible in structure, not in the sense that two judges would agree perfectly.
- **The corpus is one analyst.** It measures reproduction of one method, not analytical quality in
  general.
- **It is not a backtest.** Nothing here measures whether the method makes money. No performance
  claim is made anywhere in this repository, and the eval provides no basis for one.

What it is genuinely good for: catching the specific failure where a harness produces
correctly-shaped output that skipped the moves carrying the insight. That failure is invisible to
every other check in the repository.

---

**Next:** [Troubleshooting](Troubleshooting.md) · [Known Limitations](Known-Limitations.md) ·
[Back to index](README.md)
