#!/usr/bin/env python3
"""Debt Structure Analyzer: Analyze balance sheet health and flag toxic debt structures.

Retrieves balance sheet and income statement data to assess debt levels, interest burden,
and overall financial health. Includes stress testing for rate hike scenarios.

Args:
		symbol (str): Stock ticker symbol (e.g., "CRWV", "AAPL", "BA")
		command (str): One of analyze, stress-test

Returns:
		dict: Structure varies by command, typical fields include:
		{
				"symbol": str,
				"total_debt": int,
				"cash_and_equivalents": int,
				"net_debt": int,
				"market_cap": int,
				"net_debt_to_mcap": float,
				"total_revenue": int,
				"interest_expense": int,
				"interest_pct_revenue": float,
				"debt_to_equity": float,
				"debt_health": str,
				"implied_interest_rate": float,
				"debt_quality_grade": str,
				"interest_coverage_ratio": float,
				"interest_coverage_metric": str,  # Metric used for coverage ratio (EBIT or OperatingIncome)
				"grade_thresholds": str,          # Static: debt quality grade classification criteria
				"grade_interpretation": str       # Dynamic: context-aware reading of current debt quality
		}

Example:
		>>> python debt_structure.py analyze CRWV
		{
				"symbol": "CRWV",
				"total_debt": 5000000000,
				"debt_health": "caution",
				"implied_interest_rate": 5.25,
				"debt_quality_grade": "B",
				"interest_coverage_ratio": 3.45
		}

		>>> python debt_structure.py stress-test BA --rate-hike 300
		{
				"symbol": "BA",
				"current_interest_expense": 400000000,
				"stressed_interest_expense": 475000000,
				"stressed_debt_health": "toxic"
		}

Use Cases:
		- Credit risk assessment: Identify companies with unsustainable debt loads
		- Rate sensitivity analysis: Model impact of Fed rate hikes on interest burden
		- Distressed debt screening: Flag companies approaching debt distress
		- Sector comparison: Compare leverage ratios across industry peers

Notes:
		- Interest expense as percentage of revenue is the most actionable metric
		- Companies with >15% interest/revenue ratio often face refinancing risk
		- Net debt (not gross debt) provides a truer picture of leverage
		- Debt-to-equity varies significantly by sector; compare within industry
		- Interest coverage uses EBIT first, falls back to OperatingIncome if EBIT unavailable
		- Stress testing assumes 50% variable rate exposure as a conservative estimate
		- Market cap based valuations can be misleading for highly leveraged firms
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


def _get_field(df, names):
	"""Try multiple row names to extract the most recent value from a financial statement."""
	if df is None or df.empty:
		return None
	col = df.columns[0]  # Most recent period
	for name in names:
		if name in df.index:
			val = df.loc[name, col]
			if val is not None and val == val:  # not NaN
				return val
	return None


def _classify_debt_health(interest_pct_revenue):
	"""Classify debt health based on interest expense as percentage of revenue."""
	if interest_pct_revenue is None:
		return "unknown"
	if interest_pct_revenue < 5:
		return "healthy"
	if interest_pct_revenue <= 15:
		return "caution"
	return "toxic"


def _classify_debt_quality(implied_rate):
	"""Classify debt quality grade based on implied interest rate."""
	if implied_rate is None:
		return None
	if implied_rate < 3:
		return "A"
	if implied_rate <= 6:
		return "B"
	if implied_rate <= 8:
		return "C"
	return "D"


def _build_grade_interpretation(grade, implied_rate, coverage, net_debt):
	"""Build dynamic interpretation of debt quality grade."""
	if grade is None:
		return "Insufficient data to assess debt quality."
	parts = [f"Grade {grade}"]
	if implied_rate is not None:
		parts[0] += f" with {implied_rate}% implied interest rate"
	if grade == "A":
		parts.append("— low refinancing risk.")
		if isinstance(net_debt, (int, float)) and net_debt < 0:
			parts.append("Net cash position further reduces concern.")
	elif grade == "B":
		parts.append("— moderate debt cost, manageable if coverage adequate.")
	elif grade == "C":
		parts.append("— elevated interest burden, monitor refinancing risk.")
	elif grade == "D":
		parts.append("— high implied rate signals distress or junk-grade debt.")
	if isinstance(coverage, (int, float)):
		if coverage < 2:
			parts.append(f"Coverage ratio {coverage}x is dangerously low.")
		elif coverage < 5:
			parts.append(f"Coverage ratio {coverage}x is adequate.")
		else:
			parts.append(f"Coverage ratio {coverage}x provides strong buffer.")
	return " ".join(parts)


def _build_debt_analysis(ticker, symbol):
	"""Build comprehensive debt analysis from balance sheet and income statement."""
	bs = ticker.get_balance_sheet()
	inc = ticker.get_income_stmt()

	if (bs is None or bs.empty) and (inc is None or inc.empty):
		error_json("No financial statement data available")

	# Balance sheet fields
	total_debt = _get_field(
		bs,
		[
			"TotalDebt",
			"Total Debt",
			"LongTermDebt",
			"Long Term Debt",
		],
	)
	cash = _get_field(
		bs,
		[
			"CashAndCashEquivalents",
			"Cash And Cash Equivalents",
			"CashCashEquivalentsAndShortTermInvestments",
			"Cash Cash Equivalents And Short Term Investments",
		],
	)
	equity = _get_field(
		bs,
		[
			"StockholdersEquity",
			"Stockholders Equity",
			"TotalEquityGrossMinorityInterest",
			"Total Equity Gross Minority Interest",
		],
	)

	# If TotalDebt is missing, try summing long-term and current debt
	if total_debt is None:
		lt_debt = _get_field(bs, ["LongTermDebt", "Long Term Debt"])
		ct_debt = _get_field(
			bs,
			[
				"CurrentDebt",
				"Current Debt",
				"CurrentDebtAndCapitalLeaseObligation",
				"Current Debt And Capital Lease Obligation",
			],
		)
		if lt_debt is not None or ct_debt is not None:
			total_debt = (lt_debt or 0) + (ct_debt or 0)

	# Income statement fields
	interest_expense = _get_field(
		inc,
		[
			"InterestExpense",
			"Interest Expense",
			"InterestExpenseNonOperating",
			"Interest Expense Non Operating",
		],
	)
	total_revenue = _get_field(
		inc,
		[
			"TotalRevenue",
			"Total Revenue",
			"Revenue",
		],
	)
	operating_income = _get_field(
		inc,
		[
			"EBIT",
			"OperatingIncome",
			"Operating Income",
		],
	)

	interest_coverage_metric = None
	if inc is not None and not inc.empty:
		for name in ["EBIT", "OperatingIncome", "Operating Income"]:
			if name in inc.index:
				col = inc.columns[0]
				val = inc.loc[name, col]
				if val is not None and val == val:
					interest_coverage_metric = name
					break

	# Market cap from info
	info = ticker.info or {}
	market_cap = info.get("marketCap")

	# Derived metrics
	total_debt_val = int(total_debt) if total_debt is not None else None
	cash_val = int(cash) if cash is not None else None
	net_debt = None
	if total_debt_val is not None and cash_val is not None:
		net_debt = total_debt_val - cash_val

	net_debt_to_mcap = None
	if net_debt is not None and market_cap is not None and market_cap > 0:
		net_debt_to_mcap = round(net_debt / market_cap, 4)

	interest_pct_revenue = None
	if interest_expense is not None and total_revenue is not None and total_revenue > 0:
		# InterestExpense is often reported as negative; use absolute value
		interest_pct_revenue = round(abs(float(interest_expense)) / float(total_revenue) * 100, 2)

	debt_to_equity = None
	if total_debt_val is not None and equity is not None and float(equity) != 0:
		debt_to_equity = round(float(total_debt_val) / float(equity), 4)

	implied_interest_rate = None
	if interest_expense is not None and total_debt_val is not None and total_debt_val > 0:
		implied_interest_rate = round(abs(float(interest_expense)) / float(total_debt_val) * 100, 2)

	interest_coverage_ratio = None
	if operating_income is not None and interest_expense is not None and float(interest_expense) != 0:
		interest_coverage_ratio = round(float(operating_income) / abs(float(interest_expense)), 2)

	return {
		"symbol": symbol.upper(),
		"total_debt": total_debt_val,
		"cash_and_equivalents": cash_val,
		"net_debt": net_debt,
		"market_cap": int(market_cap) if market_cap is not None else None,
		"net_debt_to_mcap": net_debt_to_mcap,
		"total_revenue": int(total_revenue) if total_revenue is not None else None,
		"interest_expense": (int(abs(interest_expense)) if interest_expense is not None else None),
		"interest_pct_revenue": interest_pct_revenue,
		"debt_to_equity": debt_to_equity,
		"debt_health": _classify_debt_health(interest_pct_revenue),
		"implied_interest_rate": implied_interest_rate,
		"debt_quality_grade": _classify_debt_quality(implied_interest_rate),
		"interest_coverage_ratio": interest_coverage_ratio,
		"interest_coverage_metric": interest_coverage_metric,
		"grade_thresholds": {"A": "implied interest <3%", "B": "3-6%", "C": "6-8%", "D": ">8%"},
		"grade_interpretation": _build_grade_interpretation(
			_classify_debt_quality(implied_interest_rate), implied_interest_rate,
			interest_coverage_ratio, net_debt),
	}


@safe_run
def cmd_analyze(args):
	ticker = yf.Ticker(args.symbol)
	result = _build_debt_analysis(ticker, args.symbol)
	output_json(result)


@safe_run
def cmd_stress_test(args):
	ticker = yf.Ticker(args.symbol)
	analysis = _build_debt_analysis(ticker, args.symbol)

	rate_hike_bps = args.rate_hike
	variable_rate_pct = 0.50  # Assume 50% of total debt is variable rate

	total_debt = analysis["total_debt"]
	current_interest = analysis["interest_expense"]
	total_revenue = analysis["total_revenue"]

	if total_debt is None:
		error_json("Cannot stress test: total debt data unavailable")
	if current_interest is None:
		error_json("Cannot stress test: interest expense data unavailable")
	if total_revenue is None or total_revenue == 0:
		error_json("Cannot stress test: revenue data unavailable")

	variable_debt = total_debt * variable_rate_pct
	additional_interest = variable_debt * (rate_hike_bps / 10000)
	stressed_interest = int(current_interest + additional_interest)
	stressed_interest_pct = round(stressed_interest / total_revenue * 100, 2)

	output_json(
		{
			"symbol": args.symbol.upper(),
			"rate_hike_bps": rate_hike_bps,
			"variable_rate_assumption_pct": variable_rate_pct * 100,
			"total_debt": total_debt,
			"variable_rate_debt_estimate": int(variable_debt),
			"current_interest_expense": current_interest,
			"additional_interest_from_hike": int(additional_interest),
			"stressed_interest_expense": stressed_interest,
			"current_interest_pct_revenue": analysis["interest_pct_revenue"],
			"stressed_interest_pct_revenue": stressed_interest_pct,
			"current_debt_health": analysis["debt_health"],
			"stressed_debt_health": _classify_debt_health(stressed_interest_pct),
		}
	)


def main():
	parser = argparse.ArgumentParser(description="Debt structure analyzer")
	sub = parser.add_subparsers(dest="command", required=True)

	sp_analyze = sub.add_parser("analyze")
	sp_analyze.add_argument("symbol")
	sp_analyze.set_defaults(func=cmd_analyze)

	sp_stress = sub.add_parser("stress-test")
	sp_stress.add_argument("symbol")
	sp_stress.add_argument("--rate-hike", type=int, default=200, help="Rate hike in basis points (default: 200)")
	sp_stress.set_defaults(func=cmd_stress_test)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
