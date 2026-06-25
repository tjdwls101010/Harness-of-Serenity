#!/usr/bin/env python3
"""Margin Tracker: Track gross/operating/net margin changes Q/Q and Y/Y with automatic flagging.

Retrieves quarterly income statement data to calculate profitability margins over time,
detect margin expansion or compression trends, and flag material changes.

Args:
		symbol (str): Stock ticker symbol (e.g., "MU", "AAPL", "TSLA")
		command (str): One of track, flag-expansion

Returns:
		dict: Structure varies by command, typical fields include:
		{
				"symbol": str,
				"quarters_analyzed": int,
				"latest_quarter": {
						"gross_margin": float,
						"operating_margin": float,
						"net_margin": float
				},
				"gross_margin_qoq_change": float,
				"gross_margin_yoy_change": float,
				"operating_margin_qoq_change": float,
				"operating_margin_yoy_change": float,
				"trajectory": [
						{"period": str, "gross": float, "operating": float, "net": float}
				],
				"flag": str,
				"margin_thresholds": str,         # Static: flag classification criteria (YoY gross margin pp change)
				"margin_interpretation": str       # Dynamic: context-aware reading of current margin trend
		}

Example:
		>>> python margin_tracker.py track MU --quarters 8
		{
				"symbol": "MU",
				"quarters_analyzed": 8,
				"latest_quarter": {"gross_margin": 45.2, ...},
				"flag": "EXPANDING"
		}

		>>> python margin_tracker.py flag-expansion MU --threshold 5
		{
				"symbol": "MU",
				"flagged_quarters": [...]
		}

Use Cases:
		- Margin trend analysis: Identify whether a company's profitability is improving or deteriorating
		- Earnings quality: Expanding margins signal operational leverage and pricing power
		- Sector comparison: Compare margin trajectories across peers
		- Early warning: Margin compression often precedes earnings misses

Notes:
		- Quarterly data may have seasonal patterns; Y/Y comparison normalizes for seasonality
		- One-time charges can distort single-quarter margins
		- Gross margin is the most stable indicator; net margin is most volatile
		- EXPANDING flag (>+5pp YoY) often signals inflection point in business cycle
		- COLLAPSE flag (<-10pp YoY) warrants immediate investigation of structural changes
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


def _calc_margin(numerator, denominator):
	"""Calculate margin as percentage, returning None if data is missing."""
	if numerator is None or denominator is None or denominator == 0:
		return None
	return round(float(numerator) / float(denominator) * 100, 2)


def _get_field(df, col, names):
	"""Try multiple row names to extract a value from an income statement column."""
	for name in names:
		if name in df.index:
			val = df.loc[name, col]
			if val is not None and val == val:  # not NaN
				return val
	return None


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


def _build_trajectory(ticker, quarters):
	"""Build margin trajectory from quarterly income statements."""
	stmt = ticker.get_income_stmt(freq="quarterly")
	if stmt is None or stmt.empty:
		error_json("No quarterly income statement data available")

	# Columns are ordered most recent first; limit to requested quarters
	cols = list(stmt.columns[:quarters])
	if not cols:
		error_json("No quarterly data columns available")

	trajectory = []
	for col in cols:
		revenue = _get_field(stmt, col, ["TotalRevenue", "Total Revenue", "Revenue"])
		gross_profit = _get_field(stmt, col, ["GrossProfit", "Gross Profit"])
		operating_income = _get_field(
			stmt,
			col,
			[
				"OperatingIncome",
				"Operating Income",
				"EBIT",
				"OperatingRevenue",
			],
		)
		net_income = _get_field(
			stmt,
			col,
			[
				"NetIncome",
				"Net Income",
				"NetIncomeCommonStockholders",
				"Net Income Common Stockholders",
			],
		)

		trajectory.append(
			{
				"period": _format_period(col),
				"gross": _calc_margin(gross_profit, revenue),
				"operating": _calc_margin(operating_income, revenue),
				"net": _calc_margin(net_income, revenue),
			}
		)

	return trajectory


def _classify_flag(gross_yoy, operating_yoy):
	"""Classify margin trend based on BEST of gross or operating YoY change.

	Minervini Ch.8: "consistent improvement in operating margins and net profit margins."
	Uses the better of gross/operating to avoid missing major operating improvements.
	"""
	# Use the better of the two
	changes = [c for c in [gross_yoy, operating_yoy] if c is not None]
	if not changes:
		return "INSUFFICIENT_DATA"
	best_change = max(changes)

	if best_change > 5:
		return "EXPANDING"
	if best_change >= -2:
		return "STABLE"
	if best_change >= -10:
		return "COMPRESSION"
	return "COLLAPSE"


def _build_margin_interpretation(flag, latest):
	"""Build dynamic interpretation of margin flag."""
	gross = latest.get("gross")
	op = latest.get("operating")
	margin_str = ""
	if gross is not None and op is not None:
		margin_str = f" Gross {gross}%, operating {op}%."
	elif gross is not None:
		margin_str = f" Gross {gross}%."
	if flag == "EXPANDING":
		return f"Margin trend: {flag}.{margin_str} Pricing power or operating leverage improving — bullish signal."
	if flag == "COLLAPSE":
		return f"Margin trend: {flag}.{margin_str} Investigate structural cause: competition, cost inflation, or one-time charge."
	if flag == "COMPRESSION":
		return f"Margin trend: {flag}.{margin_str} Mild decline — monitor for acceleration into collapse territory."
	if flag == "STABLE":
		return f"Margin trend: {flag}.{margin_str} Margins holding — no immediate concern but limited upside signal."
	return f"Margin trend: {flag}.{margin_str} Insufficient data for YoY comparison."


@safe_run
def cmd_track(args):
	ticker = yf.Ticker(args.symbol)
	trajectory = _build_trajectory(ticker, args.quarters)

	latest = trajectory[0]
	result = {
		"symbol": args.symbol.upper(),
		"quarters_analyzed": len(trajectory),
		"latest_quarter": {
			"gross_margin": latest["gross"],
			"operating_margin": latest["operating"],
			"net_margin": latest["net"],
		},
	}

	# Q/Q change: column[0] vs column[1]
	if len(trajectory) >= 2:
		prev = trajectory[1]
		result["gross_margin_qoq_change"] = (
			round(latest["gross"] - prev["gross"], 2)
			if latest["gross"] is not None and prev["gross"] is not None
			else None
		)
		result["operating_margin_qoq_change"] = (
			round(latest["operating"] - prev["operating"], 2)
			if latest["operating"] is not None and prev["operating"] is not None
			else None
		)
	else:
		result["gross_margin_qoq_change"] = None
		result["operating_margin_qoq_change"] = None

	# Y/Y change: column[0] vs column[4]
	if len(trajectory) >= 5:
		yoy = trajectory[4]
		result["gross_margin_yoy_change"] = (
			round(latest["gross"] - yoy["gross"], 2)
			if latest["gross"] is not None and yoy["gross"] is not None
			else None
		)
		result["operating_margin_yoy_change"] = (
			round(latest["operating"] - yoy["operating"], 2)
			if latest["operating"] is not None and yoy["operating"] is not None
			else None
		)
	else:
		result["gross_margin_yoy_change"] = None
		result["operating_margin_yoy_change"] = None

	# Add QoQ changes to trajectory entries
	for i, entry in enumerate(trajectory):
		if i + 1 < len(trajectory):
			prev = trajectory[i + 1]
			entry["gross_qoq"] = round(entry["gross"] - prev["gross"], 2) if entry["gross"] is not None and prev["gross"] is not None else None
			entry["operating_qoq"] = round(entry["operating"] - prev["operating"], 2) if entry["operating"] is not None and prev["operating"] is not None else None

	result["trajectory"] = trajectory
	result["flag"] = _classify_flag(result["gross_margin_yoy_change"], result["operating_margin_yoy_change"])
	result["change_unit"] = "percentage points (pp)"
	result["thresholds"] = {
		"EXPANDING": "best of gross/operating YoY change > +5pp",
		"STABLE": "-2pp to +5pp",
		"COMPRESSION": "-10pp to -2pp",
		"COLLAPSE": "< -10pp",
	}

	output_json(result)


@safe_run
def cmd_flag_expansion(args):
	ticker = yf.Ticker(args.symbol)
	trajectory = _build_trajectory(ticker, args.quarters)
	threshold = args.threshold

	flagged = []
	for i, entry in enumerate(trajectory):
		changes = {}

		# Q/Q change
		if i + 1 < len(trajectory):
			prev = trajectory[i + 1]
			for margin_key in ["gross", "operating", "net"]:
				if entry[margin_key] is not None and prev[margin_key] is not None:
					diff = round(entry[margin_key] - prev[margin_key], 2)
					if abs(diff) > threshold:
						changes[f"{margin_key}_margin_qoq_change"] = diff

		# Y/Y change
		if i + 4 < len(trajectory):
			yoy = trajectory[i + 4]
			for margin_key in ["gross", "operating", "net"]:
				if entry[margin_key] is not None and yoy[margin_key] is not None:
					diff = round(entry[margin_key] - yoy[margin_key], 2)
					if abs(diff) > threshold:
						changes[f"{margin_key}_margin_yoy_change"] = diff

		if changes:
			flagged.append(
				{
					"period": entry["period"],
					"gross": entry["gross"],
					"operating": entry["operating"],
					"net": entry["net"],
					**changes,
				}
			)

	output_json(
		{
			"symbol": args.symbol.upper(),
			"threshold_pp": threshold,
			"quarters_analyzed": len(trajectory),
			"flagged_quarters": flagged,
		}
	)


def main():
	parser = argparse.ArgumentParser(description="Margin trajectory tracker")
	sub = parser.add_subparsers(dest="command", required=True)

	sp_track = sub.add_parser("track")
	sp_track.add_argument("symbol")
	sp_track.add_argument("--quarters", type=int, default=8)
	sp_track.set_defaults(func=cmd_track)

	sp_flag = sub.add_parser("flag-expansion")
	sp_flag.add_argument("symbol")
	sp_flag.add_argument("--threshold", type=float, default=5.0)
	sp_flag.add_argument("--quarters", type=int, default=8)
	sp_flag.set_defaults(func=cmd_flag_expansion)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
