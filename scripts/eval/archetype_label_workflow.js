export const meta = {
  name: 'serenity-archetype-label',
  description: 'One-time archetype labelling of the eval sample’s random remainder',
  whenToUse: 'Only when freezing a standing regression sample. The output is committed and never re-derived.',
  phases: [{ title: 'Label', detail: 'read each thesis, assign one archetype' }],
}

// The "inspect once and freeze" step (plan 4.2/4.3). It exists because growing n buys statistical
// power for the four always-in-scope rubric rows and NONE for the two chokepoint-scoped ones: their
// stable in-scope N stays at the four curated chokepoint cases until the rest of the sample carries
// a label. Those two rows are the moves the retrospective calls the weakest-reproduced, i.e. exactly
// what a bigger n is being bought for.
//
// This labels the ANSWER KEY, not the harness's answer — it is ground truth about what each thesis
// IS, decided once and frozen, never re-derived at judge time. That is the whole point: a borderline
// case re-scoped on every pass can flip n/a<->0 between two scorings of the identical answer.

const VOCAB = ['chokepoint', 'disruption', 'evolution', 'falling_knife', 'data_error', 'macro', 'cycle_meta']

const SCHEMA = {
  type: 'object', additionalProperties: false, required: ['labels'],
  properties: {
    labels: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false, required: ['id', 'archetype', 'why'],
        properties: {
          id: { type: 'string' },
          archetype: { enum: VOCAB },
          why: { type: 'string' },
        },
      },
    },
  },
}

// `args` can arrive as a JSON-ENCODED STRING rather than a value. Verified the hard way: a run
// passed {n: 12, seed: 7} and logged "Sampling 6 cases" — `args.n` was undefined and silently fell
// through to the default, which is the worst shape of this bug because the workflow still runs and
// still returns results, just not the ones asked for. Parse defensively and read from the result.
function _args(a) {
  if (typeof a === 'string') { try { return JSON.parse(a) } catch (e) { return null } }
  return a
}
const ARGS = _args(args)

const batches = (ARGS && ARGS.batches) || []
if (!batches.length) { log('No batches passed.'); return { error: 'no batches' } }
log(`Labelling ${batches.reduce((n, b) => n + b.length, 0)} cases across ${batches.length} batches.`)

const results = await parallel(batches.map((batch, i) => () => agent(
  `Assign ONE archetype to each thesis below. This is ground truth for a measurement instrument, ` +
  `frozen once and never re-derived, so accuracy matters more than speed.\n\n` +
  `For each id, read the thesis with EXACTLY this command (substitute the id):\n` +
  `scripts/.venv/bin/python -c "import sqlite3;print(sqlite3.connect('data/analysis_Serenity.db')` +
  `.execute('SELECT content FROM tweets WHERE id=?',('<ID>',)).fetchone()[0])"\n\n` +
  `Read ./CLAUDE.md first for what these archetypes mean. Summary of the decision:\n` +
  `- chokepoint  — a physical or jurisdictional step demand cannot route around (a substrate, a fab, ` +
  `a licence, a single refining step). Hardware/materials defaults here.\n` +
  `- disruption  — a faster entrant draining an incumbent profit pool; a margin/cost-structure inversion.\n` +
  `- evolution   — an emerging standard or asset-financed buildout a step-change just made investable ` +
  `(neoclouds, capacity financed against offtake).\n` +
  `- falling_knife — the thesis's entry IS a displacement / loss / cancellation headline whose ` +
  `mechanical claim is being litigated.\n` +
  `- data_error  — the mispricing IS a wrong number (ticker collision, phantom figure, stale field).\n` +
  `- macro       — a regime / rates / policy / geopolitics read, or an index-or-ETF-level call.\n` +
  `- cycle_meta  — a multi-name ranking or cycle-stage framework post rather than one name's thesis.\n\n` +
  `Rules that decide the awkward ones:\n` +
  `1. Label what the THESIS argues, not what the ticker's sector suggests. A semiconductor name ` +
  `argued as "the market misread this headline" is falling_knife, not chokepoint.\n` +
  `2. chokepoint requires an actual scarce step named in the thesis. Theme exposure to a bottleneck ` +
  `is NOT chokepoint ownership — that distinction is a doctrine non-negotiable.\n` +
  `3. If a post ranks several names or lays out a stage framework, it is cycle_meta even when one ` +
  `name dominates.\n` +
  `4. Pick the single best fit. Every case gets exactly one label; there is no "unclear" option, so ` +
  `where it is genuinely borderline say so in \`why\` — a label that later looks wrong needs to be ` +
  `findable, and \`why\` is what makes it findable.\n\n` +
  `Cases:\n${batch.map((c) => `- ${c.id} (${c.ticker}, ${c.date})`).join('\n')}\n\n` +
  `Return one entry per id, with a SHORT why (one clause).`,
  { label: `label:${i + 1}`, phase: 'Label', schema: SCHEMA, model: 'sonnet' },
)))

const all = results.filter(Boolean).flatMap((r) => r.labels || [])
log(`Labelled ${all.length} cases.`)
return { labels: all }
