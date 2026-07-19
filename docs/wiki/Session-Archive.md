# Session Archive

How analysis is persisted under `sessions/`, and the two rules that make a past session safe to
reuse.

## The problem it solves

Analysis that lives only in a conversation is lost when the conversation ends. Re-answering the
same question later produces a fresh view with no way to tell whether a changed conclusion
reflects changed evidence or just a differently-shaped generation.

But naive persistence introduces a worse problem. If a past analysis is simply read back, two
failures follow:

1. **Stale numbers get reused.** A market cap from three weeks ago is not a current input, but it
   sits in a file looking exactly like one.
2. **Prior conclusions anchor new ones.** Reading "Tier 1, high conviction" before forming a fresh
   view does not inform the new judgment — it replaces it. The new assessment converges on the old
   one and the drift becomes invisible.

The archive is designed around both.

## Layout

```
sessions/
├── INDEX.md                              one line per folder, no verdicts
├── 260719.ai-semiconductor-bottlenecks/   ← shape of a real session (see note below)
│   ├── _macro.md                         the regime read, once per cohort
│   ├── _ranking.md                       basket synthesis with the tier table
│   ├── NVDA.md                           one scorecard per name
│   ├── AVGO.md
│   └── …
├── 990101.hook-fixture/                  test scaffolding — do not delete
└── 990102.hook-empty/                    test scaffolding — do not add .md here
```

Only `INDEX.md` and the two `9901xx` fixture folders are committed. Real session folders are
produced locally as you use the harness; the dated folder above illustrates the shape rather than
naming something you will find in a fresh clone.

**Folder naming:** `{yymmdd}.{topic-slug}` — created **lazily on the first artifact**, never
pre-created. On a name collision, suffix `-2`.

**File conventions:**

| File | Holds |
| --- | --- |
| `TICKER.md` | One name's scorecard in the pinned schema |
| `_ranking.md` | Basket synthesis: the tier table, tier cut, and deltas |
| `_macro.md` | The regime read the whole session leaned on |

The underscore prefix sorts synthesis files above per-name files, so a folder listing shows the
summary first.

**One hard rule:** never write into a session folder the current session did not create. A folder
is one session's record; appending to someone else's makes both unreadable.

## The scorecard schema

Pinned in the `serenity-scorecard` agent definition, which is the single source of truth — the
inline path reads it from there rather than restating it.

```markdown
---
ticker: NVDA
type: scorecard                  # scorecard | analysis
session: 260718.rank-ai-supply-chain
date: 2026-07-18
data_as_of: 2026-07-18T09:32Z    # wall-clock of the pipeline run
archetype: chokepoint            # chokepoint | disruption | evolution | UNRESOLVED:<nulled line>
stage: 4                         # ladder rung 1-5
gates: pass                      # pass | fail:<gate> | conditional:<which> | blocked:<line>
conviction: high                 # this name's OWN, never cohort-relative
gate_strength: "…"               # one clause
vehicle: "…"                     # one clause, or "unavailable"
mc: "$3.2T"                      # verbatim from key_facts
---
## Structural position
## Forward revenue trajectory
## Lens                          # the literal Lens: line(s); BOTH legs if forked
## Winner-gates
## Downsides                     # 2-4 bullets, each tagged priced-in / addressed
## Falsifier                     # "breaks if …"
```

Three fields carry more weight than they look:

- **`data_as_of`** is the wall-clock time of the pipeline run, not the date the file was written.
  It is what makes the "numbers expire" rule checkable — you can see how stale a figure is without
  guessing.
- **`conviction` is the name's own**, never cohort-relative. A scorecard written while thinking
  "this is the best of the five" is not reusable in a different cohort. Cohort-relative placement
  is the synthesizer's job.
- **`archetype: UNRESOLVED:<nulled line>`** is a real state, not a failure. When a data line came
  back null and could not be reconciled, the archetype is *blocked* rather than guessed — the
  method treats an unreconciled null as a hard stop rather than proceeding structurally.

