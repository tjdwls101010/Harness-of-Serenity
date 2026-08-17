# Harness of Serenity v2 implementation plan

## Decision record

This is a clean-slate v2 plan for a research operating system that helps a user discover US-listed industry, sector, and ticker opportunities, investigate a named ticker, and trace Physical AI or other supply-chain bottlenecks. It adopts the useful parts of the prior method without treating prior conclusions, ratings, or a fixed analytic funnel as truth. Its output is research and conditional entry logic, never portfolio weights, autonomous trades, or unconditional financial advice.

The central implementation decision is **principle over rail, interface over document, dense information**. Principles constrain what a decision may claim; typed interfaces make facts, evidence, arithmetic, and research lifecycle inspectable; concise artifacts carry the full decision state without substituting prose for data. Scripts are therefore not frozen reasoning pipelines. They are deterministic adapters and lifecycle tools that produce typed facts, preserve provenance, validate arithmetic, and prevent invalid finalization. The model constructs competing hypotheses, requests adaptive evidence, judges materiality, selects and runs an appropriate valuation lens, and owns the final decision.

The system must support three ordinary user intents without forcing them through an archetype-first script: (1) “which industries/sectors are promising and which US-listed tickers deserve deeper work?”, (2) “analyze ticker XXX and state the conditions under which an entry would make sense”, and (3) “as Physical AI develops, which unavoidable physical bottlenecks, industries, sectors, and US-listed tickers could benefit?” It must also return `PASS`, `MONITOR`, or `BLOCKED` honestly when evidence cannot support a recommendation.

## Non-goals and hard boundaries

- Do not propose portfolio percentages, position sizing, automatic orders, or personal suitability advice.
- Do not make a ticker recommendation from a fixed score, a chart, a single top-down multiple, or remembered numbers.
- Do not use the tweet corpus as a routine answer key. It is method evidence during corpus work and an explicitly requested post-hoc comparator only.
- Do not preserve v1 command compatibility, code, tests, hooks, skills, or obsolete documentation in the active tree after the cutover gates pass. Preserve the exact pre-cutover Git tag and the verified session archive, not a second runtime.
- Do not duplicate the harness for Codex. Preserve `AGENTS.md -> CLAUDE.md` and preserve a local `.codex -> .claude` compatibility symlink when its E2E gate passes.
- Do not conceal unavailable, stale, conflicting, or not-disclosed data behind omitted fields or null values.

## Product model

Every research engagement creates a run with a manifest, a small deterministic fact snapshot, a model-authored hypothesis ledger, typed evidence requests/results, optional supply-chain graph, a reproducible lens result, and a decision artifact. The artifact records what is known, what would change the call, which statement is fact versus inference, and whether the decision may be finalized. A later run supersedes rather than overwrites a prior decision.

The action surface is deliberately small: `RECOMMEND_NOW`, `ENTER_ON_TRIGGER`, `MONITOR`, `PASS`, and `BLOCKED`. `RECOMMEND_NOW` means the evidence supports research-level directional interest now, not an instruction to trade. `ENTER_ON_TRIGGER` must state an observable trigger, its evidence source, a falsifier, and why the condition changes the thesis. A numeric price target is allowed only when the lens is valid, every numeric input is referenced, and the arithmetic is reproducible from the saved artifact.

The model begins with a minimal fact snapshot and several competing hypotheses rather than a preselected archetype. A scenario may still identify a physical chokepoint, displaced profit pool, emerging standard, or another structure, but that classification is an auditable hypothesis, not a rail that determines the conclusion. Physical chokepoint work must recursively trace beneath the headline layer, state a stop rationale, surface a second-order allocation or ownership effect (or explicitly mark it unresolved), compare at least one sibling layer, and resolve a US-listed expression or `no_clean_vehicle`.

## Repository end state

The v2 runtime has one public execution surface:

