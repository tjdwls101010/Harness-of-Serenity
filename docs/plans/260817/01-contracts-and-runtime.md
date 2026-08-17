# Appendix 01 — contracts and runtime

## Purpose and ownership boundary

The runtime is an evidence operating system, not an investment decision engine. It owns deterministic data collection, identity resolution, source/provenance preservation, schema validation, content hashes, arithmetic execution, and lifecycle transitions. The analyst/model owns hypothesis formation, evidence prioritization, causal inference, materiality, valuation lens selection, uncertainty, and the final action. No provider adapter, composite score, or command may label a security as a winner, assign a conviction tier, or generate an investment recommendation.

The public runtime is only `scripts/serenity.py`. Existing v1 scripts may remain during implementation as migration inputs, but they must not be documented as parallel v2 analysis entry points. Corpus and evaluation tasks are intentionally separate: `scripts/serenity_corpus.py` manages corpus/media/audit operations and `scripts/serenity_eval.py` runs reproducible evaluations.

## CLI contract

Every invocation uses `scripts/.venv/bin/python scripts/serenity.py`; stdout contains exactly one JSON object and nothing else. Human diagnostics, retry notices, warnings, and tracebacks belong on stderr. Commands accept JSON document paths or JSON values only where their command help specifies; they must never scrape prose from model output as an implicit transport format.

| Command | Required responsibility | Success artifact |
| --- | --- | --- |
| `run start` | Create an OPEN run with immutable intent, actor, and initial manifest | `.serenity/runs/<run_id>/run-manifest.json` |
| `run status` | Read lifecycle state without mutation | JSON status for one run |
| `run close` | Close a FINALIZED run after its validated decision is persisted | Updated manifest |
| `run abandon` | Mark an OPEN run abandoned with explicit reason | Updated manifest |
| `snapshot security` | Resolve security identity and record a small deterministic fact snapshot | `fact-snapshot.json` |
| `hypothesis put` | Store/replace a versioned competing-hypothesis ledger for an OPEN run | `hypothesis-ledger.json` |
| `evidence catalog` | List known evidence and unmet needs without deciding their priority | `evidence-catalog.json` |
| `evidence request` | Persist a typed adaptive evidence request | `evidence-request-<id>.json` |
| `evidence collect` | Execute the saved request under its source/network policy and persist typed available or unavailable results | `evidence-result-<id>.json` |
| `evidence read` | Read one already persisted typed evidence result without provider I/O | JSON evidence result |
| `lens run` | Evaluate a declared arithmetic lens using referenced facts | `lens-result.json` |
| `decision validate` | Validate a prospective decision without persisting final state | Validation report |
| `decision finalize` | Persist a valid immutable decision version and update current pointer | `records/decisions/<lineage>/vNNN/` |
| `outcomes register` | Bind a finalized immutable decision to a prospective benchmark/checkpoint schedule | New local prospective record |
| `outcomes refresh` | Append a dated measurement checkpoint to a prospective record | Updated local prospective record |
| `graph put` | Validate and persist an evidence-bound dependency/sector graph for an OPEN run | `sector-graph.json` (`sector-graph/1`) |

The runtime may provide a documented global working-directory/root option only if tests require isolation, but the default project root is the current directory. It must not grow convenience verbs that reintroduce a static `analyze` or `discover` rail.

## Exit codes

| Code | Meaning | Examples |
| --- | --- | --- |
| `0` | Successful command, including a typed valid `unavailable` result | Provider reports a documented missing series; decision validates. |
| `2` | Usage or schema failure | Bad arguments, malformed JSON, invalid enum, missing required schema field. |
| `3` | Identity or lifecycle block | Ticker/FIGI/CIK conflict, unknown run, closed run mutation, invalid finalization state. |
| `4` | Provider could not produce a typed result | Network/provider failure after policy retries, unparseable provider payload. |
| `5` | Persistence/hash conflict | Content-addressed object mismatch, duplicate version with different bytes, pointer conflict. |
| `70` | Unexpected internal error | An uncaught defect after stderr diagnostic emission. |

