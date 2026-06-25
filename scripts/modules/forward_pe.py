#!/usr/bin/env python3
"""Forward P/E and PEG ratio calculator for growth stock valuation.

Minervini Ch.4: "P/E Ratio: Overused and Misunderstood" — P/E alone is NOT
sufficient. Growth stocks normally trade at premium multiples. The PEG ratio
(P/E / growth rate) is a better metric for growth-relative valuation.

"Most of the best growth stocks seldom trade at a low P/E ratio. In fact,
many of the biggest winning stocks in history traded at more than 30 or 40
times earnings BEFORE they experienced their largest advance."

Commands:
	calculate: Calculate forward P/E and PEG for a single ticker
	compare: Compare two tickers
	batch: Batch calculation for multiple tickers

Args:
	symbol (str): Stock ticker symbol

Returns:
	dict: {
		"forward_pe_1y": float,
		"forward_pe_2y": float,
		"peg_ratio": float,
		"revenue_growth_yoy": float,
		"gross_margin_pct": float,
		"thresholds": dict
	}

Notes:
	- PEG < 1.0: growth undervalued (P/E below growth rate)
	- PEG 1.0-2.0: fairly valued
	- PEG > 2.0: expensive relative to growth
	- High P/E alone is NOT a reject signal (Minervini Ch.4)
	- forward_pe_2y < forward_pe_1y = earnings outpacing price (bullish)

See Also:
	- growth.py: EPS/sales acceleration and margin trends for PEG context
	- margin_tracker.py: Margin expansion tracking
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import yfinance as yf

try:
	from ..utils import error_json, output_json, safe_run
except ImportError:
	from utils import error_json, output_json, safe_run


def _calculate_forward_pe(symbol):
	"""Calculate forward P/E, PEG ratio, and growth context."""
	ticker = yf.Ticker(symbol)

	# Current price
	current_price = None
	try:
		current_price = ticker.info.get("currentPrice")
	except Exception:
		pass
	if current_price is None:
		try:
			current_price = ticker.fast_info.last_price
		except Exception:
			pass
	if current_price is None:
		error_json(f"Cannot retrieve current price for {symbol}")

	# Forward EPS estimates
	forward_1y_eps = None
	forward_2y_eps = None
	try:
		earnings_est = ticker.get_earnings_estimate()
		if earnings_est is not None and not earnings_est.empty:
			if "0y" in earnings_est.index and "avg" in earnings_est.columns:
				val = earnings_est.loc["0y", "avg"]
				if val == val:
					forward_1y_eps = float(val)
			if "+1y" in earnings_est.index and "avg" in earnings_est.columns:
				val = earnings_est.loc["+1y", "avg"]
				if val == val:
					forward_2y_eps = float(val)
			if forward_1y_eps is None and forward_2y_eps is not None:
				forward_1y_eps = forward_2y_eps
				forward_2y_eps = None
	except Exception:
		pass

	# Forward P/E
	forward_1y_pe = round(current_price / forward_1y_eps, 1) if forward_1y_eps and forward_1y_eps > 0 else None
	forward_2y_pe = round(current_price / forward_2y_eps, 1) if forward_2y_eps and forward_2y_eps > 0 else None

	# Revenue growth
	revenue_growth = None
	try:
		rev_est = ticker.get_revenue_estimate()
		if rev_est is not None and not rev_est.empty:
			if "+1y" in rev_est.index and "growth" in rev_est.columns:
				val = rev_est.loc["+1y", "growth"]
				if val == val:
					revenue_growth = round(float(val) * 100, 1)
			if revenue_growth is None and "0y" in rev_est.index and "growth" in rev_est.columns:
				val = rev_est.loc["0y", "growth"]
				if val == val:
					revenue_growth = round(float(val) * 100, 1)
	except Exception:
		pass

	# EPS growth rate for PEG (from growth_estimates)
	eps_growth_rate = None
	try:
		growth_est = ticker.get_growth_estimates()
		if growth_est is not None and not growth_est.empty:
			if "0y" in growth_est.index and "stockTrend" in growth_est.columns:
				val = growth_est.loc["0y", "stockTrend"]
				if val == val:
					eps_growth_rate = round(float(val) * 100, 1)
	except Exception:
		pass

	# PEG ratio
	peg_ratio = None
	if forward_1y_pe and eps_growth_rate and eps_growth_rate > 0:
		peg_ratio = round(forward_1y_pe / eps_growth_rate, 2)

	# Gross margin
	gross_margin_pct = None
	try:
		gm = ticker.info.get("grossMargins")
		if gm is not None:
			gross_margin_pct = round(gm * 100, 2)
	except Exception:
		pass

	return {
		"symbol": symbol.upper(),
		"current_price": round(current_price, 2),
		"forward_pe_1y": forward_1y_pe,
		"forward_pe_2y": forward_2y_pe,
		"peg_ratio": peg_ratio,
		"peg_ratio_unit": "forward P/E / expected EPS growth rate (%)",
		"eps_growth_rate_used": eps_growth_rate,
		"revenue_growth_yoy": revenue_growth,
		"gross_margin_pct": gross_margin_pct,
		"thresholds": {
			"peg_undervalued": "PEG < 1.0 (P/E below growth rate)",
			"peg_fair": "PEG 1.0-2.0",
			"peg_expensive": "PEG > 2.0",
			"pe_contraction": "forward_pe_2y < forward_pe_1y = earnings outpacing price (bullish)",
			"pe_expansion_warning": "forward_pe_2y > forward_pe_1y = growth slowing relative to price",
			"minervini_caveat": "High P/E alone is NOT a reject — biggest winners traded at 30-40x+",
		},
	}


@safe_run
def cmd_calculate(args):
	result = _calculate_forward_pe(args.symbol)
	output_json(result)


@safe_run
def cmd_compare(args):
	results = []
	for symbol in [args.symbol1, args.symbol2]:
		results.append(_calculate_forward_pe(symbol))
	output_json(results)


@safe_run
def cmd_batch(args):
	results = []
	for symbol in args.symbols:
		results.append(_calculate_forward_pe(symbol))
	output_json(results)


def main():
	parser = argparse.ArgumentParser(description="Forward P/E and PEG ratio calculator")
	sub = parser.add_subparsers(dest="command", required=True)

	sp_calc = sub.add_parser("calculate")
	sp_calc.add_argument("symbol")
	sp_calc.set_defaults(func=cmd_calculate)

	sp_cmp = sub.add_parser("compare")
	sp_cmp.add_argument("symbol1")
	sp_cmp.add_argument("symbol2")
	sp_cmp.set_defaults(func=cmd_compare)

	sp_batch = sub.add_parser("batch")
	sp_batch.add_argument("symbols", nargs="+")
	sp_batch.set_defaults(func=cmd_batch)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
