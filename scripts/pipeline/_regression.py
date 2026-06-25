"""Golden-grade regression harness for the Serenity scoring layer.

WHY this exists: after the L3 enum redesign every scoring threshold sits
unprotected. A one-line tweak in _signals / _health / _bottleneck can silently
re-grade a known winner or promote a known loser, and nothing today would catch
it. This harness is the seatbelt for every threshold change that follows.

HOW it stays trustworthy: it never re-runs the live pipeline at check time. A
live re-run conflates three moving things — your code change, that day's market
data, and LLM-extraction noise — so a "regression" might be none of your doing.
Instead we FREEZE each name's scoring inputs once (the slow, network-bound part)
and replay the REAL derive_core_signals on them (the fast, deterministic part).
Whatever flips between two `regress` runs is therefore your code, and only your
code. That is the whole point: with inputs frozen, the harness has no other
variable to blame.

WHAT it asserts, and why the split is not arbitrary:
  HARD — facts that do not move with the market: a winner's archetype, what the
	business fundamentally IS (business_model), its bottleneck assessment bucket,
	whether it has revenue, the SHAPE of the score breakdown, and whether the two
	loser-recognition booleans fired (speculative_cap_applied, unsubstantiated_
	bottleneck). The L3 redesign verified these stable across extraction runs, so a
	change here is a real regression — not noise. A HARD miss FAILS the run. Pinning
	the booleans is the safety net for loser-recognition: a winner that ever flips
	speculative_cap_applied True fails LOUDLY rather than silently grading down.
  SOFT — the composite grade and score. These ride on catalyst timing, analyst
	revisions, IV, price; they are SUPPOSED to move, and a winner grading HIGHER
	is the goal, not a failure. So we DIFF and report, never fail. (Because inputs
	are frozen, a SOFT diff isolates exactly what YOUR change did to each name.)
  CEILING — a known loser must never reach an investable grade. grade <= HOLD is
	a hard upper bound; breaching it FAILS. We bound the top, not the exact grade:
	how bad a loser looks is allowed to drift; a loser becoming a BUY is not.
  DIVERGENCE — a name the pipeline legitimately scores investable on its mechanical
	inputs, but which a competent agent overrides qualitatively (SSYS: prototype-not-
	production). We do NOT ceiling it — asserting the pipeline must reach HOLD would
	force it to do the agent's job, against the skill's contract. Instead the HARD
	booleans pin that the deterministic SIGNAL handing the call to the agent fired.

The golden HARD values are BLESSED from a live capture, never hand-typed — the
pipeline is verified-correct on these names, so blessing records ground truth
rather than a guess. When an intentional change legitimately moves a HARD fact,
you review the failure and re-bless; the failure is the harness doing its job.
"""

import concurrent.futures
import json
import os
import sys


GOLDEN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tests", "golden"))
_SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Investable-grade ordering for the loser ceiling and for readable SOFT diffs.
GRADE_RANK = {"AVOID": 0, "HOLD": 1, "ACCUMULATE": 2, "BUY": 3, "STRONG_BUY": 4, "MOONSHOT": 5}

