# Changelog

All notable changes to Harness of Serenity are documented here. Historical source and session recovery points are published on [GitHub Releases](https://github.com/tjdwls101010/Harness-of-Serenity/releases).

## [Unreleased]

### Fixed

- Stopped the lens dropping `inputs[].evidence_refs`, which left the reproducibility hash blind to the evidence a spec claims, so two specs citing different filings hashed identically.
- Drove `outcomes register` and `outcomes refresh` against a real finalized decision for the first time; both worked, and the gap was that nothing named them as a step. They are now reachable from `CLAUDE.md`'s lifecycle line and every skill's hand-off, and covered at the CLI seam rather than only at the store.
- Settled what a `macro-event` run's subjects mean: series identifiers, not tickers, stated in that mode's skill.
- Gave `EdgarToolsBackend` — the only class that talks to real `edgar` objects — a test seat, and fixed the three defects that had lived in that untested seam: `sec.submissions` could never return `available`, `sec.filing-section` with `named=` silently answered "not disclosed" for any non-10-K form, and `sec.filing-text` by accession lost its acceptance instant.
- Resolved `named` sections per form, so a 10-Q reaches Part II Item 1A instead of a `TenK` property that does not exist there, and an unsupported form/section pair returns a typed `invalid` naming what the form does define. An absence of adapter support can no longer impersonate an absence of disclosure.
- Stopped a `limit` from hiding the accession a filing search is looking for.
- Made `available_at` always present in filing metadata, so unknown availability reads as `None` rather than as a `KeyError` at the first filer that has none.
- Disabled `usitc` for the true reason that `dataweb.usitc.gov/api/data` answers the DataWeb app's HTML with HTTP 200 for every request, and rebound `uspto` from its API root, which answers 403, to the search resource that answers 401.

### Added

- `snapshot security --subject TICKER` pins one subject at a time, so a cohort can bind identity for every peer; the bare `fact-snapshot` name is kept for a single-subject run. A `single-name` or `cohort` decision is now refused unless every subject is pinned, and the refusal names the ones that are not.
- `snapshot facts RUN_ID --from-evidence RESULT_ID --fact name=..,concept=..,unit=..` derives typed facts from a saved `sec.xbrl-facts` result, stamped with the accession URL and the filing's raw-byte hash. `lens run` unions every attached fact snapshot, so a numeric target can stand on a filing rather than on a provider-computed ratio.
- `RunStore.attach_artifacts` writes the manifest once for a whole batch; `evidence collect` used it to stop being quadratic in the number of results.
- A `capability_parameters` contract per capability in the evidence catalog, validated by the registry before a provider is constructed, so a wrong `provider_parameters` shape is refused by name instead of costing an external request. It replaces the ad-hoc `alfred-fred` special case and is readable one at a time with `evidence catalog --capability <id>`.
- Bounded evidence reads: `evidence collect` and `evidence read` answer with the value's shape, `--value` opts into the payload, and `evidence read --match REGEX --context N` returns matching spans with character offsets that verify against the stored artifact. A 144k-character section now costs kilobytes to reference.
- Routed the instruction layer to those interfaces: each skill names the capabilities its mode needs and the bounded-read commands, `serenity-discovery` names `graph put` and the `us_expression.resolution` enum, `serenity-macro-event` names the macro series capabilities for the first time, and `serenity-filings` names the eight `sec.*` capability IDs and its bulk-reading role. `serenity_harness.py validate` now fails when a skill or agent names a capability the catalog does not declare.
- `alfred-fred.vintage-series` now returns the revision history its name promises; it and `alfred-fred.macro-series` had dispatched identically, so one catalog ID was a dead label.
- Recorded golden payloads under `tests/260817/fixtures/recorded/`, captured from the live endpoints through each provider's own request builder and replayed through the real adapter, with a capture tool that refuses to write a recording containing a credential.
- A `live` marker and `pytest.ini`: `pytest -m live` probes the real provider interfaces the adapters parse, and is excluded from the default run and from CI.
- `.github/workflows/tests.yml` runs the offline suite and `serenity_harness.py validate` on GitHub-hosted runners, disjoint from the self-hosted scrape workflows.

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
