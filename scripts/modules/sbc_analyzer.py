#!/usr/bin/env python3
"""Stock-Based Compensation analyzer extracting SBC data and calculating real Free Cash Flow.

Retrieves SBC amounts from cash flow statements, computes SBC as a percentage of revenue,
and derives "real FCF" by subtracting SBC from reported FCF. Flags companies where SBC
materially dilutes shareholder value.

Args:
		symbol (str): Stock ticker symbol (e.g., "SNAP", "PLTR", "AAPL")
		command (str): One of get-sbc, compare-sbc

Returns:
		dict: Structure varies by command, typical fields include:
		{
				"symbol": str,                # Ticker symbol
				"sbc_annual": int,            # Annual SBC amount (most recent)
				"sbc_pct_revenue": float,     # SBC as % of total revenue
				"reported_fcf": int,          # Reported free cash flow
				"real_fcf": int,              # FCF minus SBC
				"flag": str,                  # "healthy" | "warning" | "toxic"
				"sbc_thresholds": str,        # Static: classification criteria for flag
				"sbc_interpretation": str,    # Dynamic: context-aware reading of current SBC level
				"shares_outstanding_current": int,    # Current shares outstanding
				"shares_outstanding_prior_quarter": int,  # Prior quarter shares outstanding
				"shares_change_qoq_pct": float,   # Q/Q shares change percentage
				"dilution_flag": str,             # "active_dilution" | "normal"
				"total_dilution_annual_pct": float # Annualized total dilution estimate
		}

Example:
		>>> python sbc_analyzer.py get-sbc SNAP
		{
				"symbol": "SNAP",
				"sbc_annual": 1234567890,
				"sbc_pct_revenue": 25.3,
				"reported_fcf": 500000000,
				"real_fcf": -734567890,
				"flag": "warning",
				"shares_outstanding_current": 1650000000,
				"shares_outstanding_prior_quarter": 1600000000,
				"shares_change_qoq_pct": 3.12,
				"dilution_flag": "active_dilution",
				"total_dilution_annual_pct": 37.8
		}

		>>> python sbc_analyzer.py compare-sbc AAPL SNAP
		[
				{"symbol": "AAPL", "sbc_pct_revenue": 2.1, "flag": "healthy", ...},
				{"symbol": "SNAP", "sbc_pct_revenue": 25.3, "flag": "warning", ...}
		]

Use Cases:
		- Identify companies where SBC masks true profitability
		- Compare SBC burden across competitors in same sector
		- Flag "toxic" SBC levels that severely dilute shareholders
		- Calculate real FCF to assess genuine cash generation

Notes:
		- SBC is a real cost that dilutes existing shareholders via share issuance
		- Many high-growth tech companies report positive FCF but negative real FCF
		- SBC > 30% of revenue is a red flag for sustained shareholder dilution
		- Trend matters: rising SBC % often indicates management entrenchment

See Also:
		- analysis.py: Analyst estimates and recommendations
		- forward_pe.py: Forward P/E valuation with earnings estimates
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


def _classify_sbc(pct):
	"""Classify SBC percentage into health category."""
	if pct < 10:
		return "healthy"
	elif pct <= 30:
		return "warning"
	else:
		return "toxic"


def _build_sbc_interpretation(sbc_pct, flag, real_fcf):
	"""Build dynamic interpretation of SBC flag."""
	if flag == "toxic":
		return (f"SBC is {sbc_pct:.1f}% of revenue — toxic level. "
				"Cross-check with company lifecycle stage; pre-revenue biotech may use option pools strategically.")
	if flag == "warning":
		return (f"SBC is {sbc_pct:.1f}% of revenue — elevated. "
				"Monitor trend; rising SBC% often signals growing cost of talent retention.")
	fcf_note = "positive real FCF" if real_fcf >= 0 else "real FCF still negative despite low SBC"
	return f"SBC is {sbc_pct:.1f}% of revenue — healthy level with {fcf_note}."


def _extract_sbc_data(symbol):
	"""Extract SBC, revenue, and FCF data for a single symbol."""
	ticker = yf.Ticker(symbol)

	cashflow = ticker.get_cashflow()
	if cashflow is None or cashflow.empty:
		error_json(f"No cash flow data available for {symbol}")

	income = ticker.get_income_stmt()
	if income is None or income.empty:
		error_json(f"No income statement data available for {symbol}")

	# Extract most recent annual values (first column)
	sbc = None
	if "StockBasedCompensation" in cashflow.index:
		sbc = cashflow.loc["StockBasedCompensation"].iloc[0]
	if sbc is None or (hasattr(sbc, "item") and sbc != sbc):
		error_json(f"StockBasedCompensation not found in cash flow for {symbol}")
	sbc = float(sbc)

	revenue = None
	if "TotalRevenue" in income.index:
		revenue = income.loc["TotalRevenue"].iloc[0]
	if revenue is None or (hasattr(revenue, "item") and revenue != revenue):
		error_json(f"TotalRevenue not found in income statement for {symbol}")
	revenue = float(revenue)

	fcf = None
	if "FreeCashFlow" in cashflow.index:
		fcf = cashflow.loc["FreeCashFlow"].iloc[0]
	if fcf is None or (hasattr(fcf, "item") and fcf != fcf):
		error_json(f"FreeCashFlow not found in cash flow for {symbol}")
	fcf = float(fcf)

	sbc_pct = (abs(sbc) / revenue * 100) if revenue != 0 else 0.0
	real_fcf = fcf - abs(sbc)

	# Shares outstanding: current from ticker.info
	info = ticker.info or {}
	shares_current = info.get("sharesOutstanding")

	# Shares outstanding: prior quarter from quarterly balance sheet
	shares_prior = None
	try:
		qbs = ticker.quarterly_balance_sheet
		if qbs is not None and not qbs.empty:
			for name in ["OrdinarySharesNumber", "ShareIssued", "CommonStockSharesOutstanding"]:
				if name in qbs.index and len(qbs.columns) >= 2:
					val = qbs.loc[name].iloc[1]  # 2nd most recent quarter
					if val is not None and val == val:  # not NaN
						shares_prior = int(val)
						break
	except Exception:
		pass

	# Q/Q shares change percentage
	shares_change_qoq = None
	if shares_current and shares_prior and shares_prior > 0:
		shares_change_qoq = round((shares_current - shares_prior) / shares_prior * 100, 2)

	# Dilution flag based on Q/Q change
	dilution_flag = "active_dilution" if shares_change_qoq is not None and shares_change_qoq > 2 else "normal"

	# Annualized total dilution estimate (SBC dilution + shares change)
	total_dilution = round(sbc_pct, 1)
	if shares_change_qoq is not None:
		total_dilution = round(sbc_pct + abs(shares_change_qoq) * 4, 1)

	flag = _classify_sbc(sbc_pct)

	return {
		"symbol": symbol.upper(),
		"sbc_annual": int(abs(sbc)),
		"sbc_pct_revenue": round(sbc_pct, 1),
		"reported_fcf": int(fcf),
		"real_fcf": int(real_fcf),
		"flag": flag,
		"sbc_thresholds": {"healthy": "<10% of revenue", "warning": "10-30%", "toxic": ">30%"},
		"sbc_interpretation": _build_sbc_interpretation(sbc_pct, flag, real_fcf),
		"shares_outstanding_current": shares_current,
		"shares_outstanding_prior_quarter": shares_prior,
		"shares_change_qoq_pct": shares_change_qoq,
		"dilution_flag": dilution_flag,
		"total_dilution_annual_pct": total_dilution,
	}


@safe_run
def cmd_get_sbc(args):
	result = _extract_sbc_data(args.symbol)
	output_json(result)


@safe_run
def cmd_compare_sbc(args):
	results = []
	for symbol in [args.symbol1, args.symbol2]:
		results.append(_extract_sbc_data(symbol))
	output_json(results)


def main():
	parser = argparse.ArgumentParser(description="Stock-Based Compensation analyzer")
	sub = parser.add_subparsers(dest="command", required=True)

	sp_get = sub.add_parser("get-sbc")
	sp_get.add_argument("symbol")
	sp_get.set_defaults(func=cmd_get_sbc)

	sp_cmp = sub.add_parser("compare-sbc")
	sp_cmp.add_argument("symbol1")
	sp_cmp.add_argument("symbol2")
	sp_cmp.set_defaults(func=cmd_compare_sbc)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