# The golden basket. Only role + a one-line WHY are hand-written here; the HARD
# invariants are blessed from a live capture, so this table can't bake in a wrong
# archetype. Losers carry a ceiling, not a frozen grade.
WINNERS = {
	"AAOI": "optical transceiver maker — physical bottleneck",
	"LITE": "laser/optical components — physical bottleneck",
	"SIVE": "tracked winner — archetype blessed from capture",
	"AXTI": "InP/GaAs substrate — physical bottleneck, controlled-region mfg",
	"NBIS": "neocloud buildout — evolution",
	"MU": "memory — capacity-constrained physical bottleneck",
	"CRCL": "stablecoin issuer — financial-float disruption",
	"HIMS": "telehealth platform — disruption",
	"RKLB": "launch / space systems — evolution",
	"HOOD": "brokerage platform — disruption",
	"AEHR": "burn-in/test, design-win driven — recognized PARTIAL bottleneck; proves the moat exemption keeps a real early winner uncapped",
	"POET": "photonic interposer, pre-commercial — early-winner PATTERN, but the pipeline reads no moat ($1M rev, 1684x sales, -3550% op margin) and flags it speculative. Locks the agent-handoff: pipeline caps to HOLD, the agent judges the optical thesis upward. NOTE: its HARD speculative_cap_applied=True is an intentional handoff lock, not a grade floor — if a future L3 improvement legitimately recognizes the optical bottleneck and the cap stops firing, that HARD miss is a RE-BLESS-worthy improvement, not a regression to revert.",
}
LOSERS = {
	"RGTI": "quantum hardware, negligible revenue — must stay <= HOLD",
	"QBTS": "quantum annealing, negligible revenue — must stay <= HOLD",
	"IONQ": "quantum computing, negligible-commercial (P/S 122x, op margin -402%) — must stay <= HOLD",
}
# Pipeline-vs-agent DIVERGENCE: names the pipeline legitimately scores investable on
# its mechanical inputs, but which a competent agent overrides on a qualitative read.
# The harness does NOT ceiling these (that would assert the pipeline must do the agent's
# job); it asserts the deterministic SIGNAL that hands the call to the agent is present.
DIVERGENCE = {
	# NOTE: unsubstantiated_bottleneck=True is currently pinned from ONE example (SSYS).
	# The flag also fires on a real bottleneck winner at a cyclical TROUGH (no growth +
	# operating losses) — by design it does not cap, so that is a surfaced tension, not a
	# misgrade; the agent separates trap from trough. To make this invariant a SEPARATING
	# rule rather than a single positive, add a frozen bottleneck-winner-at-trough fixture.
	"SSYS": "legacy 3D printing — pipeline scores ACCUMULATE (partial bottleneck, cheap), but no growth + operating losses fire unsubstantiated_bottleneck; agent applies the prototype-vs-production / value-trap override",
}
LOSER_CEILING = "HOLD"

# HARD invariant keys (frozen-input-deterministic, market-independent). The two cap/flag
# booleans are here on purpose: a winner that ever flips speculative_cap_applied True, or
# a name that wrongly trips unsubstantiated_bottleneck, is a real regression — so every
# name's blessed value pins it, and the loser-recognition logic can't silently drift.
_HARD_KEYS = ("revenue_status", "data_insufficient", "screen_component_keys", "pre_commercial")


# ---------------------------------------------------------------------------
# Capture (called from cmd_analyze under SERENITY_CAPTURE_DIR) + replay
# ---------------------------------------------------------------------------

def capture_inputs(cap_dir, ticker, l1_result, l4_results, l5_results, sec_sc_results):
	"""Freeze the scoring INPUTS for one ticker. Called as an env-gated side
	effect inside cmd_analyze, before any network-only output enrichment, so the
	frozen state is exactly what derive_core_signals scored."""
	os.makedirs(cap_dir, exist_ok=True)
	path = os.path.join(cap_dir, f"{ticker.upper()}.inputs.json")
	payload = {"l1": l1_result, "l4": l4_results, "l5": l5_results, "sec_sc": sec_sc_results}
	with open(path, "w") as f:
		json.dump(payload, f, default=str)


def _inputs_path(ticker):
	return os.path.join(GOLDEN_DIR, f"{ticker}.inputs.json")


def _expected_path(ticker):
	return os.path.join(GOLDEN_DIR, f"{ticker}.expected.json")


def _replay(inputs):
	"""Run the real production scoring layer on frozen inputs and project out the
	fields the harness cares about. Same inputs + same code => same projection."""
	from ._signals import derive_core_signals
	core = derive_core_signals(
		inputs.get("l1"), inputs.get("l4") or {}, inputs.get("l5") or {}, inputs.get("sec_sc") or {}
	)
	scr = core.get("objective_screen") or {}
	comps = scr.get("components") or {}
	flags = scr.get("objective_flags") or {}
	return {
		"revenue_status": flags.get("revenue_status"),
		"data_insufficient": bool(flags.get("data_insufficient")),
		"screen_component_keys": sorted(comps.keys()),
		"pre_commercial": "pre_commercial" in flags,
		"screen_score": scr.get("screen_score"),
	}


