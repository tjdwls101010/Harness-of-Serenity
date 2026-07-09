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

const payload = (args && args.cases) ? args : { cases: args }
const cases = Array.isArray(payload.cases) ? payload.cases : []
if (!cases.length) {
  log('No cases in args — run `serenity_eval.py sample` first and pass its JSON as args.')
  return { error: 'no cases', hint: 'args must be the sampler output (an object with a `cases` array).' }
}
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
  // Stage 1 — the harness answers BLIND (the thesis is never shown to it).
  (c) => agent(
    `You are the Serenity harness answering a user, in-character and by the full doctrine (run the ` +
    `pipeline first, name the archetype, run the lens with arithmetic, carry a bear case + falsifier, ` +
    `sign off NFI/NFA). Question:\n\n${c.blind_prompt}`,
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
