#!/usr/bin/env python3
"""No-Growth Valuation Stress Test computing intrinsic value assuming zero future growth.

Serenity's baseline method: what is the stock worth if growth stops today?
Calculates a no-growth fair value using current revenue, current net margin,
and a fixed 15x P/E multiple, then compares against market cap to determine
margin of safety.

Args:
		symbol (str): Stock ticker symbol (e.g., "NBIS", "AAPL", "MSFT")
		command (str): One of calculate, compare

Returns:
		dict: Structure varies by command, typical fields include:
		{
				"symbol": str,                      # Ticker symbol
				"current_revenue": int,             # Most recent annual total revenue
				"net_margin_pct": float,            # Net income / revenue as percentage
				"implied_earnings": int,            # Revenue * net margin
				"no_growth_pe_multiple": int,       # Fixed at 15
				"no_growth_fair_value": int,        # Implied earnings * P/E multiple
				"current_market_cap": int,          # Current market capitalization
				"margin_of_safety_pct": float,      # (fair_value - market_cap) / market_cap * 100
				"stress_test": str                  # "pass", "marginal", or "fail"
		}

Example:
		>>> python no_growth_valuation.py calculate NBIS
		{
				"symbol": "NBIS",
				"current_revenue": 500000000,
				"net_margin_pct": 12.5,
				"implied_earnings": 62500000,
				"no_growth_pe_multiple": 15,
				"no_growth_fair_value": 937500000,
				"current_market_cap": 2000000000,
				"margin_of_safety_pct": -53.1,
				"stress_test": "fail"
		}

		>>> python no_growth_valuation.py compare NBIS AAPL
		{
				"symbol_a": { ... },
				"symbol_b": { ... },
				"comparison": "AAPL has better margin of safety (-20.5% vs -53.1%)"
		}

Use Cases:
		- Baseline valuation: Determine minimum intrinsic value with no growth assumption
		- Growth dependency check: How much growth is priced into the current stock price
		- Risk screening: Identify stocks that require significant growth to justify price
		- Relative value: Compare two stocks on a zero-growth basis

Notes:
		- Uses a fixed 15x P/E multiple as a conservative no-growth assumption
		- Negative net income is handled: sets negative_earnings flag but still calculates
		- Revenue and net income come from the most recent annual income statement
		- Market cap comes from ticker.info
		- This is a stress test, not a price target; most growth stocks will fail

See Also:
		- analysis.py: Analyst estimates for growth assumptions
		- institutional_quality.py: Who holds the stock (quality of holders)
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

NO_GROWTH_PE = 15


def _determine_stress_test(margin_of_safety_pct):
	"""Classify the stress test result based on margin of safety."""
	if margin_of_safety_pct >= 0:
		return "pass"
	if margin_of_safety_pct >= -30:
		return "marginal"
	return "fail"


def _compute_no_growth(symbol):
	"""Compute no-growth valuation for a single symbol."""
	ticker = yf.Ticker(symbol)

	# Fetch income statement (annual)
	income_stmt = ticker.get_income_stmt()
	if income_stmt is None or income_stmt.empty:
		error_json(f"No income statement data available for {symbol}")

	# Most recent annual column is the first column
	latest = income_stmt.iloc[:, 0]

	# Extract revenue and net income
	revenue = None
	net_income = None

	for label in ("TotalRevenue", "Total Revenue", "OperatingRevenue"):
		if label in latest.index and latest[label] is not None:
			revenue = latest[label]
			break

	for label in ("NetIncome", "Net Income", "NetIncomeCommonStockholders"):
		if label in latest.index and latest[label] is not None:
			net_income = latest[label]
			break

	if revenue is None:
		error_json(f"TotalRevenue not found in income statement for {symbol}")
	if net_income is None:
		error_json(f"NetIncome not found in income statement for {symbol}")

	# Convert to Python numeric types
	revenue = float(revenue)
	net_income = float(net_income)

	negative_earnings = net_income < 0
	net_margin = net_income / revenue if revenue != 0 else 0
	net_margin_pct = round(net_margin * 100, 2)

	implied_earnings = revenue * net_margin
	no_growth_fair_value = implied_earnings * NO_GROWTH_PE

	# Market cap
	info = ticker.info
	market_cap = info.get("marketCap")
	if market_cap is None:
		error_json(f"Market cap not available for {symbol}")

	market_cap = float(market_cap)

	# Margin of safety
	if market_cap != 0:
		margin_of_safety_pct = round((no_growth_fair_value - market_cap) / market_cap * 100, 1)
	else:
		margin_of_safety_pct = 0.0

	stress_test = _determine_stress_test(margin_of_safety_pct)

	result = {
		"symbol": symbol,
		"current_revenue": int(revenue),
		"net_margin_pct": net_margin_pct,
		"implied_earnings": int(implied_earnings),
		"no_growth_pe_multiple": NO_GROWTH_PE,
		"no_growth_fair_value": int(no_growth_fair_value),
		"current_market_cap": int(market_cap),
		"margin_of_safety_pct": margin_of_safety_pct,
		"stress_test": stress_test,
	}

	if negative_earnings:
		result["negative_earnings"] = True

	return result


@safe_run
def cmd_calculate(args):
	result = _compute_no_growth(args.symbol)
	output_json(result)


@safe_run
def cmd_compare(args):
	result_a = _compute_no_growth(args.symbol1)
	result_b = _compute_no_growth(args.symbol2)

	mos_a = result_a["margin_of_safety_pct"]
	mos_b = result_b["margin_of_safety_pct"]

	if mos_a > mos_b:
		comparison = f"{args.symbol1} has better margin of safety ({mos_a}% vs {mos_b}%)"
	elif mos_b > mos_a:
		comparison = f"{args.symbol2} has better margin of safety ({mos_b}% vs {mos_a}%)"
	else:
		comparison = f"Both have equal margin of safety ({mos_a}%)"

	output_json(
		{
			"symbol_a": result_a,
			"symbol_b": result_b,
			"comparison": comparison,
		}
	)


def main():
	parser = argparse.ArgumentParser(description="No-growth valuation stress test")
	sub = parser.add_subparsers(dest="command", required=True)

	sp_calc = sub.add_parser("calculate")
	sp_calc.add_argument("symbol")
	sp_calc.set_defaults(func=cmd_calculate)

	sp_compare = sub.add_parser("compare")
	sp_compare.add_argument("symbol1")
	sp_compare.add_argument("symbol2")
	sp_compare.set_defaults(func=cmd_compare)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
