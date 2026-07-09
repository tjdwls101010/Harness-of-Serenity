# Changelog

All notable changes to Harness of Serenity are documented here.

This project follows a pragmatic release log format inspired by Keep a Changelog and uses semantic version tags where possible.

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
