#!/usr/bin/env python3
"""Fed Net Liquidity composite (Balance Sheet - TGA - RRP) for systemic liquidity tracking.

Computes the Federal Reserve's net liquidity injection into the financial system using
the formula: Net Liquidity = WALCL (Fed Total Assets) - WTREGEN (TGA) - RRPONTSYD (RRP).
Optionally includes WRESBAL (Reserve Balances) as a variant metric.

This implements SidneyKim0's methodology Step 1.5 "Liquidity Plumbing" analysis:
"TGA + RRP + Reserve Balances = Net Liquidity. When net liquidity declines while equity
multiples are elevated, the market is on life support (산소호흡기)."

The script fetches all components from FRED, aligns dates (components have different
release schedules: WALCL weekly Wednesday, WTREGEN weekly, RRPONTSYD daily), and
computes aggregate trajectory with regime classification.

Args:
	Command: net-liquidity

	net-liquidity:
		--include-reserves (flag): Include WRESBAL (Reserve Balances) in calculation
		--lookback (int): Window for Z-score and percentile calculation (default: 252)
		--limit (int): Number of observations to return in history (default: 52)

Returns:
	dict: {
		"date": str,                       # Most recent data date
		"formula": str,                    # Formula description
		"components": {
			"fed_assets": {
				"series_id": "WALCL",
				"value": float,            # Current level (millions USD)
				"change_4w": float,        # 4-week change
				"change_13w": float        # 13-week change
			},
			"tga": {
				"series_id": "WTREGEN",
				"value": float,
				"change_4w": float,
				"change_13w": float
			},
			"rrp": {
				"series_id": "RRPONTSYD",
				"value": float,
				"change_4w": float,
				"change_13w": float
			},
			"reserves": {                  # Only if --include-reserves
				"series_id": "WRESBAL",
				"value": float,
				"change_4w": float,
				"change_13w": float
			}
		},
		"net_liquidity": {
			"current": float,              # Net liquidity level (millions USD)
			"change_4w": float,            # 4-week change
			"change_13w": float,           # 13-week change
			"change_52w": float,           # 52-week change
			"z_score": float,              # Z-score vs lookback history
			"percentile": float,           # Percentile rank
			"direction": str               # "expanding" | "contracting" | "stable"
		},
		"regime": {
			"classification": str,         # "double_tightening" | "mixed" | "liquidity_injection" | "neutral"
			"description": str,
			"tga_direction": str,          # "refilling" | "draining" | "stable"
			"qt_status": str               # "active" | "paused" | "easing"
		},
		"history": {str: float},           # Date-keyed net liquidity history
		"interpretation": str
	}

Example:
	>>> python net_liquidity.py net-liquidity
	{
		"date": "2026-02-05",
		"formula": "WALCL - WTREGEN - RRPONTSYD",
		"components": {
			"fed_assets": {"series_id": "WALCL", "value": 6720000.0, "change_4w": -25000.0, "change_13w": -75000.0},
			"tga": {"series_id": "WTREGEN", "value": 750000.0, "change_4w": 50000.0, "change_13w": 120000.0},
			"rrp": {"series_id": "RRPONTSYD", "value": 150000.0, "change_4w": -30000.0, "change_13w": -200000.0}
		},
		"net_liquidity": {
			"current": 5820000.0,
			"change_4w": -45000.0,
			"change_13w": 5000.0,
			"z_score": -0.85,
			"percentile": 32.5,
			"direction": "contracting"
		},
		"regime": {
			"classification": "double_tightening",
			"description": "TGA refilling + QT active = double liquidity drain",
			"tga_direction": "refilling",
			"qt_status": "active"
		},
		"interpretation": "Net liquidity contracting: Fed QT reducing assets while TGA refill drains reserves"
	}

	>>> python net_liquidity.py net-liquidity --include-reserves
	# Same structure with additional "reserves" component

Use Cases:
	- Detect "life support" conditions: declining net liquidity + elevated equity multiples
	- Monitor double tightening: TGA refill + QT simultaneously draining liquidity
	- Identify liquidity injection phases: TGA drawdown + QT pause
	- Track aggregate liquidity trajectory vs S&P 500 for divergence
	- Assess Fed pivot probability: net liquidity below critical threshold forces action

Notes:
	- FRED API key required in .env file
	- Data frequency: WALCL (weekly Wednesday), WTREGEN (weekly), RRPONTSYD (daily)
	- Date alignment uses forward-fill to handle different release schedules
	- Net liquidity is in millions of USD (same unit as FRED series)
	- Z-score uses 252-day (1 year) lookback by default for regime detection
	- TGA refill after debt ceiling events creates predictable liquidity drains
	- RRP near zero means QT directly impacts bank reserves (thresholds.md)
	- Reserve Balances below $3.0T = stress zone (thresholds.md)

See Also:
	- data_advanced/fred/policy.py: Individual FRED policy indicators (WALCL, TGA, RRP)
	- macro/macro.py: Multi-factor macro models for fair value analysis
	- Personas/Sidneykim0/thresholds.md: TGA, RRP, and Reserve Balance threshold levels
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import numpy as np
import pandas as pd
from fredapi import Fred
from utils import error_json, output_json, safe_run

FRED_API_KEY = os.getenv("FRED_API_KEY")

# FRED Series IDs for net liquidity components
SERIES_IDS = {
	"fed_assets": "WALCL",  # Fed Total Assets (weekly, Wednesday)
	"tga": "WTREGEN",  # Treasury General Account (weekly)
	"rrp": "RRPONTSYD",  # Reverse Repo Operations (daily)
	"reserves": "WRESBAL",  # Reserve Balances (weekly)
}


def get_fred_client():
	"""Get FRED API client."""
	if not FRED_API_KEY:
		raise ValueError("FRED_API_KEY environment variable is required")
	return Fred(api_key=FRED_API_KEY)


def fetch_and_align_series(fred, series_ids, lookback_years=3):
	"""Fetch multiple FRED series and align on common dates using forward-fill.

	Args:
		fred: FRED API client
		series_ids: Dict of {name: series_id}
		lookback_years: Years of history to fetch

	Returns:
		pd.DataFrame: Aligned data with forward-filled values
	"""
	start_date = pd.Timestamp.now() - pd.DateOffset(years=lookback_years)
	frames = {}

	for name, sid in series_ids.items():
		try:
			data = fred.get_series(sid, observation_start=start_date.strftime("%Y-%m-%d"))
			if data is not None and not data.empty:
				frames[name] = data
		except Exception:
			continue

	if not frames:
		return pd.DataFrame()

	# Combine into DataFrame and forward-fill
	df = pd.DataFrame(frames)
	df = df.sort_index()
	df = df.ffill()
	df = df.dropna()

	return df


def compute_change(series, periods):
	"""Compute change over N periods."""
	if len(series) > periods:
		return float(series.iloc[-1] - series.iloc[-1 - periods])
	return None


def classify_regime(fed_change_13w, tga_change_13w, rrp_change_13w):
	"""Classify liquidity regime based on component trajectories.

	Returns:
		tuple: (classification, description, tga_direction, qt_status)
	"""
	# TGA direction
	if tga_change_13w is not None and tga_change_13w > 50000:
		tga_dir = "refilling"
	elif tga_change_13w is not None and tga_change_13w < -50000:
		tga_dir = "draining"
	else:
		tga_dir = "stable"

	# QT status (Fed assets declining = active QT)
	if fed_change_13w is not None and fed_change_13w < -20000:
		qt_status = "active"
	elif fed_change_13w is not None and fed_change_13w > 20000:
		qt_status = "easing"
	else:
		qt_status = "paused"

	# Regime classification
	if tga_dir == "refilling" and qt_status == "active":
		classification = "double_tightening"
		description = "TGA refilling + QT active = double liquidity drain"
	elif tga_dir == "draining" and qt_status in ("paused", "easing"):
		classification = "liquidity_injection"
		description = "TGA drawdown + QT pause/ease = liquidity injection"
	elif tga_dir == "refilling" and qt_status in ("paused", "easing"):
		classification = "mixed"
		description = "TGA drain offset by QT pause = mixed signals"
	elif tga_dir == "draining" and qt_status == "active":
		classification = "mixed"
		description = "TGA injection partially offset by QT = mixed signals"
	else:
		classification = "neutral"
		description = "No strong liquidity directional bias"

	return classification, description, tga_dir, qt_status


@safe_run
def cmd_net_liquidity(args):
	"""Compute Fed Net Liquidity = WALCL - WTREGEN - RRPONTSYD."""
	fred = get_fred_client()

	# Determine which series to fetch
	series_to_fetch = {k: v for k, v in SERIES_IDS.items() if k != "reserves"}
	if args.include_reserves:
		series_to_fetch["reserves"] = SERIES_IDS["reserves"]

	# Fetch and align
	df = fetch_and_align_series(fred, series_to_fetch, lookback_years=3)
	if df.empty or "fed_assets" not in df.columns:
		error_json("Failed to fetch FRED data. Check FRED_API_KEY and network connection.")
		return

	required = ["fed_assets", "tga", "rrp"]
	missing = [c for c in required if c not in df.columns]
	if missing:
		error_json(f"Missing FRED series: {missing}")
		return

	# Compute net liquidity
	df["net_liquidity"] = df["fed_assets"] - df["tga"] - df["rrp"]

	# Component summaries
	components = {}
	for name in series_to_fetch:
		if name in df.columns:
			components[name] = {
				"series_id": series_to_fetch[name],
				"value": round(float(df[name].iloc[-1]), 2),
				"change_4w": round(compute_change(df[name], 4), 2) if compute_change(df[name], 4) is not None else None,
				"change_13w": round(compute_change(df[name], 13), 2)
				if compute_change(df[name], 13) is not None
				else None,
			}

	# Net liquidity statistics
	net_liq = df["net_liquidity"]
	current = float(net_liq.iloc[-1])
	change_4w = compute_change(net_liq, 4)
	change_13w = compute_change(net_liq, 13)
	change_52w = compute_change(net_liq, 52)

	# Z-score and percentile
	lookback = min(args.lookback, len(net_liq) - 1)
	window_data = net_liq.tail(lookback)
	nl_mean = float(window_data.mean())
	nl_std = float(window_data.std())
	z_score = (current - nl_mean) / nl_std if nl_std > 0 else 0.0
	percentile = float((window_data < current).sum() / len(window_data) * 100)

	# Direction
	if change_4w is not None:
		if change_4w > 20000:
			direction = "expanding"
		elif change_4w < -20000:
			direction = "contracting"
		else:
			direction = "stable"
	else:
		direction = "unknown"

	# Regime classification
	fed_change_13w = compute_change(df["fed_assets"], 13)
	tga_change_13w = compute_change(df["tga"], 13)
	rrp_change_13w = compute_change(df["rrp"], 13)
	classification, description, tga_dir, qt_status = classify_regime(fed_change_13w, tga_change_13w, rrp_change_13w)

	# History (last N observations)
	limit = min(args.limit, len(net_liq))
	history = {}
	for idx in net_liq.tail(limit).index:
		date_str = str(idx.date()) if hasattr(idx, "date") else str(idx)
		history[date_str] = round(float(net_liq.loc[idx]), 2)

	# Interpretation
	interp_parts = []
	if direction == "contracting":
		interp_parts.append("Net liquidity contracting")
	elif direction == "expanding":
		interp_parts.append("Net liquidity expanding")
	else:
		interp_parts.append("Net liquidity stable")

	if classification == "double_tightening":
		interp_parts.append("Fed QT reducing assets while TGA refill drains reserves")
	elif classification == "liquidity_injection":
		interp_parts.append("TGA drawdown injecting liquidity into system")

	formula = "WALCL - WTREGEN - RRPONTSYD"
	if args.include_reserves:
		formula += " (+ WRESBAL variant)"

	result = {
		"date": str(df.index[-1].date()) if hasattr(df.index[-1], "date") else str(df.index[-1]),
		"formula": formula,
		"components": components,
		"net_liquidity": {
			"current": round(current, 2),
			"change_4w": round(change_4w, 2) if change_4w is not None else None,
			"change_13w": round(change_13w, 2) if change_13w is not None else None,
			"change_52w": round(change_52w, 2) if change_52w is not None else None,
			"z_score": round(z_score, 4),
			"percentile": round(percentile, 2),
			"direction": direction,
		},
		"regime": {
			"classification": classification,
			"description": description,
			"tga_direction": tga_dir,
			"qt_status": qt_status,
		},
		"history": history,
		"interpretation": ": ".join(interp_parts),
	}
	output_json(result)


def main():
	parser = argparse.ArgumentParser(description="Fed Net Liquidity composite analysis")
	sub = parser.add_subparsers(dest="command", required=True)

	sp = sub.add_parser("net-liquidity", help="Compute Net Liquidity = WALCL - TGA - RRP")
	sp.add_argument("--include-reserves", action="store_true", help="Include Reserve Balances (WRESBAL)")
	sp.add_argument("--lookback", type=int, default=252, help="Z-score lookback window (default: 252)")
	sp.add_argument("--limit", type=int, default=52, help="Number of history observations (default: 52)")
	sp.set_defaults(func=cmd_net_liquidity)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
