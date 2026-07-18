# Decision-Reproducibility Plan — reducing session-to-session variance in Serenity

**Status:** approved by the user 2026-07-18 (planning session), then hardened by a 3-lens adversarial review workflow (doctrine / feasibility / goal red-team; 20 findings — 1 blocker, 9 major, 10 minor — all folded into this revision; see §16). Implementation happens in a NEW session that follows this document.
**Planning-session context:** the user observed that identical questions — especially "analyze these dozens of tickers and rank them by investment value" — produce different answers and different rankings across sessions. This plan is the agreed fix. Every major decision below was explicitly confirmed with the user via AskUserQuestion; do not re-litigate them, but DO surface anything that turns out to be technically impossible during implementation instead of silently improvising.

---

## 1. Goal — what "reduced randomness" means (agreed)

The target is **decision reproducibility**, NOT byte-identical output:

> Same evidence → same tier assignments. Any tier change must carry a **named evidence delta** ("fwd P/E 34 (as-of the prior run) → 39"), an **owned judgment revision**, or a **cohort delta** (see §6 Step 4) — never an unexplained flip.

Explicitly rejected targets (do not drift toward them):
- **Full reproduction** ("same question → nearly identical answer") — impossible under sampling noise + live market data, and forcing it would push judgment into code, which this harness's design thesis forbids.
- **Numeric-weight composite scoring** (0.3×moat + 0.2×valuation…) — this is the deleted legacy `objective_screen` reborn. A score *looks* like a verdict, the model defers to it and stops reasoning. The rubric below fixes *form* (fields, precedence, tie-breaks, output contract, and — per the review's blocker — the tier-assignment form itself), never *content* (no thresholds like "PEG<1.2 ⇒ Tier 1", no weights). Scoring stays Claude's judgment.

Diagnosis the plan rests on — variance has four sources:
1. **Legitimate data movement** (market moved between sessions) — must be preserved, but *attributed*.
2. **Improvised decomposition** — each session invents its own ranking criteria, precedence, and tie-breaks. Biggest fixable source. Includes a real doctrine bug: CLAUDE.md's E-type lines say "sort by gate-strength + conviction" while serenity-analysis's ladder section says "allocation is sized by stage, NOT gate-strength" — sessions follow whichever text is loaded.
3. **Order/context effects** — dozens of names analyzed sequentially in one context hit compaction; name #30 is judged under different conditions than name #1.
4. **Sampling noise** — irreducible, but its effect size depends on structure: holistic gut-ranking amplifies it; fixed-field scorecards + tier assignment damp it.

## 2. Agreed decisions log (from the planning session's question rounds)

| # | Decision | Choice |
|---|---|---|
| A1 | Success criterion | Decision reproducibility (tiers stable given same evidence; deltas named) |
| A2 | Scope | B1 ranking rubric + B2 doctrine-conflict fix + B3 session archive (modified design) + hybrid fan-out. B5's LLM-driven consistency-eval axis and a fixed `rank.js` workflow file are DEFERRED (see §14; the deterministic tier-diff comparator moved INTO scope per the review) |
| A3 | Ranking precedence | 4-step: Gate = filter → Stage rung = primary axis → within-rung gate-strength + conviction → explicit tie-breaks |
| A4 | Session archive | Lazy-created `sessions/{yymmdd}.{topic-slug}/`, `sessions/INDEX.md` retrieval index, no-number-reuse + fresh-judgment-first rules, enforcement via `verdict_gate` extension (soft), files in **English**, folder **tracked in git** |
| A5 | Fan-out | Per-name instructions pinned in a new `.claude/agents/serenity-scorecard.md`; plumbing free (parallel Agent calls as the verified-primary launcher, dynamic workflow where available). No fixed workflow file in v1 |
| A6 | No SessionStart mkdir hook | Folder creation is lazy (first artifact write), named by Claude with date + topic slug. Rejected: unconditional mkdir at session start (empty-folder litter; topic unknown at start time) |
| A7 | Plan/doc language | English for this plan and all generated components and all `sessions/` files |
| A8 | Review hardening | Plan adversarially reviewed before finalization; all 20 findings folded. The review-driven refinements below are design details inside the delegated scope, not re-opened user decisions |

## 3. Deliverables overview and implementation order

Implement in this order — each step is verifiable before the next:

| # | Deliverable | Files touched |
|---|---|---|
| D1 | Doctrine-conflict fix + E-type contract rewrite | `CLAUDE.md` (2 line edits) |
| D2 | Session-archive convention in the spine | `CLAUDE.md` (1 new block) |
| D3 | Rank-N protocol (the rubric) in the analysis skill + ladder-header reconciliation | `.claude/skills/serenity-analysis/SKILL.md` |
| D4 | `sessions/` bootstrap | `sessions/INDEX.md` (new) |
| D5 | Scorecard agent (carries the pinned schema) | `.claude/agents/serenity-scorecard.md` (new) |
| D6 | `verdict_gate` extension (`Saved:` mark check) + committed fixtures | `.claude/hooks/verdict_gate.py`, `.claude/hooks/tests/` (new) |
| D7 | `evidence_discipline` one-line retrieval nudge + committed fixtures | `.claude/hooks/evidence_discipline.py`, `.claude/hooks/tests/` |
| D8 | Self-check extension + deterministic `rankdiff` comparator | `scripts/serenity_harness.py` |
| D9 | Spec + Codex-mirror + docs sync | `.claude/harness-spec.md`, `.codex/agents/serenity-scorecard.toml` (new) |

Validation gates (run after D6/D7 and again at the end): `scripts/serenity_harness.py validate` must be green; the harness-creator validator (`~/.claude/skills/harness-creator/scripts/validate_harness.py --path .`) must exit with 0 errors; every hook edit must pass its `test_hook.py` fixture set (§9-§10) before being called done.

**Two verification items to run FIRST, before any component is written** (both are assumptions the design leans on):
1. Confirm a custom `.claude/agents` agent actually receives project CLAUDE.md context in this Claude Code version (built-in Explore/Plan agents do not; customs are believed to). If it does NOT, the D5 agent body must additionally inline compressed forms of N2, N7, N9, N10. Check with a trivial spawn test.
2. Confirm the launcher mechanics available in the implementing environment: the Agent tool's parameter is `subagent_type`; inside a dynamic-workflow script the equivalent `agent()` option is `agentType`. D3's skill text names the Agent-call form as primary precisely because it is the one that exists everywhere; do not write workflow-only phrasing into SKILL.md.

---

## 4. D1 — CLAUDE.md doctrine fix (the ranking precedence)

**Why:** CLAUDE.md's two E-type lines contradict the analysis skill's ladder section. The unified design keeps both texts' truth by separating roles: gates decide *membership*, stage decides *order and size*, gate-strength + conviction order *within* a rung.

**Edit 1** — CLAUDE.md line 95 (the "One funnel" E entry). Current text (verbatim):

> `- **E — Theme / rank**: fan the same winner-gate across names, sort by gate-strength + conviction.`

Replace with:

> `- **E — Theme / rank**: run the fixed rank-N protocol (analysis skill, "Rank-N protocol") — gates filter membership, stage rung is the ordering spine, gate-strength + conviction order within a rung.`

**Edit 2** — CLAUDE.md line 122 (the "How the answer reads" E template). Current text (verbatim):

> `- **E:** names by archetype → ranked by gate-strength + conviction → per name a standout metric, PT + timeframe, key risk → grouped into conviction tiers.`

Replace with:

> `- **E:** gate-filter first (excluded names listed with the failed gate) → survivors placed on stage rungs (the ordering + sizing spine) → within a rung, gate-strength + conviction → conviction tiers as the output, within-tier order explicitly flagged low-confidence; per name a standout metric, PT + timeframe, key risk; close with deltas vs the prior ranking when one exists in sessions/.`

Keep the surrounding lines untouched. The full protocol lives in the analysis skill (D3); CLAUDE.md carries only the always-loaded contract, per the layer-routing bar ("does literally every session need this line").

## 5. D2 — CLAUDE.md session-archive convention

**Why:** analysis work currently evaporates at session end, so every session re-derives from zero and variance reads as random re-rolls. A durable archive turns variance into tracked conviction updates (V9) and makes post-mortems (V7) possible for the first time. Retrieval (INDEX) and staleness rules are as load-bearing as storage — a pile of unfindable files helps nobody, and a stale number silently reused is worse than no memory.

**Edit:** append a new short section to CLAUDE.md, after the "How the answer reads" section (before "The thesis DB is an answer key"). Draft text (adjust wording to the spine's voice; keep it lean — the spine is 144 lines):

```markdown
## The session archive — analysis survives the session

Every substantive analysis (a B/C/E verdict, a macro regime read worth keeping) is SAVED, in English, to `sessions/{yymmdd}.{topic-slug}/` — created lazily on the first artifact, never pre-created, and **never write into a session folder this session didn't create** (on a name collision, suffix `-2`). One file per name (`TICKER.md`, the fixed scorecard pinned in the serenity-scorecard agent), `_ranking.md` for a rank/basket synthesis, `_macro.md` for the regime read the analysis leaned on. After writing, add one line to `sessions/INDEX.md` — date · type · tickers · folder, **no verdicts in the index** (an index line that carries the old call anchors the next read before fresh judgment has formed). Close a saved answer with a visible `Saved: sessions/{folder}/` line — the Stop-gate checks the mark and that the folder really holds artifacts.

Two rules make the archive safe to reuse:
- **Numbers expire, structure doesn't.** Never use a number from a prior session file as a current input — re-run the pipeline; what carries over is the judgment structure (tier, thesis, falsifier). The one exception: inside a delta line, the prior number may be quoted tagged as-of-then ("fwd P/E 34 (as-of 260711) → 39").
- **Fresh judgment first, comparison second.** On a repeat question, finish the new scorecards/tiers from fresh evidence BEFORE opening the prior session's ranking, then explain every tier delta (evidence delta / owned judgment revision / cohort delta). Reading the old ranking first anchors you; skipping the comparison hides drift. Both failure modes are the point of the rule.
```

## 6. D3 — the Rank-N protocol (rubric) in serenity-analysis

**Where:** `.claude/skills/serenity-analysis/SKILL.md`. Two edits.

**Edit A — the ladder-header reconciliation** (review finding: the plan's own "sessions follow whichever text is loaded" standard was failing at the exact insertion point). Current §3 header (verbatim, line 145):

> `## 3 — Cycle stage (an evaluation lens — how early & de-risked — never a sizing one)`

Replace with:

> `## 3 — Cycle stage (on ONE name an evaluation lens — how early & de-risked; on a basket the ladder below is also the sizing spine)`

**Edit B — the new protocol subsection**, inserted immediately after the "### The 5-stage ladder…" subsection (which ends at the line "**stage-drives-size** is the signature meta-move…", currently line 166).

Content to add (draft — keep the skill's voice; the *why* lines are load-bearing, not decoration):

```markdown
### Rank-N protocol — the fixed procedure for "rank these N names"

A ranking improvised per-session is a different ranking per-session — the criteria, precedence, tie-breaks, and even what a "tier" means silently re-invent themselves, and the output reads as random. So on any rank/basket ask the DECOMPOSITION is fixed; every judgment inside it stays yours. Fixed: the scorecard fields (pinned in the serenity-scorecard agent — read its body for the schema when filling scorecards inline), the precedence, the tie-breaks, the tier form, the output contract. Never fixed: thresholds, weights, or any formula that would assign a tier for you — a composite score is the deleted legacy screen reborn, and you'd defer to it and stop reasoning.

**Step 1 — one scorecard per name, identical procedure.** For N ≥ 5 names, fan out one agent per name — an Agent call with `subagent_type: 'serenity-scorecard'` (or, where dynamic workflows are available, `agent()` with `agentType`), each writing `sessions/{folder}/TICKER.md`. Run `macro` ONCE, write the exact regime summary you will hand the agents to `sessions/{folder}/_macro.md` (with the run's as-of time), and pass that text verbatim to every agent — per-name macro re-reads would let the regime drift mid-cohort. **The launch message is part of the pinned surface** — exactly this template, nothing more: `ticker: {T} | folder: sessions/{folder}/ | peers: {cohort tickers} | regime: {verbatim _macro.md text}`. No per-name color ("the obvious Tier 1") — an editorialized launch biases the fresh context the fan-out exists to create. Under 5 names, fill the same scorecards inline, same schema, same blindness-to-priors until Step 4.

**Step 2 — the fixed precedence.** Rank from the scorecard FRONTMATTER blocks (open a body only to resolve a declared tie — 30 full bodies in one context recreates the compaction problem the fan-out just solved):
1. **Gate = membership.** A binary disqualifier (no real revenue, dishonest mgmt, no economic anchor — V2) excludes the name to a listed "EXCLUDED, failed <gate>" row. `conditional:` gates rank within their rung below all clean passes and cap the name out of Tier 1 until the named condition resolves. `blocked:` (an N9 data-integrity hard-block the scorecard couldn't reconcile) goes to a separate "UNRESOLVED — needs main-thread filings read" row: never silently tiered, never counted as a failed gate. Gates are a filter, never rank #1-vs-#2 fuel.
2. **Stage rung = the spine.** Survivors order and size by their rung — stage-drives-size is the meta-move, and it is also what discovery's "rank by de-risk, not by cheapness" demands. A stage-5 name cannot enter Tier 1/2 regardless of gates: it lands in the named "EXIT/TRIM" row (the ladder already says so; the row makes it reproducible).
3. **Within a rung: gate-strength first, conviction breaks what's left.** (One combinator, fixed — two axes with no order is the doctrine-fork this protocol exists to kill.)
4. **Still tied: explicit tie-breaks, in order** — (a) the FLOOR leg's valuation gap as a fraction of current price, read off each name's own `Lens:` line (normalized, cross-lens comparable, still your arithmetic — never a content threshold); (b) vehicle practicality (liquidity, US-listing rung, IV tier — from the `vehicle:` field, sourced per N2 or marked unavailable). Never invent a new criterion mid-ranking; if the four steps can't separate two names, SAY they're tied.

**Step 3 — draft tiers, cohort-independent.** A tier is a function of the name's OWN scorecard (stage, gates, conviction) — cohort composition may never move a tier; adding five strong names to the ask must not demote a name whose own evidence didn't change. Tiers: 1 (core) / 2 / 3 (watch) / EXIT / EXCLUDED / UNRESOLVED. State the cut you used in one visible line (`Tier cut: …`) — the cut stays your judgment, but an unstated cut is unauditable and a changed cut is invisible.

**Step 4 — reconcile against the prior, ONLY NOW.** If a prior ranking overlaps this cohort (INDEX is verdict-free by design — a ticker grep tells you priors exist without showing you their calls), open it after your tiers are set. Diff the REGIME first: if `_macro.md` texts differ materially, a cohort-wide tier shift has one named cause — attribute it before touching per-name lines. Then reconcile the intersection only (list additions/departures explicitly; carry prior EXCLUDED verdicts forward for re-check). Every name whose tier moved gets one line with one of three labels: **evidence delta** (the named number, prior value quoted as-of-then), **judgment revision** (owned explicitly), or **cohort delta** (within-rung order / tie-break effects — legitimate, but if a cohort delta moved a TIER, your tiers weren't cohort-independent; fix the tiers, not the label). Also diff the `Tier cut:` line — a changed cut rule is itself a named delta. A tier that moved with no label is the failure this whole protocol exists to prevent; say so and re-check.

**Step 5 — archive, then answer.** Finalize `_ranking.md`: the tier table in the fixed format `| ticker | tier | rung | gates | one-line why |` (tiers from the list above — the table is what `serenity_harness.py rankdiff` parses, so keep the columns exact), the `Tier cut:` line, and a `## Deltas vs {prior-folder}` section carrying Step 4's lines (deltas live HERE, not in per-name scorecards — the scorecard agents can't see priors and shouldn't). Update `sessions/INDEX.md`, close the answer with `Saved:`.
```

**Consolidation note (agreed):** this lands as a subsection of the existing skill, NOT a new skill — skill count is a real cost and the ladder it extends already lives here.

## 7. D4 — `sessions/` bootstrap

Create `sessions/INDEX.md` with a self-documenting header (the format doc lives in the index itself so it never drifts from usage). **Index lines are verdict-free** (review finding: a one-line call in the index is a compressed verdict read at retrieval time — exactly the pre-judgment anchoring the fresh-first rule forbids; retrieval needs only date/type/tickers, and calls live inside the folder's files):

```markdown
# Session index — one line per saved session folder, newest first

Format: `- [{yymmdd}.{topic-slug}]({yymmdd}.{topic-slug}/) — {type}: {tickers}`
Types: ranking | analysis | macro | postmortem. English only. NO verdicts/calls in this file — an index line that says what you concluded anchors the next session before its fresh judgment forms; a ticker grep is all retrieval needs. Numbers inside session files EXPIRE — re-run the pipeline; reuse only tiers/theses/falsifiers, prior numbers quotable only inside delta lines tagged as-of-then (see CLAUDE.md, "The session archive").

<!-- entries below -->
```

`sessions/` is **tracked in git** (agreed): text-only, small, and the diff history of scorecards is the audit trail of conviction changes — the raw material for post-mortems. Do not add it to `.gitignore`. Committing session files stays in the user's normal flow — do NOT auto-push analysis content.

## 8. D5 — `.claude/agents/serenity-scorecard.md` (new agent)

**Why an agent and not a prompt:** the per-name instructions are the reproducibility-critical surface. Pinning them in a version-controlled agent definition means every name in every session receives byte-identical instructions, regardless of how the launcher was phrased that day. The launcher's *message* is pinned separately by D3's template — both halves of the input must be pinned, or the free half re-imports the variance.

Frontmatter: `name: serenity-scorecard`; `tools: Bash, Read, Grep, Write`; description along the lines of: "Fills Serenity's fixed per-name scorecard for one ticker as part of a rank-N cohort — runs the pipeline, applies the archetype/gate/stage/lens judgment, writes `sessions/{folder}/TICKER.md`. Invoke one instance per name during a ranking fan-out; not for full single-name deep dives (main-thread B-type reads go deeper)."

**The agent body carries the scorecard schema verbatim** (review finding: the schema previously had no on-disk home — this file IS its single source of truth; D3's inline path reads it from here):

```markdown
---
ticker: NVDA
type: scorecard            # scorecard | analysis (main-thread deep dive reusing this schema)
session: 260718.rank-ai-supply-chain
date: 2026-07-18
data_as_of: 2026-07-18T09:32Z   # wall-clock of the pipeline run this file quotes
archetype: chokepoint      # chokepoint | disruption | evolution (+ subtype in body) | UNRESOLVED:<nulled line>
stage: 4                   # ladder rung 1-5
gates: pass                # pass | fail:<gate> | conditional:<which> | blocked:<line>
conviction: high           # high | medium | low — this name's own, never cohort-relative
gate_strength: "all gates clean; inverse-proxy moat evidence"   # one clause
vehicle: "deep options chain, IV ~45%"                          # one clause, per N2 from pipeline data, or "unavailable"
mc: "$3.2T"                # verbatim from key_facts
---
## Structural position        (archetype + the shape named, chain position)
## Forward revenue trajectory (from pipeline evidence, stage-rung justification)
## Lens                       (the literal `Lens:` line(s) — both legs on a forked lens)
## Winner-gates               (each gate: verdict + the evidence line)
## Downsides                  (2-4 bullets, each tagged priced-in / addressed)
## Falsifier                  ("breaks if …")
```

No `tier` field and no delta section — tiers and deltas belong to `_ranking.md` (the synthesizer's file); a scorecard that carries a tier invites the agent to rank, and it can't see the cohort.

Body must additionally cover (draft the full text during implementation, modeled on `serenity-filings.md`'s structure — mission, hard rules, how-to, return contract):
1. **Mission:** produce ONE name's scorecard exactly per the schema above; the caller passes ticker, session folder, peers, and the regime summary via D3's fixed template — treat the regime text as given, never re-derive it, and **ignore any caller-provided characterization of the name beyond the ticker** (defense against an editorializing launcher).
2. **Procedure:** run `scripts/.venv/bin/python scripts/serenity_pipeline.py analyze TICKER --skip-macro`; reason ONLY from its JSON (`key_facts` verbatim — N2/N7 apply in full). For disclosure numbers the income statement doesn't carry, run the `serenity_filings.py` CLI directly (`segments`, `xbrl-facts` — cite the concept). **When the archetype is inherently comparative (neocloud / commodity-capacity / margin-inflection / countable-end-unit) or check 6 demands a chain-sibling rank, run `serenity_pipeline.py discover TICKER PEER1 PEER2 …` using the launcher's `peers:` list** (adding an obviously-missing sibling is allowed — name why) — the cross-peer ratio is that archetype's lens, and pipeline output preserves blindness (review finding: without this, N10/R5 is unsatisfiable here — the standalone multiple is exactly the consensus read doctrine bans).
3. **Judgment scope:** name the archetype (running N9's two forks first), run the winner-gates, place the stage rung from the name's own trajectory evidence, RUN the archetype's lens (both legs on a fork) on a visible `Lens:` line. On an N9 data-integrity hard-block the agent cannot reconcile (the serenity-filings *agent* is not invocable from in here, and its CLI may not resolve the line): set `gates: blocked:<line>` / `archetype: UNRESOLVED:<line>` and say what the main thread must fetch — never "proceed structurally". Do NOT assign a tier and do NOT read other names' scorecards — comparison is the synthesizer's job.
4. **Blindness rule (by pinned rule, verified in the smoke test — the toolset cannot physically prevent it):** never read prior `sessions/` content or sibling scorecards. The only file this agent writes is its own `TICKER.md`; the only inputs are the launcher template, pipeline output, and its own filings pulls. The smoke test asserts the transcript contains no `sessions/` reads; if real use shows slippage, escalate to a PreToolUse deny on `sessions/` reads for this agent (§13).
5. **Output:** write the scorecard file (English), return only "written: <path>" plus a one-line standout fact — the caller synthesizes from files, not from return text.

## 9. D6 — `verdict_gate.py` extension (the `Saved:` mark)

**Design (matches the hook's existing structural-contract philosophy — check marks, never semantics):** a formatted market answer carrying `strong_verdict` OR `single_name` signals (reuse the existing regexes; a casual macro comment should not demand an artifact) should carry a visible `Saved:` line per D2's contract. Checks, all SOFT (same calibration policy as the `Lens:` check — promote to hard only after real use shows no false-fires, and note the promotion raises the empty-artifact-bypass stakes, which is why the shape checks below exist):

- Mark present? Parse the first `Saved:` line with a capture that tolerates markdown and rejects wrong shapes: `` Saved:\s*`?(sessions/\d{6}\.[a-z0-9-]+(?:-\d+)?/?) `` then strip trailing `` `.,; `` before checking (review finding: the naive `[^\s]+` capture swallowed a closing backtick and false-fired "claimed-but-not-done" on true claims).
- Path is a real session folder? `os.path.isdir()` under `CLAUDE_PROJECT_DIR` (fall back to cwd; verify which is set when the hook runs — do this during implementation, it's one print statement) AND the directory contains ≥1 `.md` file (review finding: bare `exists()` passes on `Saved: sessions/INDEX.md` or an empty `mkdir` — a costless compliance token that would falsely certify archiving). Content *quality* stays unchecked — that honest residual is stated in the hook's docstring and is why the check stays soft longer.

Nudge text, short, quoting the convention: "this verdict isn't archived — write the scorecard/synthesis to sessions/{yymmdd}.{topic}/, update INDEX.md, and add the `Saved:` line (CLAUDE.md, 'The session archive')."

**Fixtures (review finding: the "existing 7 scenarios" exist only as names in harness-spec.md line 44 — the payloads were ad-hoc and never committed, so "re-run" was not executable).** Create `.claude/hooks/tests/` holding one JSON payload file per scenario plus a short README documenting the invocation (`test_hook.py --command .claude/hooks/verdict_gate.py --event Stop --input <file>`, expected outcome noted per file). Reconstruct the legacy 7 from their names (silent / soft-lens / hard-NFI / coding-silent / macro-hard / meta-silent / bear-leg-soft — note a "silent" market fixture must simultaneously satisfy NFI + `Lens:` with ×/÷ and = + Downsides + falsifier + a valid `Saved:` mark to stay silent under ALL branches), and add the new set:
1. finance verdict + no `Saved:` → soft nudge
2. finance verdict + valid mark + folder with ≥1 .md → silent
3. valid-shaped mark + folder missing → soft nudge naming the false claim
4. mark = `sessions/INDEX.md` (wrong shape) → soft nudge
5. valid-shaped mark + empty folder → soft nudge ("claimed-but-empty")
6. backtick-wrapped valid mark → silent (regex tolerance)
7. coding/harness answer with TL;DR, no finance signal → silent (false-fire regression guard)

All must pass via `test_hook.py` before D6 is done — not optional.

## 10. D7 — `evidence_discipline.py` retrieval nudge (one line)

Storage without retrieval is half the feature; the load point for "check prior work" is prompt-time. Add ONE line to the hook's existing equity-prompt action list: "If sessions/INDEX.md lists these tickers, plan to reconcile deltas AFTER fresh scorecards — never re-derive blind, never read the old ranking first (the index is verdict-free; a ticker grep is safe)." Keep the meta/dev-prompt false-fire guard untouched; no filesystem reads in the hook itself.

Fixtures: same treatment as D6 — the 8 legacy intent/meta-guard cases exist only as a count in harness-spec.md; re-derive them from the hook's actual branches, commit them under `.claude/hooks/tests/`, add one new equity-prompt case asserting the new line appears, and pass all via `test_hook.py`.

## 11. D8 — `serenity_harness.py`: validate extension + `rankdiff`

**Validate additions** (keeping the script's existing report style): (a) `.claude/agents/serenity-scorecard.md` exists, frontmatter parses with expected `name`/`tools`, and its body contains the schema's sentinel fields (`gate_strength:`, `conviction:`); (b) CLAUDE.md contains the `The session archive` heading and the literal `Saved:` token; (c) `sessions/INDEX.md` exists and its header contains the verdict-free rule. Do NOT validate sessions/ *content* — runtime data, not harness wiring.

**New subcommand `rankdiff A_ranking.md B_ranking.md`** (review finding: v1 previously shipped variance-reduction machinery with zero instruments able to observe variance — and the calibration decisions in §13 depend on observations nothing was collecting). ~30 lines, deterministic, no judgment: parse each file's fixed tier table (`| ticker | tier | rung | gates | … |`), print per-ticker tier A→B, the agreement count/percentage over the intersection, tickers only-in-A / only-in-B, and whether the two `Tier cut:` lines differ. This is fact-loading (diffing two files the analyst already wrote), squarely on the code side of the fact/judge seam. Every future repeat-ranking in the archive then yields a free reproducibility measurement.

## 12. D9 — spec + mirror + docs sync

Update `.claude/harness-spec.md` in the same implementation pass (hard line: spec and disk never drift silently):
- **Layer routing table:** add the `sessions/` archive row (layer: convention in CLAUDE.md + verdict_gate mark; why: cross-session memory turns variance into tracked conviction updates) and note the new agent under the agents row.
- **Components:** agents (2) — add serenity-scorecard with its one-line mission; hooks — verdict_gate's `Saved:` branch, evidence_discipline's added line, and the now-committed fixture directory; skills — the Rank-N protocol subsection; validator — the new checks + `rankdiff`.
- **Validation:** point at `.claude/hooks/tests/` as the now-real fixture home.
- **Change history:** date + summary, referencing this plan file by path.

**Codex mirror** (review finding: the spec's Mirror paragraph documents manually-maintained `.codex/agents/*.toml` translations — a new agent silently breaks that convention): create `.codex/agents/serenity-scorecard.toml` modeled on `serenity-filings.toml`, or — if the user prefers — record explicitly in the Mirror paragraph that the scorecard agent is Claude-Code-only and why. Default to creating the toml; ask only if its format proves non-obvious.

Also append a dated entry to this plan's **Implementation log** (§17) as steps complete.

## 13. Risks, mitigations, and honest limits

- **Residual sampling noise:** tier boundaries can still flip for names genuinely near a boundary. The protocol makes that visible (the three-label delta rule forces attribution) rather than pretending it away. This is the accepted floor of the design.
- **The tier cut itself stays judgment:** Step 3 pins the *form* (cohort-independent, stated cut line, fixed tier vocabulary) but deliberately not the mapping content — pinning "stage-4 clean-gates ⇒ Tier 1" would be a content threshold (§1). The stated `Tier cut:` line + rankdiff's cut-diff is how cut drift becomes visible instead of silent.
- **Anchoring (the memory trade-off):** mitigated by rule and by sequence (agents never see priors; the synthesizer opens priors only after tiers are set; the INDEX is verdict-free so retrieval can't leak calls). NOT physically enforced — the agent's toolset can read anything; the smoke test asserts no `sessions/` reads in agent transcripts, and a PreToolUse deny on `sessions/` for this agent is the pre-planned escalation if slippage is observed.
- **Advisory-layer slippage:** the archive convention is prose; the deterministic backstop is intentionally soft (one nudge). Promotion to hard is pre-authorized by the same calibration policy the `Lens:` check carries — but only together with the shape/non-empty checks (§9), which exist precisely because a hard gate invites the empty-artifact bypass.
- **INDEX growth:** hundreds of lines eventually. Not a v1 problem; when it bites, prune to `sessions/ARCHIVE-INDEX.md` (note only — no action now).
- **Assumption checks:** the two verification items in §3 (custom-agent CLAUDE.md context; launcher parameter names) run before any component is written.
- **Cost:** a 30-name fan-out is ~30 pipeline runs + 30 agent contexts per ranking. That is the price of uniform context; the user accepted it for rank-N asks. Do not silently downgrade to inline mode on a large cohort to save tokens — say the cost and let the user choose.

## 14. Deferred (explicitly out of scope for the implementation session)

- **B5's LLM-driven consistency-eval axis** (blind re-runs scored by a judge, extending `serenity_eval.py`): deferred for cost. What is NOT deferred — per the review — is the deterministic half: `rankdiff` (D8) ships in v1, and §15's smoke test runs the same cohort TWICE so the first reproducibility datapoint exists on day one. "Revisit after the archive has accumulated a few real rankings" now has an instrument waiting.
- **Fixed `.claude/workflows/rank.js`:** promote the launcher to a one-button workflow file only if the composed-on-the-fly plumbing proves flaky in practice. Note the launch-message template (D3 Step 1) already pins the judgment-bearing part of the launcher, so this deferral no longer leaves an unpinned surface.
- **PreToolUse blindness enforcement** for the scorecard agent: escalation path only (§13), not v1.
- **Any composite scoring, any content thresholds in the rubric:** permanently out, by design (§1).

## 15. Acceptance checklist for the implementation session

- [ ] §3's two verification items run FIRST; outcomes noted in the Implementation log (they can change D5's body and D3's launcher phrasing)
- [ ] D1-D9 implemented in order; each CLAUDE.md/SKILL.md edit matches the verbatim old-text anchors in this plan (if a file drifted since 2026-07-18, reconcile against the *intent*, and note it in the log)
- [ ] `scripts/serenity_harness.py validate` green (all checks, including the new ones); `rankdiff` runs on two hand-made fixture rankings
- [ ] harness-creator `validate_harness.py --path .` → 0 errors
- [ ] `.claude/hooks/tests/` fixture sets committed and ALL passing via `test_hook.py` (legacy-reconstructed + new, both hooks)
- [ ] `.claude/harness-spec.md` and the Codex mirror updated in the same pass
- [ ] Optional (user consent — real tokens): the smoke test is TWO live runs of the same 3-name cohort in separate sessions, diffed with `rankdiff` — one run cannot observe reproducibility; record both outcomes in the log
- [ ] Commit with a message referencing this plan; push to origin

## 16. Adversarial review log (2026-07-18, pre-finalization)

Three independent reviewers (doctrine-consistency, implementation-feasibility, goal red-team) attacked the draft; 20 findings, all folded above. The load-bearing ones, kept here so the implementer knows *why* the rules exist:

- **Blocker — tier form unpinned:** success was defined on tier stability, but nothing declared tiers cohort-independent, gave stage-5 a destination, or made the tier cut auditable. → Step 3's form pins + the `Tier cut:` line + rankdiff's cut-diff.
- **Comparative-lens dead-end:** the agent's no-comparison rule made N10/R5 unsatisfiable on inherently-comparative archetypes. → the `discover`-with-peers allowance (pipeline output preserves blindness).
- **Schema had no home; synthesis lacked its inputs:** → schema lives verbatim in the agent body; frontmatter gained `conviction` / `gate_strength` / `vehicle`; synthesis ranks from frontmatter.
- **Delta mechanics contradicted themselves:** the blind agent owned a delta section it couldn't fill; the no-reuse rule banned the delta format. → deltas live only in `_ranking.md`; the as-of-then quote exception.
- **Same-day re-ask destroyed its own baseline:** folder collision + archive-before-reconcile ordering. → never-write-into-a-foreign-folder rule; reconcile (Step 4) before finalize (Step 5).
- **The index anchored the next session; the `Saved:` mark was gameable; regressions weren't runnable; the mirror drifted; the launcher leaked judgment** — each addressed where cited above.

## 17. Implementation log

<!-- The implementation session appends dated entries here. -->
