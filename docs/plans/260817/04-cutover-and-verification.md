# Appendix 04 — cutover and verification

## Preconditions and safe sequencing

Cutover is the final stage, never a shortcut to simplify implementation. Before any v1 deletion, run the existing v1 test suite and record the exact command, environment/dependency versions, result counts, and commit SHA in a cutover evidence report. Tag the exact pre-cutover commit with the annotated tag `v1-final-260817` and push that tag to GitHub before deleting v1 material. Keep the working tree clean around archival operations. The rollback path is checking out that tag or restoring the session archive into a temporary location for inspection; it is not an unverified destructive reset.

Develop v2 on a feature branch from current `main`, preserve any unrelated user branch/worktree changes, and make logical commits as stages become independently green. Before final merge, review the actual diff against this plan: every changed line must map to a v2 requirement, no unrelated clean-up should ride along, and no source data/old artifacts should be silently destroyed.

## Session archive procedure

The v1 `sessions/` material is historical evidence, not active v2 state. Before removing it from the active tree, archive the 16 tracked session files into `archive/v1/260817-sessions.tar.gz` and create a tracked manifest alongside it. The manifest records source commit, original relative path, file mode, byte size, SHA-256, archive member path, archive SHA-256, creation command/version, and the fact that untracked OS noise such as `.DS_Store` was excluded unless deliberately included and documented.

Verify the archive before deleting the active sessions directory: extract to a newly created temporary directory, calculate SHA-256/size/mode for every manifest entry, compare byte-for-byte with the source files, and record the successful verification. If an entry differs, stop; do not delete source sessions and do not regenerate the archive in place without preserving the failed report. The archive itself must be readable after checkout from a clean clone.

## v1 removal scope

After all v2 runtime, corpus, harness, evaluation, and archive gates pass, remove v1-only runtime commands, stale v1 schemas, obsolete natural-language hooks, duplicate decision/score machinery, the old v1 test suite, and obsolete v1 operational/plan/wiki documents. Retain only the compact v2 documentation, cutover evidence, session archive/manifest, source corpus, and explicitly supported symlink compatibility surfaces. Do not retain a hidden compatibility `analyze` pipeline merely because it is convenient; it would split fact provenance and let new work bypass v2 lifecycle gates.

Update repository documentation, root harness text, and validation scripts in the same change so there is one operational path. Old plan documents do not remain in the active tree merely for history: the pushed `v1-final-260817` tag is their byte-exact record. The v2 plan itself remains at `docs/plans/260817/` as the current implementation decision record.

## Verification matrix

| Gate | Command/evidence | Passing condition |
| --- | --- | --- |
| Baseline | Existing v1 suite before deletion | Recorded command and all results retained in report. |
| Contracts | `tests/260817/contracts` | All schemas accept canonical examples and reject invalid/ambiguous availability/time documents. |
| CLI/lifecycle | `tests/260817/cli` | One JSON stdout object; exit 0/2/3/4/5/70 behavior; terminal run mutations blocked. |
| Adapters | `tests/260817/adapters` | Identity/provider envelopes retain raw provenance, date/version fields, and typed degraded states. |
| Artifacts | `tests/260817/artifacts` | Content hashes, immutable version lineage, current pointer, and append-only prospective records work. |
| Corpus | Corpus report plus fixtures | Dynamic DB query and manifest reconcile exactly; report the current rebase observation (1,874 rows / 2,062 unique media URLs) or a documented later delta, and every method claim has a traceability tag. |
| Harness | Harness validator and every hook fixture | Zero validator errors; SessionStart soft health and typed Stop gate behave as specified. |
| E2E | Six family reports | Each family has deterministic 2 + live 1 evidence, one shared-Harness Terra candidate per case, two independent Terra reviews per case, raw counts, taxonomy, and no hidden aggregate score. |
| Cleanroom | Candidate and reviewer cleanroom fixtures | Both allowlist manifests/hashes are recorded; the candidate receives only family-routed Harness instructions and no oracle/history, while reviewers receive no Harness/corpus/oracle and cannot read outside their active package. |
| Symlink compatibility | Local harness integration test | `AGENTS.md -> CLAUDE.md` remains valid and the verified `.codex -> .claude` link is tracked so a clone receives one shared harness tree. |
| GitHub v1 record | Annotated tag and remote verification | `v1-final-260817` resolves remotely to the recorded pre-cutover commit before any v1 deletion. |
| Archive | Temporary extraction/byte comparison | All 16 tracked session files match the manifest before source deletion. |

Run focused tests after each TDD slice and the complete v2 suite before cutover. Follow harness creator validation instructions after any `.claude` change: update `.claude/harness-spec.md`, run the harness validator until zero errors, execute fixture tests for every wired hook, then rerun the validator. Record actual commands and results; do not write a passing-looking report for checks that were not run.

The recorded final E2E gate is [`evaluation-report.v2.json`](evaluation-report.v2.json): canonical content hash `e4e5ae498606ff4489cc06e5e0e587b9b7422165c57cb65d3ccf143878f1fb2d`, 18 passing cases across six separately reported families, 18 shared-Harness Terra candidates, 36 independent Terra reviews, and zero Sol adjudications. Historical diagnostic executions remain evidence of corrected contracts; they do not replace this final gate.

## Release and PR workflow

Use the repository’s required Git workflow for material changes: branch from `main`, make logical commits, push, open a Korean-language PR, and squash merge after gates pass. Commit and PR titles use `<type>: <한국어 제목>`. The PR body follows `.github/pull_request_template.md` if it exists; otherwise it uses `## 무엇을 바꿨나`, `## 왜`, `## 영향`, and `## 검증`, with exact test commands and result counts. A failed/blocked live provider or cleanroom case belongs in the PR evidence; it is not a reason to claim completion.

The final handoff names the v2 public CLI, changed harness skills/agents/hooks, archive location, completed verification counts, deferred provider work if any, and the rollback tag. It also states explicitly that the product supplies research and conditional-entry analysis, not portfolio allocations or trade execution.

## Final acceptance decision

The implementation is complete only when all of the following are true: v2 owns the documented runtime path; schema/lifecycle/lens gates prevent invalid decision claims; facts and evidence remain identity/time/provenance-pinned; the corpus audit and cleanroom doctrine work are traceable; shared-Harness candidate execution and independent no-Harness review both pass their cleanroom contracts; all six evaluation families report their own denominators/failure modes; the v1 sessions archive restores byte-identically; and v1-only active code/tests/hooks have been removed without leaving a bypass.

If any of these fail, stop at the corresponding stage, retain v1 active state, record the failure evidence, and repair the smallest violated interface. Do not broaden the change into unrelated refactoring or mask the failure with a narrative exception.
