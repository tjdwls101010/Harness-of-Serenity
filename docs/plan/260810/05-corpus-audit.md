# Phase 05 — the corpus audit: does the doctrine actually contain his method?

**Prerequisite:** Phase 04 recommended (so that whatever this phase changes can be measured). The extraction itself has no dependency and can run in parallel with 04 if convenient.

**This is the phase that answers the owner's first question.** Everything else in this plan is about whether the harness honors the doctrine it has. This is about whether the doctrine is his.

---

## Why it has never been done

Trace the provenance of the current doctrine:

```
1,792 posts  ->  db-mining-report.md (74 lines, one pass, ~2026-07)  ->  legacy-monolith-skill.md (551 lines)  ->  CLAUDE.md + 3 skills
```

The only coverage audit ever run (`references/principle-inventories/critic-coverage.md`) compared the **drafts against the legacy monolith** — it verified that the rewrite into four files lost nothing from the previous document. **Nobody has ever compared the doctrine against the corpus.** Whatever the 74-line summary dropped has been invisible to every audit since, because every audit's ceiling was that summary.

That single summarizing pass already caught two errors, which is the evidence that a systematic pass will catch more:

- the "asymmetric upside" ban was **backwards** — he uses "asymmetrical [long/upside/bet]" roughly 35 times; it is a signature, and the doctrine had banned it as a forgery tell;
- the "no-growth ×15" valuation floor was **invented** — he says it zero times; his real lens is EV/Rev and EV/FCF peer and chain banding.

An invented rule is worse than a missing one. A gap costs an insight; an invention makes the harness confidently wrong in his name, and nothing downstream can detect it — the eval draws its answer key from the same corpus, so a doctrine claim absent from the corpus simply never appears as a miss.

**And the corpus has grown.** `db-mining-report.md` states 1,606 rows through 2026-06. The database holds **1,792 rows through 2026-07-25**. Roughly 186 posts (~10%) have never been read by anything.

## Corpus profile

| | |
|---|---|
| rows | 1,792 — 1,609 `post`, 181 `subscriber`, 2 `reply` |
| volume | 1.47M chars ≈ **368K tokens** |
| range | 2025-07-04 → 2026-07-25 |
| length | median 482 chars, p75 931, p90 1,808, p99 5,376 |
| noise | 41 rows under 80 chars |
| tickers | 1,593 rows carry at least one |

368K tokens means **full-corpus extraction is affordable**. This audit reads the primary source, not a summary of it — which is the entire reason it can find what every previous audit structurally could not.

---

## 5.1 — Extraction: reasoning moves, sector-abstracted

**The unit is the move, not the call.** Not "$AAOI goes 3x" but "size a design-win supplier bottom-up from content per end-unit × projected volume ÷ today's market cap." The move is the only unit that diffs against doctrine, because doctrine is made of moves.

**The abstraction instruction is the load-bearing part of the prompt.** The corpus is 2025–2026, the AI-buildout era, so most of it is semis, memory, optics and neoclouds. The doctrine states outright that "semis are a recent convenience, not the doctrine." A naive extractor returns a thousand semiconductor-specific observations and buries the method inside them. Every extracted move must therefore be written so that **the sector is an example, not the frame** — the same test Phase 06 applies to the neocloud-locked gate-3 language. If a move cannot be stated without naming a specific industry, that is itself a finding: it means the move may be genuinely sector-bound, and the doctrine should say so rather than pretending it generalizes.

Extract per move: a one-line statement of the move, the evidence-to-conclusion path it encodes, one or two source row IDs, and a confidence that this is method rather than a one-off remark.

**Record frequency.** He repeats his real moves constantly; a move appearing forty times is load-bearing in a way one appearing once is not. Frequency is not just deduplication bookkeeping — it is the weight that lets 5.3 ask a question no previous audit could: **does the doctrine's emphasis match his?** A move he makes weekly that the doctrine mentions in a subordinate clause is a coverage failure that a binary present/absent check scores as a pass.

**Fan-out shape.** Chunk chronologically at roughly 80–100 posts per agent (≈20 agents over the `post` rows), and give the 181 `subscriber` theses their own smaller chunks — they are long-form and densest. Sonnet is the right tier. Run as one workflow or two or three sequential ones; the chunking is independent, so resumption is cheap. Chronological chunking is deliberate: it keeps a multi-post thread together, and it makes it obvious if his method shifts over the year, which is itself worth knowing.

