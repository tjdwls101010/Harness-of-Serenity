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
    cases: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: true,
        required: ['ticker', 'date', 'entry_type', 'blind_prompt', 'thesis_text'],
        properties: {
          id: { type: 'string' }, ticker: { type: 'string' }, date: { type: 'string' },
          entry_type: { type: 'string' }, blind_prompt: { type: 'string' }, thesis_text: { type: 'string' },
        },
      },
    },
  },
}

let cases = (args && Array.isArray(args.cases)) ? args.cases : []
if (!cases.length) {
  const n = (args && args.n) || 6
  const seed = (args && args.seed) || 7
  log(`Sampling ${n} cases (seed ${seed}) via serenity_eval.py …`)
  const sampled = await agent(
    `Run this EXACT Bash command and return its stdout as structured data. The JSON it prints has a ` +
    `"cases" array; return every case's id, ticker, date, entry_type, blind_prompt, and thesis_text ` +
    `VERBATIM — do NOT summarize, truncate, or reword thesis_text (it is the answer key):\n\n` +
    `scripts/.venv/bin/python scripts/serenity_eval.py sample --n ${n} --seed ${seed}`,
    { label: 'sample', phase: 'Blind run', schema: CASES_SCHEMA },
  )
  cases = (sampled && Array.isArray(sampled.cases)) ? sampled.cases : []
}
if (!cases.length) {
  log('No cases — pass {n, seed} or {cases:[…]} as args.')
  return { error: 'no cases' }
}
const payload = { meta: (args && args.meta) || null, cases }
log(`Blind-running ${cases.length} cases through the harness, then judging vs the answer key.`)

// Judge output shape — mirrors scripts/serenity_eval.py RUBRIC exactly so `report` can aggregate it.
const SCORE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['archetype_named', 'lens_run', 'recursive_bottom_hop', 'second_order_and_sibling',
             'bear_and_falsifier', 'priced_in_decomposed', 'missed_signature_moves', 'notes'],
  properties: {
    archetype_named: { enum: [0, 1] },
    lens_run: { enum: [0, 1] },
    recursive_bottom_hop: { enum: [0, 1, 'n/a'] },
    second_order_and_sibling: { enum: [0, 1, 'n/a'] },
    bear_and_falsifier: { enum: [0, 1] },
    priced_in_decomposed: { enum: [0, 1] },
    missed_signature_moves: { type: 'array', items: { type: 'string' } },
    notes: { type: 'string' },
  },
}

const RUBRIC_TEXT = `Score the harness ANSWER against the answer-key THESIS for signature-move reproduction.
1 = met, 0 = not met, "n/a" = out of scope for this case's archetype (a disruptor/evolution name has no
recursive-bottom-hop — score n/a there, never 0). Score reproduction of METHOD, not number-match (the
pipeline loads CURRENT data, so figures will differ from the thesis date — that is expected, not a miss).
- archetype_named: named the archetype off the name's economics, no escape to a softer lens.
- lens_run: ran the valuation lens with driver arithmetic shown, BOTH legs if it forks — not just named,
  not a bare top-down multiple.
- recursive_bottom_hop: [chokepoint only] traced to the substep UNDER the headline node.
- second_order_and_sibling: [chokepoint only] a 2nd-order allocation actor AND a chain-sibling ranked.
- bear_and_falsifier: explicit bear case AND a 'breaks if…' falsifier.
- priced_in_decomposed: named the mispricing gap (what is vs isn't priced), not just consensus multiples.
- missed_signature_moves: the moves the THESIS made that the ANSWER dropped or weakened (short phrases).
- notes: one line — same structural insight / weaker version / different-but-defensible.`

const scored = await pipeline(
  cases,
  // Stage 1 — the harness answers BLIND (the thesis is never shown to it). We load the doctrine
  // EXPLICITLY (Read ./CLAUDE.md + the matching skill, run the pipeline) rather than trust subagent
  // auto-injection — that's what makes a before/after dedup difference actually register in the score.
  (c) => agent(
    `You are the Serenity harness. Reproduce its method FAITHFULLY on the question below:\n` +
    `1. Read ./CLAUDE.md — that is your operating doctrine (voice, funnel, roots, non-negotiables).\n` +
    `2. Name the question type, then load the matching skill from .claude/skills/ (serenity-macro / ` +
    `serenity-discovery / serenity-analysis) and follow it.\n` +
    `3. Run \`scripts/.venv/bin/python scripts/serenity_pipeline.py analyze <TICKER>\` (add macro if the ` +
    `question needs regime) and reason from its JSON — never numbers from memory.\n` +
    `4. Answer fully in-character: TLDR, archetype, the lens RUN with arithmetic (both legs if it forks), ` +
    `winner-gate, cycle stage, a Downsides block + falsifier, rating + vehicle, NFI/NFA.\n\n` +
    `Question:\n${c.blind_prompt}`,
    { label: `run:${c.ticker}`, phase: 'Blind run' },
  ),
  // Stage 2 — judge the answer against the hidden answer-key thesis.
  (answer, c) => agent(
    `${RUBRIC_TEXT}\n\n=== ANSWER-KEY THESIS (${c.ticker}, ${String(c.date).slice(0,10)}, ` +
    `entry=${c.entry_type}) ===\n${c.thesis_text}\n\n=== HARNESS ANSWER (blind) ===\n${answer}\n\n` +
    `Return the score object.`,
    { label: `judge:${c.ticker}`, phase: 'Judge', schema: SCORE_SCHEMA },
  ).then((scores) => ({
    id: c.id, ticker: c.ticker, date: c.date, entry_type: c.entry_type,
    scores, response: answer,
  })),
)

const cleaned = scored.filter(Boolean)
log(`Scored ${cleaned.length}/${cases.length} cases. Write this to scored.json and run ` +
    `\`serenity_eval.py report --results scored.json\` for the doctrine-delta list.`)
return { meta: payload.meta || null, cases: cleaned }
