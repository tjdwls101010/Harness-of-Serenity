# Appendix 03 — harness and evaluation

## Harness design

The harness should be lean at the root and deep only at the interface the current task needs. `CLAUDE.md`/`AGENTS.md` carries the product boundaries, hard evidence/lifecycle rules, user-facing style constraints, and routing to focused skills. It does not embed an ever-growing encyclopedia of archetypes, shell snippets, or old conclusions. The operative instruction is to use the typed runtime and artifacts; natural-language reminders are a safety net, not the source of fact identity or finalization validity.

Preserve the shared entry point: `AGENTS.md` remains a symlink to `CLAUDE.md`. Preserve a local `.codex -> .claude` symlink if and only if compatibility testing proves it works. This avoids duplicated doctrine and lets Claude and normal Codex consume the same local harness. It is not a substitute for independent evaluation, which happens in a separate cleanroom that allowlists only the materials needed for the test.

## Skills and agents

Create exactly four focused user-workflow skills, each with a clear trigger, required runtime artifacts, and stopping conditions:

| Skill | Scope | Required behavior |
| --- | --- | --- |
| `serenity-macro-event` | Regime, policy, macro, headline, selloff, and mechanical-catalyst questions | Create/consume cutoff-safe macro evidence; distinguish event facts from inference; state what would change forward economics. |
| `serenity-discovery` | Industry/sector/theme discovery and supply-chain mapping | Form competing chain/scenario hypotheses, build a typed sector graph where justified, resolve US-listed expressions, and surface no-clean-vehicle cases. |
| `serenity-single-name` | A named ticker’s structural, valuation, and conditional-entry research | Require identity snapshot, competing hypotheses, adaptive filing/evidence requests, valid lens before numeric target, bear case/falsifier, and action enum. |
| `serenity-cohort` | Candidate comparison/ranking without a hidden score | Keep a peer-blind candidate stage, enumerate exclusions/uncertainty, compare evidence and lenses, and avoid auto-ranking from provider fields. |

Add a typed `serenity-filings` agent responsible for reading filing narratives and structured disclosures through evidence requests. It returns evidence objects with accession/concept/location/time/provenance, does not infer a recommendation, and reports missing disclosure explicitly. Add a peer-blind cohort candidate agent that receives the discovery question and evidence rules but not prior candidate verdicts/rankings; it proposes or challenges candidates with traceable reasons. The main analyst synthesizes only after independent candidate work is recorded.

Use subagents with the default terra/sonnet tier for exploration, collection, and independent review. Reserve sol/opus for one final synthesis or disagreement adjudication stage, never broad fan-out. Agents must not overwrite artifacts owned by another active task; they return typed outputs or proposed patches through their assigned boundary.

## Hooks and harness validation

Replace broad natural-language enforcement hooks with two narrow typed hooks:

- A `SessionStart` soft health check verifies runtime availability, schema/harness wiring, required symlink state, and active-run summary. It emits actionable diagnostics but does not block ordinary work for transient provider failures.
- A typed `Stop` gate checks only for an OPEN run that attempted a final decision: it requires saved typed artifacts, validates the decision/lens rules, and blocks final answer completion only on a concrete lifecycle/contract violation.

Remove v1 hooks that parse or score arbitrary prose, invoke multiple hidden analysis rails, or make decisions from static fields. Every retained/generated hook must have a fixture-driven test through the harness creator test utility and be included in the harness validator. Update `.claude/harness-spec.md` to explain the v2 design, source of truth, hook inputs/outputs, recovery behavior, and why symlinks are preserved.

## Codex cleanroom E2E

Normal Codex uses the shared local symlinked harness. Independent Codex evaluation must instead create a temporary cleanroom outside the repository and copy only an explicit allowlist: v2 executable files, v2 schemas, required dependency metadata, public test fixture/case, and a case-specific input packet. It must exclude `CLAUDE.md`, `AGENTS.md`, `.claude/`, `.codex/`, `data/analysis_Serenity.db`, original corpus/media, old session artifacts, old verdicts/scores, and prior evaluation results.

The cleanroom runner records the exact allowlist, source file hashes, model/agent configuration, prompts, timestamps, network policy, command transcript, raw output hashes, and pass/fail criteria. It must assert exclusions before starting the agent and fail the test if a forbidden path is present or readable. This is the control against “same harness gives same answer” being mistaken for independent quality evidence.

## Evaluation architecture

Evaluation has three complementary tracks:

1. **A — historical independent-first:** construct a case with a cutoff and only information available by that cutoff; the model makes a fresh decision before any old corpus comparison. Measure decision-process invariants and later outcome observations separately.
2. **B — cutoff-frozen current packets:** use current code against a packet frozen at a documented cutoff to detect availability leakage, provider drift, and schema/provenance failures.
3. **C — prospective:** save a decision’s conditions and falsifiers, then append future checkpoints without rewriting its original thesis.

For each scored case, run deterministic validators first, then two independent Codex terra evaluations. Use one sol adjudication only if the deterministic layer or the two reviewers disagree materially. Record the disagreement and adjudication rationale; a consensus must not erase it. Evaluation results never collapse to one dashboard “quality score.”

## Required E2E families

Implement six families, each with two deterministic fixture cases and one live/provider-enabled case where source availability permits:

| Family | Invariants tested |
| --- | --- |
| Industry/sector discovery | Competing mechanisms, US-listed resolution, no fixed score/rank, evidence-backed candidate distinctions. |
| Single ticker | Identity pinned, adaptive evidence, lens/decision gates, conditional entry and bear case. |
| Physical AI | Recursive bottom hop, typed graph, sibling comparison, second-order actor/unresolved status, vehicle resolution. |
| Near-miss/no-clean-vehicle | Honest `PASS`, `MONITOR`, or `BLOCKED`; foreign/indirect vehicle limitation is preserved. |
| Degraded identity/data | Conflict/unavailable/stale data stay explicit; finalization/targets block appropriately. |
| Displacement/fear event | Mechanical claim is tested before sentiment inference; catalyst, forward economics, and falsifier remain separate. |

The deterministic cases live in `tests/260817/e2e/` and use checked-in typed fixtures. Live cases may be opt-in or marked separately from the default suite, but their reports must show exact provider/date state. Every family report includes raw numerator/denominator, failure taxonomy, case IDs, deterministic/live split, and a Wilson confidence interval where a pass-rate summary is useful. Never aggregate the six families into a claim such as “95% quality”; different failure classes have different safety meaning.

## Test layout and completion gates

```text
tests/260817/
  contracts/     # JSON-schema examples and invalid documents
  cli/           # one-JSON stdout, exit codes, lifecycle public seam
  adapters/      # mocked external provider boundaries and live-safe contracts
  artifacts/     # hashes, lineage, current pointer, append-only outcomes
  e2e/           # six families, cleanroom runner, deterministic fixtures
  fixtures/      # small JSON/SQLite/media/provider packets
```

No new v2 tests belong in `scripts/tests/`. Start every vertical slice with a test at one of these public seams; do not test private parsing helpers just because they are easy to call. At harness completion, run the full v2 suite, each hook fixture test, `scripts/serenity_harness.py validate` (or its v2 replacement) to zero errors, and the cleanroom exclusion/allowlist test. A live E2E failure is reported as evidence, not hidden by rerunning until it passes.
