#!/usr/bin/env python3
"""SessionStart hook — fail loud if the harness wiring regressed, stay silent when it's green.

The deterministic layer's whole value is that it grades nothing and never drifts; a judgment leak or
a broken skill is invisible until a call inverts. This hook runs `serenity_harness.py validate` at
session start and injects a WARNING only when something is not green — keeping the happy path
noise-free (no per-session context tax) and surfacing a regression the moment it matters. It can
never break the session: every failure path below still exits 0.

THREE FAILURES, NOT ONE. This hook used to wrap everything in a bare `except: return`, which mapped
"validate is healthy and green" and "validate crashed with a traceback" onto the identical silent
output. That is the worst possible signature for a health check: the harness reports perfect health
*precisely because* its health check is broken, and the louder the breakage the quieter the hook.
So the three are now distinguished:

  - **red** — validate ran, returned JSON, `ok: false`. A real regression.
  - **crashed** — validate ran but produced no parseable JSON. The self-check itself is broken, and
    nothing downstream of it can be trusted, including the green it can no longer report.
  - **timed out** — validate did not finish. This became a signal rather than a non-event when the
    hook fixture suite was wired into validate: a timeout now means the fixtures did not finish, so
    swallowing it would restore exactly the blind spot this hook exists to remove. If it starts
    firing, something in validate has gone network-bound — that is the bug, not the timeout.

Genuinely-nothing-to-report stays silent: no venv, no validator script, an empty checkout. Those
mean the harness isn't installed here, not that it regressed.
"""

import json
import os
import subprocess
import sys


def _emit(ctx):
	print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ctx}}))


def main():
	root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
	py = os.path.join(root, "scripts", ".venv", "bin", "python")
	script = os.path.join(root, "scripts", "serenity_harness.py")
	if not (os.path.isfile(py) and os.path.isfile(script)):
		return  # not installed here — nothing to report
	try:
		out = subprocess.run(
			[py, script, "validate"],
			capture_output=True, text=True, timeout=30, cwd=root,
		)
	except subprocess.TimeoutExpired:
		_emit("[harness-status] serenity_harness.py validate TIMED OUT after 30s, so the harness is "
		      "unverified this session. Since the hook fixture suite runs inside validate, a timeout "
		      "means the fixtures did not finish — most likely something in validate has gone "
		      "network-bound. Run it directly to see where it hangs.")
		return
	except Exception as e:  # noqa: BLE001 — a self-check that can't run must not block the session
		_emit(f"[harness-status] serenity_harness.py validate could not be run "
		      f"({type(e).__name__}: {e}). The harness is unverified this session.")
		return
	try:
		report = json.loads(out.stdout)
	except Exception:  # noqa: BLE001
		tail = (out.stderr or out.stdout or "").strip().splitlines()
		_emit("[harness-status] serenity_harness.py validate CRASHED — it exited "
		      f"{out.returncode} without parseable JSON, so the self-check itself is broken and its "
		      "silence is not evidence of health. Last line: "
		      f"{tail[-1][:200] if tail else '(no output)'}")
		return
	if report.get("ok"):
		return  # green — stay silent, no per-session context tax
	summary = report.get("summary") or {}
	bad = [c for c in (report.get("checks") or []) if c.get("status") == "fail"]
	detail = "; ".join(f"{c.get('check')}: {c.get('detail', '')}" for c in bad) or "see validate"
	_emit(
		f"[harness-status] serenity_harness.py validate is RED "
		f"(pass={summary.get('pass')} warn={summary.get('warn')} fail={summary.get('fail')}). "
		f"Failing: {detail}. The deterministic layer or a skill regressed — fix the wiring before trusting a call."
	)


if __name__ == "__main__":
	main()
	sys.exit(0)
