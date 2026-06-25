#!/usr/bin/env python3
"""Sector-agnostic CapEx tracker across supply chain layers for any industry.

Tracks quarterly Capital Expenditure trends for individual companies, performs
supply chain cascade health analysis across user-defined layers, and provides
side-by-side CapEx comparisons. Works for any industry: AI, defense, EV,
agriculture, etc. No hardcoded tickers or sectors.

Commands:
	track: Track quarterly CapEx for given symbols
	cascade: Supply chain layer CapEx cascade health analysis
	compare: Side-by-side CapEx comparison of two companies

Args:
	For track:
		symbols (list): Ticker symbols (e.g., "GOOGL", "META", "TSM")
		--quarters (int): Number of quarters to analyze (default: 8)

	For cascade:
		--layers (list): Layer definitions as "Name:SYM1,SYM2" strings
		--quarters (int): Number of quarters (default: 8)

	For compare:
		symbol1 (str): First ticker symbol
		symbol2 (str): Second ticker symbol
		--quarters (int): Number of quarters (default: 8)

Returns:
	dict: {
		"command": str,
		"symbols": [
			{
				"symbol": str,
				"quarters": [
					{
						"period": str,
						"capex": int,
						"qoq_change_pct": float or null,
						"yoy_change_pct": float or null
					}
				],
				"direction": str,
				"latest_capex": int,
				"avg_capex": float
			}
		]
	}

Example:
	>>> python capex_tracker.py track GOOGL META --quarters 8
	{
		"command": "track",
		"quarters_requested": 8,
		"symbols": [
			{
				"symbol": "GOOGL",
				"direction": "accelerating",
				"latest_capex": 12000000000,
				...
			}
		]
	}

	>>> python capex_tracker.py cascade --layers "Hyperscaler:GOOGL,META" "Semi:TSM,NVDA"
	{
		"command": "cascade",
		"layers": [...],
		"cascade_health": "healthy"
	}

	>>> python capex_tracker.py compare GOOGL META
	{
		"command": "compare",
		"symbol1": {...},
		"symbol2": {...},
		"comparison": {...}
	}

Use Cases:
	- Track CapEx acceleration/deceleration across supply chain
	- Validate downstream demand through upstream spending
	- Compare CapEx intensity between competitors
	- Identify spending inflection points in any sector

Notes:
	- CapitalExpenditure from yfinance is typically negative (cash outflow); script uses absolute values
	- Quarters with missing data are marked as null, not estimated
	- cascade_health assessment: "healthy" when upstream CapEx growth >= downstream
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import yfinance as yf

# Support both standalone execution and module imports
try:
	from ..utils import error_json, output_json, safe_run
except ImportError:
	from utils import error_json, output_json, safe_run


def _format_period(ts):
	"""Format a pandas Timestamp into 'YYYY-QN' quarter label."""
	month = ts.month
	if month <= 3:
		q = 1
	elif month <= 6:
		q = 2
	elif month <= 9:
		q = 3
	else:
		q = 4
	return f"{ts.year}-Q{q}"


def _fetch_capex_series(symbol, quarters):
	"""Fetch quarterly CapEx data for a symbol.

	Returns a list of dicts with period and absolute capex value,
	ordered most recent first, or None with an error note if unavailable.
	"""
	try:
		ticker = yf.Ticker(symbol)
		cf = ticker.get_cash_flow(freq="quarterly")
	except Exception as e:
		return None, f"Failed to fetch data for {symbol}: {e}"

	if cf is None or cf.empty:
		return None, f"No quarterly cash flow data available for {symbol}"

	if "CapitalExpenditure" not in cf.index:
		return None, f"CapitalExpenditure row not found for {symbol}"

	row = cf.loc["CapitalExpenditure"]
	cols = list(cf.columns[:quarters])
	if not cols:
		return None, f"No quarterly data columns available for {symbol}"

	series = []
	for col in cols:
		val = row[col]
		if val is None or (hasattr(val, "item") and val != val):
			continue  # null capex quarters excluded from output
		else:
			series.append({"period": _format_period(col), "capex": int(abs(float(val)))})

	return series, None


def _calc_growth_pct(current, previous):
	"""Calculate percentage change: (current - previous) / abs(previous) * 100.

	Returns None if either value is None or previous is zero.
	"""
	if current is None or previous is None or previous == 0:
		return None
	return round((current - previous) / abs(previous) * 100, 2)


def _enrich_series(series):
	"""Add QoQ and YoY change percentages to a capex series."""
	for i, entry in enumerate(series):
		# QoQ: compare with next element (previous quarter, since sorted most recent first)
		if i + 1 < len(series) and entry["capex"] is not None and series[i + 1]["capex"] is not None:
			entry["qoq_change_pct"] = _calc_growth_pct(entry["capex"], series[i + 1]["capex"])
		else:
			entry["qoq_change_pct"] = None

		# YoY: compare with element 4 positions later (same quarter previous year)
		if i + 4 < len(series) and entry["capex"] is not None and series[i + 4]["capex"] is not None:
			entry["yoy_change_pct"] = _calc_growth_pct(entry["capex"], series[i + 4]["capex"])
		else:
			entry["yoy_change_pct"] = None

	return series


def _determine_direction(series):
	"""Determine CapEx direction: accelerating, decelerating, or stable.

	Based on the latest two QoQ changes:
	- accelerating: both positive
	- decelerating: both negative
	- stable: otherwise
	"""
	qoq_values = [e["qoq_change_pct"] for e in series if e.get("qoq_change_pct") is not None]
	if len(qoq_values) < 2:
		return "insufficient_data"

	latest_two = qoq_values[:2]
	if latest_two[0] > 0 and latest_two[1] > 0:
		return "accelerating"
	elif latest_two[0] < 0 and latest_two[1] < 0:
		return "decelerating"
	else:
		return "stable"


def _build_symbol_data(symbol, quarters):
	"""Build complete CapEx data for a single symbol."""
	series, error_note = _fetch_capex_series(symbol, quarters)

	if series is None:
		return {
			"symbol": symbol.upper(),
			"error": error_note,
			"quarters": [],
			"direction": None,
			"latest_capex": None,
			"avg_capex": None,
		}

	series = _enrich_series(series)
	direction = _determine_direction(series)

	valid_capex = [e["capex"] for e in series if e["capex"] is not None]
	avg_capex = round(sum(valid_capex) / len(valid_capex)) if valid_capex else None
	latest_capex = series[0]["capex"] if series else None

	return {
		"symbol": symbol.upper(),
		"quarters": series,
		"direction": direction,
		"latest_capex": latest_capex,
		"avg_capex": avg_capex,
	}


def _parse_layer(layer_str):
	"""Parse a layer definition string 'Name:SYM1,SYM2' into components.

	Returns dict with 'name' and 'symbols' keys, or None on parse failure.
	"""
	if ":" not in layer_str:
		return None
	name, syms_str = layer_str.split(":", 1)
	symbols = [s.strip().upper() for s in syms_str.split(",") if s.strip()]
	if not name.strip() or not symbols:
		return None
	return {"name": name.strip(), "symbols": symbols}


def _calc_layer_aggregate_growth(symbol_data_list):
	"""Calculate aggregate CapEx growth for a layer from its constituent symbols.

	Uses the sum of latest capex vs sum of previous quarter capex for QoQ,
	and sum of latest vs sum of 4 quarters ago for YoY.
	"""
	latest_sum = 0
	prev_sum = 0
	yoy_current_sum = 0
	yoy_prior_sum = 0
	has_latest = False
	has_prev = False
	has_yoy_current = False
	has_yoy_prior = False

	for sd in symbol_data_list:
		quarters = sd.get("quarters", [])
		if len(quarters) >= 1 and quarters[0]["capex"] is not None:
			latest_sum += quarters[0]["capex"]
			has_latest = True
		if len(quarters) >= 2 and quarters[1]["capex"] is not None:
			prev_sum += quarters[1]["capex"]
			has_prev = True
		if len(quarters) >= 1 and quarters[0]["capex"] is not None:
			yoy_current_sum += quarters[0]["capex"]
			has_yoy_current = True
		if len(quarters) >= 5 and quarters[4]["capex"] is not None:
			yoy_prior_sum += quarters[4]["capex"]
			has_yoy_prior = True

	qoq_growth = None
	if has_latest and has_prev and prev_sum != 0:
		qoq_growth = round((latest_sum - prev_sum) / abs(prev_sum) * 100, 2)

	yoy_growth = None
	if has_yoy_current and has_yoy_prior and yoy_prior_sum != 0:
		yoy_growth = round((yoy_current_sum - yoy_prior_sum) / abs(yoy_prior_sum) * 100, 2)

	total_latest = latest_sum if has_latest else None
	total_prev = prev_sum if has_prev else None

	return {
		"aggregate_latest_capex": total_latest,
		"aggregate_prev_capex": total_prev,
		"qoq_growth_pct": qoq_growth,
		"yoy_growth_pct": yoy_growth,
	}


def _assess_cascade_health(layers_data):
	"""Assess whether the supply chain cascade is healthy.

	Healthy: upstream (earlier layers) CapEx growth >= downstream (later layers).
	This validates that upstream spending supports downstream demand signals.
	Compares adjacent layers pairwise.
	"""
	growths = []
	for ld in layers_data:
		agg = ld.get("aggregate", {})
		# Prefer YoY growth for robustness; fall back to QoQ
		g = agg.get("yoy_growth_pct")
		if g is None:
			g = agg.get("qoq_growth_pct")
		growths.append(g)

	# If we cannot compute growth for any layer, return unknown
	if not growths or all(g is None for g in growths):
		return "unknown"

	# Check pairwise: each layer's growth vs the next layer downstream
	healthy_pairs = 0
	unhealthy_pairs = 0
	for i in range(len(growths) - 1):
		upstream = growths[i]
		downstream = growths[i + 1]
		if upstream is None or downstream is None:
			continue
		if upstream >= downstream:
			healthy_pairs += 1
		else:
			unhealthy_pairs += 1

	if healthy_pairs + unhealthy_pairs == 0:
		return "unknown"
	if unhealthy_pairs == 0:
		return "healthy"
	if healthy_pairs == 0:
		return "unhealthy"
	return "mixed"


@safe_run
def cmd_track(args):
	"""Track quarterly CapEx for given symbols."""
	symbols = [s.upper() for s in args.symbols]
	results = []
	for symbol in symbols:
		results.append(_build_symbol_data(symbol, args.quarters))

	output_json({
		"command": "track",
		"quarters_requested": args.quarters,
		"symbols": results,
	})


@safe_run
def cmd_cascade(args):
	"""Supply chain CapEx cascade health."""
	if not args.layers:
		error_json("--layers is required. Format: \"Name:SYM1,SYM2\" \"Name:SYM3\"")

	parsed_layers = []
	for layer_str in args.layers:
		parsed = _parse_layer(layer_str)
		if parsed is None:
			error_json(f"Invalid layer format: '{layer_str}'. Expected 'Name:SYM1,SYM2'")
		parsed_layers.append(parsed)

	layers_output = []
	for layer in parsed_layers:
		symbol_data_list = []
		for sym in layer["symbols"]:
			symbol_data_list.append(_build_symbol_data(sym, args.quarters))

		aggregate = _calc_layer_aggregate_growth(symbol_data_list)

		layers_output.append({
			"name": layer["name"],
			"symbols": symbol_data_list,
			"aggregate": aggregate,
		})

	cascade_health = _assess_cascade_health(layers_output)

	output_json({
		"command": "cascade",
		"quarters_requested": args.quarters,
		"layers": layers_output,
		"cascade_health": cascade_health,
	})


@safe_run
def cmd_compare(args):
	"""Side-by-side CapEx comparison."""
	s1 = _build_symbol_data(args.symbol1, args.quarters)
	s2 = _build_symbol_data(args.symbol2, args.quarters)

	# Build comparison summary
	comparison = {}

	# Latest capex ratio
	if s1["latest_capex"] is not None and s2["latest_capex"] is not None and s2["latest_capex"] != 0:
		comparison["capex_ratio"] = round(s1["latest_capex"] / s2["latest_capex"], 2)
	else:
		comparison["capex_ratio"] = None

	# Direction comparison
	comparison["direction_match"] = s1["direction"] == s2["direction"]
	comparison["symbol1_direction"] = s1["direction"]
	comparison["symbol2_direction"] = s2["direction"]

	# Latest QoQ comparison
	s1_qoq = s1["quarters"][0].get("qoq_change_pct") if s1["quarters"] else None
	s2_qoq = s2["quarters"][0].get("qoq_change_pct") if s2["quarters"] else None
	comparison["symbol1_latest_qoq_pct"] = s1_qoq
	comparison["symbol2_latest_qoq_pct"] = s2_qoq

	# Latest YoY comparison
	s1_yoy = s1["quarters"][0].get("yoy_change_pct") if s1["quarters"] else None
	s2_yoy = s2["quarters"][0].get("yoy_change_pct") if s2["quarters"] else None
	comparison["symbol1_latest_yoy_pct"] = s1_yoy
	comparison["symbol2_latest_yoy_pct"] = s2_yoy

	# Avg capex comparison
	if s1["avg_capex"] is not None and s2["avg_capex"] is not None and s2["avg_capex"] != 0:
		comparison["avg_capex_ratio"] = round(s1["avg_capex"] / s2["avg_capex"], 2)
	else:
		comparison["avg_capex_ratio"] = None

	output_json({
		"command": "compare",
		"quarters_requested": args.quarters,
		"symbol1": s1,
		"symbol2": s2,
		"comparison": comparison,
	})


def main():
	parser = argparse.ArgumentParser(
		description="Sector-agnostic CapEx tracker across supply chain layers"
	)
	sub = parser.add_subparsers(dest="command", required=True)

	# track subcommand
	sp_track = sub.add_parser("track", help="Track quarterly CapEx for given symbols")
	sp_track.add_argument("symbols", nargs="+", help="Ticker symbols (e.g., GOOGL META TSM)")
	sp_track.add_argument("--quarters", type=int, default=8, help="Number of quarters to analyze")
	sp_track.set_defaults(func=cmd_track)

	# cascade subcommand
	sp_cascade = sub.add_parser("cascade", help="Supply chain layer CapEx cascade health")
	sp_cascade.add_argument(
		"--layers", nargs="+", required=True,
		help='Layer definitions as "Name:SYM1,SYM2" strings'
	)
	sp_cascade.add_argument("--quarters", type=int, default=8, help="Number of quarters to analyze")
	sp_cascade.set_defaults(func=cmd_cascade)

	# compare subcommand
	sp_compare = sub.add_parser("compare", help="Side-by-side CapEx comparison of two companies")
	sp_compare.add_argument("symbol1", help="First ticker symbol")
	sp_compare.add_argument("symbol2", help="Second ticker symbol")
	sp_compare.add_argument("--quarters", type=int, default=8, help="Number of quarters to analyze")
	sp_compare.set_defaults(func=cmd_compare)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
