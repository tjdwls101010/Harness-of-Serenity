# Phase 04 — the measurement instrument

**Prerequisite:** Phase 01; Phase 02.6 (the shared structural module) should land first, since the deterministic pre-pass imports it.

**Why this phase exists:** the owner's first question — did his tacit knowledge get captured? — is answerable only by measurement, and the current instrument cannot answer it. The one recorded run (n=6, seed 7, 72% → 70%) was described by its own authors as inside the noise floor. The audit found that the problem runs deeper than sample size: **16% of the n=25 draw returns empty pipeline data**, and the twelve hand-curated archetype-labeled gold theses are never sampled at all. Part of what the instrument measures is nothing.

Findings covered: F29–F37.

**Decide 4.8 first.** It sets the target n and the budget everything else fits inside.

---

## 4.1 — Resolve every sampled ticker before accepting the case

Verified live on `sample --n 25 --seed 7`: SIVE, ASHM, APPL and XFAB are selected as primary tickers, and `analyze` returns `"key_facts": {}` for all four. ASHM and XFAB 404 on yfinance; SIVE resolves with `quoteType=NONE` and no market cap; **APPL is a typo for AAPL in the source post** and yfinance resolves the literal string to an unrelated mutual fund. A blind run on any of these has no data to build a `Lens:` line or an archetype read from, and scores near-zero on grounds unrelated to doctrine quality. At the current recorded n=6 baseline, SIVE alone is one of six cases.

In `cmd_sample`'s candidate loop, resolve the primary ticker before accepting a candidate and require at least `marketCap` or `sector` to be non-null; on failure drop it and keep scanning, exactly as the existing regex ticker filter does. This is a fact check, not a judgment, so it belongs in the deterministic sampler (C1). Cost is roughly 25–40 pipeline calls once.

**The 16th case:** a ticker that resolves but to the wrong company — the harness's own "ticker collision is itself the mispricing" gotcha, turned on the eval. A resolution check that only asks "did something come back" will happily accept the mutual fund. Compare the resolved name against the thesis text where cheap, and accept that the residue is handled by 4.2.

## 4.2 — Guard against a ticker the thesis explicitly disclaims

Case `2059532571839729902` tags `["DPZ"]` and reads *"This was the company i personally liked… **Definitely not $DPZ.** But kinda reminds me of Soitec… Power semi / SiPH exposure, ~$1.28B MC."* `_primary_ticker` returns DPZ because it is the only regex-valid ticker present, so the blind prompt asks for a read on Domino's Pizza while the answer key is about an unnamed European power-semi name. The six binary scores are tallied as misses; the judge's free-text note that the case is broken is never read by `cmd_report`.

Add a cheap negation guard — skip a candidate whose selected cashtag is closely preceded by a negation — and accept it is a proxy. Pair it with a **one-time human eyeball pass** over whichever seed's case set becomes the standing regression sample. That is a fixed cost, because the point of the standing set is that it is reused across every future audit.

**The 16th case:** rhetorical anchoring generally — "not X, but something like it" is a normal way to write, and a regex will keep losing to it. The structural answer is that the standing sample is *inspected once and frozen*, not re-drawn each run.

## 4.3 — Force the twelve gold theses into every sample, and persist the archetype

Only one of the twelve curated IDs appears in the n=25/seed=7 draw, and even that one is assigned an `entry_type` by keyword heuristic that does not correspond to its curated archetype label. The other eleven — including the AXTI case built specifically with *"Tests: chain-trace to feedstock, demand>supply gate"* for the recursive-bottom-hop move that the baseline says is weakest-reproduced — are absent. The sampler draws from the full pool on an entry-type heuristic orthogonal to archetype, so nothing guarantees a draw contains a chokepoint case at all.

Give `cmd_sample` a forced-include path: a companion JSON of the twelve IDs with their §D archetype labels, entering the sample before the remainder of `--n` is filled from the existing draw. That guarantees an archetype-diverse floor regardless of seed.

Then **persist `archetype` as a fixed field on every case at sample time.** This is the fix for the n/a-versus-0 stochasticity the spec names as a confound: today the judge re-decides "is this case chokepoint-scoped?" from unstructured text on every scoring pass, so a borderline case can flip n/a↔0 between two passes of the *identical* answer — a false regression with zero underlying change. With the field persisted, `cmd_report` applies the scope split mechanically and the judge never re-derives it.

**The 16th case:** a case whose archetype is genuinely contested. Persisting a label does not make it correct — but it makes it *stable*, which is what an instrument needs. Record where each label came from (curated versus one-time cached pass) so a wrong label is findable rather than mysterious.

## 4.4 — Anchor the discovery prompt to the thesis date

The `fear_dip` and `event` branches say "around {day}"; the `discovery` branch says "right now" with no date. A September-2025 NBIS thesis with a $225 PT, asked today, generates *"Is NBIS structurally mispriced right now?"* — and if it has since re-rated, the objectively correct answer is "already re-rated, look elsewhere," which the rubric scores as a miss on six binary items. Only the free-text `notes` field has an escape hatch, and `cmd_report` never reads it.

Anchor the discovery prompt the same way the other two branches already are. Additionally, either bias the sampler toward theses recent enough that the setup is unlikely to have resolved, or instruct the judge to score decomposition *method* rather than directional agreement past an age threshold — and say which, in the report.

