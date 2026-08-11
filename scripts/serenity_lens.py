#!/usr/bin/env python3
"""Deterministic driver-arithmetic CLI for Serenity's valuation `Lens:` line.

The harness's central invariant is code loads facts, the model judges — no score,
archetype tag, or verdict may live in code. A valuation verdict still has to show its
driver arithmetic on one visible line (CLAUDE.md "How the answer reads" / non-negotiable
#10): ``Lens: <name> — <input>×<input>÷<input> = <result>``, checked by the Stop hook in
.claude/hooks/verdict_gate.py. Composing that line by hand risks exactly the failure the
doctrine warns about hardest — dividing by a remembered/mistyped market cap instead of
the one the pipeline actually loaded — so this CLI does the arithmetic itself and, for
every market-cap-shaped denominator, can read it out of a saved pipeline run instead of
taking the model's word for it.

This tool NEVER judges: it takes named numbers and combines them with named operators.
It has no notion of a ticker, an archetype, or a sector, and its output never renders a
valuation verdict (cheap/expensive/priced/buy/sell/... never appear). It never decides
which driver applies to a given name — that selection is the model's, same as every
number that ends up after a flag.

	serenity_lens.py content-volume     --content --volume [--mc | --from-run]
	serenity_lens.py mw-irr             --rev-per-mw --cogs-per-mw --mw --financing-rate
	serenity_lens.py replacement-cost   --capacity-units --cost-per-unit --comp-ev-per-unit
	serenity_lens.py pro-forma-fcf      --cogs-addressable --opex-saved --new-recurring-rev --multiple
	serenity_lens.py net-cash-after-atm --raised --shares-cost --sbc-funded
	serenity_lens.py sum-of-parts       --stake-value --operating-value [--parent-mc | --from-run]
	serenity_lens.py custom             --expr 'a×b÷c' --inputs a=42,b=180e6,c=101.3e9

Every subcommand accepts ``--fork floor|upside`` — a provenance TAG only (it never
changes the arithmetic): run the floor and upside legs as two separate invocations so
"both legs ran" is a fact the output carries, not a hope (non-negotiable #10's single
biggest direction-miss is a bear-leg-only call that silently inverts a long into a pass).

``--from-run PATH`` reads a market cap out of a saved `serenity_pipeline.py
analyze`/`evidence` JSON payload's ``key_facts.marketCap``, and the output labels that
provenance. A hand-typed ``--mc``/``--parent-mc`` still works but is labeled UNVERIFIED —
visible, never forbidden; PEG and the no-growth floor are NOT here because the pipeline
already loads them (`valuation_inputs.forward_pe`, `valuation_inputs.no_growth`).

All output is one JSON object on stdout. Errors are a one-line JSON envelope with a
nonzero exit code — never a raw traceback.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import operator
import re
import sys
from typing import Any, Dict, Optional, Sequence, Tuple

JsonObject = Dict[str, Any]


class LensError(Exception):
	"""A user-facing failure that must be serialized as a JSON error envelope."""

	def __init__(self, payload: JsonObject, exit_code: int = 1) -> None:
		super().__init__(str(payload.get("detail", payload.get("error", "lens error"))))
		self.payload = payload
		self.exit_code = exit_code


class JsonArgumentParser(argparse.ArgumentParser):
	"""Keep argparse failures inside the CLI's JSON-only error contract."""

	def error(self, message: str) -> None:
		raise LensError(
			{"error": "invalid_arguments", "detail": message},
			exit_code=2,
		)


def _emit(value: JsonObject, *, compact: bool = False) -> None:
	if compact:
		json.dump(
			value,
			sys.stdout,
			ensure_ascii=False,
			sort_keys=True,
			separators=(",", ":"),
		)
	else:
		json.dump(value, sys.stdout, ensure_ascii=False, sort_keys=True, indent=2)
	print()


def _raise_error(error: str, detail: str, **context: Any) -> None:
	raise LensError({"error": error, "detail": detail, **context})


# --------------------------------------------------------------------------------------
# Numeric parsing / formatting
# --------------------------------------------------------------------------------------


