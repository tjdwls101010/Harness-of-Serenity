#!/usr/bin/env python3
"""PostToolUse hook — flag a session scorecard that violates its own pinned schema, at write time.

All seven scorecards in the archive violate the schema `.claude/agents/serenity-scorecard.md` pins,
including the one field that body explicitly forbids, and `validate` reported green throughout —
because its scorecard check greps the AGENT FILE for the strings `gate_strength:` and `conviction:`.
It verified that the spec contains its own sentinels, never that any produced file conformed. A
schema nothing reads at write time is a suggestion.

This fires at the moment the context to fix it is still live: the model has the pipeline output in
hand and can supply the missing `mc` or `data_as_of` for free. An hour later that costs a re-run.

SOFT ONLY. A malformed scorecard is bad analysis hygiene, not a corrupted harness, and a hook that
blocks often becomes a hook people disable — there is exactly one hard block in this whole layer and
it guards the NFI/NFA disclaimer.

THE SCHEMA LIVES IN ONE PLACE. This shells out to `serenity_harness.py scorecard-lint` rather than
reimplementing the field list, the same way `session_status.py` shells out to `validate`. Two
implementations of one enum set is how the enum set stops being one — and the drift being fixed here
started as exactly that kind of gap.

WHY THE PATH FILTER IS IN THIS SCRIPT AND NOT IN settings.json's `if` FIELD.
`run_fixtures.py` pipes payloads straight to the hook script and never reads settings.json, so
anything expressed as `"if": "Write(sessions/**)"` is invisible to the regression suite BY
CONSTRUCTION — unfixable, not merely untested. Putting the most failure-prone logic where the
self-check cannot see it defeats the point of having a self-check. Two lesser reasons: a glob on
`Write` misses `Edit`/`MultiEdit`, which is how a scorecard gets revised; and a naive `sessions/`
substring would match this suite's own `fixtures/sessions/` sandbox. The filter here is a
repo-root-relative PREFIX test, so the sandbox is out of scope by position rather than by luck.

The failure mode of a too-narrow filter is silence, which is indistinguishable from "the file was
fine." That is the same shape as every other defect this hook layer had.
"""

import json
import os
import re
import subprocess
import sys

# `_ranking.md`, `_macro.md`, `_sectormap.json` are synthesis artifacts with their own shapes; only
# per-name scorecards carry this schema. The convention is that scorecards are TICKER.md and
# synthesis files lead with an underscore.
_SCORECARD_NAME = re.compile(r"^[A-Z0-9][A-Z0-9.\-]*\.md$")

# Two different roots, deliberately.
#
# The LINTER is found relative to this file, because the hook and the harness ship together — this
# script is always at <repo>/.claude/hooks/, so the repo is three levels up regardless of what any
# environment variable says.
#
# The SESSIONS SCOPE comes from CLAUDE_PROJECT_DIR, because that is the tree whose archive is being
# written. Splitting them is what lets the fixture suite point CLAUDE_PROJECT_DIR at its own sandbox
# and still exercise the real linter — a hook that could only run against the live archive could
# only be tested by writing junk into it.
_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _target_paths(data):
	"""Every file path this tool call wrote. Write/Edit carry one; MultiEdit may carry a batch."""
	ti = data.get("tool_input") or {}
	paths = []
	if isinstance(ti.get("file_path"), str):
		paths.append(ti["file_path"])
	for e in (ti.get("edits") or []):
		if isinstance(e, dict) and isinstance(e.get("file_path"), str):
			paths.append(e["file_path"])
	return paths


def main():
	try:
		data = json.load(sys.stdin)
	except Exception:  # noqa: BLE001 — a hook must never crash a turn
		return
	if data.get("tool_name") not in ("Write", "Edit", "MultiEdit"):
		return
	root = os.environ.get("CLAUDE_PROJECT_DIR") or _REPO
	sessions = os.path.join(os.path.realpath(root), "sessions") + os.sep
	py = os.path.join(_REPO, "scripts", ".venv", "bin", "python")
	script = os.path.join(_REPO, "scripts", "serenity_harness.py")
	if not (os.path.isfile(py) and os.path.isfile(script)):
		return  # harness not installed here — nothing to check against

	# Prefix test on the resolved path: a substring match on "sessions/" would also catch the hook
	# suite's own fixtures/sessions/ sandbox, which exists precisely to hold deliberately-malformed
	# files.
	targets = [
		p for p in _target_paths(data)
		if os.path.realpath(p).startswith(sessions) and _SCORECARD_NAME.match(os.path.basename(p))
	]
	if not targets:
		return

	flags = []
	for path in targets:
		try:
			out = subprocess.run([py, script, "scorecard-lint", path],
			                     capture_output=True, text=True, timeout=20, cwd=root)
			report = json.loads(out.stdout)
		except Exception:  # noqa: BLE001
			continue  # the linter is unavailable; say nothing rather than guess at the schema
		for r in report.get("reports", []):
			if r.get("conforms") or r.get("grandfathered"):
				continue
			v = r.get("violations", [])
			# Truncated because ten lines of frontmatter complaints is noise that gets skimmed —
			# but the remainder is COUNTED and named, never silently dropped. A guard that hides
			# how much it hid is how "I fixed what it flagged" turns into a file still failing.
			shown = "; ".join(v[:4])
			more = f" (+{len(v) - 4} more — run `serenity_harness.py scorecard-lint` for the full list)" if len(v) > 4 else ""
			flags.append(f"- {os.path.basename(r['file'])}: {shown}{more}")
	if not flags:
		return
	print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext":
		"[scorecard-schema] This file does not match the schema pinned in "
		"`.claude/agents/serenity-scorecard.md` (NOT a judgment about the analysis — format only):\n"
		+ "\n".join(flags) +
		"\nFix it now while the pipeline output is still in context; `date`/`data_as_of`/`mc` cost a "
		"re-run to recover later. `tier` belongs in the synthesizer's _ranking.md, never here."}}))


if __name__ == "__main__":
	main()
	sys.exit(0)
