# Appendix 03 — harness and evaluation

## Harness design

The harness should be lean at the root and deep only at the interface the current task needs. `CLAUDE.md`/`AGENTS.md` carries the product boundaries, hard evidence/lifecycle rules, user-facing style constraints, and routing to focused skills. It does not embed an ever-growing encyclopedia of archetypes, shell snippets, or old conclusions. The operative instruction is to use the typed runtime and artifacts; natural-language reminders are a safety net, not the source of fact identity or finalization validity.

Preserve the shared entry point: `AGENTS.md` remains a symlink to `CLAUDE.md`, and track `.codex -> .claude` after compatibility testing proves it works. This avoids duplicated doctrine and lets Claude and normal Codex consume the same harness after a clone. It is not a substitute for independent evaluation, which uses separately packaged candidate and reviewer boundaries.

## Skills and agents

Create exactly four focused user-workflow skills, each with a clear trigger, required runtime artifacts, and stopping conditions:

| Skill | Scope | Required behavior |
| --- | --- | --- |
| `serenity-macro-event` | Regime, policy, macro, headline, selloff, and mechanical-catalyst questions | Create/consume cutoff-safe macro evidence; distinguish event facts from inference; state what would change forward economics. |
| `serenity-discovery` | Industry/sector/theme discovery and supply-chain mapping | Form competing chain/scenario hypotheses, build a typed sector graph where justified, resolve US-listed expressions, and surface no-clean-vehicle cases. |
| `serenity-single-name` | A named ticker’s structural, valuation, and conditional-entry research | Require identity snapshot, competing hypotheses, adaptive filing/official-issuer evidence requests, management-claim versus operating-observation separation, valid lens before numeric target, bear case/falsifier, and action enum. |
| `serenity-cohort` | Candidate comparison/ranking without a hidden score | Keep a peer-blind candidate stage, enumerate exclusions/uncertainty, compare evidence and lenses, and avoid auto-ranking from provider fields. |

Add a typed `serenity-filings` issuer-evidence agent responsible for reading SEC narratives/structured disclosures and official issuer documents through evidence requests. For issuer IR it uses WebSearch/WebFetch only to locate an official issuer-owned URL, then requires `issuer-ir.document` to revalidate the domain from the attached live snapshot's raw SEC submissions payload and bind identity, publication time, every redirect hop, final URL, and raw bytes before the content becomes evidence; frozen snapshots cannot authorize this live fetch. It keeps prepared remarks separate from Q&A, management claims separate from hard operating observations, and disclosed/corroborated relationships separate from inferred/contradicted ones; omissions and cross-company read-through candidates remain explicit. It does not infer a recommendation. Add a peer-blind cohort candidate agent that receives the discovery question and evidence rules but not prior candidate verdicts/rankings; it proposes or challenges candidates with traceable reasons. The main analyst synthesizes only after independent candidate work is recorded.

Use subagents with the default terra/sonnet tier for exploration, collection, and independent review. Reserve sol/opus for one final synthesis or disagreement adjudication stage, never broad fan-out. Agents must not overwrite artifacts owned by another active task; they return typed outputs or proposed patches through their assigned boundary.

## Hooks and harness validation

Replace broad natural-language enforcement hooks with two narrow typed hooks:

- A `SessionStart` soft health check verifies runtime availability, schema/harness wiring, required symlink state, and active-run summary. It emits actionable diagnostics but does not block ordinary work for transient provider failures.
- A typed `Stop` gate checks only the content-hashed active-run pointer and referenced manifest. Any verified OPEN run is unfinished and blocks stopping until the runtime finalizes a typed decision, including `BLOCKED`, or records an explicit abandonment reason. Decision and lens validity remain runtime responsibilities; the hook never parses answer prose or grades research quality.

Remove v1 hooks that parse or score arbitrary prose, invoke multiple hidden analysis rails, or make decisions from static fields. Every retained/generated hook must have a fixture-driven test through the harness creator test utility and be included in the harness validator. Update `.claude/harness-spec.md` to explain the v2 design, source of truth, hook inputs/outputs, recovery behavior, and why symlinks are preserved.

## Codex cleanroom E2E

Normal Codex uses the tracked symlinked harness. Evaluation first creates a fresh candidate package outside the repository with a user-facing question, cutoff-safe typed evidence, and a content-hashed receipt of the shared Harness tree and symlinks. The inline model prompt loads only `CLAUDE.md` plus the skill or ordered skills selected for that family; agents, hooks, settings, and the specification remain integrity receipts rather than candidate instructions. One Terra candidate returns a strict typed research artifact and locale-neutral user artifact; the runner, not the model, binds trusted package, harness, model, transcript, and result hashes. The candidate receives no expected invariants, answer key, prior verdict, corpus answer, session, score, or previous candidate output, and the package records that hooks are not executed in this instruction-integration arm.