def _number_type(option: str):
	"""argparse ``type=`` factory for a required numeric flag.

	Raising ArgumentTypeError (not a plain ValueError) routes the failure through
	argparse's own error path into JsonArgumentParser.error(), so a bad number and a
	missing required flag land in the identical ``invalid_arguments`` JSON envelope —
	one error shape for every argument-level mistake, regardless of which flag it's on.
	"""

	def _parse(raw: str) -> float:
		try:
			value = float(raw)
		except ValueError:
			raise argparse.ArgumentTypeError(f"{option} expects a number, got {raw!r}") from None
		if not math.isfinite(value):
			raise argparse.ArgumentTypeError(f"{option} expects a finite number, got {raw!r}")
		return value

	return _parse


def _fmt_money(value: float) -> str:
	"""Render a dollar figure with a B/M/K suffix. The 1e9/1e6/1e3 thresholds only pick
	how many zeros to hide — they never change the number itself, so this can't distort
	what a figure means (unlike a modeling assumption, which would).
	"""
	sign = "-" if value < 0 else ""
	magnitude = abs(value)
	if magnitude >= 1e9:
		return f"{sign}${magnitude / 1e9:,.2f}B"
	if magnitude >= 1e6:
		return f"{sign}${magnitude / 1e6:,.2f}M"
	if magnitude >= 1e3:
		return f"{sign}${magnitude / 1e3:,.2f}K"
	return f"{sign}${magnitude:,.2f}"


def _fmt_num(value: float) -> str:
	"""Neutral numeric display (no currency symbol) for unit counts, ratios, and rates —
	and for every `custom` input/result, since this tool has no way to know whether a
	user-named variable is a dollar figure and prepending "$" would be a guess it has no
	business making. Whole numbers under 1e15 print with digit grouping (a share count
	should read as digits, not scientific notation); past that, ``%g`` is more legible
	than a 16-digit string.
	"""
	if math.isfinite(value) and float(value).is_integer() and abs(value) < 1e15:
		return f"{value:,.0f}"
	return f"{value:.6g}"


# --------------------------------------------------------------------------------------
# Stop hook marker — mirrors (independently of) .claude/hooks/verdict_gate.py's
# `lens_marker` regex: "Lens:", then an operator character, then "=" on the same line (or
# the reverse order). Copied rather than imported so this CLI has no runtime dependency
# on the hooks directory — a sibling change may be mid-editing that file right now — and
# so the CLI still works if the hook is ever removed. If the hook's regex changes, this
# copy goes stale and should be re-synced by hand; the seam test in
# test_serenity_lens.py pins this copy against sample output so drift is at least
# visible in this file's own tests.
# --------------------------------------------------------------------------------------

_HOOK_MARKER_RE_1 = re.compile(r"Lens:[^\n]*[×÷*][^\n]*=")
_HOOK_MARKER_RE_2 = re.compile(r"Lens:[^\n]*=[^\n]*[×÷*]")


def _hook_marker_present(line: str) -> bool:
	return bool(_HOOK_MARKER_RE_1.search(line)) or bool(_HOOK_MARKER_RE_2.search(line))


def _fork_tag(args: argparse.Namespace) -> str:
	return f" [{args.fork}]" if args.fork else ""


# --------------------------------------------------------------------------------------
# --from-run — read a market-cap-shaped denominator out of a saved pipeline payload
# instead of the model retyping it. This is the mechanism behind claim (1) in the task
# brief: the doctrine's most-repeated numeric warning is dividing by a remembered or
# mistyped market cap, so a hand-typed value is never silently indistinguishable from a
# verified one — the provenance travels with the number onto the output line itself.
# --------------------------------------------------------------------------------------


