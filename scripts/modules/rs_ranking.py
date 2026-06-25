#!/usr/bin/env python3
"""RS (Relative Strength) Ranking: IBD-style RS Rating via ibd-rs-rating library.

Provides percentile-based Relative Strength ratings (1-99) calculated across
~4,600 US-listed stocks. Powered by the ibd-rs-rating library which uses
daily-updated data from Supabase.

Formula: 0.4*ROC(63) + 0.2*ROC(126) + 0.2*ROC(189) + 0.2*ROC(252)
         -> percentile ranked 1-99

Commands:
	score: RS Rating with benchmark comparison and history for a single ticker
	screen: Screen for high-RS stocks by minimum rating
	compare: Compare RS ratings across multiple tickers

Args:
	For score:
		symbol (str): Ticker symbol (e.g., "AAPL", "NVDA")

	For screen:
		--min-rating (int): Minimum RS rating (default: 80)
		--limit (int): Maximum results (default: 50)

	For compare:
		symbols (list): List of ticker symbols to compare

Returns:
	For score:
		dict: {
			"rs_rating": int,
			"vs_spy": int,
			"history": {"1w_ago": int, "1m_ago": int, "3m_ago": int, "6m_ago": int},
			"threshold": str
		}

	For screen:
		dict: {
			"data": [{"ticker": str, "rs_rating": int, "rs_raw": float}, ...],
			"metadata": {"count": int, "min_rating": int}
		}

	For compare:
		dict: {
			"rankings": [{"ticker": str, "rs_rating": int, "rs_raw": float}, ...],
			"count": int
		}

Example:
	>>> python rs_ranking.py score NVDA
	{
		"rs_rating": 69,
		"vs_spy": 16,
		"history": {"1w_ago": 70, "1m_ago": 65, "3m_ago": 58, "6m_ago": 45},
		"threshold": "RS >= 70 for TT criterion 8"
	}

	>>> python rs_ranking.py screen --min-rating 90 --limit 10
	{
		"data": [{"ticker": "MU", "rs_rating": 98}, ...],
		"metadata": {"count": 10, "min_rating": 90}
	}

	>>> python rs_ranking.py compare NVDA AMD AVGO MU
	{
		"rankings": [
			{"ticker": "MU", "rs_rating": 98},
			{"ticker": "AVGO", "rs_rating": 85},
			...
		]
	}

Use Cases:
	- Identify market leaders with strongest relative price performance
	- Filter SEPA candidates by RS >= 70 (Trend Template criterion 8)
	- Compare sector peers to find the strongest name
	- Track RS trend over time (history) for divergence detection
	- Screen for high-RS universe for momentum strategies

Notes:
	- RS Rating is percentile-based: 99 = top 1%, 70 = top 30% of ~4,600 stocks
	- Data updated daily after market close via GitHub Actions
	- History enables divergence detection: price down but RS stable = institutional support
	- No yfinance dependency — all data from ibd-rs-rating library (Supabase backend)

See Also:
	- trend_template.py: Uses RS >= 70 as criterion 8
	- stage_analysis.py: RS improving is a Stage 1->2 transition signal
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils import error_json, output_json, safe_run

from rs_rating import RS

_rs = RS()

# Trading day targets for history lookups
_HISTORY_TARGETS = {
	"1w_ago": 5,
	"1m_ago": 20,
	"3m_ago": 63,
	"6m_ago": 126,
}


def _find_rs_at_offset(history, target_days, tolerance=3):
	"""Find RS rating at approximately target_days ago from history list.

	History is sorted newest-first. We look for the entry closest to target_days
	offset from the first entry, within tolerance.
	"""
	if not history or len(history) <= target_days - tolerance:
		return None

	# Clamp to available range
	idx = min(target_days, len(history) - 1)

	# Search within tolerance window for best match
	best_idx = idx
	for candidate in range(max(0, idx - tolerance), min(len(history), idx + tolerance + 1)):
		if abs(candidate - target_days) < abs(best_idx - target_days):
			best_idx = candidate

	return history[best_idx].get("rs_rating")


def _build_history(ticker):
	"""Build history dict with RS ratings at 1w, 1m, 3m, 6m ago."""
	try:
		hist = _rs.history(ticker, days=130)
	except Exception:
		return {}

	if not hist:
		return {}

	result = {}
	for label, target_days in _HISTORY_TARGETS.items():
		rs_val = _find_rs_at_offset(hist, target_days)
		if rs_val is not None:
			result[label] = rs_val

	return result


def _get_spy_rs():
	"""Get SPY's current RS rating from reference endpoint."""
	try:
		ref = _rs.reference()
		for item in ref:
			if item.get("ticker") == "SPY":
				return item.get("rs_rating")
	except Exception:
		pass
	return None


