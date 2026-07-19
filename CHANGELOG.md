# Changelog

All notable changes to Harness of Serenity are documented here.

This project follows a pragmatic release log format inspired by Keep a Changelog and uses semantic version tags where possible.

## [Unreleased]

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
