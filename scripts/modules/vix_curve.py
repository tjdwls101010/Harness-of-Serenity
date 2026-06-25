#!/usr/bin/env python3
"""VIX Futures Curve analyzer for market regime detection and fear assessment.

Analyzes the VIX futures term structure by fetching the VIX spot price and VX1-VX9
futures prices from CBOE delayed quotes. The term structure reveals the market's
expectation of future volatility: contango (upward sloping) indicates normal conditions
where hedging costs increase with time, while backwardation (downward sloping) signals
acute fear where near-term protection is more expensive than longer-dated insurance.

The shape of the VIX curve is one of the most powerful regime indicators available.
Persistent contango with low spot VIX suggests complacency, while steep backwardation
with elevated VIX signals panic -- historically a contrarian buy signal for risk assets.

Args:
	command (str): "analyze" (primary command)
	--date (str, optional): Date string (YYYY-MM-DD) for historical front month calculation.
		Defaults to today. Affects which VX symbols are considered front month.

Returns:
	dict: {
		"vix_spot": float,                     # Current VIX spot price
		"term_structure": {
			"VX1": {"price": float, "expiration": str},  # Front month
			"VX2": {"price": float, "expiration": str},  # Second month
			...
			"VX9": {"price": float, "expiration": str}   # Ninth month
		},
		"structure_type": str,                 # "contango" | "backwardation" | "flat"
		"slope_per_month": float,              # (VX4 - VX1) / 3, avg monthly vol change
		"vix_vs_vx1_spread": float,            # VIX_spot - VX1
		"front_month_roll_yield_pct": float,   # (VX1 - VIX_spot) / VIX_spot * 100
		"regime": str,                         # "complacent" | "normal" | "anxious" | "panic"
		"analysis": {
			"fear_level": str,                 # "low" | "moderate" | "elevated" | "extreme"
			"options_market_signal": str,       # Interpretation for risk positioning
			"contrarian_signal": str            # Contrarian trading interpretation
		}
	}

Example:
	>>> python vix_curve.py analyze
	{
		"vix_spot": 14.50,
		"term_structure": {
			"VX1": {"price": 15.20, "expiration": "2026-03"},
			"VX2": {"price": 16.80, "expiration": "2026-04"}
		},
		"structure_type": "contango",
		"slope_per_month": 0.97,
		"regime": "complacent"
	}

Use Cases:
	- Market regime detection: Identify complacent, normal, anxious, or panic regimes
	- Contrarian timing: Extreme backwardation + VIX > 30 historically marks capitulation
	- Macro overlay: Combine with net liquidity and ERP for composite risk assessment
	- Volatility trading: Assess roll yield for VIX ETP positioning (SVXY, UVXY, VXX)

Notes:
	- VIX futures roll on the third Wednesday of each month (settlement day)
	- Contango is the normal state (~80% of time); sustained contango favors short-vol
	- Backwardation signals stress; deep backwardation is rare and contrarian bullish
	- Regime thresholds are approximate and should be combined with other indicators
	- CBOE delayed quotes may lag by 15-20 minutes during market hours
	- Some back-month futures may lack quotes during low-activity periods
	- Data source requires no authentication (public CBOE delayed quotes API)

See Also:
	- fear_greed.py: CNN Fear & Greed composite for sentiment overlay
	- net_liquidity.py: Fed liquidity plumbing for systemic context
	- iv_context.py: Individual stock implied volatility analysis
"""

import argparse
import os
import sys
from calendar import monthcalendar
from collections import deque
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests

# Support both standalone execution and module imports
try:
	from ..utils import error_json, output_json, safe_run
except ImportError:
	from utils import error_json, output_json, safe_run


# CBOE delayed quotes base URL
CBOE_QUOTES_URL = "https://cdn.cboe.com/api/global/delayed_quotes/quotes/{symbol}.json"

# VIX spot symbol
VIX_SPOT_SYMBOL = "_VIX"

# VX futures month-to-symbol mapping (same as OpenBB reference)
VX_SYMBOL_ORDER = [
	"UZF",  # January
	"UZG",  # February
	"UZH",  # March
	"UZJ",  # April
	"UZK",  # May
	"UZM",  # June
	"UZN",  # July
	"UZQ",  # August
	"UZU",  # September
	"UZV",  # October
	"UZX",  # November
	"UZZ",  # December
]

# Month names for expiration display
MONTH_NUMBERS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]