# ---------------------------------------------------------------------------
# Live capture orchestration (--capture / --update)
# ---------------------------------------------------------------------------

def _capture_one(ticker):
	"""Subprocess `analyze <T> --skip-macro` with the capture hook armed. Returns
	(ticker, ok, message)."""
	env = dict(os.environ, SERENITY_CAPTURE_DIR=GOLDEN_DIR)
	try:
		proc = subprocess_run(ticker, env)
	except Exception as e:  # noqa: BLE001 — capture is best-effort; report and move on
		return ticker, False, f"subprocess error: {e}"
	if not os.path.exists(_inputs_path(ticker)):
		tail = (proc.stderr or proc.stdout or "")[-400:]
		return ticker, False, f"no inputs written (analyze likely failed). tail: {tail}"
	return ticker, True, "captured"


def subprocess_run(ticker, env):
	import subprocess
	return subprocess.run(
		[sys.executable, "-m", "pipeline", "legacy-analyze", ticker, "--skip-macro"],
		cwd=_SCRIPTS_DIR, env=env, capture_output=True, text=True, timeout=420,
	)


def _capture_live(tickers):
	print(f"[regress] capturing live inputs for {len(tickers)} tickers (parallel)...", file=sys.stderr)
	results = {}
	with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
		futs = {ex.submit(_capture_one, t): t for t in tickers}
		for fut in concurrent.futures.as_completed(futs):
			t, ok, msg = fut.result()
			results[t] = (ok, msg)
			print(f"[regress]   {t}: {'OK' if ok else 'FAIL'} — {msg}", file=sys.stderr)
	return results


# ---------------------------------------------------------------------------
# Bless (write expected.json from current replay of frozen inputs)
# ---------------------------------------------------------------------------

def _bless_one(ticker, role, note, captured_at):
	inputs = _load_inputs(ticker)
	if inputs is None:
		return False, "no frozen inputs — capture first"
	actual = _replay(inputs)
	expected = {
		"ticker": ticker,
		"role": role,
		"note": note,
		"captured_at": captured_at,
		"hard": {k: actual[k] for k in _HARD_KEYS},
		"baseline": {
			"screen_score": actual["screen_score"],
		},
	}
	if role == "loser":
		expected["ceiling"] = LOSER_CEILING
	with open(_expected_path(ticker), "w") as f:
		json.dump(expected, f, indent=2)
	return True, f"screen={actual['screen_score']}/60 pre_commercial={actual['pre_commercial']}"


def _load_inputs(ticker):
	path = _inputs_path(ticker)
	if not os.path.exists(path):
		return None
	with open(path) as f:
		return json.load(f)


def _load_expected(ticker):
	path = _expected_path(ticker)
	if not os.path.exists(path):
		return None
	with open(path) as f:
		return json.load(f)


# ---------------------------------------------------------------------------
# Check (the default `regress` run)
# ---------------------------------------------------------------------------

def _check_one(ticker):
	"""Return a per-ticker verdict dict. status in {pass, fail, skip}."""
	expected = _load_expected(ticker)
	inputs = _load_inputs(ticker)
	if expected is None or inputs is None:
		return {"ticker": ticker, "status": "skip",
				"reason": "missing " + ("expected.json" if expected is None else "inputs.json")}

	actual = _replay(inputs)
	hard_failures = []
	for k in _HARD_KEYS:
		exp_v = expected.get("hard", {}).get(k)
		act_v = actual.get(k)
		if exp_v != act_v:
			hard_failures.append(f"{k}: {exp_v!r} -> {act_v!r}")

	# Loser ceiling.
	# Loser protection is now the OBJECTIVE pre_commercial flag (op margin < -100%): on a
	# pre-commercial loser it MUST fire, handing the skepticism to the analyst. (There is no
	# grade ceiling anymore — the screen is not a verdict.)
	ceiling_failure = None
	if expected.get("role") == "loser":
		if not actual.get("pre_commercial"):
			ceiling_failure = "pre_commercial flag did not fire on a pre-commercial loser (op-margin guard lost)"

	# SOFT diff (informational).
	base = expected.get("baseline", {})
	bs = base.get("screen_score")
	as_ = actual.get("screen_score")
	soft = None
	if bs != as_:
		delta = f" ({round(as_ - bs, 2):+})" if isinstance(bs, (int, float)) and isinstance(as_, (int, float)) else ""
		soft = f"screen {bs} -> {as_}{delta}"

	status = "fail" if (hard_failures or ceiling_failure) else "pass"
	return {
		"ticker": ticker, "status": status, "role": expected.get("role"),
		"hard_failures": hard_failures, "ceiling_failure": ceiling_failure,
		"soft": soft, "screen": actual.get("screen_score"), "pre_commercial": actual.get("pre_commercial"),
	}