def compute_rs_score(symbol):
	"""Public API: compute RS score (0-99) for use by other modules.

	Called by trend_template.py criterion 8 and minervini pipeline RS component.

	Args:
		symbol: Ticker symbol (e.g., "NVDA")

	Returns:
		int or None: RS rating 0-99, or None if data unavailable
	"""
	try:
		result = _rs.get(symbol.upper())
		if result and "rs_rating" in result:
			return result["rs_rating"]
		return None
	except Exception:
		return None


@safe_run
def cmd_score(args):
	"""RS Rating with benchmark comparison and history."""
	ticker = args.symbol.upper()

	try:
		result = _rs.get(ticker)
	except Exception as e:
		error_json(f"RS data unavailable for {ticker}: {e}")
		return

	if not result or "rs_rating" not in result:
		error_json(f"No RS data found for {ticker}")
		return

	rs_rating = result["rs_rating"]
	spy_rs = _get_spy_rs()
	history = _build_history(ticker)

	output = {
		"rs_rating": rs_rating,
		"spy_rs": spy_rs,
		"history": history if history else None,
		"threshold": "RS >= 70 for TT criterion 8",
	}

	output_json(output)


@safe_run
def cmd_screen(args):
	"""Screen for high-RS stocks by minimum rating."""
	min_rating = args.min_rating
	limit = args.limit

	try:
		stocks = _rs.filter(min_rating=min_rating)
	except Exception as e:
		error_json(f"RS screen failed: {e}")
		return

	if not stocks:
		output_json({
			"data": [],
			"metadata": {"count": 0, "min_rating": min_rating},
		})
		return

	# Sort by rs_rating descending, limit results
	stocks.sort(key=lambda x: x.get("rs_rating", 0), reverse=True)
	if limit:
		stocks = stocks[:limit]

	output_json({
		"data": stocks,
		"metadata": {
			"count": len(stocks),
			"min_rating": min_rating,
		},
	})


@safe_run
def cmd_compare(args):
	"""Compare RS ratings across multiple tickers."""
	tickers = [t.upper() for t in args.symbols]

	try:
		results = _rs.compare(tickers)
	except Exception as e:
		error_json(f"RS compare failed: {e}")
		return

	if not results:
		output_json({"rankings": [], "count": 0})
		return

	# Already sorted by rs_rating descending from library
	output_json({
		"rankings": results,
		"count": len(results),
	})


def main():
	parser = argparse.ArgumentParser(description="RS (Relative Strength) Ranking")
	sub = parser.add_subparsers(dest="command", required=True)

	# score
	sp = sub.add_parser("score", help="RS Rating for a single ticker")
	sp.add_argument("symbol", help="Ticker symbol")
	sp.set_defaults(func=cmd_score)

	# screen
	sp = sub.add_parser("screen", help="Screen for high-RS stocks")
	sp.add_argument("--min-rating", type=int, default=80, help="Minimum RS rating (default: 80)")
	sp.add_argument("--limit", type=int, default=50, help="Max results (default: 50)")
	sp.set_defaults(func=cmd_screen)

	# compare
	sp = sub.add_parser("compare", help="Compare RS ratings for multiple tickers")
	sp.add_argument("symbols", nargs="+", help="Ticker symbols to compare")
	sp.set_defaults(func=cmd_compare)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
