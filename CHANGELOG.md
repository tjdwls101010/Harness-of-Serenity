# Changelog

All notable changes to Harness of Serenity are documented here.

This project follows a pragmatic release log format inspired by Keep a Changelog and uses semantic version tags where possible.

## [Unreleased]

### Fixed — the self-check can go red

The harness reported `validate` 15/15 green while its committed hook fixture suite sat at 19/22, all seven archived scorecards violated the schema the harness pins, and `session_status.py` was silent when `validate` *crashed*. A check nobody has watched fail is not a check.

- `validate` now runs the hook fixture suite and adopts its exit code, so a hook that is present, wired, and broken is finally visible. Verified: a one-character regex edit in a hook reddens `validate`, exits 1, names the failing fixture, and makes the next SessionStart loud.
- `session_status.py` distinguishes red / crashed / timed out. A bare `except` previously mapped "healthy" and "crashed with a traceback" onto identical silent output.
- `sec_consolidation` → `xbrl_module_boundary`: two of its three conjuncts were `True` by construction for every possible input, while the failure message printed all three as independently informative.
- `scripts/tests/test_evidence_contract.py` resolved the repository root three levels too high, so both tests guarding the code/judgment boundary had never executed. Fixed; the boundary is now actually enforced.
- Hook fixtures moved out of `sessions/` into the suite's own sandbox, and `run_fixtures.py` sets `CLAUDE_PROJECT_DIR` explicitly rather than relying on a fallback that passes in a terminal and fails at every real SessionStart.
- `verdict_gate.py`: entry no longer gated on the literal `TLDR` token; a section label with a negating body (`Downsides: none that matter`) no longer passes; the `Lens:` marker accepts any arithmetic expression rather than a fixed operator set, so the doctrine's own slash and additive drivers stop being flagged.
- `evidence_discipline.py` no longer treats bare pipeline field names as proof of a market question. `data_integrity_guard.py` tiers the revenue-agreement check by magnitude.

### Added

- `scripts/serenity_lens.py` — one subcommand per valuation driver, emitting the verified `Lens:` line. `--from-run` reads the market cap from a saved `analyze` payload, so dividing by a remembered market cap becomes structurally unavailable; `custom --expr` keeps the driver list open.
- `harness scorecard-lint` and a `scorecard_guard` PostToolUse hook — one schema definition, checked at write time. Scorecards predating enforcement are grandfathered by boundary date.
- `harness new-session` — rejects a non-kebab or non-English slug at the argument boundary and prints the paste-ready `Saved:` and `INDEX.md` lines.
- `scripts/serenity_sectormap.py` adopted (previously untracked and referenced by no doctrine file); `cohort` now carries each candidate's role/note so the map's own "theme exposure, not bottleneck ownership" caveat reaches the comparator.
- `scripts/tests/test_filings_contract.py` — the filings layer's error contract: a blocked EDGAR read surfaces as an explicit null, never a value.
- `validate` checks `scorecard_conformance` and `prose_growth`, both warn-only.
- `pytest` added to `scripts/requirements.txt`; the unsatisfiable `sec-analyzer` pin removed.

### Removed

- The `.codex/` mirror. Its `hooks.json` bound every hook to a path under `~/Documents/` that stopped existing when the repository moved, so the layer had been inert long enough to be documented as a known limitation and still not fixed. `AGENTS.md → CLAUDE.md` remains.

### Added

- `CONTRIBUTING.md` — development setup, the three test suites with exact commands, the fixture-regeneration procedure, and the boundary rule every contribution is checked against.
- `SECURITY.md` — private reporting channel, in-scope and out-of-scope definitions, and the repository's secret-handling boundary (`.env`, `EDGAR_IDENTITY`, X session cookies).
- `CODE_OF_CONDUCT.md` — Contributor Covenant 2.1 with a named enforcement contact.
- Eleven new `docs/wiki/` pages: `Overview`, `Concepts`, `Data-Modules`, `Filings-and-SEC`, `Agent-Harness`, `Hooks-Reference`, `Session-Archive`, `Testing-and-Validation`, `Eval-Harness`, `Troubleshooting`, and `Known-Limitations`.

### Changed

- Rewrote `README.md` around the problem the project solves rather than its file layout; added the brand header, real badges, an explicit project-status section, and a first run that is verifiable offline before any network call.
- Rewrote all five pre-existing wiki pages (`README`, `Getting-Started`, `Architecture`, `Pipeline-Reference`, `Release-Process`) against the current code. `Pipeline-Reference` now documents every subcommand, every flag, and the complete output schema field by field; `Architecture` documents the fetch flow, the legacy quarantine, and the SEC split.
- Documentation now covers the agent-harness layer, which was previously undocumented: the four lifecycle hooks and their block/warn/silent contracts, the three skills, the two subagents, the rank-N protocol, and the session archive.

### Documented

- Verified defects, recorded in `docs/wiki/Known-Limitations.md` with file, line, root cause, and a suggested fix rather than being papered over:
  - `.env` is never loaded for the macro modules, so configured FRED gauges are silently dropped.
  - `catalyst_inputs.next_report` is always `null` — earnings dates live in the DataFrame index, and the normalizer emits columns only.
  - `filing_evidence.recent_events` is always `[]` — a list is coerced through a dict-only helper, discarding the slowest fetch in the fan-out.
  - `filing_evidence` is empty on the live path following the SEC consolidation into the `serenity-filings` subagent; frozen fixtures still show pre-consolidation data.
  - `scripts/tests/test_evidence_contract.py` computes the repository root three levels too high, so both contract tests fail.
  - `.codex/hooks.json` binds all four hooks to a nonexistent absolute path, leaving the Codex hook layer inert.
  - Stale `requirements.txt` entries with no corresponding imports; `legacy-regress` pointing at a nonexistent golden directory.

### Verification

- `scripts/serenity_harness.py validate` → `"ok": true`, 15 pass / 0 warn / 0 fail.
- `.claude/hooks/tests/run_fixtures.py` → 22/22 fixtures passed.
- Every defect above reproduced against `main` before being documented.
- No code changed in this release — documentation only.

## [0.1.0] - 2026-07-09

### Added

- Initial open-source documentation package.
- Root `README.md` with project purpose, architecture, setup, common commands, contribution guidance, and disclaimer.
- `docs/wiki/` pages for the project overview, setup, architecture, pipeline reference, and release process.
- MIT `LICENSE`.
- Release notes under `docs/releases/v0.1.0.md`.

### Documented

- The core design boundary: code loads deterministic evidence, the analyst judges.
- The main CLI surfaces: `serenity_pipeline.py`, `serenity_filings.py`, and `serenity_harness.py`.
- The role of `CLAUDE.md`, Serenity skills, hooks, filing subagent, and local-only build scaffolding.

### Verification

- Documentation package verified with CLI file and content checks.
- Harness validation expected through `scripts/.venv/bin/python scripts/serenity_harness.py validate`.
