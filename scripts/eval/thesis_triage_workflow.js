export const meta = {
  name: 'serenity-thesis-triage',
  description: 'Separate real theses from non-theses in the eval sample’s cycle_meta bucket',
  whenToUse: 'Once, while freezing a standing sample. Output is committed and never re-derived.',
  phases: [{ title: 'Triage', detail: 'is this a scoreable single-name thesis at all?' }],
}

// WHY THIS EXISTS. The first labelling pass was told "there is no 'unclear' option — pick the single
// best fit". That was wrong, and it showed: `cycle_meta` absorbed everything that is not one name's
// argument, including posts that are not investment theses at all (a five-ticker idea-share list of
// bare one-liners, a table of 23 tickers' daily moves, a follower-milestone thank-you note).
//
// It matters because the eval asks a SINGLE-NAME question — "as of {date}, what's your read on
// {TICKER}?" — and scores the answer against that post as the answer key. Against a post ranking 23
// newsletter authors, every rubric item is a miss for reasons that have nothing to do with doctrine
// quality. That is the "part of what the instrument measures is nothing" failure this phase exists
// to remove, arriving through the fix for a different instance of it.
//
// A forced-choice taxonomy with no escape hatch does not make labels more decisive, it just hides
// the residue in whichever bucket is broadest.

function _args(a) {
  if (typeof a === 'string') { try { return JSON.parse(a) } catch (e) { return null } }
  return a
}
const ARGS = _args(args)

const SCHEMA = {
  type: 'object', additionalProperties: false, required: ['verdicts'],
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['id', 'verdict', 'why'],
        properties: {
          id: { type: 'string' },
          // `cycle_meta` stays a REAL archetype — the curated gold set has one (an explicit 5-stage
          // cycle map with named exemplars and allocation logic). The distinction being drawn here
          // is between a post that argues a stage/ranking FRAMEWORK and a post that is simply not a
          // thesis about the tagged ticker.
          verdict: { enum: ['cycle_meta', 'exclude'] },
          why: { type: 'string' },
        },
      },
    },
  },
}

const batches = (ARGS && ARGS.batches) || []
if (!batches.length) { log('No batches passed.'); return { error: 'no batches' } }
log(`Triaging ${batches.reduce((n, b) => n + b.length, 0)} cycle_meta cases.`)

const results = await parallel(batches.map((batch, i) => () => agent(
  `Each case below was labelled \`cycle_meta\` by an earlier pass that had no way to say "this is ` +
  `not a thesis". Decide which it actually is.\n\n` +
  `Read each with EXACTLY this command (substitute the id):\n` +
  `scripts/.venv/bin/python -c "import sqlite3;print(sqlite3.connect('data/analysis_Serenity.db')` +
  `.execute('SELECT content FROM tweets WHERE id=?',('<ID>',)).fetchone()[0])"\n\n` +
  `The question that decides it: this post will be turned into the blind question "as of {date}, ` +
  `what's your read on {TICKER}?", and the post itself becomes the answer key an LLM judge scores ` +
  `the reply against. **Is that a fair thing to score?**\n\n` +
  `- \`cycle_meta\` — YES. The post argues a cycle-stage or ranking FRAMEWORK with real reasoning: ` +
  `named rungs or tiers, why one name sits above another, allocation or sizing logic. A reply that ` +
  `places the ticker and sizes it could be judged against this fairly.\n` +
  `- \`exclude\` — NO. There is no argument to reproduce about the tagged ticker: a bare list of ` +
  `tickers or one-liners, a table of price moves, a trade log, a research-in-progress scan with no ` +
  `landed claim, a meta/community post, or anything where the tagged ticker is incidental. Also ` +
  `exclude when the post IS a real thesis but about a DIFFERENT company than the tagged one.\n\n` +
  `Bias: when a post has real analytical content about the tagged name, keep it. When you would ` +
  `struggle to say what claim a reply is supposed to reproduce, exclude it. An excluded case costs ` +
  `one case of sample size; a wrongly-kept one adds a guaranteed miss on every rubric row and drags ` +
  `the measurement for reasons unrelated to the harness.\n\n` +
  `Cases:\n${batch.map((c) => `- ${c.id} (${c.ticker}, ${c.date})`).join('\n')}\n\n` +
  `One entry per id, with a SHORT why.`,
  { label: `triage:${i + 1}`, phase: 'Triage', schema: SCHEMA, model: 'sonnet' },
)))

const all = results.filter(Boolean).flatMap((r) => r.verdicts || [])
log(`Triaged ${all.length}: ${all.filter((v) => v.verdict === 'exclude').length} excluded.`)
return { verdicts: all }
