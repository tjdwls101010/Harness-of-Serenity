# Harness spec — Serenity

The record of what this harness is and why each piece sits in the layer it sits in. Regenerated 2026-07-09 from disk + the design-review plan (`.tmp/plans/2026-07-09-harness-design-review-plan.md`). The next audit compares against this; keep it in sync with every component change.

## Goal

Make Claude embody "Serenity," a supply-chain-architect equity analyst, reproducing his *method* (map where economic power structurally concentrates before consensus prices it; name the archetype, run the winner-gates, run the demanded valuation lens with arithmetic, rate the name) — not a fixed set of past calls. The one design invariant everything serves: **code loads facts, Claude judges.** Deterministic code loads the objective numbers (yfinance financials, SEC XBRL disclosure) so no judgment is baked into code where it would drift silently run-to-run; every verdict, archetype tag, and rating is Claude's.

## Design thesis (the standard every component is held to)

Serenity's methodology is tacit — it cannot be enumerated "case X → action Y." So:
- **Facts** (enumerable, verifiable) → deterministic code, identity checks, structural output-contract checks.
- **Judgment** (not enumerable) → re-derivable principles with their *why*, worked examples / war stories, and the model's own intelligence.
- **Reproduction assurance** (can't be added by more rules) → measurement (the §5 eval), where a missed move feeds back as a *generalized* principle, never a new case-rule. Bloat's root cause is per-miss patching (a miss → a case-targeted rule → the spine grows → the 17th case still uncovered); the cure is generalization, not accretion.

## Layer routing — what lives where and why

| Layer | Holds | Why here |
|---|---|---|
| **CLAUDE.md** (spine, always loaded) | voice, the six roots + ten values, the archetype funnel + routing reflexes, the five/six pre-answer checks, the answer contract (A/B/C/D/E templates + the `Lens:` line), the ten non-negotiables | every session needs these; the bar for a line is "does literally every turn need it" |
| **skills** (`.claude/skills/*`, on-demand) | the situational depth that bites once the JSON is in front of you — macro (regime + catalyst), discovery (find a US-listed name), analysis (gate/value/time/rate one name) | triggered by `description`; body loads only when the question type needs it |
| **hooks** (`.claude/hooks/*` + `settings.json`, deterministic) | the four points where determinism earns its process cost — session-start self-check, prompt-time action nudge, post-analyze identity tripwire, answer-end verdict contract | advisory layers can be skipped under output pressure; a hook fires regardless |
| **agent** (`.claude/agents/serenity-filings.md`, context-isolated) | the filing's honest reader — extracts objective relationship facts (named counterparties, country %, financing structure) verbatim, renders no judgment | a context-hungry read-heavy role where only the extracted facts come back |
| **pipeline** (`scripts/`, deterministic) | the fact loader — `serenity_pipeline.py` (yfinance financials + macro gauges), `serenity_filings.py` (edgartools XBRL for the agent). `pipeline/legacy/` is the quarantined judgmentful old pipeline (reference only) | numbers must be byte-stable and judgment-free; the seam drops every judgment label before the agent sees the evidence |
| **eval** (`scripts/serenity_eval.py` + `scripts/eval/`, user-triggered) | the reproduction-measurement harness — sampler + rubric + report (deterministic) and a blind-run/judge workflow (token-spending); measures method reproduction on real past theses | not runtime; reads the thesis DB as an answer key, so explicit-trigger only (N8) |

## Components

**CLAUDE.md** — the spine. Self-contained doctrine; the skills rely on its non-negotiables and never restate them.

**Skills (3)** — `serenity-macro` (aggression dial + catalyst gate), `serenity-discovery` (finding an under-priced US-listed name; owns chain-tracing, the DEDUCED-vs-CONFIRMED discipline, the US-listed resolution ladder), `serenity-analysis` (the single-name engine; owns the archetype playbooks, winner-gates, valuation lenses, the falling-knife 4-step, entry/vehicle/kill). Organized by funnel step, not archetype — the valuation lens forks on capital structure, which cuts across archetypes, so an archetype split would not reduce load.

**Hooks (4)** — `session_status.py` (SessionStart: runs `serenity_harness.py validate`, silent when green, loud when red), `evidence_discipline.py` (UserPromptSubmit: three just-in-time actions — pipeline-first, dated-catalyst scan, lens-at-intake — plus a meta/dev-prompt false-fire guard), `data_integrity_guard.py` (PostToolUse/Bash: recomputes balance-sheet identities after `analyze`, flags a phantom/stale/collision number), `verdict_gate.py` (Stop: a STRUCTURAL contract — hard-blocks a market verdict missing NFI/NFA; soft-nudges a valuation verdict missing the `Lens:` driver line or running only the bear leg). All exec-form in `settings.json` (an `args` array, not shell-form — shell-form let a shell-profile banner silently no-op a JSON-emitting hook).

**Agent (1)** — `serenity-filings` (tools: Bash, Read, Grep). Extract-never-judge; silence is null; quote + cite.

**Validator** — `scripts/serenity_harness.py validate` (12 checks: spine + skills present, pipeline imports, the fact/judge seam, the 4-hook wiring, the SEC layer). Green = 12/12.

**Mirror** — the harness is mirrored for the Codex / AGENTS CLIs: `AGENTS.md` → `CLAUDE.md` (symlink), `.codex/hooks` → `.claude/hooks` and `.codex/skills` → `.claude/skills` (symlinks, so content auto-syncs), plus manually-maintained Codex translations `.codex/hooks.json` and `.codex/agents/serenity-filings.toml`. (The `.agents` → `.claude` symlink was retired 2026-07-09.)

## Validation

- `scripts/serenity_harness.py validate` → 12/12 green.
- Hooks: `test_hook.py` for wiring; verdict_gate has 7 scenario fixtures (silent / soft-lens / hard-NFI / coding-silent / macro-hard / meta-silent / bear-leg-soft); evidence_discipline has 8 intent/meta-guard cases.
- Pipeline: `scripts/tests/test_evidence_contract.py` (the fact/judge seam is judgment-free) + a fixture-based `evidence --fixture` smoke.
- Reproduction: `scripts/serenity_eval.py` — baseline before a doctrine edit, re-run after, compare per-move rates.

## Change history

**2026-07-09** — design-review implementation (plan `.tmp/plans/2026-07-09-harness-design-review-plan.md`):
- **§3 hooks (Session A)**: shell-form → exec-form (bug fix); cut `web_number_guard` + `subagent_discipline` (each re-stated context already present at the same lifecycle point); slimmed `evidence_discipline` to three actions + a meta-prompt guard; redesigned `verdict_gate` as a structural `Lens:`-token contract and fixed the hard-block to gate on a finance signal, not a bare TLDR; dual-class wording on the data-integrity flag.
- **§5 eval (Session B)**: built the reproduction-measurement harness (`serenity_eval.py` + `scripts/eval/`).
- **§1/§2 dedup (Session C)**: conservative spine dedup (NN#9/NN#10 enumerations → skill pointers; hardware-relabel pointer) and one clean skill removal (macro INVARIANT #7). NOT done: demoting check-6 — the baseline eval proved recursive-bottom-hop / 2nd-order are the weakest-reproduced moves, so thinning them was contraindicated. Measured: baseline 72% → after 70% overall (seed 7, same 6 cases), inside the n=6 noise floor — every per-move Δ is a single stochastic judge flip, so no regression. Instrument note: at n=6 the ±~17%/move noise + judge n/a-vs-0 stochasticity means the eval detects only GROSS regressions; a sensitive before/after wants larger n and a deterministically-scoped rubric.
- **§4 code (Session D, partial)**: moved the legacy-only `cockroach_effect` judgment out of the live `_postprocess.py`; pinned the edgartools version note. Deferred: the bottleneck dead-surface move (4-1/4-2) and the trend_direction removal (4-4) — both are entangled with the quarantined legacy path or the golden test fixture, and the live evidence output is already judgment-free.
