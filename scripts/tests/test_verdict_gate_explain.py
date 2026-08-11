"""Coverage for `verdict_gate.py --explain` — the structural oracle the reproduction eval
(`scripts/serenity_eval.py`, docs/plan/260810/04-measurement-instrument.md §4.5) calls instead of
reimplementing this hook's regexes a second time.

`evaluate()` inside the hook is the only place these predicates are computed; `--explain` just dumps
its return value as JSON, and hook mode formats the same value into a block reason / Stop context /
nothing. So the test that matters most here is the invariance check at the bottom: `--explain`'s
`decision` must agree with what hook mode itself prints, for every fixture already committed under
`.claude/hooks/tests/verdict_gate/`. If the two ever disagree, the two output modes have somehow
stopped sharing one function — exactly the drift this split exists to make impossible.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
ROOT = SCRIPTS_DIR.parent
HOOK = ROOT / ".claude" / "hooks" / "verdict_gate.py"
FIXTURES_DIR = ROOT / ".claude" / "hooks" / "tests" / "verdict_gate"
# The same sandbox run_fixtures.py points CLAUDE_PROJECT_DIR at, so a `Saved:` mark resolves against
# real scaffolding (an actual .md file at sessions/990101.hook-fixture/, a deliberately empty folder
# at 990102.hook-empty/) instead of whatever this checkout happens to have lying around.
SANDBOX = ROOT / ".claude" / "hooks" / "tests" / "fixtures"


def _run(payload_text, *extra_args):
	"""Pipe raw JSON text to the real hook script, exactly as Claude Code / run_fixtures.py do."""
	env = {**os.environ, "CLAUDE_PROJECT_DIR": str(SANDBOX)}
	return subprocess.run(
		[sys.executable, str(HOOK), *extra_args],
		input=payload_text, capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=30,
	)


def _explain_text(payload_text: str) -> dict:
	p = _run(payload_text, "--explain")
	assert p.returncode == 0, f"--explain exited {p.returncode}: stderr={p.stderr!r}"
	return json.loads(p.stdout)


def _explain(payload: dict) -> dict:
	return _explain_text(json.dumps(payload))


def _hook_decision(payload_text: str) -> str:
	"""Classify what hook mode (no args, the real Claude Code invocation) actually printed, the same
	three ways `evaluate()` itself does: nothing -> silent, `{"decision": ...}` -> block, a Stop
	`hookSpecificOutput` -> context."""
	p = _run(payload_text)
	assert p.returncode == 0, f"hook mode exited {p.returncode}: stderr={p.stderr!r}"
	out = p.stdout.strip()
	if not out:
		return "silent"
	data = json.loads(out)
	if "decision" in data:
		return data["decision"]
	if "hookSpecificOutput" in data:
		return "context"
	raise AssertionError(f"hook mode printed an unrecognized shape: {out[:200]!r}")


def _fixture_message(name: str) -> str:
	payload = json.loads((FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8"))
	return payload["last_assistant_message"]


# --- required cases, each asserting the exact `checks` dict --------------------------------------

def test_clean_full_verdict_is_silent_with_every_check_true():
	"""silent_full.json — a complete verdict (TLDR, NFI/NFA, Lens: line, Downsides, Falsifier, both
	legs, a valid Saved: mark pointing at a real .md). Nothing to complain about anywhere."""
	result = _explain({"last_assistant_message": _fixture_message("silent_full"), "stop_hook_active": False})
	assert result["decision"] == "silent"
	assert result["checks"] == {
		"entered": True, "signoff": True, "tldr": True, "lens_line": True,
		"downsides": True, "falsifier": True, "both_legs": True, "saved_mark": True,
	}


def test_verdict_missing_nfi_blocks_on_signoff():
	"""hard_nfi.json — same shape as silent_full but the sign-off is missing. Every other check still
	passes; only signoff flips, and that alone is enough to force decision=block."""
	result = _explain({"last_assistant_message": _fixture_message("hard_nfi"), "stop_hook_active": False})
	assert result["decision"] == "block"
	assert result["checks"] == {
		"entered": True, "signoff": False, "tldr": True, "lens_line": True,
		"downsides": True, "falsifier": True, "both_legs": True, "saved_mark": True,
	}


def test_harness_dev_report_quoting_finance_vocab_does_not_block():
	"""dev_report_quoting_finance_vocab_silent.json quotes a price target, a rating, and "overweight"
	while narrating this very hook's own fixtures — single_name/strong_verdict fire on the vocabulary,
	but the message also names `verdict_gate.py` and `run_fixtures.py`, so `repo_artifact` overrides
	and `finance_signal` stays False regardless. That is the load-bearing assertion.

	`entered` lands False for this exact fixture too (it never carries a TLDR token either), which is
	worth recording plainly rather than papering over: the task brief hedged "entered may be true" and
	for this concrete case it is not. The mechanism the case is actually about — repo_artifact beating
	a real finance-vocabulary match — holds regardless of entered's value here."""
	result = _explain({
		"last_assistant_message": _fixture_message("dev_report_quoting_finance_vocab_silent"),
		"stop_hook_active": False,
	})
	assert result["signals"]["finance_signal"] is False
	assert result["signals"]["repo_artifact"] is True
	assert result["signals"]["single_name"] is True          # the vocabulary really is there
	assert result["decision"] != "block"
	assert result["decision"] == "silent"
	assert result["checks"] == {
		"entered": False, "signoff": None, "tldr": None, "lens_line": None,
		"downsides": None, "falsifier": None, "both_legs": None, "saved_mark": None,
	}