There is deliberately **no `tier` field and no delta section**. Both belong to `_ranking.md`. A
scorecard that assigned its own tier would defeat the cohort-independence the
[rank-N protocol](Agent-Harness.md#the-rank-n-protocol) depends on.

## The ranking file

`_ranking.md` carries a table whose column order is exact, because
`serenity_harness.py rankdiff` parses it:

```markdown
| ticker | tier | rung | gates | one-line why |
| --- | --- | --- | --- | --- |
| NVDA | 1 | 4 | pass | scarce node, allocation control intact |
| AVGO | 2 | 3 | conditional:demand-breadth | strong position, breadth unproven |
```

Plus a `Tier cut:` line stating where the boundaries fall and why, and a
`## Deltas vs {prior-folder}` section when a prior ranking exists.

## INDEX.md

One line per folder, newest first:

```markdown
- [260719.ai-semiconductor-bottlenecks](260719.ai-semiconductor-bottlenecks/) — ranking: NVDA, AVGO, MU, TSM
```

Format: `- [{yymmdd}.{topic-slug}]({folder}/) — {type}: {tickers}`, where type is one of `ranking`,
`analysis`, `macro`, `postmortem`. English only.

**The index deliberately holds no verdicts.** Not brevity — an index line stating a past
conclusion would anchor the next reading before fresh judgment forms, which is the exact failure
the archive is structured to avoid. A ticker grep is all retrieval actually needs, and a ticker
grep is safe.

`serenity_harness.py validate` asserts the index remains verdict-free.

The fixture folders (`990101.*`, `990102.*`) are **never listed** — they are test scaffolding,
not analysis.

## The two reuse rules

### Numbers expire; structure does not

A number from a past session file is **never** a current input. Re-run the pipeline. What carries
forward is the judgment structure: the tier, the thesis, the falsifier, the archetype.

The single exception is a delta line, where a prior number may be quoted if tagged as-of-then:

```markdown
fwd P/E 34 (as-of 260711) → 39
```

The tag is what makes it a comparison rather than an input.

### Fresh judgment first, comparison second

On a repeat question, complete the new scorecards and tiers from current evidence **before**
opening the prior ranking. Then explain every tier that moved, labeled as one of:

| Label | Meaning |
| --- | --- |
| **Evidence delta** | The facts changed — new filing, new quarter, new price |
| **Judgment revision** | Same facts, read differently. Owned as a revision, not disguised as new evidence. |
| **Cohort delta** | The name did not move; the comparison set did |

Both halves of the rule are load-bearing, and they fail in opposite directions:

- Reading the old ranking first **anchors** the new one — you converge on the previous answer
  without noticing.
- Skipping the comparison **hides drift** — you never see that a name quietly moved two tiers on
  no new information.

Doing them in this order is what makes the archive an audit trail rather than a source of
contamination.

## How a session gets written

1. Analysis completes and a verdict is formed.
2. The folder is created — `sessions/{yymmdd}.{topic-slug}/`, lazily, on the first artifact.
3. Artifacts are written: `TICKER.md` per name, `_macro.md` if a regime read was used,
   `_ranking.md` for a basket.
4. One line is appended to `sessions/INDEX.md`.
5. The answer closes with a visible `Saved: sessions/{folder}/` line.

Step 5 is verified. The `Stop` hook resolves the path against the real filesystem and checks the
folder exists and contains at least one `.md` — because a costless `mkdir` or a
`Saved: sessions/INDEX.md` token would otherwise falsely certify that archiving happened. See
[Hooks Reference](Hooks-Reference.md#verdict_gatepy--stop).

## The test-scaffolding folders

Two committed folders exist solely so the `Stop` hook's `Saved:` check has a real filesystem to
resolve against:

| Folder | Contains | Tests |
| --- | --- | --- |
| `990101.hook-fixture/` | `FIXT.md` | The valid case: folder exists and holds a `.md` |
| `990102.hook-empty/` | `.gitkeep` only | The claimed-but-empty case |
| `990199.hook-missing/` | *(deliberately absent)* | The nonexistent-folder case |

Both self-document in their own contents. **Do not add a `.md` to `990102.hook-empty`** — that
would silently stop the empty-folder fixture from testing what it claims, and the fixture would
keep passing while checking nothing.

## Current state

The archive convention is fully specified and has **no committed worked example.** A fresh clone
contains `INDEX.md` with zero entries and the two fixture folders — nothing else. Session folders
are generated locally as you use the harness and are not published with the repository.

Two consequences worth knowing:

- There is no reference `_ranking.md` in the repository, so the tier table, the `Tier cut:` line,
  and the deltas section described above have no example to copy from. The column contract in
  [Agent Harness](Agent-Harness.md#the-rank-n-protocol) is the specification.
- `serenity_harness.py rankdiff` parses `_ranking.md`, so it has nothing in a fresh clone to run
  against. Point it at two of your own session folders.

See [Known Limitations](Known-Limitations.md#the-session-archive-has-no-committed-worked-example).

---

**Next:** [Testing and Validation](Testing-and-Validation.md) · [Back to index](README.md)
