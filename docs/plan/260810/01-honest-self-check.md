# Phase 01 — make the self-check capable of going red

**Prerequisite:** none. This is the first thing done, in this order, before any other file in this plan.

**Why first:** every later phase is verified by running something. Right now `serenity_harness.py validate` reports `ok: true, 15/15` in a working tree where the committed hook-fixture suite is at 19/22, one of the fifteen checks is a tautology, and the SessionStart hook that surfaces validate's health is silent when validate *crashes*. Fixing hooks against that baseline means every "it's green now" is unfalsifiable. A self-check that has never been observed going red is not a check.

Findings covered: F01, F04, F16/F21 (rediscovered independently by two lenses), F23, F24 (see `99-appendix-findings.md`).

---

## 1.1 — Restore the deleted fixture scaffolding, and move it where a hygiene sweep can't reach it

`sessions/990101.hook-fixture/FIXT.md` and `sessions/990102.hook-empty/.gitkeep` are tracked files currently showing as unstaged deletions. They are the filesystem scaffolding `verdict_gate.py`'s `Saved:`-mark branch resolves against, which is why three fixtures fail. Recover them from the index (`git checkout --`), then **relocate the scaffolding outside `sessions/`** — for example under `.claude/hooks/tests/fixtures/sessions/` — and point the fixtures at the new path.

The relocation is the actual fix, not the restore. These folders were deleted because they sit inside `sessions/`, a directory whose entire documented purpose is real archived analysis; anything that looks like debris there invites deletion, and the wiki's "do not delete" comment is the weakest possible defense — a comment in a file nobody reads at deletion time. Scaffolding that lives where it is structurally distinguishable from real output cannot be swept by someone doing the right thing.

**The 16th case:** a future session tidying `sessions/` of anything not matching `{yymmdd}.{slug}`. After this fix, that sweep is correct and harmless.

## 1.2 — Wire the fixture suite's exit code into `validate`

Add a check that shells out to `run_fixtures.py` and fails when it does. The current hooks check asserts only that four hook scripts exist on disk and are wired in `settings.json` — existence, not behavior, which is RC3 in one line. A hook script can be present, wired, and completely broken, and today nothing notices.

This is also what makes `session_status.py` earn its place: it is gated on `report.ok`, so it stays silent through a fixture regression that a developer only discovers by manually running the suite.

**The 16th case:** someone edits a hook's regex, breaks two fixtures, and commits. Today: green everywhere. After: loud at the next SessionStart.

## 1.3 — Make `session_status.py` distinguish "validate is red" from "validate crashed"

The hook wraps its subprocess call in a broad `except` that swallows a crashed validate into the same silent path as a healthy one — verified by pointing `CLAUDE_PROJECT_DIR` at a copy whose `cmd_validate` raises: direct invocation gives a traceback and exit 1, the hook gives zero output and exit 0.

Narrow the except to the modes that genuinely mean "nothing to report" (missing file, timeout, empty stdout), and emit a distinct warning when the subprocess exits non-zero with stderr content. Keep the failure non-blocking: the reason a hook wraps everything is that a crashing hook must never take the turn down with it, and that instinct is right. The fix is to distinguish two failures, not to remove the guard.

**The 16th case:** a bad import lands in `serenity_harness.py`. Today the harness reports perfect health precisely because its health check is broken — the worst possible failure signature.

## 1.4 — Fix the tautological check in `sec_consolidation`

`_check_sec_consolidation` computes `ok = not leaked and xbrl_empty and classification_empty`, where the last two derive from `_extract_sec_supply_chain`, which is an unconditional `return {"data": {"filing": {}, "classification": {}, "xbrl": {}}, …}` that ignores its own ticker argument. Both conjuncts are `True` by construction for every possible input, so the check's entire discriminating power is the module-leak scan — while its failure message prints all three as if independently informative.

Either drop the two dead conjuncts and rename the check to what it actually guards (the module-leak boundary), or replace the stub call with something that would exercise a non-empty branch if one were reintroduced. Prefer the rename: it is honest about current coverage, and 15 checks of which one is decorative is worse than 14 real ones.

**The 16th case:** any future check written the same way. The general lesson to carry into the rest of this plan — an assertion whose subject is a hardcoded literal tests the source code, not the behavior — belongs as a one-line comment where a future editor will hit it.

## 1.5 — Fix the path bug that makes both evidence-contract tests unrunnable

`scripts/tests/test_evidence_contract.py` computes `ROOT = SCRIPTS_DIR.parents[3]`, three levels too many, resolving to the user's home directory — a real directory, so nothing errors early. Both tests then invoke a nonexistent path under `check=True` and die before any contract assertion runs. `ROOT = SCRIPTS_DIR.parent` is the fix.

This one matters beyond the two tests: they are the mechanical guard on the fact/judgment seam (C1), the harness's central invariant. It has been unenforced for as long as the bug has existed. `harness-spec.md:46` still lists it as a plain uncaveated validation, which is its own small instance of RC3.

**The 16th case:** any test that fails by not running. Consider having `validate` invoke the contract tests too, so "the seam is guarded" becomes a claim the harness can check rather than one it asserts.

---

## Exit criteria

Mechanically checkable, all four required:

1. `scripts/.venv/bin/python .claude/hooks/tests/run_fixtures.py` → **22/22**, with the scaffolding living outside `sessions/`.
2. `scripts/.venv/bin/python scripts/serenity_harness.py validate` → green, with a check count that reflects the additions.
3. **Validate goes red on demand.** Deliberately break one fixture, confirm `validate` fails and `session_status.py` is loud, then restore. Record that you did this — an untested red path is exactly the failure this phase exists to remove, and the check is worthless if nobody has ever seen it fire.
4. `scripts/.venv/bin/python -m pytest scripts/tests/test_evidence_contract.py` runs and passes.

## Documentation to correct in the same pass

The false "22/22" appears in `.claude/harness-spec.md:45`, `CHANGELOG.md:36`, and six `docs/wiki/` pages. Correct all of them, and note in `harness-spec.md` that the fixture suite is now wired into `validate` — the spec's own preamble says the next audit compares against it, so a spec that overstates coverage sends the next audit looking in the wrong place.
