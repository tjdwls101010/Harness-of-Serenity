# Changelog

All notable changes to Harness of Serenity are documented here. Historical source and session recovery points are published on [GitHub Releases](https://github.com/tjdwls101010/Harness-of-Serenity/releases).

## [Unreleased]

### Fixed

- Separated registry identity from source identity in the evidence catalog, so `sec.*` and `alfred-fred.*` results can be recorded at all; before this every one of them was rejected as not owning its own capability.
- Exposed the six implemented-but-unreachable SEC narrative capabilities (`sec.filing-text`, `sec.filing-section`, `sec.xbrl-facts`, `sec.segments`, `sec.statement`, `sec.eightk`) and replaced the registry's string-split verb derivation with an explicit map.
- Kept the SEC acceptance instant that `edgartools` returns as a `datetime`, which had been discarded and left every filing unusable under an intraday cutoff.
- Derived the ALFRED vintage from the run cutoff rather than the cutoff's own date, and passed `observation_start`/`observation_end` through; before this `alfred-fred` could never return an available observation.
- Recorded an issuer that declares no website in its SEC submission as typed `not_disclosed` evidence instead of failing the run with a misleading origin-mismatch error.
- Enabled `federal-register` against its real documents API and replaced the doctrine-flavored reason on `bis` with the true one, that no API endpoint is bound.

### Changed

- Renamed the internal Python package to `serenity_core` while preserving the public `scripts/serenity.py` CLI.
- Flattened canonical versioned JSON Schemas into `schemas/`; schema URNs and artifact format versions remain unchanged.
- Limited `config/` to runtime configuration, moved content-addressed method artifacts to `method/`, and registered method/media output contracts under `schemas/`.
- Promoted current design documents to `docs/architecture/` and the latest E2E receipt to `docs/evaluation/evaluation-report.json`.

### Removed

- Removed retired runtime cache directories and the in-tree historical session archive after publishing and independently verifying the GitHub Release assets.

### Verification

- The complete test suite passed `648` tests with `24` multiprocessing fork deprecation warnings, and the static Harness validator reported no errors or warnings.
- All four run modes reached a finalized typed decision against live providers, together with the honest-failure path that records an unavailable issuer-ir result and finalizes `BLOCKED`.
- The refreshed candidate-first E2E completed all 18 cases with 18 Terra candidates, 36 independent Terra reviews, zero material disagreements, zero Sol adjudications, and zero command/tool audit violations. The report canonical hash is `d41d9995e7178f6e151a74cda6126b3447b770b4b474671e6af8a94e414f212f`; its raw SHA-256 is `c51d19144d7e3de0e847f64e3d693c9b99563eae7cbee194a880b06c4a0812bc`.
