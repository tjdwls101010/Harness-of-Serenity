#!/usr/bin/env python3
"""Re-run every committed hook fixture and assert the expected branch fired.

    scripts/.venv/bin/python .claude/hooks/tests/run_fixtures.py

This is the durable, dependency-free re-runner: it pipes each fixture's JSON to the hook on stdin
(exactly as Claude Code does at the real lifecycle event) and checks stdout. It mirrors what the
harness-creator tool does per file —
    test_hook.py --command .claude/hooks/<hook>.py --event <Event> --input <fixture>.json
— but without needing that tool on PATH, so the suite stays runnable from any checkout. See README.md
for the per-fixture expected outcomes.

verdict_gate's Saved:-mark branch resolves a session folder against CLAUDE_PROJECT_DIR, so the suite
points that variable at its own fixtures/ sandbox and the scaffolding lives there rather than in
sessions/. It is set EXPLICITLY rather than left to the hook's `or os.getcwd()` fallback, because
the fallback only applies when the variable is unset: a terminal run would pass while every real
SessionStart — where Claude Code sets it to the repo root — would fail against a sandbox that isn't
there. Verify any change to this both ways.

The scaffolding sits here and not under sessions/ because sessions/ is documented as real archived
analysis. Debris there invites a tidy-up, and it got one: both folders were deleted from the working
tree, three fixtures went red, and validate reported green throughout. A comment saying "do not
delete" is the weakest possible guard — it is read by nobody at the moment of deletion. Scaffolding
that is structurally distinguishable from real output cannot be swept by someone doing the right
thing.
"""
import json
import os
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
HOOKS_DIR = os.path.dirname(TESTS_DIR)
ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))
SANDBOX = os.path.join(TESTS_DIR, "fixtures")
VG = os.path.join(HOOKS_DIR, "verdict_gate.py")
ED = os.path.join(HOOKS_DIR, "evidence_discipline.py")


def silent(out):
    return None if out.strip() == "" else f"expected SILENT, got: {out[:120]!r}"


def contains(*subs):
    def f(out):
        miss = [s for s in subs if s not in out]
        return None if not miss else f"missing {miss}"
    return f


def excludes(*subs):
    def f(out):
        bad = [s for s in subs if s in out]
        return None if not bad else f"unexpectedly present {bad}"
    return f


def all_of(*fns):
    def f(out):
        for fn in fns:
            e = fn(out)
            if e:
                return e
        return None
    return f


# (fixture path under tests/, hook script, assertion) — expected outcomes documented in README.md.
CASES = [
    ("verdict_gate/silent_full", VG, silent),
    ("verdict_gate/soft_lens", VG, all_of(contains("machine-checkable"), excludes("isn't archived", "UPSIDE leg"))),
    ("verdict_gate/hard_nfi", VG, contains('"decision": "block"', "NFI/NFA sign-off")),
    ("verdict_gate/coding_silent", VG, silent),
    ("verdict_gate/macro_hard", VG, contains('"decision": "block"', "NFI/NFA sign-off")),
    ("verdict_gate/meta_silent", VG, silent),
    ("verdict_gate/bear_leg_soft", VG, all_of(contains("UPSIDE leg"), excludes("isn't archived", "machine-checkable"))),
    ("verdict_gate/saved_missing", VG, all_of(contains("isn't archived"), excludes("machine-checkable", "UPSIDE leg"))),
    ("verdict_gate/saved_folder_missing", VG, contains("no such session folder exists")),
    ("verdict_gate/saved_wrong_shape", VG, contains("not a valid session path")),
    ("verdict_gate/saved_empty_folder", VG, contains("holds no `.md`")),
    ("verdict_gate/saved_backtick_silent", VG, silent),
    ("verdict_gate/false_fire_guard", VG, silent),
    ("evidence_discipline/equity_cashtag", ED, contains("[evidence-discipline]")),
    ("evidence_discipline/equity_korean", ED, contains("[evidence-discipline]")),
    ("evidence_discipline/macro_regime", ED, contains("[evidence-discipline]")),
    ("evidence_discipline/equity_english_phrase", ED, contains("[evidence-discipline]")),
    ("evidence_discipline/meta_hook_no_anchor", ED, silent),
    ("evidence_discipline/meta_dev_refactor", ED, silent),
    ("evidence_discipline/meta_with_anchor", ED, contains("[evidence-discipline]")),
    ("evidence_discipline/non_market", ED, silent),
    ("evidence_discipline/ranking_retrieval", ED, contains("[evidence-discipline]", "reconcile deltas AFTER fresh scorecards")),
]


def main():
    fails = 0
    for fixture, hook, check in CASES:
        payload = open(os.path.join(TESTS_DIR, fixture + ".json"), encoding="utf-8").read()
        p = subprocess.run([sys.executable, hook], input=payload, cwd=ROOT,
                           env={**os.environ, "CLAUDE_PROJECT_DIR": SANDBOX},
                           capture_output=True, text=True)
        err = check(p.stdout)
        if err:
            print(f"FAIL  {fixture}: {err}; stdout={p.stdout[:160]!r}")
            fails += 1
        else:
            print(f"ok    {fixture}")
    print(f"\n{len(CASES) - fails}/{len(CASES)} fixtures passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
