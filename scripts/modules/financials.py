#!/usr/bin/env python3
"""Financial statements retrieval.

Retrieve income statement, balance sheet, and cash flow statement data for fundamental
analysis via Yahoo Finance API. Supports annual, quarterly, and trailing twelve month (TTM) periods.

Commands:
	get-income-stmt: Income statement (revenue, expenses, net income)
	get-balance-sheet: Balance sheet (assets, liabilities, equity)
	get-cash-flow: Cash flow statement (operating, investing, financing activities)

Args:
	symbol (str): Ticker symbol (e.g., "AAPL", "MSFT", "SPY")
	--freq (str): Reporting frequency (yearly/quarterly/trailing, default: yearly)
		- yearly: Annual financial statements
		- quarterly: Quarterly reports (last 4-5 quarters)
		- trailing: Trailing twelve months (TTM) for income and cash flow

Returns:
	dict: {
		"Date": str,                          # Fiscal period end date
		"Total Revenue": int,                 # Revenue (income statement)
		"Gross Profit": int,                  # Revenue minus COGS
		"Operating Income": int,              # EBIT
		"Net Income": int,                    # Bottom line earnings
		"Total Assets": int,                  # Assets (balance sheet)
		"Total Liabilities Net Minority Interest": int,  # Liabilities
		"Stockholders Equity": int,           # Shareholders equity
		"Operating Cash Flow": int,           # Cash from operations (cash flow)
		"Investing Cash Flow": int,           # Capital expenditures
		"Financing Cash Flow": int,           # Dividends, buybacks, debt
		"Free Cash Flow": int                 # Operating CF - CapEx
	}

Example:
	>>> python financials.py get-income-stmt AAPL --freq yearly
	{
		"2024-09-30": {
			"Total Revenue": 391035000000,
			"Gross Profit": 170782000000,
			"Operating Income": 123216000000,
			"Net Income": 96995000000,
			"Basic EPS": 6.11,
			"Diluted EPS": 6.08
		},
		"2023-09-30": {
			"Total Revenue": 383285000000,
			"Net Income": 96995000000
		}
	}

	>>> python financials.py get-balance-sheet MSFT --freq quarterly
	{
		"2025-12-31": {
			"Total Assets": 512163000000,
			"Total Liabilities Net Minority Interest": 238283000000,
			"Stockholders Equity": 273880000000,
			"Cash And Cash Equivalents": 80021000000,
			"Current Debt": 5247000000,
			"Long Term Debt": 47032000000
		}
	}

	>>> python financials.py get-cash-flow AAPL --freq trailing
	{
		"TTM": {
			"Operating Cash Flow": 118254000000,
			"Investing Cash Flow": -9163000000,
			"Financing Cash Flow": -103510000000,
			"Free Cash Flow": 111628000000,
			"Capital Expenditure": -6626000000
		}
	}

Use Cases:
	- Fundamental analysis and financial health assessment
	- Valuation modeling (DCF, comparables, multiples)
	- Financial ratio calculation (P/E, ROE, debt-to-equity)
	- Revenue growth and profitability trend analysis
	- Free cash flow analysis for dividend sustainability
	- Quarterly performance tracking and earnings quality review

Notes:
	- Yahoo Finance API rate limits: ~2000 requests/hour
	- Financial data typically lags 1-3 months after fiscal period end
	- Quarterly data shows last 4-5 quarters available
	- Trailing frequency calculates TTM by summing last 4 quarters
	- Data granularity varies by company (some fields may be null)
	- GAAP vs non-GAAP metrics: Returns as-reported values
	- Currency in company's reporting currency (check info.py)

See Also:
	- info.py: Company metadata including financial currency
	- actions.py: Earnings dates and quarterly earnings summaries
	- price.py: Stock price for valuation multiples calculation
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import yfinance as yf
from utils import output_json, safe_run


def _extract_revenue_trajectory(financials_data):
	"""Extract quarterly revenue trajectory from income statement data.

	Parses raw income statement output (column-oriented or row-oriented)
	and returns a list of {quarter, revenue} dicts for up to 8 quarters.
	"""
	revenue_by_quarter = []

	if isinstance(financials_data, dict):
		records = financials_data.get("data", financials_data)
		if isinstance(records, dict):
			rev_data = records.get("TotalRevenue") or records.get("Total Revenue")
			if isinstance(rev_data, dict):
				for quarter, revenue in list(rev_data.items())[:8]:
					revenue_by_quarter.append({
						"quarter": str(quarter),
						"revenue": revenue,
					})
			else:
				for date_key, row in list(records.items())[:8]:
					if isinstance(row, dict):
						rev = row.get("TotalRevenue") or row.get("Total Revenue")
						if rev is not None:
							revenue_by_quarter.append({
								"quarter": str(date_key),
								"revenue": rev,
							})
	elif isinstance(financials_data, list):
		for record in financials_data[:8]:
			if isinstance(record, dict):
				quarter = record.get("quarter") or record.get("date") or record.get("period")
				rev = record.get("TotalRevenue") or record.get("Total Revenue") or record.get("revenue")
				if quarter and rev is not None:
					revenue_by_quarter.append({
						"quarter": str(quarter),
						"revenue": rev,
					})

	return {"revenue_by_quarter": revenue_by_quarter}


@safe_run
def cmd_get_income_stmt(args):
	import pandas as pd
	from utils import normalize
	ticker = yf.Ticker(args.symbol)
	raw = ticker.get_income_stmt(freq=args.freq)
	# Enrich quarterly output with revenue_trajectory
	if args.freq == "quarterly":
		# Convert DataFrame to dict before enriching
		if isinstance(raw, pd.DataFrame):
			data = normalize(raw) if not raw.empty else {}
		elif isinstance(raw, dict):
			data = raw
		else:
			data = {}
		if isinstance(data, dict):
			data["revenue_trajectory"] = _extract_revenue_trajectory(data)
		output_json(data)
	else:
		output_json(raw)


@safe_run
def cmd_get_balance_sheet(args):
	ticker = yf.Ticker(args.symbol)
	output_json(ticker.get_balance_sheet(freq=args.freq))


@safe_run
def cmd_get_cash_flow(args):
	ticker = yf.Ticker(args.symbol)
	output_json(ticker.get_cash_flow(freq=args.freq))


def main():
	parser = argparse.ArgumentParser(description="Financial statements retrieval")
	sub = parser.add_subparsers(dest="command", required=True)

	# get-income-stmt
	sp = sub.add_parser("get-income-stmt", help="Get income statement")
	sp.add_argument("symbol")
	sp.add_argument("--freq", default="yearly", choices=["yearly", "quarterly", "trailing"])
	sp.set_defaults(func=cmd_get_income_stmt)

	# get-balance-sheet
	sp = sub.add_parser("get-balance-sheet", help="Get balance sheet")
	sp.add_argument("symbol")
	sp.add_argument("--freq", default="yearly", choices=["yearly", "quarterly"])
	sp.set_defaults(func=cmd_get_balance_sheet)

	# get-cash-flow
	sp = sub.add_parser("get-cash-flow", help="Get cash flow statement")
	sp.add_argument("symbol")
	sp.add_argument("--freq", default="yearly", choices=["yearly", "quarterly", "trailing"])
	sp.set_defaults(func=cmd_get_cash_flow)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
