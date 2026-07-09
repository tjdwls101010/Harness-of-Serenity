#!/usr/bin/env python3
"""SessionStart hook — fail loud if the harness wiring regressed, stay silent when it's green.

The deterministic layer's whole value is that it grades nothing and never drifts; a judgment leak or
a broken skill is invisible until a call inverts. This hook runs `serenity_harness.py validate` at
session start and injects a WARNING only when something is not green — keeping the happy path
noise-free (no per-session context tax) and surfacing a regression the moment it matters. It can
never break the session: any failure to run is swallowed and the session proceeds.
"""

import json
import os
import subprocess
import sys


def main():
	root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
	py = os.path.join(root, "scripts", ".venv", "bin", "python")
	script = os.path.join(root, "scripts", "serenity_harness.py")
	if not (os.path.isfile(py) and os.path.isfile(script)):
		return
	try:
		out = subprocess.run(
			[py, script, "validate"],
			capture_output=True, text=True, timeout=30, cwd=root,
		)
		report = json.loads(out.stdout)
	except Exception:  # noqa: BLE001 — a self-check that can't run must not block the session
		return
	if report.get("ok"):
		return  # green — stay silent, no per-session context tax
	summary = report.get("summary") or {}
	bad = [c for c in (report.get("checks") or []) if c.get("status") == "fail"]
	detail = "; ".join(f"{c.get('check')}: {c.get('detail', '')}" for c in bad) or "see validate"
	ctx = (
		f"[harness-status] serenity_harness.py validate is RED "
		f"(pass={summary.get('pass')} warn={summary.get('warn')} fail={summary.get('fail')}). "
		f"Failing: {detail}. The deterministic layer or a skill regressed — fix the wiring before trusting a call."
	)
	print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))


if __name__ == "__main__":
	main()
	sys.exit(0)
