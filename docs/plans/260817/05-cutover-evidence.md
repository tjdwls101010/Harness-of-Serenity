# Appendix 05 — cutover evidence

## Evidence convention

This report records commands and observations from the final v2 implementation worktree on 2026-08-17. A passing command proves only the named contract at that repository state; the six evaluation families remain separate and are not collapsed into an “overall quality” or investment-performance score.

## Source and recovery identity

| Item | Recorded value |
| --- | --- |
| v1 source commit | `290355655eb1fb0b7b30803879d15eacd52f0416` |
| annotated source tag | `v1-final-260817` |
| remote tag object | `c46af84dd1e64743cb4204e1dff03af1094b0029` |
| remote peeled tag target | `290355655eb1fb0b7b30803879d15eacd52f0416` |
| remote | `https://github.com/tjdwls101010/Harness-of-Serenity.git` |
| session archive | `archive/v1/260817-sessions.tar.gz` |
| archive SHA-256 | `2cf3590aa0e54c15ef06d5340db89f429c8b69791e0c84c209e6d2f9ad555bc7` |
| archive manifest SHA-256 | `fa49ec76f7ec66e8f4c02d04c825bdeaeca75d0b380e957f20e9b93cfada899d` |
| archive member count | 16 |

The archive manifest records deterministic tar/gzip metadata, every original path/mode/byte size/SHA-256, and the exclusion of untracked `sessions/**/.DS_Store`. `scripts/.venv/bin/python -m pytest tests/260817/artifacts/test_v1_session_archive.py -q` passed `2` tests, including a fresh temporary extraction and byte/hash/mode comparison of all 16 members. The archive is for historical inspection or rollback into a temporary location; it is not a v2 runtime input.

## Baseline, dependencies, and final suite

| Measurement | Recorded result |
| --- | --- |
| v1 baseline before removal | `pytest scripts/tests -q` → `340 passed` |
| final v2 suite | `scripts/.venv/bin/python -m pytest -q tests/260817` → `591 passed`, `24` multiprocessing fork deprecation warnings |
| dependency consistency | `scripts/.venv/bin/python -m pip check` → `No broken requirements found` |
| Python | `3.13.12` |
| `yfinance` | `1.4.1` |
| `edgartools` | `5.35.1` |
| `ibd-rs-rating` | `0.3.0` |
| `jsonschema` | `4.26.0` |
| `python-dotenv` | `1.2.2` |
| `pytest` | `9.1.1` |

`scripts/requirements.txt` is the installation constraint source; the versions above are observations from `scripts/.venv`, not a lockfile. The user-owned `ibd-rs-rating==0.3.0` adapter preserves raw records and dates as evidence and contributes no recommendation threshold.

## Corpus and method evidence

`scripts/.venv/bin/python scripts/serenity_corpus.py inventory --db data/analysis_Serenity.db` returned 1,874 tweets, 1,463 tweets with media, and 2,062 media references/unique URLs. It bound that inventory to database SHA-256 `6c7cafab481ee721c001746d5a5008e77de5f2cbf989d705929f58fa8403c713`, SQLite `user_version` `0`, and query `SELECT id, type, media FROM tweets ORDER BY id`.

The strict command `scripts/.venv/bin/python scripts/serenity_corpus.py audit --db data/analysis_Serenity.db --manifest data/corpus-media-manifest.v1.jsonl --cache-root .serenity/media-cache --require-extraction` returned `valid=true` and a reconciliation gate with zero blocking issues. The manifest covered all 2,062 references; 1,911 fetched relations were cache/hash-valid, while 151 terminal HTTP 404 responses remained explicit typed `unavailable_fetch` records rather than fabricated data. OCR covered the 1,911 available relations, approved vision supplied the required alternative where OCR was insufficient, and no unapproved or invalid provenance remained.

The final blind method set contains 1,874 text chunks plus 1,892 SHA-deduplicated media chunks: 3,766 chunks across 76 packets. It records 1,953 coded units and 1,813 no-reusable-move units. One bounded final `gpt-5.6-sol` synthesis produced 12 corpus-`sourced`, 8 explicitly engineered `augmented`, and 0 `unverified` claims; the ledger content hash is `dba5fe018b2061048cb97d0207b363f6ac0ecddef6735bef7f1f2fdbc369aaab`. The canonical public validation command passed with content hash `4929f608651fbaa3ada72dd9edd4c3c847b07291fe16bae3766e3bbc3c5d35c7` and reconciliation `{chunks:3766, coding_units:1953, codes:3680, claims:20, traceable_claims:12}`.

