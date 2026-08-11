export const meta = {
  name: 'serenity-eval',
  description: 'Blind-run sampled past theses through the harness and score signature-move reproduction',
  whenToUse: 'Only on an explicit request to measure harness reproduction (N8: the thesis DB is an answer key). Feed it the cases from `serenity_eval.py sample`.',
  phases: [
    { title: 'Blind run', detail: 'each case answered blind by the harness' },
    { title: 'Judge', detail: 'score each answer vs the answer-key thesis' },
  ],
}

// The token-spending middle of plan §5. The DETERMINISTIC parts (sampling, the rubric, the report)
// live in scripts/serenity_eval.py and cost nothing; this is the part that spends tokens, so it is
// user-triggered only (see scripts/eval/README.md). Pass the sampler's output as args:
//   scripts/.venv/bin/python scripts/serenity_eval.py sample --n 8 --seed 7 > cases.json
//   Workflow({ scriptPath: 'scripts/eval/serenity_eval_workflow.js', args: <parsed cases.json> })
//
// FIDELITY CAVEAT: a workflow agent() is a subagent — it reasons from CLAUDE.md + skills but does
// NOT fire the UserPromptSubmit/Stop hooks (the WF4 confound). So this measures the DOCTRINE's
// reproduction (which is most of the method). For a full-harness run incl. hooks, use the
// high-fidelity `claude -p` mode in the README instead. Either way the JUDGE scores the same rubric.

// Cases come either directly in args (args.cases), or are SAMPLED here via the deterministic CLI.
// Workflow scripts can't read files, so the one-button path is: pass {n, seed} and let a phase-0
// agent run `serenity_eval.py sample` and return the cases (schema-validated so thesis_text survives).
const CASES_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['cases'],
  properties: {
    // The sampler's own meta rides back with the cases. Without it the scored file carried only
    // `model`, so `report` printed `seed: None` — and a run whose seed is unrecorded cannot be
    // compared against another run, which is the entire point of seeding the sampler.
    meta: { type: 'object', additionalProperties: true },
    cases: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: true,
        // `thesis_text` is NOT required: on the self-sampling path the judge fetches it from the DB
        // by id rather than having it transcribed through this schema. `id` is, because that fetch
        // has nothing to key on without it.
        required: ['id', 'ticker', 'date', 'entry_type', 'blind_prompt'],
        properties: {
          id: { type: 'string' }, ticker: { type: 'string' }, date: { type: 'string' },
          entry_type: { type: 'string' }, blind_prompt: { type: 'string' }, thesis_text: { type: 'string' },
          // Carried through so `report` can split chokepoint scope mechanically and the judge can
          // see a gold case's curated hint. Nullable: only the twelve curated cases have them.
          archetype: { type: ['string', 'null'] }, gold: { type: 'boolean' },
          gold_tests: { type: ['string', 'null'] },
        },
      },
    },
  },
}

let cases = (args && Array.isArray(args.cases)) ? args.cases : []
let sampledMeta = null
if (!cases.length) {
  const n = (args && args.n) || 6
  const seed = (args && args.seed) || 7
  log(`Sampling ${n} cases (seed ${seed}) via serenity_eval.py …`)
  // `thesis_text` is deliberately NOT requested here. It is the answer key, it runs to several KB
  // per case, and asking a model to reproduce ~55KB of it verbatim through a schema is a lossy step
  // on the one input whose integrity everything downstream rests on — a silently truncated answer
  // key would make every score look fine while measuring against half a thesis. The judge reads its
  // own case straight from the DB by id instead, so the key never passes through a transcription.
  const sampled = await agent(
    `Run this EXACT Bash command and return its stdout as structured data. The JSON it prints has a ` +
    `"cases" array; return every case's id, ticker, date, entry_type, archetype, gold_tests and ` +
    `blind_prompt VERBATIM, plus the top-level "meta" object verbatim (the seed lives there and a ` +
    `run whose seed is unrecorded cannot be compared against another). Do NOT return thesis_text — ` +
    `omit that field entirely:\n\n` +
    `scripts/.venv/bin/python scripts/serenity_eval.py sample --n ${n} --seed ${seed}`,
    { label: 'sample', phase: 'Blind run', schema: CASES_SCHEMA },
  )
  cases = (sampled && Array.isArray(sampled.cases)) ? sampled.cases : []
  if (sampled && sampled.meta) sampledMeta = sampled.meta
}
if (!cases.length) {
  log('No cases — pass {n, seed} or {cases:[…]} as args.')
  return { error: 'no cases' }
}
const payload = { meta: (args && args.meta) || sampledMeta || null, cases }
log(`Blind-running ${cases.length} cases through the harness, then judging vs the answer key.`)