def test_macro_only_answer_leaves_lens_line_not_applicable():
	"""macro_overweight_silent.json trips strong_verdict's vocabulary ("overweight semis, underweight
	defensives") but names no company, so single_name is False. checks.lens_line must be None (n/a),
	never False — collapsing the two would manufacture a miss on an answer the hook never questioned,
	the exact n/a-vs-0 distinction 04-measurement-instrument.md §4.3 is about."""
	result = _explain({"last_assistant_message": _fixture_message("macro_overweight_silent"), "stop_hook_active": False})
	assert result["signals"]["single_name"] is False
	assert result["checks"]["lens_line"] is None
	assert result["checks"] == {
		"entered": True, "signoff": True, "tldr": True, "lens_line": None,
		"downsides": None, "falsifier": None, "both_legs": None, "saved_mark": True,
	}


def test_stop_hook_active_still_emits_a_full_silent_object():
	"""Hook mode returns silently on stop_hook_active (the one-corrective-round guard) without even
	looking at the message. --explain must still answer — the eval needs a verdict, not silence — so
	it reports decision=silent, entered=false, and every signal/check at its empty default rather than
	reflecting the (unread) message content."""
	result = _explain({
		"last_assistant_message": "TLDR: $NVDA priced-in but a quality compounder — I'd nibble. NFI/NFA.",
		"stop_hook_active": True,
	})
	assert result["decision"] == "silent"
	assert result["checks"]["entered"] is False
	assert all(v is None for k, v in result["checks"].items() if k != "entered")
	assert all(v is False for v in result["signals"].values())


def test_malformed_stdin_reports_an_error_and_exits_nonzero():
	"""--explain's caller is a program (the eval), not a human watching a transcript — it needs a
	machine-checkable failure, not silence."""
	p = _run("not valid json {{{", "--explain")
	assert p.returncode != 0
	payload = json.loads(p.stdout)
	assert "error" in payload


def test_malformed_stdin_stays_silent_in_hook_mode():
	"""The identical malformed input must not crash hook mode — a hook that raises kills the turn, and
	that guard must survive the --explain refactor untouched."""
	p = _run("not valid json {{{")
	assert p.returncode == 0
	assert p.stdout.strip() == ""


# --- invariance: --explain must agree with what the real hook actually prints --------------------

_FIXTURE_NAMES = sorted(p.stem for p in FIXTURES_DIR.glob("*.json"))


@pytest.mark.parametrize("name", _FIXTURE_NAMES)
def test_explain_decision_agrees_with_hook_mode(name):
	"""The most important test in this file. Run every committed verdict_gate fixture through BOTH
	hook mode and --explain, on the exact same bytes, and assert they name the same decision.
	`evaluate()` is the one function behind both output modes, so a divergence here means hook mode
	and --explain have somehow stopped computing the same thing — the drift this whole split exists to
	make structurally impossible. This reddens on that divergence; nothing else in this file would."""
	raw = (FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8").replace("{{SANDBOX}}", str(SANDBOX))
	expected = _hook_decision(raw)
	explained = _explain_text(raw)
	assert explained["decision"] == expected, (
		f"{name}: hook mode printed decision={expected!r} but --explain says {explained['decision']!r}"
	)