## Harness and symlink evidence

`scripts/.venv/bin/python -m pytest -q tests/260817/e2e/test_harness_hooks.py` passed `18` tests. `scripts/.venv/bin/python scripts/serenity_harness.py validate` returned v2 with four skills, two agents, one SessionStart hook, one Stop hook, 12 sourced/8 augmented method claims, and no errors or warnings. The harness-creator validator separately reported zero errors and zero warnings; its SessionStart and Stop loop-guard wiring checks all exited `0`.

`readlink AGENTS.md` returned `CLAUDE.md`, and `readlink .codex` returned `.claude`; the final staged index records both paths with Git mode `120000`. The Claude/Codex doctrine therefore has one source rather than two divergent copies. `CLAUDE.md` is 51 lines/5,799 bytes, begins with `# Harness of Serenity`, defines the generic multi-user Harness identity and always-loaded capabilities, and states the typed lifecycle, evidence boundary, supported outcomes, and no-portfolio-allocation constraint; detailed component contracts remain in `.claude/harness-spec.md`.

The existing `serenity-filings` subagent now owns both SEC disclosure collection and official issuer narrative collection instead of adding a broad news agent. Web search only locates an issuer-owned document; `issuer-ir.document` authorizes its domain from the attached live snapshot's byte-verified SEC submissions payload, validates every redirect hop and the final URL, stores exact raw bytes and source-derived time, and rejects frozen-snapshot authorization or manual-result injection. The focused issuer/CLI tests passed `9`, the related provider/runtime/harness suite passed `281`, and a separate read-only adversarial audit reported no remaining P0/P1 evidence-boundary finding.

## Real Codex cleanroom E2E

The current final command used `scripts/serenity_eval.py --execute-cli` with a fresh unique cleanroom/results/report root and the six case-bound, cutoff-safe provider packets with their exact raw cache bindings. The durable report is [`evaluation-report.v2.json`](evaluation-report.v2.json): generated at `2026-08-17T14:08:53Z`, canonical content hash `e4e5ae498606ff4489cc06e5e0e587b9b7422165c57cb65d3ccf143878f1fb2d`, and raw file SHA-256 `f87850b49659d3aa91f16ad34bbd59d90faeea5f592360e77c3a39d345ca3e6c`. Recomputing the canonical hash after removing its self-hash field matched exactly, and a secret/local-path scan found no provider credential names or `/Users`/`/private/tmp` paths.

All 18 cases executed: two deterministic cases and one live case for each of six families. Every case first ran one family-routed `gpt-5.6-terra` candidate from a content-hashed shared-Harness receipt and cutoff-safe evidence, then two independent `gpt-5.6-terra` reviewers from a no-Harness packet. No pair had a material invariant-level disagreement, so the final run invoked no `gpt-5.6-sol` adjudicator. It therefore contains 18 candidate and 36 reviewer records, all with status `completed`, return code `0`, and `os-enforced` isolation. Across every transcript, command, tool-event, network/search, forbidden-path, and unapproved-tool counts were all zero, and all 54 ephemeral auth paths were absent after process exit.

| Family | Pass | Fail | Needs review | Denominator |
| --- | ---: | ---: | ---: | ---: |
| Discovery | 3 | 0 | 0 | 3 |
| Single ticker | 3 | 0 | 0 | 3 |
| Physical AI | 3 | 0 | 0 | 3 |
| Near miss / no clean vehicle | 3 | 0 | 0 | 3 |
| Degraded identity/data | 3 | 0 | 0 | 3 |
| Displacement/fear | 3 | 0 | 0 | 3 |

These are QA invariant outcomes, not market-performance labels, and the report keeps `aggregate_quality_score` null. All six live cases retain a yfinance provider envelope with serialized-envelope and exact raw-response-cache hashes kept distinct. Because those live captures are `transport_only`, post-cutoff transport is recorded but cannot enter candidate or reviewer invariant evidence; no SEC result was substituted after the official endpoint returned unavailable from this environment.