```text
scripts/.venv/bin/python scripts/serenity.py run start|status|close|abandon
scripts/.venv/bin/python scripts/serenity.py snapshot security
scripts/.venv/bin/python scripts/serenity.py hypothesis put
scripts/.venv/bin/python scripts/serenity.py evidence catalog|request|read
scripts/.venv/bin/python scripts/serenity.py lens run
scripts/.venv/bin/python scripts/serenity.py decision validate|finalize
scripts/.venv/bin/python scripts/serenity.py outcomes refresh
```

`scripts/serenity_corpus.py` and `scripts/serenity_eval.py` are separate maintenance/evaluation CLIs, not competing analysis runtimes. All runtime commands write exactly one JSON object to stdout and diagnostics only to stderr. The canonical schema set lives in `schemas/v2/`. Tests for this plan live exclusively in `tests/260817/` and exercise public commands and real artifact boundaries rather than private helper implementation.

## Implementation order and done criteria

| Stage | Outcome | Done when |
| --- | --- | --- |
| 0. Baseline and plan | Preserve the pre-v2 state and freeze decisions | Existing v1 tests run and this five-file plan is present; no v1 deletion occurs. |
| 1. Contracts and lifecycle | A run can be created, inspected, and safely finalized or blocked | Versioned schemas validate, lifecycle exit codes are stable, and contract/CLI tests are green. |
| 2. Facts and evidence | Deterministic identities and typed adaptive evidence replace static analysis rails | Provider envelopes preserve provenance and availability, fact snapshots use required time fields, and adapters pass fixtures/live-safe tests. |
| 3. Corpus and method | The source corpus becomes auditable method evidence rather than hidden doctrine | The manifest dynamically reconciles the current DB row/media counts (rebased pre-implementation: 1,874 rows and 2,062 unique media URLs); cleanroom doctrine is generated from open coding. |
| 4. Decisions and outcomes | Research decisions can be saved, superseded, and measured without auto-trading | Lens and decision gates reject invalid claims; prospective records are append-only and refreshable. |
| 5. Harness and evaluation | Claude/Codex operate the same principles through small adaptive interfaces | Four skills, two agents, hooks, cleanroom E2E, and six-family evaluation evidence pass their gates. |
| 6. Cutover | v2 becomes the only active runtime while v1 remains recoverable from GitHub | Session archive restores byte-identically, all v2 gates pass, v1-only runtime/tests/docs are removed, and the pushed pre-cutover tag is identifiable. |

Each stage is a vertical slice: write the public seam test under `tests/260817/`, observe it fail, implement the minimum behavior, then run the focused test before expanding. Do not turn a stage green by mocking internal functions; mocks belong only at external provider, filesystem-clock, or network boundaries.

## Cross-cutting acceptance gates

- Every stored fact/evidence result carries an explicit availability state, source identity, source URL or stable identifier where applicable, `fetched_at`, and the time fields required by its schema.
- Historical/cutoff evaluation may use an item only if `available_at <= cutoff`; `effective_at` or `period_end` alone never establish availability.
- An identity conflict, invalid provider result, hash collision, or open lifecycle violation stops finalization with the documented non-zero exit code.
- A finalized decision has a valid action, linked evidence, explicit bear case/falsifier, and a lens result when it makes a valuation claim.
- A decision with a numeric target additionally has `lens_validity=valid`, complete fact references, and reproducible arithmetic.
- The harness never infers a decision from a provider score; `ibd-rs-rating` is evidence only.
- All tests added by this project live beneath `tests/260817/`; legacy tests are retained only until cutover.

Detailed interfaces and runtime behavior are in [01-contracts-and-runtime.md](01-contracts-and-runtime.md); corpus and method work in [02-corpus-and-method.md](02-corpus-and-method.md); harness/evaluation work in [03-harness-and-evaluation.md](03-harness-and-evaluation.md); and destructive cutover verification in [04-cutover-and-verification.md](04-cutover-and-verification.md).