`unavailable`, `not_disclosed`, and similar evidence conditions are data, not command errors. A command returns `4` only when it cannot create the typed result required by the interface.

## Versioned JSON schemas

Use JSON Schema 2020-12. The canonical IDs are `urn:serenity:schema:<name>:<version>`, schemas are immutable once used by a saved artifact, and a breaking change creates a new version. Store schemas under `schemas/v2/` with filenames that make the version visible.

| Schema | Required role |
| --- | --- |
| `run-manifest/2` | Intent, actor, timestamps, lifecycle, source policy, run/content identifiers. |
| `fact-snapshot/2` | Resolved security identity, deterministic fields, field-level provenance and availability. |
| `provider-envelope/1` | Uniform raw provider response/result metadata before conversion to fact/evidence. |
| `evidence-catalog/1` | Known evidence, evidence gaps, and requestable types without a recommendation. |
| `evidence-request/1` | Hypothesis-linked question, requested evidence type, provider policy, and acceptance criteria. |
| `evidence-result/1` | Typed result, availability, provenance, temporal fields, raw-content hash, and conflicts. |
| `hypothesis-ledger/1` | Competing hypotheses, predictions, disconfirmers, dependencies, and status. |
| `lens-spec/1` | Declared lens formula/inputs/unit assumptions and validity constraints. |
| `lens-result/1` | Executed arithmetic, input fact references, output, validity, and reproducibility hash. |
| `sector-graph/1` | Typed nodes/edges, recursive bottleneck findings, siblings, and US vehicle resolution. |
| `research-decision/1` | Final action, thesis/bear case, conditions, evidence links, lens claims, and supersession. |
| `prospective-record/1` | Local append-only outcome tracking and dated checkpoints. |
| `qa-case/1` | E2E/evaluation scenario, cutoff, expected invariants, and isolation policy. |
| `qa-result/1` | Deterministic/live result, counts, taxonomy, evidence links, and reviewer outcome. |

All schemas must distinguish absent information from a missing implementation. Any fact or evidence-bearing value has an `availability` enum with exactly `available`, `not_disclosed`, `not_applicable`, `unavailable`, `invalid`, `not_requested`, `stale`, or `conflict`. The value may be omitted only when the field is genuinely outside the type; an expected field uses an explicit availability object. `null` is not a substitute for an availability decision.

## Temporal and provenance rules

For every fact/evidence result, retain the fields relevant to its source rather than collapsing time to one timestamp: `effective_at` (when an event/economic condition applies), `period_start`/`period_end` (measurement period), `observed_at` (when a value was observed), `available_at` (when the information became usable to the market/researcher), `fetched_at` (when this run collected it), and `source_version` (filing accession, release version, dataset revision, or equivalent). `available_at` is mandatory whenever a historical cutoff can be applied.

An evaluation with cutoff `T` can consume only evidence with `available_at <= T`. If availability cannot be established, the result is `unavailable` for cutoff use even if the fact’s effective date is older. Later revised macro series need their release/vintage represented so current retrieval cannot silently leak future knowledge into an as-of evaluation.

Every source-derived object includes provider name, endpoint/document identifier, canonical URL when available, retrieval parameters, raw-content hash, transformation/version identifier, and identity bindings used to resolve the security. Provider raw payloads belong in an ignored cache or content-addressed store referenced by hash; the tracked artifact must remain enough to identify and re-fetch/re-audit the claim.

## Lifecycle, persistence, and lineage

Runs live while OPEN in `.serenity/runs/<run_id>/`. A run manifest is append-only for events and records one of `OPEN`, `FINALIZED`, `CLOSED`, or `ABANDONED`. `FINALIZED` seals the decision and permits only the explicit `run close` transition; `CLOSED` and `ABANDONED` are terminal, and every later mutation fails with exit `3`. The system content-hashes canonical JSON and refuses a mismatched write at the same content address with exit `5`.

Final decisions are immutable versions at `records/decisions/<lineage>/vNNN/{decision.json,analysis.md,evidence-manifest.json}`. `current.json` points to the active version. A revision is a new version with `supersedes` and a non-empty `changed_because`; it never mutates the old decision. `analysis.md` is a dense human reading layer over `decision.json`, not an alternative source of truth.