// Judge output shape — mirrors scripts/serenity_eval.py RUBRIC exactly so `report` can aggregate it.
const SCORE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['archetype_named', 'lens_run', 'recursive_bottom_hop', 'second_order_and_sibling',
             'bear_and_falsifier', 'priced_in_decomposed', 'missed_signature_moves', 'notes'],
  properties: {
    // Every item accepts 'n/a', including the four that are always in scope. Without that the
    // ANSWER-KEY-UNAVAILABLE path below is inexpressible, and a judge forced to pick 0 or 1 with no
    // key to score against would emit a normal-looking number instead of a visible gap.
    archetype_named: { enum: [0, 1, 'n/a'] },
    lens_run: { enum: [0, 1, 'n/a'] },
    recursive_bottom_hop: { enum: [0, 1, 'n/a'] },
    second_order_and_sibling: { enum: [0, 1, 'n/a'] },
    bear_and_falsifier: { enum: [0, 1, 'n/a'] },
    priced_in_decomposed: { enum: [0, 1, 'n/a'] },
    missed_signature_moves: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
}

const RUBRIC_TEXT = `Score the harness ANSWER against the answer-key THESIS for signature-move reproduction.
1 = met, 0 = not met, "n/a" = the item does not apply to this answer.
- archetype_named: named the archetype off the name's economics, no escape to a softer lens.
- lens_run: ran the valuation lens with driver arithmetic shown, BOTH legs if it forks — not just named,
  not a bare top-down multiple.
- recursive_bottom_hop: traced to the substep UNDER the headline node (bottleneck within a bottleneck).
- second_order_and_sibling: a 2nd-order allocation actor AND a chain-sibling ranked.
- bear_and_falsifier: explicit bear case AND a 'breaks if…' falsifier.
- priced_in_decomposed: named the mispricing gap (what is vs isn't priced), not just consensus multiples.
- missed_signature_moves: the moves the THESIS made that the ANSWER dropped or weakened (short phrases).
- notes: one line — same structural insight / weaker version / different-but-defensible.

THREE RULES THAT DECIDE MORE SCORES THAN THE ITEMS ABOVE DO:
1. Score METHOD, never direction or numbers. The pipeline loads CURRENT data and these theses are
   months old, so figures will differ — expected, not a miss. More importantly: if the setup has since
   RESOLVED and the harness therefore reaches a different verdict ("already re-rated, look elsewhere"),
   that is a PASS on every item whose method was run properly. This measures whether his method was
   reproduced, not whether his call was right.
2. Do NOT decide whether this case is chokepoint-scoped. That split is applied mechanically downstream
   from a fixed per-case archetype label. Score recursive_bottom_hop / second_order_and_sibling on their
   merits and let the aggregator decide whether they count. Re-deciding scope per pass is what let a
   borderline case flip n/a↔0 between two scorings of the identical answer.
3. lens_run and bear_and_falsifier are ALSO scored by running the live production hook over this
   answer, and the hook's verdict overrides yours where you disagree. Score them anyway — the
   disagreement rate is reported and is itself a measurement of this rubric.`

// 4.7 — PIN the model and stamp it into the output. Without this a before/after separated by weeks
// could reflect a default-model change rather than the doctrine edit under test, and the confound is
// unrecoverable after the fact: nothing in the scored JSON records which model produced an answer.
// Default to the production model, not a cheap one — the eval measures the harness as it actually
// runs, and scoring a weaker model's answers measures the model.
const MODEL = (args && args.model) || 'opus'