def _load_run_payload(path: str) -> JsonObject:
	try:
		with open(path, "r", encoding="utf-8") as handle:
			payload = json.load(handle)
	except FileNotFoundError:
		_raise_error("run_not_found", f"--from-run file not found: {path}", path=path)
	except json.JSONDecodeError as exc:
		_raise_error(
			"malformed_run",
			f"{path}: {exc.msg} at line {exc.lineno}, column {exc.colno}",
			path=path,
		)
	except UnicodeDecodeError as exc:
		_raise_error("invalid_run_encoding", f"{path}: expected UTF-8 JSON ({exc})", path=path)
	except OSError as exc:
		_raise_error("run_unavailable", f"{path}: {exc}", path=path)
	if not isinstance(payload, dict):
		_raise_error(
			"invalid_run_shape",
			f"{path}: expected a JSON object (a `serenity_pipeline.py analyze`/`evidence` "
			f"payload), got {type(payload).__name__}",
			path=path,
		)
	return payload


def _extract_market_cap(payload: JsonObject, path: str) -> Tuple[float, str]:
	key_facts = payload.get("key_facts")
	if not isinstance(key_facts, dict):
		_raise_error(
			"market_cap_unavailable",
			f"{path}: no key_facts object found — expected a `serenity_pipeline.py "
			"analyze`/`evidence` payload",
			path=path,
		)
		raise AssertionError("unreachable")
	mc = key_facts.get("marketCap")
	is_number = isinstance(mc, (int, float)) and not isinstance(mc, bool)
	if not is_number or not math.isfinite(mc):
		_raise_error(
			"market_cap_unavailable",
			f"{path}: key_facts.marketCap is missing or not a number — the fetch may have "
			"been silent; never substitute a remembered figure",
			path=path,
		)
		raise AssertionError("unreachable")
	ticker = payload.get("ticker")
	ticker_note = f", ticker {ticker}" if isinstance(ticker, str) and ticker else ""
	return float(mc), f"[from {path} key_facts.marketCap{ticker_note}]"


def _resolve_denominator(
	*,
	from_run: Optional[str],
	hand_value: Optional[float],
	flag_name: str,
) -> Tuple[float, str]:
	"""Resolve a market-cap-shaped denominator and always label where it came from.

	Neither source is required by argparse itself — ``--from-run`` must be allowed to
	coexist with the hand-typed flag and win, which argparse's own mutually-exclusive
	groups cannot express (they reject having both present). So "at least one of the
	two" is enforced here instead, after parsing.
	"""
	if from_run is not None:
		payload = _load_run_payload(from_run)
		value, provenance = _extract_market_cap(payload, from_run)
		if hand_value is not None:
			provenance += f" ({flag_name} {_fmt_money(hand_value)} also given — --from-run wins)"
		return value, provenance
	if hand_value is not None:
		return hand_value, "[UNVERIFIED — typed by hand, not sourced from a run]"
	_raise_error(
		"missing_denominator",
		f"supply either --from-run or {flag_name} — a lens ratio needs a real "
		"denominator, never a default",
		option=flag_name,
	)
	raise AssertionError("unreachable")


def _safe_div(numerator: float, denominator: float, *, what: str) -> float:
	"""Guard every division in this file. A zero denominator here is a plausible bad
	input (a hand-typed 0, a payload field that came back null and was coerced upstream)
	rather than an impossible case, so it gets a specific, named error instead of a
	generic traceback-shaped one.
	"""
	if denominator == 0:
		_raise_error("division_by_zero", f"{what} is zero — cannot divide by it")
		raise AssertionError("unreachable")
	return numerator / denominator


# --------------------------------------------------------------------------------------
# `custom` — the escape hatch. Evaluated via a strict ast.AST walk, never eval(): a
# crafted --expr must never be able to do anything but arithmetic on the named inputs.
# --------------------------------------------------------------------------------------

_IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

_BIN_OPS = {
	ast.Add: operator.add,
	ast.Sub: operator.sub,
	ast.Mult: operator.mul,
	ast.Div: operator.truediv,
}
_UNARY_OPS = {
	ast.UAdd: operator.pos,
	ast.USub: operator.neg,
}


def _normalize_expr(expr: str) -> str:
	"""ASCII-fold the doctrine's ×/÷ glyphs so ``ast.parse`` (which only knows
	``*``/``/``) can read the expression — the unicode glyphs are purely a display
	convention, not a different grammar.
	"""
	return expr.replace("×", "*").replace("÷", "/")


