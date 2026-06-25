#!/usr/bin/env python3
"""IV Context Analyzer: Determine if current implied volatility is relatively high or low for options timing.

Retrieves 30-day implied volatility (IV30) and historical volatility (HV30) data from the CBOE
delayed quotes API to calculate IV Rank, a normalized percentile measure of where current IV sits
within its 1-year range. IV Rank is the primary metric for options timing decisions: low IV Rank
signals cheap options ideal for buying LEAPS or debit spreads, while high IV Rank signals expensive
options ideal for selling premium through covered calls or cash-secured puts.

Args:
	symbol (str): Stock or index ticker symbol (e.g., "AAPL", "MSFT", "SPX", "VIX")
	command (str): One of analyze

Returns:
	dict: {
		"symbol": str,               # Ticker symbol (uppercased)
		"current_price": float,      # Current stock/index price
		"iv30": float,               # Current 30-day implied volatility (percentage)
		"iv30_annual_high": float,   # 1-year high of IV30 (percentage)
		"iv30_annual_low": float,    # 1-year low of IV30 (percentage)
		"iv_rank": float,            # IV Rank: (iv30 - low) / (high - low) * 100
		"hv30_annual_high": float,   # 1-year high of 30-day realized volatility (percentage)
		"hv30_annual_low": float,    # 1-year low of 30-day realized volatility (percentage)
		"iv_vs_hv_spread": float,    # iv30 minus midpoint of HV30 range (percentage points)
		"interpretation": str        # cheap | fair | elevated | expensive
	}

Example:
	>>> python iv_context.py analyze AAPL
	{
		"symbol": "AAPL",
		"current_price": 185.50,
		"iv30": 22.5,
		"iv30_annual_high": 45.0,
		"iv30_annual_low": 15.0,
		"iv_rank": 25.0,
		"hv30_annual_high": 38.0,
		"hv30_annual_low": 12.0,
		"iv_vs_hv_spread": -2.5,
		"interpretation": "fair"
	}

	>>> python iv_context.py analyze SPX
	{
		"symbol": "SPX",
		"current_price": 5450.00,
		"iv30": 14.2,
		"iv_rank": 18.5,
		"interpretation": "cheap"
	}

Use Cases:
	- Options timing: Identify when IV is cheap for buying calls, puts, or LEAPS
	- LEAPS entry: IV Rank below 25 signals favorable entry for long-dated options
	- Premium selling: IV Rank above 50 indicates elevated premium for covered calls or CSPs
	- IV vs HV spread: Positive spread means options are overpriced relative to realized moves
	- Earnings positioning: Compare pre-earnings IV Rank to assess if volatility crush is priced in

Notes:
	- IV Rank ranges from 0 to 100; it measures where current IV sits within its annual range
	- IV Rank < 25: "cheap" (favorable for buying options)
	- IV Rank 25-50: "fair" (neutral, no strong edge either way)
	- IV Rank 50-75: "elevated" (consider selling premium)
	- IV Rank > 75: "expensive" (best for premium sellers, worst for option buyers)
	- CBOE data is delayed (typically 15 minutes) and may not reflect real-time IV
	- CBOE returns IV values as percentages (e.g., 22.5 means 22.5%)
	- Index symbols are prefixed with underscore in the CBOE API (SPX -> _SPX)
	- Some tickers may lack IV data if they have no listed options

See Also:
	- data_sources/options.py: Raw options chain data for detailed strike-level analysis
	- analysis/putcall_ratio.py: Sentiment overlay using put/call volume ratios
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import requests

# Support both standalone execution and module imports
try:
	from ..utils import error_json, output_json, safe_run
except ImportError:
	from utils import error_json, output_json, safe_run


# CBOE index symbols require underscore prefix
_INDEX_SYMBOLS = {
	"SPX": "_SPX",
	"VIX": "_VIX",
	"RUT": "_RUT",
	"DJX": "_DJX",
	"NDX": "_NDX",
	"OEX": "_OEX",
	"XSP": "_XSP",
}


def _cboe_symbol(symbol):
	"""Convert a ticker symbol to CBOE API format.

	Index symbols like SPX, VIX need an underscore prefix in the CBOE URL.
	Regular equity symbols are used as-is.
	"""
	upper = symbol.upper().replace("^", "")
	return _INDEX_SYMBOLS.get(upper, upper)


def _fetch_cboe_quote(symbol):
	"""Fetch delayed quote data from the CBOE API.

	Returns the 'data' dict from the CBOE JSON response, which includes
	current_price, iv30, iv30_annual_high, iv30_annual_low, etc.
	"""
	cboe_sym = _cboe_symbol(symbol)
	url = f"https://cdn.cboe.com/api/global/delayed_quotes/quotes/{cboe_sym}.json"

	resp = requests.get(url, timeout=15)
	if resp.status_code != 200:
		error_json(f"CBOE API returned status {resp.status_code} for symbol {symbol.upper()}")

	payload = resp.json()
	data = payload.get("data")
	if not data:
		error_json(f"No quote data returned from CBOE for symbol {symbol.upper()}")

	return data


def _fetch_cboe_iv_history(symbol):
	"""Fetch historical IV data from the CBOE API.

	Returns the 'data' dict containing iv30_annual_high, iv30_annual_low,
	hv30_annual_high, hv30_annual_low, and other volatility fields.
	"""
	cboe_sym = _cboe_symbol(symbol)
	url = f"https://cdn.cboe.com/api/global/delayed_quotes/historical_data/{cboe_sym}.json"

	resp = requests.get(url, timeout=15)
	if resp.status_code != 200:
		return {}

	payload = resp.json()
	return payload.get("data", {})


def _classify_iv(iv_rank):
	"""Classify IV environment based on IV Rank percentile.

	IV Rank < 25: cheap (favorable for buying options/LEAPS)
	IV Rank 25-50: fair (neutral)
	IV Rank 50-75: elevated (consider selling premium)
	IV Rank > 75: expensive (best for premium selling, worst for buying)
	"""
	if iv_rank is None:
		return "unknown"
	if iv_rank < 25:
		return "cheap"
	if iv_rank <= 50:
		return "fair"
	if iv_rank <= 75:
		return "elevated"
	return "expensive"


def _safe_float(value):
	"""Safely convert a value to float, returning None for missing or invalid data."""
	if value is None:
		return None
	try:
		f = float(value)
		if f != f:  # NaN check
			return None
		return f
	except (ValueError, TypeError):
		return None


def _compute_realized_vol(symbol):
	"""Current 30-day realized volatility + typical daily move via yfinance prices.

	hv30_current: annualized stdev of the last ~30 daily log returns (percent).
	typical_daily_move_pct: 1-sigma daily move (percent) — feeds the strike
	move-budget arithmetic (daily move x DTE + buffer) and the overshoot test.
	"""
	try:
		import math
		import statistics
		import yfinance as yf
		hist = yf.Ticker(symbol).history(period="3mo")
		closes = [float(c) for c in hist["Close"].dropna().tolist()]
		if len(closes) < 21:
			return {}
		rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes)) if closes[i - 1] > 0]
		window = rets[-30:] if len(rets) >= 30 else rets
		if len(window) < 5:
			return {}
		daily_std = statistics.pstdev(window)
		return {
			"hv30_current": round(daily_std * math.sqrt(252) * 100, 2),
			"typical_daily_move_pct": round(daily_std * 100, 2),
		}
	except Exception:
		return {}


@safe_run
def cmd_analyze(args):
	"""Analyze IV context for a given symbol using CBOE delayed quote data."""
	symbol = args.symbol.upper()

	# Fetch quote data (current_price, possibly some IV fields)
	quote_data = _fetch_cboe_quote(symbol)

	# Fetch historical IV data (annual high/low for IV and HV)
	iv_history = _fetch_cboe_iv_history(symbol)

	# Extract current price
	current_price = _safe_float(quote_data.get("current_price"))

	# Extract IV30 from quote data; CBOE returns percentages (e.g., 22.5 = 22.5%)
	iv30 = _safe_float(quote_data.get("iv30"))

	# IV annual range: prefer historical_data endpoint, fall back to quote data
	iv30_annual_high = _safe_float(iv_history.get("iv30_annual_high") or quote_data.get("iv30_annual_high"))
	iv30_annual_low = _safe_float(iv_history.get("iv30_annual_low") or quote_data.get("iv30_annual_low"))

	# HV annual range from historical data
	hv30_annual_high = _safe_float(iv_history.get("hv30_annual_high") or quote_data.get("hv30_annual_high"))
	hv30_annual_low = _safe_float(iv_history.get("hv30_annual_low") or quote_data.get("hv30_annual_low"))

	# Calculate IV Rank: (current_iv30 - annual_low) / (annual_high - annual_low) * 100
	iv_rank = None
	if iv30 is not None and iv30_annual_high is not None and iv30_annual_low is not None:
		iv_range = iv30_annual_high - iv30_annual_low
		if iv_range > 0:
			iv_rank = round((iv30 - iv30_annual_low) / iv_range * 100, 2)

	# Calculate IV vs HV spread: iv30 minus midpoint of HV30 range
	iv_vs_hv_spread = None
	if iv30 is not None and hv30_annual_high is not None and hv30_annual_low is not None:
		hv30_midpoint = (hv30_annual_high + hv30_annual_low) / 2
		iv_vs_hv_spread = round(iv30 - hv30_midpoint, 2)

	# 5-tier classification for instrument selection
	iv_percentile = iv_rank  # iv_rank is the IV percentile (0-100)
	iv_tier = "unknown"
	if isinstance(iv_percentile, (int, float)):
		if iv_percentile < 30:
			iv_tier = "compressed"
		elif iv_percentile < 45:
			iv_tier = "normal_low"
		elif iv_percentile < 65:
			iv_tier = "normal"
		elif iv_percentile < 100:
			iv_tier = "elevated"
		else:
			iv_tier = "extreme"

	# Regime shift: IV30 vs HV30 divergence > 15pp suggests structural shift
	iv_regime_shift = False
	hv30_mid = None
	if hv30_annual_high is not None and hv30_annual_low is not None:
		hv30_mid = (hv30_annual_high + hv30_annual_low) / 2
	if isinstance(iv30, (int, float)) and isinstance(hv30_mid, (int, float)) and hv30_mid > 0:
		if abs(iv30 - hv30_mid) > 15:
			iv_regime_shift = True

	# Realized vol (current HV30) + typical daily move + IV/RV ratio for strike math
	rv = _compute_realized_vol(symbol)
	hv30_current = rv.get("hv30_current")
	typical_daily_move_pct = rv.get("typical_daily_move_pct")
	iv_rv_ratio = round(iv30 / hv30_current, 2) if isinstance(iv30, (int, float)) and isinstance(hv30_current, (int, float)) and hv30_current > 0 else None
	result = {
		"symbol": symbol,
		"current_price": round(current_price, 2) if current_price is not None else None,
		"iv30": round(iv30, 2) if iv30 is not None else None,
		"iv30_annual_high": round(iv30_annual_high, 2) if iv30_annual_high is not None else None,
		"iv30_annual_low": round(iv30_annual_low, 2) if iv30_annual_low is not None else None,
		"iv_rank": iv_rank,
		"hv30_annual_high": round(hv30_annual_high, 2) if hv30_annual_high is not None else None,
		"hv30_annual_low": round(hv30_annual_low, 2) if hv30_annual_low is not None else None,
		"iv_vs_hv_spread": iv_vs_hv_spread,
		"interpretation": _classify_iv(iv_rank),
		"iv_tier": iv_tier,
		"iv_regime_shift": iv_regime_shift,
		"hv30_current": hv30_current,
		"typical_daily_move_pct": typical_daily_move_pct,
		"iv_rv_ratio": iv_rv_ratio,
		"iv_tier_thresholds": {
			"compressed": "<30",
			"normal_low": "30-45",
			"normal": "45-65",
			"elevated": "65-100",
			"extreme": ">100",
			"regime_shift": "|IV30-HV30| > 15",
			"iv_rv_ratio": ">1 = IV rich vs realized (favor selling premium); <1 = cheap (favor buying options)",
		},
	}

	output_json(result)


def main():
	parser = argparse.ArgumentParser(description="IV Context Analyzer - Implied volatility ranking for options timing")
	sub = parser.add_subparsers(dest="command", required=True)

	sp_analyze = sub.add_parser("analyze")
	sp_analyze.add_argument("symbol", help="Stock or index ticker symbol (e.g., AAPL, SPX, VIX)")
	sp_analyze.set_defaults(func=cmd_analyze)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
