#!/usr/bin/env python3
"""Re-run every committed hook fixture and assert the expected branch fired.

    scripts/.venv/bin/python .claude/hooks/tests/run_fixtures.py

This is the durable, dependency-free re-runner: it pipes each fixture's JSON to the hook on stdin
(exactly as Claude Code does at the real lifecycle event) and checks stdout. It mirrors what the
harness-creator tool does per file —
    test_hook.py --command .claude/hooks/<hook>.py --event <Event> --input <fixture>.json
— but without needing that tool on PATH, so the suite stays runnable from any checkout.

TWO CONVENTIONS CARRY THE WHOLE SUITE, and both exist so that adding a fixture touches nothing but
the new file itself:

1. **The directory names the hook.** A fixture at `verdict_gate/foo.json` runs against
   `../verdict_gate.py`. A fixture cannot drift from the hook it claims to test, because its
   location IS the claim.
2. **The fixture carries its own expectation**, in an `_expect` key the hooks ignore (each reads
   only its own input fields). So there is no central list to append to, and README.md documents
   rather than defines.

That matters more than it looks: the alternative — one CASES list plus a hand-maintained table —
is a single file every concurrent change has to edit, and a count in prose that is wrong the moment
anyone adds a case. This repository has already shipped "22/22" in nine documents while the suite
was at 19/22. Numbers that must be restated to stay true will eventually be false; a number the
runner prints is true by construction.

A fixture with no `_expect` is a hard FAIL, never a skip. A skipped fixture is indistinguishable
from a passing one, which is the failure this whole suite exists to make impossible.

verdict_gate's `Saved:`-mark branch resolves a session folder against CLAUDE_PROJECT_DIR, so the
suite points that variable at its own `fixtures/` sandbox and the scaffolding lives there rather
than in `sessions/`. It is set EXPLICITLY rather than left to the hook's `or os.getcwd()` fallback,
because the fallback only applies when the variable is unset: a terminal run would pass while every
real SessionStart — where Claude Code sets it to the repo root — would fail against a sandbox that
isn't there. Verify any change to this both ways.

The scaffolding sits there and not under `sessions/` because `sessions/` is documented as real
archived analysis. Debris there invites a tidy-up, and it got one: both folders were deleted from
the working tree, three fixtures went red, and validate reported green throughout. A comment saying
"do not delete" is the weakest possible guard — it is read by nobody at the moment of deletion.
"""
import json
import os
import subprocess
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
HOOKS_DIR = os.path.dirname(TESTS_DIR)
ROOT = os.path.dirname(os.path.dirname(HOOKS_DIR))
SANDBOX = os.path.join(TESTS_DIR, "fixtures")
# Not a fixture directory: it holds the filesystem verdict_gate resolves Saved: marks against.
NOT_A_HOOK_DIR = {"fixtures"}


def _haystack(out):
    """The raw stdout PLUS every string inside it, when it is JSON.

    Hooks emit `json.dumps(...)` at its default `ensure_ascii=True`, so an em-dash on the wire is
    the six characters `\\u2014`. Matching only the raw text would mean fixtures had to assert the
    ESCAPED form — which is invisible until it bites, and bites hardest on exactly the messages
    worth asserting, since a hook's prose uses dashes and Korean freely.

    So assertions run against what the model actually reads. Both forms are searched, because a
    fixture written either way should work."""
    hay = [out]

    def walk(node):
        if isinstance(node, str):
            hay.append(node)
        elif isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    try:
        walk(json.loads(out))
    except Exception:  # noqa: BLE001 — plain-text output is fine; the raw string is already in hay
        pass
    return "\n".join(hay)


def check(expect, out):
    """Return an error string, or None when the output matches. Structural only — never semantic."""
    if expect.get("silent"):
        return None if out.strip() == "" else f"expected SILENT, got: {out[:120]!r}"
    out = _haystack(out)
    miss = [s for s in expect.get("contains", []) if s not in out]
    if miss:
        return f"missing {miss}"
    bad = [s for s in expect.get("excludes", []) if s in out]
    if bad:
        return f"unexpectedly present {bad}"
    if not expect.get("contains") and not expect.get("excludes"):
        return "_expect names no assertion (need `silent`, `contains`, or `excludes`)"
    return None


def discover():
    """Yield (rel_name, hook_script, expect_or_None) for every fixture, sorted for stable output."""
    for d in sorted(os.listdir(TESTS_DIR)):
        if d in NOT_A_HOOK_DIR or not os.path.isdir(os.path.join(TESTS_DIR, d)):
            continue
        hook = os.path.join(HOOKS_DIR, d + ".py")
        for f in sorted(os.listdir(os.path.join(TESTS_DIR, d))):
            if not f.endswith(".json"):
                continue
            path = os.path.join(TESTS_DIR, d, f)
            payload = json.load(open(path, encoding="utf-8"))
            yield f"{d}/{f[:-5]}", hook, payload.get("_expect")


def main():
    fails = total = 0
    for name, hook, expect in discover():
        total += 1
        if not os.path.isfile(hook):
            print(f"FAIL  {name}: no hook script at {os.path.relpath(hook, ROOT)} "
                  f"(the directory name must match a hook in .claude/hooks/)")
            fails += 1
            continue
        if expect is None:
            print(f"FAIL  {name}: fixture carries no `_expect` key, so it asserts nothing")
            fails += 1
            continue
        payload = open(os.path.join(TESTS_DIR, name + ".json"), encoding="utf-8").read()
        p = subprocess.run([sys.executable, hook], input=payload, cwd=ROOT,
                           env={**os.environ, "CLAUDE_PROJECT_DIR": SANDBOX},
                           capture_output=True, text=True)
        err = check(expect, p.stdout)
        if err:
            print(f"FAIL  {name}: {err}; stdout={p.stdout[:160]!r}")
            fails += 1
        else:
            print(f"ok    {name}")
    if not total:
        print("FAIL  no fixtures discovered — the suite would pass by finding nothing")
        sys.exit(1)
    print(f"\n{total - fails}/{total} fixtures passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
