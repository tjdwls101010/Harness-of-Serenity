# Changelog

All notable changes to Harness of Serenity are documented here. This project uses an unreleased section until a v2 release/tag is intentionally published.

## [Unreleased]

### Breaking — v2 cutover

- The v2 public research interface is `scripts/.venv/bin/python scripts/serenity.py`; it replaces v1 analysis rails with an explicit lifecycle for runs, snapshots, hypotheses, evidence, lenses, graphs, decisions, and prospective outcomes.
- Prior v1 analysis commands, natural-language verdict hooks, active session files, tests, and obsolete documentation were removed from the active tree after the v2 suite passed; they are not a supported parallel interface.
- v1 state is recoverable from the annotated `v1-final-260817` tag and `archive/v1/260817-sessions.tar.gz`. The archive source commit is `290355655eb1fb0b7b30803879d15eacd52f0416`; its archive SHA-256 is `2cf3590aa0e54c15ef06d5340db89f429c8b69791e0c84c209e6d2f9ad555bc7`.
- Historical inspection or rollback uses the recorded pre-cutover tag or restores the byte-verified v1 archive into a temporary directory. v1 and v2 artifacts must not be mixed in place.

### Added

- Versioned v2 contracts for provider envelopes, fact snapshots, evidence, hypotheses, lenses, sector graphs, decisions, prospective records, and QA.
- Added identity-, domain-, cutoff-, and raw-byte-bound official issuer narrative capture through `issuer-ir.document`; only a byte-verified live SEC submissions snapshot can authorize the issuer domain, every redirect hop is checked, manual result injection is rejected, and Web search remains source discovery rather than evidence or judgment.
- A corpus/method pipeline that audits source text/media separately from routine research.
- A candidate-first Codex evaluation design: a family-routed Terra candidate consumes the shared Harness, two independent Terra reviewers receive only the typed candidate artifact and permitted evidence, and Sol runs only on material disagreement.

### Verification status

- The final v2 suite passed 591 tests. The strict corpus audit reconciled 1,874 tweets and 2,062 media references with zero blocking issues, the v1 archive restored all 16 members byte-for-byte, and the harness validators reported zero errors or warnings.
- The current real cleanroom evaluation executed all 18 cases with 18 Terra candidates and 36 independent Terra reviews; no material invariant-level disagreement remained, so no Sol adjudication ran. Every family recorded 3 pass / 0 fail / 0 needs review; its canonical content hash is `e4e5ae498606ff4489cc06e5e0e587b9b7422165c57cb65d3ccf143878f1fb2d`, and preserved diagnostic runs and the isolation residual are recorded without an aggregate quality score in [cutover evidence](docs/plans/260817/05-cutover-evidence.md).

## [0.1.0] - 2026-07-09

### Added

- Initial public documentation package, research harness, and MIT license.