**The 16th case:** a thesis that was simply wrong. The eval measures method reproduction, not his hit rate, so the harness reaching a different conclusion from the same method must be scoreable as a pass. Make sure the rubric says so explicitly rather than leaving it to a judge's discretion.

## 4.5 — Score mechanically first, judge only what needs judging

Import Phase 02.6's shared structural module and run it as a deterministic pre-pass. `lens_run` and `bear_and_falsifier` are exactly the hook's own checks and need no LLM at all — running them through a judge is both more expensive and *less* faithful, since a judge can score `lens_run = 1` on an answer that would fail the live hook.

Strengthen further where it is cheap: extract the numbers from the `Lens:` line and confirm each appears (within tolerance) in that case's captured `key_facts` — a fully mechanical version of "each input traced to `key_facts`." Give `archetype_named` and `priced_in_decomposed` a fast-reject to 0 when no expected keyword appears at all, and call the judge only when one does, since presence does not imply correctness.

`recursive_bottom_hop` and `second_order_and_sibling` get no shortcut — identifying the true bottom hop needs company-specific domain knowledge no regex supplies. The available lever there is feeding the judge the gold set's own `Tests:` annotation rather than trying to mechanize the check.

**The 16th case:** a new rubric item. The rule to carry forward — mechanize what the hook already checks, judge only what is genuinely semantic — is what keeps the two from drifting apart again.

## 4.6 — Isolate mode-B runs from the live archive

Mode B is documented as "a fresh top-level session in the project dir." At n=25 that means 25 real sessions, each producing a verdict that CLAUDE.md's archive rule and `verdict_gate`'s `Saved:` nudge push toward writing into the **real** `sessions/` and appending to the **real** `INDEX.md`. Parallelize to keep wall-clock sane — the natural move — and two processes can interleave on the same index.

Run each case in its own git worktree or a throwaway copy, so `CLAUDE_PROJECT_DIR` resolves to a private disposable tree. This preserves the realism worth measuring (the hook still fires, the archive step still happens) while removing both the pollution and the race.

## 4.7 — Pin and record the model

Neither the README's mode B nor the workflow's `agent()` calls pin a model or temperature, and nothing in the scored output records which model produced an answer. A before/after separated by weeks could reflect a default-model change rather than a doctrine edit, and the confound is unrecoverable after the fact. Pin both, and stamp the resolved model identity into the scored JSON's `meta` block beside the seed.

## 4.8 — Decide the split, and state honestly what n can claim

**Decide this first.** The power arithmetic, at α = 0.05 two-sided and 80% power: detecting a 50%→70% shift needs ≈90 in-scope cases; 60%→90% needs ≈29; only a ≈40-point swing (40%→80%) drops to ≈20. The one recorded measurement moved by an amount its authors called a single stochastic judge flip. **n=25 in mode B cannot support a per-move claim**, and the two chokepoint-scoped items have a strictly smaller in-scope N still.

Separately, none of the four hooks check archetype naming, chain depth, second-order actors, or priced-in decomposition — `verdict_gate` touches only the `Lens:` token, the Downsides/falsifier phrasing, and the `Saved:` mark. So routing those four doctrine items through the expensive hook-firing mode buys **zero** extra fidelity over the cheap mode.

The split that follows:

- **a cheap, high-n mode-A pass (n ≈ 60–100)** scoring the four doctrine-content items, affordable because mode A is the documented fast parallel path;
- **a small mode-B pass (n ≈ 15–20)** confirming only the hook-triggered structural items still fire — scored mechanically per 4.5, so it needs no judge and therefore no judge-level n.

And have `cmd_report` **suppress a per-move percentage when in-scope n is below ~10–15**, printing "insufficient n for a per-move claim" instead. A 100%-on-one-case row read as a result is how a broken instrument produces confident wrong conclusions — the same failure mode the harness's own doctrine warns about for market data.

State plainly in the report what the design *can* claim: gross regressions, a pooled cross-move aggregate as a coarse dashboard number, and a running trend across edits. Those are real and useful. A per-move before/after at this n is not.

**Reference cost for mode B**, measured this session: CLAUDE.md ≈ 7K tokens, `serenity-analysis` ≈ 15K, an `analyze` payload ≈ 4.5K (12.5s wall-clock), plus a multi-turn agentic loop that resends the transcript — realistically 40K–150K tokens per case, 2–6 minutes each. At n=25 that is roughly 1–4M tokens and 1–2.75 hours serial. This is the number that makes the split worth doing rather than a nicety.

---

## Exit criteria

1. `sample --n <target> --seed 7` yields zero unresolvable tickers, contains all twelve gold cases, and persists `archetype` per case.
2. The standing regression sample is frozen, human-inspected once, and committed.
3. `report` runs the deterministic pre-pass, calls a judge only where required, and suppresses per-move percentages below the n floor.
4. A mode-B run touches no file under the real `sessions/`.
5. Model identity and seed appear in the scored output's `meta`.
6. **A baseline exists** — a run whose numbers you are willing to compare a later run against. That artifact, not any single number, is this phase's deliverable and the gate on Phase 06.