Independent review is a second boundary. Current deterministic v2 services execute outside the reviewer cleanroom and project typed outputs into case-specific raw observations bound to real output hashes. Each reviewer package contains exactly `qa-case.json`, `frozen-packet.json`, `qa-result.schema.json`, and `package-manifest.json`; its hash-bound prompt carries the candidate artifact and permitted evidence but no Harness files, candidate prompt, expected outcome, prior result, corpus, source checkout, or executable. A live provider capture is a non-citable transport checkpoint unless the case explicitly maps it to an invariant and proves identity and `available_at <= cutoff`.

Both runners record the exact allowlist, package and harness hashes where applicable, requested and resolved CLI, model/role, prompts, timestamps, network policy, audited transcript, raw output hashes, and semantic validation. The canonical documents are embedded in each hash-bound model prompt, so no filesystem tool is needed and every completed tool event is rejected. On macOS the outer Seatbelt profile broadly denies the repository, home, temporary storage, and pre-existing result trees, then permits only the active case/result directory, resolved Codex runtime, ephemeral auth copy, and exact Codex helper processes. `--search` is absent and child execution is denied outside that exact allowlist; hosted model transport remains a recorded parent-process residual because denying it would also prevent Codex from running. This separates shared-Harness candidate behavior from independent artifact quality review without requiring Docker or OrbStack.

## Evaluation architecture

Evaluation has three complementary tracks:

1. **A — historical independent-first:** construct a case with a cutoff and only information available by that cutoff; the model makes a fresh decision before any old corpus comparison. Measure decision-process invariants and later outcome observations separately.
2. **B — cutoff-frozen current packets:** use current code against a packet frozen at a documented cutoff to detect availability leakage, provider drift, and schema/provenance failures.
3. **C — prospective:** save a decision’s conditions and falsifiers, then append future checkpoints without rewriting its original thesis.

For each scored case, run deterministic validators first, one family-routed Codex Terra candidate through the shared-Harness snapshot, and then two independent no-Harness Terra artifact reviews. Use one Sol adjudication only if the two reviewers disagree materially at the invariant level. Record candidate, reviewer, disagreement, and adjudication receipts; a consensus must not erase its underlying records. Evaluation results never collapse to one dashboard “quality score.”

## Required E2E families

Implement six families, each with two deterministic fixture cases and one live/provider-enabled case where source availability permits:

| Family | Invariants tested |
| --- | --- |
| Industry/sector discovery | Competing mechanisms, US-listed resolution, no fixed score/rank, evidence-backed candidate distinctions. |
| Single ticker | Identity is pinned before an action is allowed; a conflict blocks action, while adaptive evidence, lens/decision gates, conditional entry, and bear case remain separate. |
| Physical AI | Recursive bottom hop, typed graph, sibling comparison, second-order actor/unresolved status, vehicle resolution. |
| Near-miss/no-clean-vehicle | Honest `PASS`, `MONITOR`, or `BLOCKED`; foreign/indirect vehicle limitation is preserved. |
| Degraded identity/data | Conflict/unavailable/stale data stay explicit; finalization/targets block appropriately. |
| Displacement/fear event | Mechanical claim is tested before sentiment inference; catalyst, forward economics, and falsifier remain separate. |

The deterministic cases live in `tests/260817/e2e/` and use checked-in typed fixtures. Live cases may be opt-in or marked separately from the default suite, but their reports must show exact provider/date state. Every family report includes raw numerator/denominator, failure taxonomy, case IDs, deterministic/live split, and a Wilson confidence interval where a pass-rate summary is useful. Never aggregate the six families into a claim such as “95% quality”; different failure classes have different safety meaning.

The current recorded E2E evidence is [`evaluation-report.v2.json`](evaluation-report.v2.json), with canonical content hash `e4e5ae498606ff4489cc06e5e0e587b9b7422165c57cb65d3ccf143878f1fb2d`: 18 cases passed, each family reported `3 / 0 / 0`, and the run contains 18 candidate plus 36 Terra reviewer receipts with no Sol receipt. This is distinct from retained diagnostic runs, which remain documented in the cutover evidence rather than being relabeled as final evidence.

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

All v2 tests live under `tests/260817/`. Start every vertical slice with a test at one of these public seams; do not test private parsing helpers just because they are easy to call. At harness completion, run the full v2 suite, each hook fixture test, `scripts/serenity_harness.py validate` to zero errors, and the cleanroom exclusion/allowlist test. A live E2E failure is reported as evidence, not hidden by rerunning until it passes.