Prospective measurement stays local and append-only. A refresh records price/benchmark observation, thesis-mechanism observation, falsifier state, measurement provenance, and the refresh timestamp. It does not execute trades, send trade instructions, or redefine the original decision. A condition hit is a measurement event, not proof that a trade should occur.

## Security identity and provider envelope

Security identity must resolve and record at least ticker as requested, normalized symbol, exchange/listing, issuer legal name, CIK where applicable, OpenFIGI binding where available, US-listing type (common/ADR/ETF), and resolution source. If SEC, OpenFIGI, and requested ticker conflict materially, snapshot finalization blocks with exit `3` and an evidence result marked `conflict`; the model may not reason past an unresolved identity.

Provider adapters return `provider-envelope/1` before data enters a snapshot. The envelope records request parameters, response status, retry count, provider time/version, identity bindings, raw payload hash, parsing result, source locations, and one explicit availability outcome. A provider field cannot be transformed into a headline recommendation or an implicit minimum-score gate.

Issuer narrative uses the same evidence boundary rather than a search-summary shortcut. `issuer-ir.document` accepts one already-resolved official issuer URL only after the attached live fact snapshot's exact raw SEC submissions payload re-establishes the CIK, issuer name, and declared issuer domain; a frozen snapshot cannot authorize live collection. It captures the exact response bytes, validates every redirect hop and final URL against that domain, preserves response metadata, and records a source-derived publication time or becomes unavailable for historical use. The manual `evidence read --document` seam is unavailable for this capability because supplied JSON cannot prove that origin or raw response. WebSearch/WebFetch may locate the official source, but management claims, hard operating observations, named relationships, omissions, and cross-company read-through candidates remain distinct; no provider or evidence agent turns them into a thesis or action.

## Lens and decision gates

`lens-spec/1` declares the business question, formula, units, all fact/evidence references, assumptions, scenario labels, and validity constraints. `lens run` only performs declared arithmetic and produces a `lens-result/1`; it never selects the lens. The result states `lens_validity` as `valid`, `invalid`, `insufficient_evidence`, or `not_applicable`, preserves each input’s availability/provenance, and writes a canonical reproducibility hash.

`decision validate` rejects a finalizable decision unless it has a permitted action, security/sector scope, competing-hypothesis disposition, linked evidence, explicit uncertainty, strongest bear case, falsifier, and conditions appropriate to the action. Any valuation assertion needs a linked lens result. A numeric target/range needs `lens_validity=valid`, full references for all formula inputs, compatible units, and reproducible arithmetic; otherwise it must be represented as qualitative or the action must be downgraded.

For Physical AI and other physical-chain work, `sector-graph/1` makes the narrative testable: nodes have typed roles and evidence references; edges have direction/type/evidence; the graph names the headline bottleneck, recursively records the lower hop(s), and either records a defensible stopping rationale or leaves the result unresolved. It includes a sibling-layer comparison, a named second-order allocation/ownership actor or `unresolved`, concentration/ownership evidence, and a US-listed vehicle resolution (`clean_vehicle`, `indirect_vehicle`, or `no_clean_vehicle`).

## Initial test seams

All new tests live in `tests/260817/`. Begin with public CLI subprocess tests in `tests/260817/cli/` for one JSON stdout object, exit-code mapping, lifecycle state transitions, and no-write validation. Put schema examples and invalid fixtures in `tests/260817/fixtures/`; contract validation in `tests/260817/contracts/`; adapter network boundaries in `tests/260817/adapters/`; artifact lineage/content-hash behavior in `tests/260817/artifacts/`; and scenario-facing checks in `tests/260817/e2e/`.

The first red-green slice is `run start/status/abandon`: a test starts an isolated run, parses exactly one JSON stdout object, verifies the manifest and content identity, abandons it, and proves later mutation is exit `3`. The next slice adds schema validation and the explicit availability object. Continue with identity/provider envelope, snapshot, hypothesis/evidence, lens, decision finalization, then prospective refresh. Each slice is complete only after focused tests and the growing `tests/260817` suite pass.
