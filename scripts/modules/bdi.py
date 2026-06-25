#!/usr/bin/env python3
"""Baltic Dry Index (BDI) tracking via BDRY ETF with z-score analysis.

BDI measures shipping costs for dry bulk commodities (iron ore, coal, grain)
and serves as a leading indicator of global economic activity. Since direct
BDI data is delayed, this script uses BDRY ETF as a real-time proxy.

ETF Proxy Methodology:
	- Direct Source: Baltic Dry Index (BDI) from Baltic Exchange
	- Proxy Instrument: BDRY (Breakwave Dry Bulk Shipping ETF)
	- Tracking: BDRY holds futures contracts on BDI and related shipping indices
	- Correlation: BDRY price movements closely mirror BDI fluctuations
	- Advantages: Real-time data, intraday updates, options chain availability
	- Limitations: ETF management fees, tracking error ~2-5% annually

Args:
	--period (str): Historical data period for analysis (default: 2y)
	--interval (str): Data interval (default: 1d for daily)

Returns:
	dict: {
		"date": str,                      # Latest data date
		"ticker": str,                    # BDRY proxy ticker
		"name": str,                      # Full name
		"proxy_for": str,                 # Indicates BDI proxy
		"current_value": float,           # Current BDRY price
		"period": str,                    # Analysis period used
		"statistics": {
			"mean": float,                # Mean price over period
			"std": float,                 # Standard deviation
			"z_score": float,             # Current z-score
			"percentile": float,          # Percentile rank
			"min": float,                 # Minimum price
			"max": float                  # Maximum price
		},
		"shipping_demand": str,           # Demand interpretation
		"interpretation": str,            # Human-readable summary
		"data_points": int,               # Number of observations
		"recent_values": dict             # Last 20 daily values
	}

Example:
	>>> python bdi.py --period 2y --interval 1d
	{
		"date": "2026-02-05",
		"ticker": "BDRY",
		"proxy_for": "Baltic Dry Index (BDI)",
		"current_value": 18.45,
		"statistics": {
			"z_score": 1.25,
			"percentile": 89.5
		},
		"shipping_demand": "High",
		"interpretation": "Global shipping demand indicator: High"
	}

Use Cases:
	- Global trade activity monitoring for economic forecasting
	- Commodity cycle timing using shipping rate trends
	- China demand proxy (major dry bulk importer)
	- Supply chain bottleneck detection via extreme z-scores
	- Contrarian trading signals when z-score exceeds ±2σ

Notes:
	- BDI is not directly tradable; BDRY ETF enables exposure
	- Z-score thresholds: >2 (Extremely High), 1-2 (High), -1 to 1 (Normal), -2 to -1 (Low), <-2 (Extremely Low)
	- Historical BDI range: 600-11,000 points (2000-2025)
	- BDRY launched in 2018; limited pre-2018 data
	- Dry bulk includes Capesize, Panamax, Supramax vessels
	- Seasonal patterns: Q4 often strong (harvest season shipping)
	- ETF expense ratio: 0.65% annually

See Also:
	- dxy.py: Dollar strength indicator (inverse correlation with commodities)
	- zscore.py: General z-score calculation for any ticker
	- commodities.py: Broader commodity index tracking
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import yfinance as yf
from utils import output_json, safe_run


@safe_run
def cmd_bdi(args):
	"""Get Baltic Dry Index (BDI) via BDRY ETF proxy with z-score analysis.

	BDRY (Breakwave Dry Bulk Shipping ETF) tracks BDI futures and serves as
	a reliable proxy for the Baltic Dry Index. BDI measures shipping costs
	for dry bulk commodities and indicates global trade activity.
	"""
	ticker = yf.Ticker("BDRY")
	data = ticker.history(period=args.period, interval=args.interval)

	if data.empty:
		output_json({"error": "No data available for BDRY"})
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

	# Shipping demand interpretation
	if z_score > 2:
		demand = "Extremely High"
	elif z_score > 1:
		demand = "High"
	elif abs(z_score) <= 1:
		demand = "Normal"
	elif z_score > -2:
		demand = "Low"
	else:
		demand = "Extremely Low"

	result = {
		"date": str(prices.index[-1].date()),
		"ticker": "BDRY",
		"name": "Baltic Dry Index (BDI) via BDRY ETF",
		"proxy_for": "Baltic Dry Index (BDI)",
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
		"shipping_demand": demand,
		"data_points": len(prices),
		"recent_values": {str(idx.date()): round(float(val), 4) for idx, val in prices.tail(20).items()},
	}
	output_json(result)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="Baltic Dry Index (BDI) tracking via BDRY ETF")
	parser.add_argument("--period", default="2y", help="Data period (e.g., 1y, 2y, 5y)")
	parser.add_argument("--interval", default="1d", help="Data interval (e.g., 1d, 1wk, 1mo)")
	args = parser.parse_args()

	cmd_bdi(args)