def get_front_month(date=None):
	"""Get the front month based on the third Wednesday of the current month.

	If today is past the third Wednesday, the front month rolls to next month.
	This mirrors the VIX futures settlement schedule.

	Args:
		date: Optional date string (YYYY-MM-DD). Defaults to today.

	Returns:
		int: Front month number (1-12)
	"""
	today = datetime.now() if date is None else datetime.strptime(date, "%Y-%m-%d")
	third_wednesday = [week[2] for week in monthcalendar(today.year, today.month) if week[2] != 0][2]
	if today.day > third_wednesday:
		return (today.month % 12) + 1
	return today.month


def get_vx_symbols(date=None):
	"""Get VX futures symbols mapped to VX1-VX9 based on front month rotation.

	Rotates the symbol deque so that VX1 corresponds to the current front month.

	Args:
		date: Optional date string (YYYY-MM-DD). Defaults to today.

	Returns:
		dict: {\"VX1\": \"UZF\", \"VX2\": \"UZG\", ...} (rotated based on front month)
	"""
	symbols = deque(VX_SYMBOL_ORDER[:])
	symbols.rotate(-(get_front_month(date) - 1))
	return {f"VX{i + 1}": symbol for i, symbol in enumerate(symbols)}


def get_expiration_months(date=None):
	"""Get expiration month numbers for VX1-VX9.

	Args:
		date: Optional date string (YYYY-MM-DD). Defaults to today.

	Returns:
		dict: {\"VX1\": 3, \"VX2\": 4, ...} month numbers rotated by front month
	"""
	front = get_front_month(date)
	months = deque(MONTH_NUMBERS[:])
	months.rotate(-front + 1)
	return {f"VX{i + 1}": month for i, month in enumerate(months)}


def get_expiration_labels(date=None):
	"""Build YYYY-MM expiration labels for VX1-VX9.

	Handles year rollover when months wrap past December.

	Args:
		date: Optional date string (YYYY-MM-DD). Defaults to today.

	Returns:
		dict: {\"VX1\": \"2026-03\", \"VX2\": \"2026-04\", ...}
	"""
	today = datetime.now() if date is None else datetime.strptime(date, "%Y-%m-%d")
	current_year = today.year
	front = get_front_month(date)
	months = get_expiration_months(date)

	labels = {}
	for vx_label in [f"VX{i}" for i in range(1, 10)]:
		month = months[vx_label]
		# Detect year rollover: if month < front month and front != January
		if month < front and front != 1:
			year = current_year + 1
		else:
			year = current_year
		labels[vx_label] = f"{year}-{month:02d}"

	return labels


def fetch_cboe_quote(symbol):
	"""Fetch a single delayed quote from CBOE.

	Args:
		symbol: CBOE symbol (e.g., \"_VIX\", \"UZF\")

	Returns:
		float or None: Current price, or None if fetch fails
	"""
	# VX futures symbols (UZF-UZZ) require underscore prefix for CBOE API
	if symbol.startswith("UZ") and not symbol.startswith("_"):
		symbol = f"_{symbol}"
	url = CBOE_QUOTES_URL.format(symbol=symbol)
	try:
		resp = requests.get(url, timeout=10)
		resp.raise_for_status()
		data = resp.json()
		# CBOE quote structure: {"data": {"current_price": ..., ...}}
		quote_data = data.get("data", {})
		price = quote_data.get("current_price")
		if price is None:
			price = quote_data.get("last_price")
		if price is not None and float(price) > 0:
			return float(price)
		return None
	except Exception:
		return None


def classify_structure(vx1_price, vx2_price):
	"""Classify term structure as contango, backwardation, or flat.

	Args:
		vx1_price: Front month futures price
		vx2_price: Second month futures price

	Returns:
		str: \"contango\", \"backwardation\", or \"flat\"
	"""
	if vx1_price is None or vx2_price is None:
		return "unknown"
	spread = vx2_price - vx1_price
	if spread > 0.10:
		return "contango"
	elif spread < -0.10:
		return "backwardation"
	else:
		return "flat"


def classify_regime(vix_spot, structure_type):
	"""Classify the volatility regime based on VIX level and term structure shape.

	Regime definitions:
		- complacent: VIX < 15 and contango (low fear, risk assets favorable)
		- normal: VIX 15-25 and contango (healthy market regime)
		- anxious: VIX 20-30 and flat or mild backwardation (elevated concern)
		- panic: VIX > 30 and backwardation (extreme fear, contrarian buy signal)

	Args:
		vix_spot: Current VIX spot level
		structure_type: Term structure classification

	Returns:
		str: Regime classification
	"""
	if vix_spot is None:
		return "unknown"

	if vix_spot > 30 and structure_type == "backwardation":
		return "panic"
	if vix_spot >= 20 and structure_type in ("flat", "backwardation"):
		return "anxious"
	if vix_spot >= 15 and structure_type == "contango":
		return "normal"
	if vix_spot < 15 and structure_type == "contango":
		return "complacent"

	# Edge cases: moderate VIX with unusual structure
	if vix_spot < 15:
		return "complacent"
	if vix_spot <= 25:
		return "normal"
	if vix_spot <= 30:
		return "anxious"
	return "panic"


