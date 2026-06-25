#!/usr/bin/env python3
"""CNN Fear & Greed Index tracking market sentiment through 7-indicator composite scoring system.

Uses the `fear-greed` PyPI library (https://pypi.org/project/fear-greed/) which fetches data
from CNN's internal API. Composite score ranges from Extreme Fear (0) to Extreme Greed (100).

Args:
	--include-indicators (flag): Include detailed breakdown of all 7 individual sentiment indicators

Returns:
	dict: {
		"current": {
			"score": float,             # 0-100 composite sentiment score
			"rating": str,              # extreme fear, fear, neutral, greed, extreme greed
			"timestamp": str            # Data timestamp
		},
		"previous": {
			"1_week_ago": float,        # Score 1 week ago
			"1_month_ago": float,       # Score 1 month ago
			"1_year_ago": float         # Score 1 year ago
		},
		"indicators": {                 # Optional, if --include-indicators flag set
			"market_momentum_sp500": {"score": float, "rating": str},
			"stock_price_strength": {"score": float, "rating": str},
			"stock_price_breadth": {"score": float, "rating": str},
			"put_call_options": {"score": float, "rating": str},
			"junk_bond_demand": {"score": float, "rating": str},
			"market_volatility_vix": {"score": float, "rating": str},
			"safe_haven_demand": {"score": float, "rating": str}
		},
		"interpretation": str           # Contextual interpretation with contrarian guidance
	}

Example:
	>>> python fear_greed.py
	{"current": {"score": 25, "rating": "fear", ...}, "previous": {...}, "interpretation": "..."}

Notes:
	- Powered by fear-greed library (pip install fear-greed)
	- Extreme Fear (0-25): Panic selling, strong contrarian buy signal
	- Fear (25-45): Bearish sentiment, potential buying opportunity
	- Neutral (45-55): Balanced market, no clear directional signal
	- Greed (55-75): Bullish sentiment, overbought conditions possible
	- Extreme Greed (75-100): Euphoria, correction risk high
"""

import argparse
import os
import sys

# Avoid self-import: script filename matches library name.
# Remove script's own directory from sys.path, import library, then restore.
_own_dir = os.path.dirname(os.path.abspath(__file__))
_filtered = [p for p in sys.path if os.path.abspath(p) != _own_dir]
_orig_path = sys.path[:]
sys.path = _filtered

import fear_greed as _fear_greed_lib

sys.path = _orig_path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from utils import output_json, safe_run


@safe_run
def cmd_fear_greed_index(args):
	"""Fetch CNN Fear & Greed Index data via fear-greed library."""
	data = _fear_greed_lib.get()

	result = {
		"current": {
			"score": data["score"],
			"rating": data["rating"],
			"timestamp": data.get("timestamp", ""),
		},
		"previous": {
			"1_week_ago": data["history"].get("1w"),
			"1_month_ago": data["history"].get("1m"),
			"1_year_ago": data["history"].get("1y"),
		},
	}

	if args.include_indicators:
		result["indicators"] = data.get("indicators", {})

	score = result["current"]["score"]
	if score >= 75:
		interpretation = f"Extreme Greed ({score}): Market euphoria, potential correction risk"
	elif score >= 55:
		interpretation = f"Greed ({score}): Bullish sentiment, overbought conditions possible"
	elif score >= 45:
		interpretation = f"Neutral ({score}): Balanced market sentiment"
	elif score >= 25:
		interpretation = f"Fear ({score}): Bearish sentiment, potential buying opportunity"
	else:
		interpretation = f"Extreme Fear ({score}): Market panic, strong contrarian buy signal"

	result["interpretation"] = interpretation

	output_json(result)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="CNN Fear & Greed Index - Market Sentiment Indicator")
	parser.add_argument(
		"--include-indicators",
		action="store_true",
		help="Include all 7 individual sentiment indicators in output",
	)

	args = parser.parse_args()
	cmd_fear_greed_index(args)