def _display_expr(expr: str) -> str:
	"""The inverse of ``_normalize_expr`` — canonicalize to ×/÷ for display so
	the echoed expression always carries an operator character the Stop hook's marker
	regex looks for, regardless of whether the model typed ASCII or the doctrine glyphs.
	"""
	return expr.replace("*", "×").replace("/", "÷")


def _parse_inputs(raw: str) -> Dict[str, float]:
	inputs: Dict[str, float] = {}
	for item in raw.split(","):
		item = item.strip()
		if not item:
			continue
		if "=" not in item:
			_raise_error("invalid_inputs", f"--inputs: expected name=value, got {item!r}", option="--inputs")
		name, _, value_text = item.partition("=")
		name = name.strip()
		if not _IDENTIFIER_RE.fullmatch(name):
			_raise_error("invalid_inputs", f"--inputs: {name!r} is not a valid input name", option="--inputs")
		value_text = value_text.strip()
		try:
			value = float(value_text)
		except ValueError:
			_raise_error("invalid_inputs", f"--inputs: {name}={value_text!r} is not a number", option="--inputs")
			raise AssertionError("unreachable")
		if not math.isfinite(value):
			_raise_error("invalid_inputs", f"--inputs: {name}={value_text!r} must be finite", option="--inputs")
		inputs[name] = value
	if not inputs:
		_raise_error("invalid_inputs", "--inputs must supply at least one name=value pair", option="--inputs")
	return inputs


def _safe_eval_node(node: ast.AST, inputs: Dict[str, float]) -> float:
	"""Walk a --expr AST under a strict allowlist — Expression/Constant/Name/BinOp
	(+-*/only)/UnaryOp(+-) and nothing else. This is the non-negotiable line: `eval()` on
	a user string would let a crafted --expr execute arbitrary Python; walking the parsed
	tree ourselves means a disallowed node (a call, an attribute, a comprehension) simply
	has no case here and is rejected outright, not sandboxed.
	"""
	if isinstance(node, ast.Expression):
		return _safe_eval_node(node.body, inputs)
	if isinstance(node, ast.Constant):
		if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
			_raise_error("invalid_expr", f"--expr: only numeric literals are allowed, got {node.value!r}", option="--expr")
			raise AssertionError("unreachable")
		return float(node.value)
	if isinstance(node, ast.Name):
		if node.id not in inputs:
			_raise_error("invalid_expr", f"--expr references {node.id!r}, which --inputs does not define", option="--expr")
			raise AssertionError("unreachable")
		return inputs[node.id]
	if isinstance(node, ast.BinOp):
		op_fn = _BIN_OPS.get(type(node.op))
		if op_fn is None:
			_raise_error(
				"invalid_expr",
				f"--expr: operator {type(node.op).__name__} is not allowed — only × ÷ * / + - are",
				option="--expr",
			)
			raise AssertionError("unreachable")
		left = _safe_eval_node(node.left, inputs)
		right = _safe_eval_node(node.right, inputs)
		if op_fn is operator.truediv:
			return _safe_div(left, right, what="--expr divisor")
		return op_fn(left, right)
	if isinstance(node, ast.UnaryOp):
		op_fn = _UNARY_OPS.get(type(node.op))
		if op_fn is None:
			_raise_error("invalid_expr", f"--expr: unary operator {type(node.op).__name__} is not allowed", option="--expr")
			raise AssertionError("unreachable")
		return op_fn(_safe_eval_node(node.operand, inputs))
	_raise_error(
		"invalid_expr",
		f"--expr: disallowed syntax ({type(node).__name__}) — only numbers, named "
		"inputs, × ÷ * / + -, and parentheses are allowed",
		option="--expr",
	)
	raise AssertionError("unreachable")


def _safe_eval(expr: str, inputs: Dict[str, float]) -> float:
	try:
		tree = ast.parse(_normalize_expr(expr), mode="eval")
	except SyntaxError as exc:
		_raise_error("invalid_expr", f"--expr is not a valid expression: {exc.msg}", option="--expr")
		raise AssertionError("unreachable")
	return _safe_eval_node(tree, inputs)


