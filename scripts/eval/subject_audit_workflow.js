export const meta = {
  name: 'serenity-subject-audit',
  description: 'Check that each eval case asks about the company its thesis is actually about',
  whenToUse: 'Once, while freezing a standing sample, after labelling and triage.',
  phases: [{ title: 'Audit', detail: 'is the subject ticker the one the thesis argues?' }],
}

// The third defect of the same family, and the one that survived two earlier passes.
//
// `_primary_ticker` takes the FIRST regex-valid ticker in the DB's tags — tagging order, not
// relevance. For the curated twelve that was fixed by hand with `subject` pins. The random remainder
// never got the same treatment, and the labelling pass noticed but had no field to say so: its own
// reasons read "despite the AMD tag", "HIMX is merely the earnings-call catalyst", "the chokepoint
// is Macronix/Winbond" on a case whose subject is NVDA.
//
// So the blind prompt asks "as of {date}, what's your read on {TICKER}?" while the answer key argues
// a different company. Every rubric row is then a miss for a reason that has nothing to do with the
// harness — the same contamination the gold `subject` pins removed, still live in the remainder.
//
// Note what the earlier triage did and did not ask. It asked whether the POST is a scoreable thesis.
// It never asked whether the SUBJECT is right, so a real, well-argued thesis about company X, tagged
// with company Y, passed it cleanly.

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
          verdict: { enum: ['ok', 'resubject', 'exclude'] },
          // Required only in spirit for `resubject`; the schema keeps it optional so a model never
          // invents a ticker to satisfy a required field.
          subject: { type: ['string', 'null'] },
          why: { type: 'string' },
        },
      },
    },
  },
}

const batches = (ARGS && ARGS.batches) || []
if (!batches.length) { log('No batches passed.'); return { error: 'no batches' } }
log(`Auditing subjects for ${batches.reduce((n, b) => n + b.length, 0)} cases.`)

const results = await parallel(batches.map((batch, i) => () => agent(
  `For each case below, decide whether the TICKER it is filed under is the company its thesis is ` +
  `actually about.\n\n` +
  `Read each with EXACTLY this command (substitute the id):\n` +
  `scripts/.venv/bin/python -c "import sqlite3;print(sqlite3.connect('data/analysis_Serenity.db')` +
  `.execute('SELECT content FROM tweets WHERE id=?',('<ID>',)).fetchone()[0])"\n\n` +
  `Each case becomes the blind question "as of {date}, what's your read on {TICKER}?", and the post ` +
  `is the answer key a judge scores the reply against. So the ticker has to be the name the post ` +
  `argues, not merely a name it mentions.\n\n` +
  `- \`ok\` — the post argues THIS ticker: a claim about its business, valuation, position in a ` +
  `chain, or a directional call on it.\n` +
  `- \`resubject\` — the post is a real thesis but about a DIFFERENT company that it names. Put that ` +
  `company's ticker in \`subject\`. Only when the post names it and argues it; do not infer a ticker ` +
  `the post does not give, and do not pick a foreign line if the post names a US-listed one.\n` +
  `- \`exclude\` — the post argues no single company, or the one it argues has no ticker you can ` +
  `read off the text.\n\n` +
  `Judgement calls worth stating: a post about a supply chain that names one company as the scarce ` +
  `node is about THAT company, even if it is tagged with the customer. A post about an earnings ` +
  `print that uses the reporter as evidence for a DIFFERENT name's thesis is about the different ` +
  `name. A post that genuinely argues the tagged name AND others is \`ok\` — the tagged name only has ` +
  `to be one the post actually argues.\n\n` +
  `Cases (id:ticker):\n${batch.map((c) => `- ${c.id}:${c.ticker} (${c.date}, labelled ${c.archetype})`).join('\n')}\n\n` +
  `One entry per id, SHORT why.`,
  { label: `subject:${i + 1}`, phase: 'Audit', schema: SCHEMA, model: 'sonnet' },
)))

const all = results.filter(Boolean).flatMap((r) => r.verdicts || [])
const bad = all.filter((v) => v.verdict !== 'ok').length
log(`Audited ${all.length}: ${bad} need a subject change or removal.`)
return { verdicts: all }