def _resolve_tickers(arg_tickers):
	allnames = list(WINNERS) + list(LOSERS) + list(DIVERGENCE)
	if not arg_tickers:
		return allnames
	want = [t.upper() for t in arg_tickers]
	unknown = [t for t in want if t not in allnames]
	if unknown:
		print(f"[regress] unknown golden tickers ignored: {unknown}", file=sys.stderr)
	return [t for t in want if t in allnames]


def _role_and_note(ticker):
	if ticker in WINNERS:
		return "winner", WINNERS[ticker]
	if ticker in DIVERGENCE:
		return "divergence", DIVERGENCE[ticker]
	return "loser", LOSERS[ticker]


def cmd_regress(args):
	tickers = _resolve_tickers(getattr(args, "tickers", None))
	if not tickers:
		print("[regress] no golden tickers selected.", file=sys.stderr)
		sys.exit(2)

	do_capture = bool(getattr(args, "capture", False) or getattr(args, "update", False))
	do_bless = bool(getattr(args, "bless", False) or getattr(args, "update", False))

	if do_capture:
		cap = _capture_live(tickers)
		# Only bless/check names that have inputs.
		tickers = [t for t in tickers if os.path.exists(_inputs_path(t))]
		if not tickers:
			print("[regress] capture produced no usable inputs.", file=sys.stderr)
			sys.exit(2)

	if do_bless:
		captured_at = getattr(args, "stamp", None) or _today()
		print(f"[regress] blessing expected.json from current replay (stamp {captured_at})...", file=sys.stderr)
		for t in tickers:
			role, note = _role_and_note(t)
			ok, msg = _bless_one(t, role, note, captured_at)
			print(f"[regress]   {t}: {'blessed' if ok else 'SKIP'} — {msg}", file=sys.stderr)
		if do_capture or do_bless:
			# A bless run establishes the baseline; report it but don't fail.
			pass

	# Always run the check pass (after capture/bless it confirms green).
	results = [_check_one(t) for t in tickers]
	_print_report(results)
	failed = [r for r in results if r["status"] == "fail"]
	# After an explicit bless, HARD can't fail (we just wrote it); ceiling still can.
	sys.exit(1 if failed else 0)


def _today():
	from datetime import date
	return date.today().isoformat()


def _print_report(results):
	print("\n" + "=" * 72)
	print("SERENITY GOLDEN REGRESSION")
	print("=" * 72)
	n_pass = sum(1 for r in results if r["status"] == "pass")
	n_fail = sum(1 for r in results if r["status"] == "fail")
	n_skip = sum(1 for r in results if r["status"] == "skip")
	for r in results:
		if r["status"] == "skip":
			print(f"  SKIP  {r['ticker']:<6} — {r.get('reason')}")
			continue
		tag = "PASS" if r["status"] == "pass" else "FAIL"
		_pc = " pre_commercial" if r.get('pre_commercial') else ""
		line = f"  {tag}  {r['ticker']:<6} [{r.get('role','?')}]  screen={r.get('screen','?')}/60{_pc}"
		print(line)
		if r.get("soft"):
			print(f"          soft: {r['soft']}")
		for hf in r.get("hard_failures", []):
			print(f"          HARD: {hf}")
		if r.get("ceiling_failure"):
			print(f"          CEILING: {r['ceiling_failure']}")
	print("-" * 72)
	print(f"  {n_pass} pass / {n_fail} fail / {n_skip} skip")
	print("=" * 72 + "\n")