# --------------------------------------------------------------------------------------
# Result envelope shared by every subcommand
# --------------------------------------------------------------------------------------


def _finish(
	driver: str,
	args: argparse.Namespace,
	inputs: JsonObject,
	lens_line: str,
	result: float,
	**extra: Any,
) -> JsonObject:
	body: JsonObject = {
		"driver": driver,
		"fork": args.fork,
		"inputs": inputs,
		"result": result,
		"lens": lens_line,
		"hook_marker_present": _hook_marker_present(lens_line),
	}
	body.update(extra)
	return body


# --------------------------------------------------------------------------------------
# Subcommands — one per doctrine-named valuation driver, plus `custom`.
# --------------------------------------------------------------------------------------


def cmd_content_volume(args: argparse.Namespace) -> JsonObject:
	mc, mc_note = _resolve_denominator(from_run=args.from_run, hand_value=args.mc, flag_name="--mc")
	total = args.content * args.volume
	result = _safe_div(total, mc, what="mc")
	lens = (
		f"Lens: content-volume{_fork_tag(args)} — "
		f"content ({_fmt_money(args.content)}) × volume ({_fmt_num(args.volume)}) "
		f"÷ mc ({_fmt_money(mc)} {mc_note}) = {_fmt_num(result)}"
	)
	inputs = {"content": args.content, "volume": args.volume, "mc": mc}
	return _finish("content-volume", args, inputs, lens, result, content_volume_total=total)


def cmd_mw_irr(args: argparse.Namespace) -> JsonObject:
	margin_per_mw = args.rev_per_mw - args.cogs_per_mw
	unlevered_yield = _safe_div(margin_per_mw, args.cogs_per_mw, what="cogs_per_mw")
	levered_yield = unlevered_yield - args.financing_rate
	fleet_margin = margin_per_mw * args.mw
	lens = (
		f"Lens: mw-irr{_fork_tag(args)} — "
		f"(rev_per_mw ({_fmt_money(args.rev_per_mw)}) − cogs_per_mw ({_fmt_money(args.cogs_per_mw)})) "
		f"÷ cogs_per_mw = unlevered_yield ({_fmt_num(unlevered_yield)}); "
		f"unlevered_yield − financing_rate ({_fmt_num(args.financing_rate)}) = levered_yield ({_fmt_num(levered_yield)}); "
		f"margin_per_mw × mw ({_fmt_num(args.mw)}) = fleet_margin ({_fmt_money(fleet_margin)})"
	)
	inputs = {
		"rev_per_mw": args.rev_per_mw,
		"cogs_per_mw": args.cogs_per_mw,
		"mw": args.mw,
		"financing_rate": args.financing_rate,
	}
	return _finish(
		"mw-irr", args, inputs, lens, levered_yield,
		unlevered_yield=unlevered_yield, fleet_margin=fleet_margin,
	)


def cmd_replacement_cost(args: argparse.Namespace) -> JsonObject:
	replacement_cost = args.capacity_units * args.cost_per_unit
	comp_value = args.capacity_units * args.comp_ev_per_unit
	ratio = _safe_div(comp_value, replacement_cost, what="replacement_cost (capacity_units × cost_per_unit)")
	lens = (
		f"Lens: replacement-cost{_fork_tag(args)} — "
		f"capacity_units ({_fmt_num(args.capacity_units)}) × cost_per_unit ({_fmt_money(args.cost_per_unit)}) "
		f"= replacement_cost ({_fmt_money(replacement_cost)}); "
		f"capacity_units × comp_ev_per_unit ({_fmt_money(args.comp_ev_per_unit)}) = comp_value ({_fmt_money(comp_value)}); "
		f"comp_value ÷ replacement_cost = {_fmt_num(ratio)}"
	)
	inputs = {
		"capacity_units": args.capacity_units,
		"cost_per_unit": args.cost_per_unit,
		"comp_ev_per_unit": args.comp_ev_per_unit,
	}
	return _finish(
		"replacement-cost", args, inputs, lens, ratio,
		replacement_cost=replacement_cost, comp_value=comp_value,
	)