def build_analysis(regime, vix_spot, structure_type):
	"""Build human-readable analysis based on regime classification.

	Args:
		regime: Regime string from classify_regime
		vix_spot: Current VIX spot level
		structure_type: Term structure classification

	Returns:
		dict: Analysis with fear_level, options_market_signal, contrarian_signal
	"""
	analysis_map = {
		"complacent": {
			"fear_level": "low",
			"options_market_signal": "Risk assets favorable, low hedging demand",
			"contrarian_signal": "Extended complacency may precede volatility spike",
		},
		"normal": {
			"fear_level": "moderate",
			"options_market_signal": "Healthy hedging activity, normal risk premium",
			"contrarian_signal": "No extreme signal; trend-following preferred",
		},
		"anxious": {
			"fear_level": "elevated",
			"options_market_signal": "Increased hedging demand, risk-off positioning building",
			"contrarian_signal": "Elevated fear but not extreme; selective dip-buying possible",
		},
		"panic": {
			"fear_level": "extreme",
			"options_market_signal": "Maximum hedging demand, capitulation-level protection buying",
			"contrarian_signal": "Historically strong contrarian buy signal for risk assets",
		},
		"unknown": {
			"fear_level": "unknown",
			"options_market_signal": "Insufficient data for signal generation",
			"contrarian_signal": "No signal available",
		},
	}
	return analysis_map.get(regime, analysis_map["unknown"])


@safe_run
def cmd_analyze(args):
	"""Fetch VIX curve data and produce regime analysis."""
	date_str = getattr(args, "date", None)

	# Fetch VIX spot
	vix_spot = fetch_cboe_quote(VIX_SPOT_SYMBOL)
	if vix_spot is None:
		error_json("Failed to fetch VIX spot price from CBOE")

	# Determine VX symbols for front month rotation
	vx_symbols = get_vx_symbols(date_str)
	expiration_labels = get_expiration_labels(date_str)

	# Fetch VX1 through VX9
	term_structure = {}
	for vx_label in [f"VX{i}" for i in range(1, 10)]:
		cboe_symbol = vx_symbols[vx_label]
		price = fetch_cboe_quote(cboe_symbol)
		if price is not None:
			term_structure[vx_label] = {
				"price": round(price, 2),
				"expiration": expiration_labels[vx_label],
			}

	if not term_structure:
		error_json("Failed to fetch any VX futures quotes from CBOE")

	# Extract prices for calculations
	vx1_price = term_structure.get("VX1", {}).get("price")
	vx2_price = term_structure.get("VX2", {}).get("price")
	vx4_price = term_structure.get("VX4", {}).get("price")

	# Term structure classification
	structure_type = classify_structure(vx1_price, vx2_price)

	# Slope: average monthly change across front 4 months
	slope_per_month = None
	if vx1_price is not None and vx4_price is not None:
		slope_per_month = round((vx4_price - vx1_price) / 3, 2)

	# VIX spot vs VX1 spread
	vix_vs_vx1_spread = None
	if vix_spot is not None and vx1_price is not None:
		vix_vs_vx1_spread = round(vix_spot - vx1_price, 2)

	# Front-month roll yield
	front_month_roll_yield_pct = None
	if vix_spot is not None and vx1_price is not None and vix_spot != 0:
		front_month_roll_yield_pct = round((vx1_price - vix_spot) / vix_spot * 100, 2)

	# Regime classification
	regime = classify_regime(vix_spot, structure_type)

	# Analysis
	analysis = build_analysis(regime, vix_spot, structure_type)

	result = {
		"vix_spot": round(vix_spot, 2) if vix_spot is not None else None,
		"term_structure": term_structure,
		"structure_type": structure_type,
		"slope_per_month": slope_per_month,
		"vix_vs_vx1_spread": vix_vs_vx1_spread,
		"front_month_roll_yield_pct": front_month_roll_yield_pct,
		"regime": regime,
		"analysis": analysis,
	}
	output_json(result)


def main():
	parser = argparse.ArgumentParser(description="VIX futures curve analyzer for market regime detection")
	sub = parser.add_subparsers(dest="command", required=True)

	sp_analyze = sub.add_parser("analyze", help="Analyze current VIX term structure")
	sp_analyze.add_argument(
		"--date",
		type=str,
		default=None,
		help="Date (YYYY-MM-DD) for front month calculation (default: today)",
	)
	sp_analyze.set_defaults(func=cmd_analyze)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