## 5.2 — The move inventory, as a checked-in artifact

Dedupe into a committed file — `references/move-inventory.md` or a JSON companion. This is a durable asset, not a report: every future doctrine edit can re-diff against it for free, and a future corpus refresh appends rather than restarts.

Each entry carries the move statement, its frequency, representative row IDs, and the doctrine location that covers it (filled in by 5.3).

## 5.3 — `harness coverage` — the A/B/C diff

A command that diffs the inventory against the doctrine files and emits three buckets:

| Bucket | Meaning | Disposition |
|---|---|---|
| **A** — in corpus, in doctrine | captured | none; the size of A **is** the quantitative answer to "was his tacit knowledge captured" |
| **B** — in corpus, not in doctrine | missing tacit knowledge | absorb per C6 — see below |
| **C** — in doctrine, not in corpus | harness augmentation, possibly invention | keep if independently useful, but **catalogue** — see 5.4 |

Report A both unweighted and **frequency-weighted**, and treat the gap between those two numbers as a finding in its own right: high unweighted coverage with low weighted coverage means the doctrine has captured his rare moves and thinned his common ones.

The matching itself needs judgment (a move can be present under different words), so this command is a *router*, not a verdict — it proposes matches and flags uncertain ones for human or model review. Do not let it assign a bucket silently on a string match; that would be judgment in code, and the harness has deleted one such mechanism already.

## 5.4 — The provenance layer

The owner's decision on bucket C: **keep a useful claim even without corpus grounding, but record where it came from.** Implement that as a provenance tag on doctrine claims — sourced (corpus-grounded, with row IDs), augmented (defensible, added by the harness), or unverified.

This does more than tidy the record. It converts a vague worry into a number: *what fraction of this harness is actually him?* It makes an invention like the ×15 floor visible **before** someone builds on it. And it gives a future reader — including a future session of this project — the one thing that is otherwise unrecoverable, which is knowing which parts of the doctrine carry his authority and which carry ours.

Keep it lightweight. A tag per major claim, not per sentence; the goal is auditability, not annotation for its own sake.

---

## Absorption discipline — pre-committed, before any finding is seen

This is set in advance deliberately, because the temptation arrives with the findings.

**Bucket B is absorbed by widening the trigger or the why of an existing root or value — never by adding a standalone rule.** For each finding, name which `R#` / `V#` / non-negotiable should already have fired, and why it didn't. If nothing plausibly should have fired, that is the rare case for a new item, and it should be rare enough to count on one hand.

The reason is written in the harness's own spec: bloat's root cause is per-miss patching, where a miss becomes a case-targeted rule, the spine grows, and the seventeenth case is still uncovered. The commit history shows four consecutive rounds of exactly that. A corpus audit producing two hundred findings is the single largest bloat risk this project has ever faced — which is precisely why the discipline is fixed before the findings exist.

**Set a budget.** Decide in advance roughly how many doctrine edits this phase may produce. If the audit surfaces more than that, the correct response is to widen further and more generally, not to spend more. An audit that produces fifty new clauses has damaged the harness regardless of how correct each clause is.

## What this phase also produces for Phase 06

Real corpus cases exercising the generalization points. Phase 06's RC4 fixes — permitting risk in the winner gates, funded-versus-dilution outside the neocloud, a fifth liquidity channel — are otherwise unverifiable, because the current twelve-case gold set contains none of those situations and you cannot invent a case he never wrote without changing what the eval measures. If the corpus contains a non-semiconductor funded-versus-dilution read or a permitting-blocked name, those become gold cases and Phase 06's fixes become measurable. **Watch for them explicitly during extraction** rather than hoping they surface.

---

## Exit criteria

1. All 1,792 rows processed; the count is reported, not assumed.
2. `references/move-inventory.md` (or its JSON companion) committed, with frequencies.
3. `harness coverage` runs and emits A/B/C, with A reported both unweighted and frequency-weighted.
4. Bucket C reviewed item by item; each keep decision recorded with its reason.
5. Provenance tags applied to the doctrine's major claims.
6. Any corpus case exercising a Phase-06 generalization point is added to the gold set.
7. **The answer to the owner's first question, stated as a number with its method** — including what the number does not cover.