def cmd_pro_forma_fcf(args: argparse.Namespace) -> JsonObject:
	pro_forma_fcf = args.cogs_addressable + args.opex_saved + args.new_recurring_rev
	implied_value = pro_forma_fcf * args.multiple
	lens = (
		f"Lens: pro-forma-fcf{_fork_tag(args)} — "
		f"cogs_addressable ({_fmt_money(args.cogs_addressable)}) + opex_saved ({_fmt_money(args.opex_saved)}) "
		f"+ new_recurring_rev ({_fmt_money(args.new_recurring_rev)}) = pro_forma_fcf ({_fmt_money(pro_forma_fcf)}); "
		f"pro_forma_fcf × multiple ({_fmt_num(args.multiple)}) = implied_value ({_fmt_money(implied_value)})"
	)
	inputs = {
		"cogs_addressable": args.cogs_addressable,
		"opex_saved": args.opex_saved,
		"new_recurring_rev": args.new_recurring_rev,
		"multiple": args.multiple,
	}
	return _finish("pro-forma-fcf", args, inputs, lens, implied_value, pro_forma_fcf=pro_forma_fcf)


def cmd_net_cash_after_atm(args: argparse.Namespace) -> JsonObject:
	net_cash = args.raised - args.shares_cost - args.sbc_funded
	clean_fraction = _safe_div(net_cash, args.raised, what="raised")
	lens = (
		f"Lens: net-cash-after-atm{_fork_tag(args)} — "
		f"raised ({_fmt_money(args.raised)}) − shares_cost ({_fmt_money(args.shares_cost)}) "
		f"− sbc_funded ({_fmt_money(args.sbc_funded)}) = net_cash ({_fmt_money(net_cash)}); "
		f"net_cash ÷ raised = {_fmt_num(clean_fraction)}"
	)
	inputs = {"raised": args.raised, "shares_cost": args.shares_cost, "sbc_funded": args.sbc_funded}
	return _finish("net-cash-after-atm", args, inputs, lens, net_cash, clean_fraction_of_raised=clean_fraction)


def cmd_sum_of_parts(args: argparse.Namespace) -> JsonObject:
	parts_sum = args.stake_value + args.operating_value
	parent_mc, mc_note = _resolve_denominator(from_run=args.from_run, hand_value=args.parent_mc, flag_name="--parent-mc")
	ratio = _safe_div(parts_sum, parent_mc, what="parent_mc")
	lens = (
		f"Lens: sum-of-parts{_fork_tag(args)} — "
		f"stake_value ({_fmt_money(args.stake_value)}) + operating_value ({_fmt_money(args.operating_value)}) "
		f"= parts_sum ({_fmt_money(parts_sum)}); "
		f"parts_sum ÷ parent_mc ({_fmt_money(parent_mc)} {mc_note}) = {_fmt_num(ratio)}"
	)
	inputs = {"stake_value": args.stake_value, "operating_value": args.operating_value, "parent_mc": parent_mc}
	return _finish("sum-of-parts", args, inputs, lens, ratio, parts_sum=parts_sum)


def cmd_custom(args: argparse.Namespace) -> JsonObject:
	inputs = _parse_inputs(args.inputs)
	result = _safe_eval(args.expr, inputs)
	shown_inputs = ", ".join(f"{name}={_fmt_num(value)}" for name, value in inputs.items())
	lens = f"Lens: custom({_display_expr(args.expr)}){_fork_tag(args)} — {shown_inputs} = {_fmt_num(result)}"
	return _finish("custom", args, inputs, lens, result, expr=args.expr)


# --------------------------------------------------------------------------------------
# Parser
# --------------------------------------------------------------------------------------


def _add_fork_arg(sp: argparse.ArgumentParser) -> None:
	sp.add_argument(
		"--fork",
		choices=("floor", "upside"),
		default=None,
		help=(
			"Tag this run as the floor or upside leg of a forked lens. A label only — it "
			"never changes the arithmetic. Run the other leg as a separate invocation so "
			"both legs are visible facts, not just the one you remembered to compute."
		),
	)


