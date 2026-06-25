#!/usr/bin/env python3
"""Dollar Index (DXY) tracking with z-score analysis.

U.S. Dollar Index (DXY) measures the value of USD against a basket of six major
currencies (EUR, JPY, GBP, CAD, SEK, CHF). DXY is a critical indicator for
forex markets, commodity prices, and emerging market risk assessment.

Data Source:
	- Ticker: DX-Y.NYB (ICE U.S. Dollar Index Futures)
	- Exchange: ICE Futures U.S. (Intercontinental Exchange)
	- Currency Basket Weights:
		* EUR (Euro): 57.6%
		* JPY (Japanese Yen): 13.6%
		* GBP (British Pound): 11.9%
		* CAD (Canadian Dollar): 9.1%
		* SEK (Swedish Krona): 4.2%
		* CHF (Swiss Franc): 3.6%
	- Base Value: 100 (March 1973)
	- Updates: Real-time during forex market hours (24/5)

Args:
	--period (str): Historical data period for analysis (default: 2y)
	--interval (str): Data interval (default: 1d for daily)

Returns:
	dict: {
		"date": str,                      # Latest data date
		"ticker": str,                    # DX-Y.NYB futures ticker
		"name": str,                      # U.S. Dollar Index (DXY)
		"current_value": float,           # Current index value
		"period": str,                    # Analysis period used
		"statistics": {
			"mean": float,                # Mean index value over period
			"std": float,                 # Standard deviation
			"z_score": float,             # Current z-score
			"percentile": float,          # Percentile rank
			"min": float,                 # Minimum value in period
			"max": float                  # Maximum value in period
		},
		"dollar_strength": str,           # Strength interpretation
		"data_points": int,               # Number of observations
		"recent_values": dict             # Last 20 daily values
	}

Example:
	>>> python dxy.py --period 2y --interval 1d
	{
		"date": "2026-02-05",
		"ticker": "DX-Y.NYB",
		"name": "U.S. Dollar Index (DXY)",
		"current_value": 103.25,
		"statistics": {
			"z_score": 0.85,
			"percentile": 78.3
		},
		"dollar_strength": "Normal",
		"data_points": 504
	}

Use Cases:
	- Currency risk assessment for international portfolios
	- Commodity price forecasting (inverse correlation with gold, oil)
	- Emerging market equity timing (strong dollar pressures EM stocks)
	- Forex pair analysis using DXY as USD strength baseline
	- Federal Reserve policy impact analysis on dollar strength

Notes:
	- Z-score thresholds: >2 (Extremely Strong), 1-2 (Strong), -1 to 1 (Normal), -2 to -1 (Weak), <-2 (Extremely Weak)
	- Historical DXY range: 70-165 (1973-2025), typical range 80-120 (2000-2025)
	- Strong dollar (DXY >100): Benefits U.S. importers, pressures exporters and commodities
	- Weak dollar (DXY <95): Boosts U.S. exports, supports commodity prices
	- DXY inversely correlated with gold (~-0.7), crude oil (~-0.5)
	- Fed rate hikes typically strengthen DXY, rate cuts weaken it
	- Euro dominates basket (57.6%), so EUR/USD is primary driver

See Also:
	- bdi.py: Shipping cost indicator (commodity demand proxy)
	- zscore.py: General z-score calculation for any ticker
	- forex.py: Individual currency pair analysis beyond DXY basket
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import yfinance as yf
from utils import output_json, safe_run


@safe_run
def cmd_dxy(args):
	"""Get Dollar Index (DXY) with z-score analysis.

	Tracks U.S. Dollar Index futures (DX-Y.NYB) and calculates statistical
	positioning relative to historical mean. Z-score interpretation provides
	dollar strength assessment for forex and commodity analysis.
	"""
	ticker = yf.Ticker("DX-Y.NYB")
	data = ticker.history(period=args.period, interval=args.interval)

	if data.empty:
		output_json({"error": "No data available for DXY"})
		return

	# Get close prices
	prices = data["Close"]

	# Current value
	current_value = float(prices.iloc[-1])

	# Calculate statistics
	mean_value = float(prices.mean())
	std_value = float(prices.std())
	z_score = (current_value - mean_value) / std_value if std_value > 0 else 0

	# Percentile ranking
	percentile = float(np.percentile(prices, 100 * (prices < current_value).sum() / len(prices)))

	# Min/Max
	min_value = float(prices.min())
	max_value = float(prices.max())

	# Strength interpretation
	if z_score > 2:
		strength = "Extremely Strong"
	elif z_score > 1:
		strength = "Strong"
	elif abs(z_score) <= 1:
		strength = "Normal"
	elif z_score > -2:
		strength = "Weak"
	else:
		strength = "Extremely Weak"

	result = {
		"date": str(prices.index[-1].date()),
		"ticker": "DX-Y.NYB",
		"name": "U.S. Dollar Index (DXY)",
		"current_value": round(current_value, 4),
		"period": args.period,
		"statistics": {
			"mean": round(mean_value, 4),
			"std": round(std_value, 4),
			"z_score": round(z_score, 4),
			"percentile": round(percentile, 2),
			"min": round(min_value, 4),
			"max": round(max_value, 4),
		},
		"dollar_strength": strength,
		"data_points": len(prices),
		"recent_values": {str(idx.date()): round(float(val), 4) for idx, val in prices.tail(20).items()},
	}
	output_json(result)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Dollar Index (DXY) tracking")
	parser.add_argument("--period", default="2y", help="Data period (e.g., 1y, 2y, 5y)")
	parser.add_argument("--interval", default="1d", help="Data interval (e.g., 1d, 1wk, 1mo)")
	args = parser.parse_args()

	cmd_dxy(args)