The candidate package receipts the shared Harness and both symlinks, but its inline prompt loads only `CLAUDE.md` and the family-routed skill sequence; it receives no expected invariants, answer key, prior verdict, or corpus answer, and it accurately records that hook lifecycle is not executed. Each reviewer cleanroom contains only `qa-case.json`, `frozen-packet.json`, `qa-result.schema.json`, and `package-manifest.json`; the hash-bound prompt contains the typed candidate artifact and permitted evidence but no Harness file, candidate prompt, expected outcome, or prior result. The macOS outer Seatbelt broadly denies the repository, home, temporary storage, and prior results, then allows only the active case/result tree, resolved Codex runtime, ephemeral auth copy, and exact Codex/helper processes. `--search` is absent and child process execution is denied outside that allowlist. A residual remains explicit: hosted model transport occurs in the parent Codex process and cannot be OS-denied without preventing the model call itself; completed tool events are therefore also rejected by transcript audit.

Four pre-final executions are retained as diagnostic history rather than hidden. The earlier reviewer-only design produced `5 pass / 6 fail / 7 needs_review` with canonical hash `09154dea3a73d371fc4c2ef8671148ace1aedf45798b57649f69073ba725be6b`; it demonstrated that no actual shared-Harness candidate was under test and drove the candidate-first redesign. The first candidate-first diagnostic produced `15 pass / 3 fail` with canonical hash `8f79946ce7e0678ea4816c18a0c4cba1a141c1a97e8c5e60a18316b89f48b458`: all three single-ticker candidates correctly returned `BLOCKED` on a raw `FICT`/company-name conflict, but the old invariant still required “identity is pinned.” A TDD regression changed only the contract to “identity conflict blocks action,” preserved the conflicting evidence, and rejected an action-bearing candidate under the same facts.

An intermediate 18/18 diagnostic had canonical hash `31caea85a246917b838c969a6f70a04febf121d713488a5ef261120fdf4e1577` and raw SHA-256 `10904c62c85b4c10b40e910539c0706604bfcb5465cbb80ac230af35a25dc213`. Its `displacement-fear-det-02` Terra disagreement invoked one Sol adjudication and was retained as diagnostic evidence while the displacement arithmetic and durable adjudication-result contracts were corrected. The next 17/18 diagnostic had canonical content hash `cf2bcf68eeb98f982afdb8767ad8fd3c79fedc9186a6ab3ab980e177366c185d`: `near-miss-det-02` correctly selected `BLOCKED` for an undisclosed US listing/access gap, revealing that its fixture required `PASS or MONITOR` despite the approved plan allowing `PASS`, `MONITOR`, or `BLOCKED`. A TDD contract correction replaced that impossible action expectation with “no unsupported US-listed action is taken,” then the current final run was executed from a new root.

## Cutover and public surface

The active v2 public research CLI is `scripts/.venv/bin/python scripts/serenity.py`, with `run`, `snapshot`, `hypothesis`, `evidence`, `lens`, `decision`, `outcomes`, and `graph` groups. Stdout is one JSON object; documented exit categories are `0`, `2`, `3`, `4`, `5`, and `70`. Corpus, method, evaluation, and harness maintenance remain separate CLIs with detailed root and leaf `--help` contracts. No Docker or OrbStack runtime is required.

The cutover removes 242 tracked v1-only files: the parallel analysis/pipeline/module commands, prose-verdict hooks and fixtures, old eval/tests, active sessions, and obsolete plans/wiki/release documentation. One scraper regression test is moved from `scripts/tests/` into `tests/260817/corpus/` rather than deleted. The source DB, scraper/update workflows, verified archive, v2 plans, and the shared harness exposed through the two tracked symlinks remain. A final active-tree reference scan and staged-diff review are part of the publication gate; the pushed `v1-final-260817` tag is the byte-exact recovery source.

## Residuals that are not hidden

- The full suite emitted 24 Python 3.13 multiprocessing `fork()` deprecation warnings; tests passed, but a future change may migrate those process tests to a safer start method.
- The corpus has 151 terminal HTTP 404 media references. They are preserved as non-blocking typed unavailable evidence and are not silently dropped or counted as extracted content.
- Cleanroom parent-process provider transport is an explicit residual as described above. No claim of network-air-gapped evaluation is made.
- Provider availability, research conclusions, and prospective outcomes can change after the recorded cutoff. Passing these gates does not establish alpha, future returns, or personal suitability.
