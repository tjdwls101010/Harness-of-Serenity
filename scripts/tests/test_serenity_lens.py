import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "serenity_lens.py"
PIPELINE_SCRIPT = ROOT / "scripts" / "serenity_pipeline.py"
GOLDEN_FIXTURE = ROOT / "scripts" / "tests" / "golden" / "MU.inputs.json"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
	return subprocess.run(
		[sys.executable, str(SCRIPT), *args],
		cwd=ROOT,
		capture_output=True,
		text=True,
		check=False,
	)


def _payload(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
	return json.loads(proc.stdout)


def _load_module():
	"""Direct-import serenity_lens.py for structural introspection (the argparse tree,
	the private _hook_marker_present helper) — everything else in this file drives the
	CLI as a subprocess, matching test_serenity_sectormap.py's black-box style. Only the
	seam-constraint tests need the live Python objects, since checking "no subcommand
	accepts a ticker" by scraping --help text would miss a bare positional argument
	(argparse renders those without a leading `--`, so a text scan for `--[\\w-]+` tokens
	would silently pass one right through).
	"""
	spec = importlib.util.spec_from_file_location("serenity_lens_test", SCRIPT)
	assert spec is not None and spec.loader is not None
	module = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(module)
	return module


def _subparser_choices(module: Any) -> dict[str, argparse.ArgumentParser]:
	parser = module.build_parser()
	subparsers_action = next(
		action for action in parser._actions
		if isinstance(action, argparse._SubParsersAction)
	)
	return subparsers_action.choices


# Independent copy of .claude/hooks/verdict_gate.py's `lens_marker` regex, snapshotted
# from that file's source rather than imported from it: a sibling task edits that hook
# concurrently with this one, so importing it would make this suite's pass/fail depend
# on unrelated concurrent edits landing in a particular order. This test's job is "does
# our Lens line satisfy the documented contract", not "does whatever the hook currently
# contains happen to accept it" — if the hook's regex is ever revised, both this copy and
# serenity_lens.py's own `_hook_marker_present` need a deliberate re-sync.
_HOOK_LENS_RE_1 = re.compile(r"Lens:[^\n]*[×÷*][^\n]*=")
_HOOK_LENS_RE_2 = re.compile(r"Lens:[^\n]*=[^\n]*[×÷*]")


def _hook_would_accept(line: str) -> bool:
	return bool(_HOOK_LENS_RE_1.search(line)) or bool(_HOOK_LENS_RE_2.search(line))


# One valid sample invocation per subcommand — used by every test that just needs "a
# successful run", so the seam-constraint tests don't have to hardcode driver arithmetic.
SAMPLE_ARGS: dict[str, list[str]] = {
	"content-volume": ["--content", "42", "--volume", "180e6", "--mc", "101.3e9"],
	"mw-irr": ["--rev-per-mw", "9000000", "--cogs-per-mw", "6000000", "--mw", "50", "--financing-rate", "0.08"],
	"replacement-cost": ["--capacity-units", "1000000", "--cost-per-unit", "400", "--comp-ev-per-unit", "250"],
	"pro-forma-fcf": ["--cogs-addressable", "5e6", "--opex-saved", "2e6", "--new-recurring-rev", "3e6", "--multiple", "15"],
	"net-cash-after-atm": ["--raised", "500e6", "--shares-cost", "50e6", "--sbc-funded", "20e6"],
	"sum-of-parts": ["--stake-value", "12e9", "--operating-value", "3e9", "--parent-mc", "9e9"],
	"custom": ["--expr", "a×b÷c", "--inputs", "a=42,b=180e6,c=101.3e9"],
}
NAMED_DRIVER_ARGS = {name: args for name, args in SAMPLE_ARGS.items() if name != "custom"}

FORBIDDEN_VALUATION_WORDS = (
	"cheap", "expensive", "priced", "rich", "buy", "sell", "pass",
	"overvalued", "undervalued", "attractive", "compelling",
)


@pytest.fixture(scope="session")
def run_payload_path(tmp_path_factory: pytest.TempPathFactory) -> str:
	"""A real `serenity_pipeline.py evidence --fixture` replay of the MU golden fixture,
	written once to a session-scoped tmp file so every --from-run test reads the ACTUAL
	analyze/evidence payload shape (key_facts.marketCap) instead of a hand-rolled mock
	that could silently drift from what the pipeline really emits. No network call:
	`evidence --fixture` only replays a frozen local JSON file (see
	scripts/pipeline/_evidence.py cmd_evidence, which just json.load()s the fixture).
	"""
	proc = subprocess.run(
		[sys.executable, str(PIPELINE_SCRIPT), "evidence", "--fixture", str(GOLDEN_FIXTURE)],
		cwd=ROOT,
		capture_output=True,
		text=True,
		check=True,
	)
	path = tmp_path_factory.mktemp("lens") / "mu_run.json"
	path.write_text(proc.stdout, encoding="utf-8")
	return str(path)


@pytest.fixture(scope="session")
def real_market_cap() -> float:
	with GOLDEN_FIXTURE.open(encoding="utf-8") as handle:
		fixture = json.load(handle)
	return float(fixture["l4"]["info"]["marketCap"])


# --------------------------------------------------------------------------------------
# Seam constraints — mechanical, not stylistic. Each of these is meant to fail loudly
# (and say why) if a future change quietly lets a judgment slip into this file.
# --------------------------------------------------------------------------------------


def test_subcommand_set_is_exactly_the_fixed_driver_list() -> None:
	module = _load_module()
	choices = set(_subparser_choices(module))
	assert choices == set(SAMPLE_ARGS), (
		f"subcommand set changed to {choices!r} — if this is a deliberate new driver, "
		"extend SAMPLE_ARGS deliberately; if it's an auto-select/recommend feature, it "
		"violates the closed-driver-list seam (task brief: 'never ranks drivers, never "
		"selects which lens applies')"
	)


def test_no_argument_across_any_subcommand_accepts_a_ticker_or_archetype() -> None:
	"""Introspects the live argparse tree (dest + option strings) rather than checking a
	hardcoded flag list, so a flag added later — on ANY subcommand — is caught here too.
	"""
	module = _load_module()
	forbidden_substrings = ("ticker", "archetype", "sector", "symbol")
	offenders = []
	for name, subparser in _subparser_choices(module).items():
		for action in subparser._actions:
			haystack = " ".join([action.dest or "", *action.option_strings]).lower()
			for word in forbidden_substrings:
				if word in haystack:
					offenders.append((name, action.option_strings or [action.dest], word))
	assert offenders == [], (
		f"a subcommand argument surface accepts a ticker/archetype-shaped input: "
		f"{offenders} — this tool must never select or scope a driver by identity, only "
		"compute arithmetic on numbers the model already decided on"
	)


@pytest.mark.parametrize("command", sorted(SAMPLE_ARGS))
def test_output_never_contains_valuation_vocabulary(command: str) -> None:
	proc = _run(command, *SAMPLE_ARGS[command])
	assert proc.returncode == 0
	lowered = proc.stdout.lower()
	hits = [word for word in FORBIDDEN_VALUATION_WORDS if re.search(rf"\b{word}\b", lowered)]
	assert hits == [], f"{command} output contains forbidden valuation vocabulary: {hits}"


@pytest.mark.parametrize("fork", ["floor", "upside"])
@pytest.mark.parametrize("command", sorted(SAMPLE_ARGS))
def test_output_never_contains_valuation_vocabulary_with_fork_tag(command: str, fork: str) -> None:
	proc = _run(command, *SAMPLE_ARGS[command], "--fork", fork)
	assert proc.returncode == 0
	lowered = proc.stdout.lower()
	hits = [word for word in FORBIDDEN_VALUATION_WORDS if re.search(rf"\b{word}\b", lowered)]
	assert hits == [], f"{command} --fork {fork} output contains forbidden vocabulary: {hits}"


@pytest.mark.parametrize("command", sorted(NAMED_DRIVER_ARGS))
def test_every_named_driver_lens_line_satisfies_the_stop_hook_marker(command: str) -> None:
	"""The whole point of claim (3) in the task brief: a driver's Lens line must be a
	checkable fact, not a hope that the model composed it correctly by hand. Every fixed
	doctrine driver (everything except the open-ended `custom`) is guaranteed by
	construction to satisfy the Stop hook's marker regex.
	"""
	proc = _run(command, *NAMED_DRIVER_ARGS[command])
	assert proc.returncode == 0
	payload = _payload(proc)
	assert _hook_would_accept(payload["lens"])
	assert payload["hook_marker_present"] is True


def test_sum_of_parts_requires_a_denominator_to_stay_a_ratio_not_a_subtotal() -> None:
	"""sum-of-parts is doctrine's own callout: it is the ADDITIVE case that keeps
	breaking the hook's operator regex when composed by hand. This tool ends that class
	of problem by construction — by refusing to emit a bare (stake + operating) subtotal
	with no comparison point, which is what guarantees the ÷ character (and hence hook
	compliance) is never optional for this driver, not merely likely.
	"""
	proc = _run("sum-of-parts", "--stake-value", "12e9", "--operating-value", "3e9")
	assert proc.returncode != 0
	assert _payload(proc)["error"] == "missing_denominator"


def test_content_volume_requires_a_denominator_too() -> None:
	proc = _run("content-volume", "--content", "42", "--volume", "180e6")
	assert proc.returncode != 0
	assert _payload(proc)["error"] == "missing_denominator"


# --------------------------------------------------------------------------------------
# `custom` — the escape hatch: must be genuinely usable, and safe.
# --------------------------------------------------------------------------------------


def test_custom_purely_additive_expression_is_honestly_flagged_not_forced() -> None:
	"""custom must stay a real escape hatch — including for an expression that is pure
	addition, which this tool must NOT fake an operator into. It just tells the truth
	about whether the line would satisfy the hook, via hook_marker_present.
	"""
	proc = _run("custom", "--expr", "a+b-c", "--inputs", "a=10,b=5,c=2")
	assert proc.returncode == 0
	payload = _payload(proc)
	assert payload["result"] == pytest.approx(13.0)
	assert payload["hook_marker_present"] is False
	assert not _hook_would_accept(payload["lens"])


def test_custom_with_an_operator_satisfies_the_hook_marker() -> None:
	proc = _run("custom", "--expr", "a×b÷c", "--inputs", "a=42,b=180e6,c=101.3e9")
	payload = _payload(proc)
	assert payload["hook_marker_present"] is True
	assert _hook_would_accept(payload["lens"])


def test_custom_accepts_ascii_operators_too() -> None:
	proc = _run("custom", "--expr", "a*b/c", "--inputs", "a=42,b=180e6,c=101.3e9")
	assert proc.returncode == 0
	payload = _payload(proc)
	assert payload["result"] == pytest.approx((42 * 180e6) / 101.3e9)
	# displayed canonicalized to the doctrine glyphs regardless of ASCII input
	assert "×" in payload["lens"] and "÷" in payload["lens"]


def test_custom_arithmetic_matches_content_volume() -> None:
	proc = _run("custom", "--expr", "a×b÷c", "--inputs", "a=42,b=180e6,c=101.3e9")
	payload = _payload(proc)
	assert payload["result"] == pytest.approx((42 * 180e6) / 101.3e9)


def test_custom_supports_parentheses() -> None:
	proc = _run("custom", "--expr", "(a+b)÷c", "--inputs", "a=4,b=6,c=5")
	payload = _payload(proc)
	assert payload["result"] == pytest.approx((4 + 6) / 5)


@pytest.mark.parametrize(
	"expr",
	[
		'__import__("os").system("echo pwned")',
		'open("/etc/passwd")',
		"a**b",
		"[x for x in range(3)]",
		"(lambda: 1)()",
		"a if b else c",
		"a and b",
		'a+"x"',
		"",
		"a+(b",
	],
)
def test_custom_rejects_disallowed_or_malformed_expressions_without_executing_them(expr: str) -> None:
	"""ast.eval() is never called on the raw string — the parsed tree is walked under a
	strict allowlist, so a crafted --expr has no path to execute anything beyond +-*/ on
	the named inputs. Every case here must fail CLEANLY (a JSON error, exit 1) rather
	than crash or, worse, succeed.
	"""
	proc = _run("custom", "--expr", expr, "--inputs", "a=1,b=2,c=3")
	assert proc.returncode == 1
	assert proc.stderr == ""
	payload = _payload(proc)
	assert payload["error"] == "invalid_expr"


def test_custom_expr_division_by_zero_is_a_clean_error() -> None:
	proc = _run("custom", "--expr", "a÷b", "--inputs", "a=1,b=0")
	assert proc.returncode == 1
	assert _payload(proc)["error"] == "division_by_zero"


def test_custom_expr_referencing_undefined_input_is_a_clean_error() -> None:
	proc = _run("custom", "--expr", "a×z", "--inputs", "a=1,b=2")
	assert proc.returncode == 1
	assert _payload(proc)["error"] == "invalid_expr"


@pytest.mark.parametrize(
	"inputs_value",
	["a", "", "a=banana", "1foo=2", "a=1=2"],
)
def test_custom_inputs_rejects_malformed_pairs(inputs_value: str) -> None:
	proc = _run("custom", "--expr", "a", "--inputs", inputs_value)
	assert proc.returncode == 1
	assert _payload(proc)["error"] == "invalid_inputs"


# --------------------------------------------------------------------------------------
# --from-run — the market-cap denominator provenance mechanism (task brief claim 1)
# --------------------------------------------------------------------------------------


def test_from_run_reads_market_cap_from_the_real_pipeline_payload(run_payload_path: str, real_market_cap: float) -> None:
	proc = _run("content-volume", "--content", "42", "--volume", "180e6", "--from-run", run_payload_path)
	assert proc.returncode == 0
	payload = _payload(proc)
	assert payload["inputs"]["mc"] == pytest.approx(real_market_cap)
	assert "key_facts.marketCap" in payload["lens"]
	assert run_payload_path in payload["lens"]
	assert "UNVERIFIED" not in payload["lens"]
	assert "MU" in payload["lens"]


def test_hand_typed_mc_is_labeled_unverified() -> None:
	proc = _run("content-volume", "--content", "42", "--volume", "180e6", "--mc", "101.3e9")
	assert proc.returncode == 0
	payload = _payload(proc)
	assert "UNVERIFIED" in payload["lens"]


def test_from_run_wins_over_hand_typed_mc_and_says_so(run_payload_path: str, real_market_cap: float) -> None:
	proc = _run(
		"content-volume", "--content", "42", "--volume", "180e6",
		"--mc", "5000000000", "--from-run", run_payload_path,
	)
	assert proc.returncode == 0
	payload = _payload(proc)
	assert payload["inputs"]["mc"] == pytest.approx(real_market_cap)
	assert "also given" in payload["lens"]
	assert "--from-run wins" in payload["lens"]


def test_neither_mc_nor_from_run_is_a_clear_error() -> None:
	proc = _run("content-volume", "--content", "42", "--volume", "180e6")
	assert proc.returncode != 0
	assert proc.stderr == ""
	assert _payload(proc)["error"] == "missing_denominator"


def test_from_run_missing_file_is_a_clear_error() -> None:
	proc = _run("content-volume", "--content", "1", "--volume", "1", "--from-run", "/nonexistent/path.json")
	assert proc.returncode != 0
	payload = _payload(proc)
	assert payload["error"] == "run_not_found"


def test_from_run_malformed_json_is_a_clear_error(tmp_path: Path) -> None:
	bad = tmp_path / "bad.json"
	bad.write_text("{not json", encoding="utf-8")
	proc = _run("content-volume", "--content", "1", "--volume", "1", "--from-run", str(bad))
	assert proc.returncode != 0
	assert _payload(proc)["error"] == "malformed_run"


def test_from_run_missing_key_facts_is_a_clear_error(tmp_path: Path) -> None:
	missing = tmp_path / "missing_kf.json"
	missing.write_text(json.dumps({"ticker": "XX"}), encoding="utf-8")
	proc = _run("content-volume", "--content", "1", "--volume", "1", "--from-run", str(missing))
	assert proc.returncode != 0
	assert _payload(proc)["error"] == "market_cap_unavailable"


def test_from_run_null_market_cap_is_a_clear_error(tmp_path: Path) -> None:
	null_mc = tmp_path / "null_mc.json"
	null_mc.write_text(json.dumps({"ticker": "XX", "key_facts": {"marketCap": None}}), encoding="utf-8")
	proc = _run("content-volume", "--content", "1", "--volume", "1", "--from-run", str(null_mc))
	assert proc.returncode != 0
	assert _payload(proc)["error"] == "market_cap_unavailable"


def test_from_run_non_numeric_market_cap_is_a_clear_error(tmp_path: Path) -> None:
	bad_type = tmp_path / "bad_type.json"
	bad_type.write_text(json.dumps({"ticker": "XX", "key_facts": {"marketCap": "a lot"}}), encoding="utf-8")
	proc = _run("content-volume", "--content", "1", "--volume", "1", "--from-run", str(bad_type))
	assert proc.returncode != 0
	assert _payload(proc)["error"] == "market_cap_unavailable"


def test_from_run_non_object_json_is_a_clear_error(tmp_path: Path) -> None:
	arr = tmp_path / "arr.json"
	arr.write_text("[1, 2, 3]", encoding="utf-8")
	proc = _run("content-volume", "--content", "1", "--volume", "1", "--from-run", str(arr))
	assert proc.returncode != 0
	assert _payload(proc)["error"] == "invalid_run_shape"


def test_sum_of_parts_from_run_reads_parent_mc(run_payload_path: str, real_market_cap: float) -> None:
	proc = _run(
		"sum-of-parts", "--stake-value", "12e9", "--operating-value", "3e9",
		"--from-run", run_payload_path,
	)
	assert proc.returncode == 0
	payload = _payload(proc)
	assert payload["inputs"]["parent_mc"] == pytest.approx(real_market_cap)
	assert "key_facts.marketCap" in payload["lens"]


# --------------------------------------------------------------------------------------
# Driver arithmetic — each expected value is computed independently of the
# implementation (plain Python matching the doctrine formula), not copy-pasted from it.
# --------------------------------------------------------------------------------------


def test_content_volume_arithmetic() -> None:
	proc = _run("content-volume", "--content", "42", "--volume", "180e6", "--mc", "101.3e9")
	payload = _payload(proc)
	assert payload["content_volume_total"] == pytest.approx(42 * 180e6)
	assert payload["result"] == pytest.approx((42 * 180e6) / 101.3e9)


def test_mw_irr_arithmetic() -> None:
	proc = _run(
		"mw-irr", "--rev-per-mw", "9000000", "--cogs-per-mw", "6000000",
		"--mw", "50", "--financing-rate", "0.08",
	)
	payload = _payload(proc)
	margin = 9_000_000 - 6_000_000
	unlevered = margin / 6_000_000
	assert payload["unlevered_yield"] == pytest.approx(unlevered)
	assert payload["result"] == pytest.approx(unlevered - 0.08)
	assert payload["fleet_margin"] == pytest.approx(margin * 50)


def test_replacement_cost_arithmetic() -> None:
	proc = _run(
		"replacement-cost", "--capacity-units", "1000000",
		"--cost-per-unit", "400", "--comp-ev-per-unit", "250",
	)
	payload = _payload(proc)
	replacement_cost = 1_000_000 * 400
	comp_value = 1_000_000 * 250
	assert payload["replacement_cost"] == pytest.approx(replacement_cost)
	assert payload["comp_value"] == pytest.approx(comp_value)
	assert payload["result"] == pytest.approx(comp_value / replacement_cost)


def test_pro_forma_fcf_arithmetic() -> None:
	proc = _run(
		"pro-forma-fcf", "--cogs-addressable", "5e6", "--opex-saved", "2e6",
		"--new-recurring-rev", "3e6", "--multiple", "15",
	)
	payload = _payload(proc)
	bridge = 5e6 + 2e6 + 3e6
	assert payload["pro_forma_fcf"] == pytest.approx(bridge)
	assert payload["result"] == pytest.approx(bridge * 15)


def test_net_cash_after_atm_arithmetic() -> None:
	proc = _run("net-cash-after-atm", "--raised", "500e6", "--shares-cost", "50e6", "--sbc-funded", "20e6")
	payload = _payload(proc)
	net_cash = 500e6 - 50e6 - 20e6
	assert payload["result"] == pytest.approx(net_cash)
	assert payload["clean_fraction_of_raised"] == pytest.approx(net_cash / 500e6)


def test_sum_of_parts_arithmetic() -> None:
	proc = _run("sum-of-parts", "--stake-value", "12e9", "--operating-value", "3e9", "--parent-mc", "9e9")
	payload = _payload(proc)
	parts_sum = 12e9 + 3e9
	assert payload["parts_sum"] == pytest.approx(parts_sum)
	assert payload["result"] == pytest.approx(parts_sum / 9e9)


@pytest.mark.parametrize(
	"command,args",
	[
		("mw-irr", ["--rev-per-mw", "1", "--cogs-per-mw", "0", "--mw", "1", "--financing-rate", "0"]),
		("replacement-cost", ["--capacity-units", "1", "--cost-per-unit", "0", "--comp-ev-per-unit", "1"]),
		("net-cash-after-atm", ["--raised", "0", "--shares-cost", "0", "--sbc-funded", "0"]),
	],
)
def test_division_by_zero_is_a_clean_error_not_a_crash(command: str, args: list[str]) -> None:
	proc = _run(command, *args)
	assert proc.returncode == 1
	assert proc.stderr == ""
	assert _payload(proc)["error"] == "division_by_zero"


# --------------------------------------------------------------------------------------
# --fork — a provenance tag only
# --------------------------------------------------------------------------------------


def test_fork_tag_appears_in_lens_line_and_never_changes_the_arithmetic() -> None:
	floor = _payload(_run("content-volume", "--content", "42", "--volume", "180e6", "--mc", "101.3e9", "--fork", "floor"))
	upside = _payload(_run("content-volume", "--content", "42", "--volume", "180e6", "--mc", "101.3e9", "--fork", "upside"))
	bare = _payload(_run("content-volume", "--content", "42", "--volume", "180e6", "--mc", "101.3e9"))
	assert "[floor]" in floor["lens"]
	assert "[upside]" in upside["lens"]
	assert floor["fork"] == "floor"
	assert upside["fork"] == "upside"
	assert bare["fork"] is None
	assert floor["result"] == pytest.approx(upside["result"]) == pytest.approx(bare["result"])


def test_fork_rejects_invalid_choice() -> None:
	proc = _run("content-volume", "--content", "1", "--volume", "1", "--mc", "1", "--fork", "bearish")
	assert proc.returncode == 2
	assert _payload(proc)["error"] == "invalid_arguments"


# --------------------------------------------------------------------------------------
# Error shape / general CLI contract — mirrors test_serenity_sectormap.py's checks
# --------------------------------------------------------------------------------------


def test_errors_are_single_line_json_with_empty_stderr() -> None:
	proc = _run("content-volume", "--content", "1", "--volume", "1")
	assert proc.returncode != 0
	assert proc.stderr == ""
	assert proc.stdout.count("\n") == 1
	payload = _payload(proc)
	assert "error" in payload and "detail" in payload


def test_argparse_missing_required_argument_is_json_not_a_traceback() -> None:
	proc = _run("content-volume")
	assert proc.returncode == 2
	assert proc.stderr == ""
	assert _payload(proc)["error"] == "invalid_arguments"


def test_argparse_non_numeric_value_is_json_not_a_traceback() -> None:
	proc = _run("content-volume", "--content", "abc", "--volume", "1", "--mc", "1")
	assert proc.returncode == 2
	assert proc.stderr == ""
	assert _payload(proc)["error"] == "invalid_arguments"


def test_unknown_subcommand_is_a_json_error() -> None:
	proc = _run("not-a-real-driver")
	assert proc.returncode == 2
	assert proc.stderr == ""
	assert _payload(proc)["error"] == "invalid_arguments"


def test_unrecognized_flag_is_a_json_error() -> None:
	proc = _run("content-volume", "--ticker", "MU", "--content", "1", "--volume", "1", "--mc", "1")
	assert proc.returncode == 2
	assert _payload(proc)["error"] == "invalid_arguments"


def test_successful_output_is_deterministic() -> None:
	first = _run("content-volume", "--content", "42", "--volume", "180e6", "--mc", "101.3e9")
	second = _run("content-volume", "--content", "42", "--volume", "180e6", "--mc", "101.3e9")
	assert first.returncode == 0
	assert first.stdout == second.stdout