def _add_denominator_args(sp: argparse.ArgumentParser, *, hand_flag: str, hand_help: str) -> None:
	"""Wire up a market-cap-shaped denominator: a hand-typed flag plus --from-run, with
	NEITHER required by argparse — "at least one" is enforced in _resolve_denominator
	instead, since --from-run must be allowed to coexist with the hand-typed flag and
	win, which argparse's mutually-exclusive groups cannot express. A bare sum or
	product with no denominator isn't a valuation lens per R5 ("meaningless until
	divided by the denominator the structure demands") — it's a subtotal — so this CLI
	never lets that ratio go uncomputed.
	"""
	sp.add_argument(
		hand_flag,
		type=_number_type(hand_flag),
		default=None,
		help=f"{hand_help} Hand-typed — the output marks it UNVERIFIED. Prefer --from-run.",
	)
	sp.add_argument(
		"--from-run",
		default=None,
		help=(
			"Path to a saved `serenity_pipeline.py analyze`/`evidence` JSON payload — "
			f"the denominator is read from its key_facts.marketCap instead of {hand_flag}, "
			"so it is a traced fact rather than a retyped one. Wins if both are given."
		),
	)


def build_parser() -> argparse.ArgumentParser:
	parser = JsonArgumentParser(
		prog="serenity_lens.py",
		description=(
			"Compute one doctrine-named valuation driver's arithmetic and emit the Stop "
			"hook's required `Lens:` line. Never judges: no subcommand accepts a ticker "
			"or an archetype, and no output renders a valuation verdict word."
		),
	)
	sub = parser.add_subparsers(dest="command", required=True)

	sp = sub.add_parser(
		"content-volume",
		help="content × volume ÷ market cap — dollar content per unit times unit volume, sized against market cap",
	)
	sp.add_argument(
		"--content", required=True, type=_number_type("--content"),
		help="Dollar content per unit (e.g. $ BOM/ASP captured per device) — a fact you supply, not derived here",
	)
	sp.add_argument(
		"--volume", required=True, type=_number_type("--volume"),
		help="Unit volume for the same period as --content (e.g. shipment/build units)",
	)
	_add_denominator_args(sp, hand_flag="--mc", hand_help="Market cap.")
	_add_fork_arg(sp)
	sp.set_defaults(func=cmd_content_volume)

	sp = sub.add_parser(
		"mw-irr",
		help="Per-MW levered-return proxy — a simplified single-period yield, not a solved multi-period IRR",
	)
	sp.add_argument(
		"--rev-per-mw", required=True, type=_number_type("--rev-per-mw"),
		help="Revenue per MW of capacity, any consistent period basis (e.g. $/MW/yr)",
	)
	sp.add_argument(
		"--cogs-per-mw", required=True, type=_number_type("--cogs-per-mw"),
		help="Cost per MW of capacity — SAME period basis as --rev-per-mw (this tool does not convert units)",
	)
	sp.add_argument(
		"--mw", required=True, type=_number_type("--mw"),
		help="Deployed capacity in MW — scales the per-MW margin to a fleet total",
	)
	sp.add_argument(
		"--financing-rate", required=True, type=_number_type("--financing-rate"),
		help="Cost of levered capital as a decimal (0.08 = 8%%), subtracted from the unlevered yield as a spread",
	)
	_add_fork_arg(sp)
	sp.set_defaults(func=cmd_mw_irr)

	sp = sub.add_parser(
		"replacement-cost",
		help="Replacement cost per unit of capacity vs. what a pure-play comp's EV implies for the same capacity",
	)
	sp.add_argument(
		"--capacity-units", required=True, type=_number_type("--capacity-units"),
		help="Physical capacity in the comp's own unit (e.g. wafer starts, MW, seats)",
	)
	sp.add_argument(
		"--cost-per-unit", required=True, type=_number_type("--cost-per-unit"),
		help="Dollar cost to build one unit of that capacity from scratch, today",
	)
	sp.add_argument(
		"--comp-ev-per-unit", required=True, type=_number_type("--comp-ev-per-unit"),
		help="A pure-play comp's enterprise value divided by ITS capacity, in the same unit",
	)
	_add_fork_arg(sp)
	sp.set_defaults(func=cmd_replacement_cost)

	sp = sub.add_parser(
		"pro-forma-fcf",
		help="Bridge cost/revenue deltas to a pro-forma FCF figure, then capitalize it with an FCF multiple",
	)
	sp.add_argument(
		"--cogs-addressable", required=True, type=_number_type("--cogs-addressable"),
		help="Addressable COGS savings folded into the bridge, in dollars",
	)
	sp.add_argument(
		"--opex-saved", required=True, type=_number_type("--opex-saved"),
		help="Opex savings folded into the bridge, in dollars",
	)
	sp.add_argument(
		"--new-recurring-rev", required=True, type=_number_type("--new-recurring-rev"),
		help="New recurring revenue folded into the bridge, in dollars",
	)
	sp.add_argument(
		"--multiple", required=True, type=_number_type("--multiple"),
		help="FCF multiple applied to the bridged pro-forma FCF to get an implied value",
	)
	_add_fork_arg(sp)
	sp.set_defaults(func=cmd_pro_forma_fcf)

	sp = sub.add_parser(
		"net-cash-after-atm",
		help="Net cash raised after backing out dilution cost and SBC-funded issuance — R4: never credit the gross raise as a floor",
	)
	sp.add_argument(
		"--raised", required=True, type=_number_type("--raised"),
		help="Gross dollars raised (e.g. via a live ATM)",
	)
	sp.add_argument(
		"--shares-cost", required=True, type=_number_type("--shares-cost"),
		help="Dollar cost of the dilution incurred to raise it",
	)
	sp.add_argument(
		"--sbc-funded", required=True, type=_number_type("--sbc-funded"),
		help="Dollars of the raise attributable to SBC-driven issuance, not fresh capital",
	)
	_add_fork_arg(sp)
	sp.set_defaults(func=cmd_net_cash_after_atm)

	sp = sub.add_parser(
		"sum-of-parts",
		help=(
			"Additive SOTP value vs. the parent's actual market cap — the only ADDITIVE "
			"lens, so it always divides by parent_mc to stay a checkable ratio, not just a subtotal"
		),
	)
	sp.add_argument(
		"--stake-value", required=True, type=_number_type("--stake-value"),
		help="Dollar value of the owned stake/segment being summed",
	)
	sp.add_argument(
		"--operating-value", required=True, type=_number_type("--operating-value"),
		help="Dollar value of the remaining operating business being summed",
	)
	_add_denominator_args(sp, hand_flag="--parent-mc", hand_help="Parent's market cap.")
	_add_fork_arg(sp)
	sp.set_defaults(func=cmd_sum_of_parts)

	sp = sub.add_parser(
		"custom",
		help="Escape hatch for a driver this list doesn't name — doctrine explicitly authorizes re-anchoring on a new driver when the fixed framework breaks",
	)
	sp.add_argument(
		"--expr", required=True,
		help="Arithmetic expression over named inputs — ×, ÷, *, /, +, - and parentheses only",
	)
	sp.add_argument(
		"--inputs", required=True,
		help="Comma-separated name=value pairs feeding --expr, e.g. a=42,b=180e6,c=101.3e9",
	)
	_add_fork_arg(sp)
	sp.set_defaults(func=cmd_custom)

	return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
	try:
		args = build_parser().parse_args(argv)
		result = args.func(args)
	except LensError as exc:
		_emit(exc.payload, compact=True)
		return exc.exit_code
	except Exception as exc:  # noqa: BLE001 — preserve the JSON-only CLI contract
		_emit(
			{"error": "internal_error", "detail": f"{type(exc).__name__}: {exc}"},
			compact=True,
		)
		return 1
	_emit(result)
	return 0


if __name__ == "__main__":
	sys.exit(main())
