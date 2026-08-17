# Changelog

All notable changes to Harness of Serenity are documented here. Historical source and session recovery points are published on [GitHub Releases](https://github.com/tjdwls101010/Harness-of-Serenity/releases).

## [Unreleased]

### Changed

- Renamed the internal Python package to `serenity_core` while preserving the public `scripts/serenity.py` CLI.
- Flattened canonical versioned JSON Schemas into `schemas/`; schema URNs and artifact format versions remain unchanged.
- Limited `config/` to runtime configuration, moved content-addressed method artifacts to `method/`, and registered method/media output contracts under `schemas/`.
- Promoted current design documents to `docs/architecture/` and the latest E2E receipt to `docs/evaluation/evaluation-report.json`.

### Removed

- Removed retired runtime cache directories and the in-tree historical session archive after publishing and independently verifying the GitHub Release assets.

### Verification

- The complete test suite passed `594` tests with `24` multiprocessing fork deprecation warnings, and the static Harness validator reported no errors or warnings.
- The refreshed candidate-first E2E completed all 18 cases with 18 Terra candidates, 36 independent Terra reviews, zero material disagreements, zero Sol adjudications, and zero command/tool audit violations. The report canonical hash is `d41d9995e7178f6e151a74cda6126b3447b770b4b474671e6af8a94e414f212f`; its raw SHA-256 is `c51d19144d7e3de0e847f64e3d693c9b99563eae7cbee194a880b06c4a0812bc`.