const scored = await pipeline(
  cases,
  // Stage 1 — the harness answers BLIND. `thesis_text`, `archetype`, `gold_label` and `gold_tests`
  // are ALL answer key and none of them may appear here; only `blind_prompt` crosses. We load the
  // doctrine EXPLICITLY (Read ./CLAUDE.md + the matching skill, run the pipeline) rather than trust
  // subagent auto-injection — that's what makes a doctrine edit actually register in the score.
  (c) => agent(
    `You are the Serenity harness. Reproduce its method FAITHFULLY on the question below:\n` +
    `1. Read ./CLAUDE.md — that is your operating doctrine (voice, funnel, roots, non-negotiables).\n` +
    `2. Name the question type, then load the matching skill from .claude/skills/ (serenity-macro / ` +
    `serenity-discovery / serenity-analysis) and follow it.\n` +
    `3. Run \`scripts/.venv/bin/python scripts/serenity_pipeline.py analyze <TICKER>\` (add macro if the ` +
    `question needs regime) and reason from its JSON — never numbers from memory.\n` +
    `4. Answer fully in-character: TLDR, archetype, the lens RUN with arithmetic (both legs if it forks), ` +
    `winner-gate, cycle stage, a Downsides block + falsifier, rating + vehicle, NFI/NFA.\n` +
    // CLAUDE.md's archive rule tells a real answer to write sessions/{yymmdd}.{slug}/ and append to
    // INDEX.md. A mode-A subagent runs in the REAL project directory, so without this line an n=12
    // pass leaves twelve junk folders in the live archive and twelve INDEX lines — and parallel
    // cases race on the same index. Mode B is where the archive step is genuinely measured (it runs
    // in a disposable worktree); here no hooks fire, so nothing scores the `Saved:` mark anyway.
    `5. EXCEPTION to the archive rule, and only this one: do NOT create any session folder, write ` +
    `any file, or edit INDEX.md. This is an evaluation run in the live project directory. Return ` +
    `the full answer as your text — that IS the deliverable. Everything else in the doctrine applies ` +
    `normally.\n\n` +
    // The data-timing note is NOT repeated here. It lives in `_blind_prompt()` in serenity_eval.py
    // and therefore rides inside `blind_prompt` itself, so mode B — which passes that string to
    // `claude -p` with no wrapper — inherits it too. Anything stated only in this wrapper reaches
    // half the runs, and the half it misses is the high-fidelity one.
    `Question:\n${c.blind_prompt}`,
    { label: `run:${c.ticker}`, phase: 'Blind run', model: MODEL },
  ),
  // Stage 2 — judge the answer against the hidden answer-key thesis. A gold case also hands over its
  // curated `Tests:` annotation: identifying the true bottom hop needs company-specific domain
  // knowledge no rubric supplies, so without the hint the judge reverse-engineers "what should the
  // bottom hop have been here" from raw prose on every run — the least reliable scoring in the set,
  // on the two items the retrospective calls the weakest-reproduced moves.
  (answer, c) => agent(
    `${RUBRIC_TEXT}\n\n=== ANSWER-KEY THESIS (${c.ticker}, ${String(c.date).slice(0,10)}, ` +
    `entry=${c.entry_type}) ===\n` +
    (c.thesis_text
      ? `${c.thesis_text}\n`
      : `Run this EXACT command and use its stdout as the answer-key thesis:\n\n` +
        `scripts/.venv/bin/python -c "import sqlite3;print(sqlite3.connect('data/analysis_Serenity.db')` +
        `.execute('SELECT content FROM tweets WHERE id=?',('${c.id}',)).fetchone()[0])"\n\n` +
        `If that command fails or prints nothing, do NOT guess and do not score from the answer ` +
        `alone — return the score object with every binary item "n/a" and \`notes\` beginning with ` +
        `"ANSWER KEY UNAVAILABLE". A judge scoring without the key produces numbers that look ` +
        `normal and mean nothing, which is worse than a gap the report can show.\n`) +
    (c.gold_tests ? `\n=== CURATED HINT — the moves this case was built to test ===\n${c.gold_tests}\n` : '') +
    `\n=== HARNESS ANSWER (blind) ===\n${answer}\n\nReturn the score object.`,
    { label: `judge:${c.ticker}`, phase: 'Judge', schema: SCORE_SCHEMA, model: MODEL },
  ).then((scores) => ({
    id: c.id, ticker: c.ticker, date: c.date, entry_type: c.entry_type,
    // `archetype` rides along so `report` can apply the chokepoint scope split mechanically. Dropping
    // it here would send the scored file downstream with nothing to split on, and the aggregator
    // would silently fall back to the judge's own per-pass scope guess.
    archetype: c.archetype ?? null, gold: !!c.gold,
    scores, response: answer,
  })),
)

const cleaned = scored.filter(Boolean)
log(`Scored ${cleaned.length}/${cases.length} cases. Write this to scored.json and run ` +
    `\`serenity_eval.py report --results scored.json\` for the doctrine-delta list.`)
return { meta: { ...(payload.meta || {}), model: MODEL }, cases: cleaned }
