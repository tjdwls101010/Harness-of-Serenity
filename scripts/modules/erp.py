#!/usr/bin/env python3
"""Equity Risk Premium (ERP) = Earnings Yield - US10Y for valuation danger detection.

Computes the Equity Risk Premium using the formula: ERP = (1/CAPE) - (US10Y/100).
This measures how much extra return stocks offer over risk-free bonds. When ERP is
negative, stocks offer LESS than bonds -- an extreme danger signal per SidneyKim0's
thresholds.md.

The ERP is a critical valuation metric in SidneyKim0's methodology for detecting
bubble conditions. At CAPE ~40 and US10Y ~4.5%, ERP = 2.5% - 4.5% = -2.0%, meaning
investors are paying MORE for risky equity earnings than they would receive from
risk-free Treasury bonds.

Data sources:
- CAPE: YCharts scraping (primary, same as cape.py) or Shiller cache (fallback)
- US10Y: FRED series DGS10 (10-Year Treasury Constant Maturity Rate)

Args:
	Command: erp

	erp:
		--period (str): Time series length for historical context (default: "25y")
		--refresh (flag): Reserved for future use (cache refresh)

Returns:
	dict: {
		"date": str,                       # Most recent data date
		"current": {
			"cape": float,                 # Current CAPE ratio
			"earnings_yield": float,       # 1/CAPE as percentage
			"us10y": float,                # US 10-Year yield (%)
			"erp": float,                  # ERP = earnings_yield - us10y (percentage points)
			"implied_pe_from_rate": float   # 1/(US10Y/100) = max PE justified by rates
		},
		"signal": {
			"classification": str,         # "extreme_danger" | "danger" | "thin_margin" | "normal" | "opportunity"
			"description": str,
			"stocks_vs_bonds": str         # "stocks cheaper" | "bonds cheaper" | "roughly equal"
		},
		"historical_context": {
			"erp_percentile": float,       # Current ERP percentile vs history
			"erp_z_score": float,          # Z-score vs history
			"erp_mean": float,             # Historical average ERP
			"erp_min": float,              # Historical minimum ERP
			"erp_min_date": str,           # Date of minimum ERP
			"data_points": int             # Number of monthly observations
		},
		"erp_history": {str: float},       # Recent monthly ERP values
		"interpretation": str
	}

Example:
	>>> python erp.py erp
	{
		"date": "2026-01-01",
		"current": {
			"cape": 38.5,
			"earnings_yield": 2.60,
			"us10y": 4.45,
			"erp": -1.85,
			"implied_pe_from_rate": 22.47
		},
		"signal": {
			"classification": "extreme_danger",
			"description": "ERP negative: stocks offer LESS than bonds; only justified during bubble",
			"stocks_vs_bonds": "bonds cheaper"
		},
		"historical_context": {
			"erp_percentile": 3.2,
			"erp_z_score": -2.15,
			"erp_mean": 2.8,
			"erp_min": -2.5,
			"erp_min_date": "2000-03-01",
			"data_points": 300
		}
	}

	>>> python erp.py erp --period 50y
	# Same structure with longer historical context

Use Cases:
	- Detect bubble conditions: negative ERP = stocks priced worse than bonds
	- Monitor valuation danger: ERP declining toward zero = thinning margin of safety
	- Compare current valuation extremes vs dot-com era (when ERP was also negative)
	- Assess rate sensitivity: how much would rates need to fall for ERP to normalize
	- Cross-validate with CAPE percentile for comprehensive valuation assessment

Notes:
	- ERP < 0 = "stocks offer LESS than bonds; extreme danger; only justified during bubble" (thresholds.md)
	- ERP 0-1% = very thin margin; vulnerable to any rate spike
	- ERP 2-3% = normal; stocks modestly compensate for risk
	- ERP 4%+ = cheap; strong buy signal if not recession
	- CAPE data: primary from YCharts scraping (~4 years monthly), fallback to Shiller cache
	- US10Y (DGS10) is daily from FRED, matched to nearest CAPE date
	- Historical depth depends on CAPE source: YCharts ~4y, Shiller cache up to 150y
	- At US10Y 4.4%, implied PE = 22x (without duration); with duration compound = ~8x
	- FRED API key required for US10Y data

See Also:
	- cape_historical.py: Shiller CAPE data fetching and historical analysis
	- cape.py: Current CAPE from YCharts
	- data_advanced/fred/rates.py: Treasury yield data from FRED
	- Personas/Sidneykim0/thresholds.md: ERP interpretation thresholds
"""

import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pandas as pd
from fredapi import Fred
from utils import error_json, output_json, safe_run

YCHARTS_URL = "https://ycharts.com/indicators/cyclically_adjusted_pe_ratio"


def fetch_ycharts_html() -> str:
	"""Fetch HTML from YCharts using curl with browser-like headers."""
	try:
		result = subprocess.run(
			["curl", "-L", "-s", "-A", "Mozilla/5.0", YCHARTS_URL],
			capture_output=True,
			text=True,
			timeout=10,
		)
		if result.returncode != 0:
			raise Exception(f"curl failed: {result.stderr}")
		return result.stdout
	except subprocess.TimeoutExpired:
		raise Exception("Request timeout")
	except Exception as e:
		raise Exception(f"Failed to fetch data: {str(e)}")


def parse_cape_table(html: str) -> list:
	"""Parse CAPE data table from YCharts HTML.

	Returns:
		List of dicts with 'date' and 'cape' keys.
	"""
	pattern = (
		r"(January|February|March|April|May|June|July|August|September|"
		r"October|November|December)\s+(\d{1,2}),\s+(\d{4})\s*</td>\s*"
		r"<td[^>]*>\s*([0-9.]+)"
	)
	matches = re.findall(pattern, html, re.IGNORECASE)
	if not matches:
		raise Exception("No CAPE data found in HTML")

	month_map = {
		"January": "01", "February": "02", "March": "03", "April": "04",
		"May": "05", "June": "06", "July": "07", "August": "08",
		"September": "09", "October": "10", "November": "11", "December": "12",
	}
	results = []
	for month, day, year, value in matches:
		date_str = f"{year}-{month_map[month]}-{day.zfill(2)}"
		results.append({"date": date_str, "cape": float(value)})
	return results

FRED_API_KEY = os.getenv("FRED_API_KEY")


def _fetch_cape_from_ycharts():
	"""Fetch CAPE data from YCharts scraping (primary source).

	Returns:
		pd.DataFrame with 'Date' and 'CAPE' columns, or None on failure.
	"""
	try:
		html = fetch_ycharts_html()
		data = parse_cape_table(html)
		if not data:
			return None
		df = pd.DataFrame(data)
		df["Date"] = pd.to_datetime(df["date"])
		df["CAPE"] = df["cape"].astype(float)
		return df[["Date", "CAPE"]].sort_values("Date").reset_index(drop=True)
	except Exception:
		return None


def _fetch_cape_from_shiller_cache():
	"""Try loading Shiller CAPE from cache only (no network request).

	Returns:
		pd.DataFrame with 'Date' and 'CAPE' columns, or None if no cache.
	"""
	cache_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".cache", "shiller_cape.csv")
	if os.path.exists(cache_file):
		try:
			return pd.read_csv(cache_file, parse_dates=["Date"])
		except Exception:
			return None
	return None


def fetch_cape_data():
	"""Fetch CAPE data: YCharts primary, Shiller cache fallback.

	Returns:
		pd.DataFrame with 'Date' and 'CAPE' columns.
	"""
	# Primary: YCharts scraping (~4 years of monthly data)
	df = _fetch_cape_from_ycharts()
	if df is not None and not df.empty:
		return df

	# Fallback: Shiller cache (if previously downloaded)
	df = _fetch_cape_from_shiller_cache()
	if df is not None and not df.empty:
		return df

	raise ValueError("Failed to fetch CAPE data from both YCharts and Shiller cache")


def get_fred_client():
	"""Get FRED API client."""
	if not FRED_API_KEY:
		raise ValueError("FRED_API_KEY environment variable is required")
	return Fred(api_key=FRED_API_KEY)


def classify_erp(erp_value):
	"""Classify ERP signal based on thresholds.md levels.

	Returns:
		tuple: (classification, description, stocks_vs_bonds)
	"""
	if erp_value < 0:
		return (
			"extreme_danger",
			"ERP negative: stocks offer LESS than bonds; only justified during bubble",
			"bonds cheaper",
		)
	elif erp_value < 1.0:
		return (
			"danger",
			"ERP very thin: vulnerable to any rate spike; minimal equity risk compensation",
			"roughly equal",
		)
	elif erp_value < 2.0:
		return (
			"thin_margin",
			"ERP below average: stocks marginally compensate for risk",
			"stocks slightly cheaper",
		)
	elif erp_value < 4.0:
		return (
			"normal",
			"ERP in normal range: stocks modestly compensate for equity risk",
			"stocks cheaper",
		)
	else:
		return (
			"opportunity",
			"ERP elevated: stocks significantly cheaper than bonds; strong buy if not recession",
			"stocks much cheaper",
		)


@safe_run
def cmd_erp(args):
	"""Compute ERP = (1/CAPE) - (US10Y/100) with historical context."""
	# Fetch CAPE data (YCharts primary, Shiller cache fallback)
	cape_df = fetch_cape_data()
	if cape_df is None or cape_df.empty:
		error_json("Failed to fetch CAPE data from YCharts and Shiller cache")
		return

	# Fetch US10Y from FRED
	fred = get_fred_client()

	# Determine start date based on period
	period_map = {"10y": 10, "25y": 25, "50y": 50, "100y": 100, "max": 150}
	years = period_map.get(args.period, 25)
	start_date = pd.Timestamp.now() - pd.DateOffset(years=years)

	us10y_data = fred.get_series("DGS10", observation_start=start_date.strftime("%Y-%m-%d"))
	if us10y_data is None or us10y_data.empty:
		error_json("Failed to fetch US10Y (DGS10) from FRED")
		return

	# Convert US10Y to monthly (last observation per month) to match CAPE frequency
	us10y_monthly = us10y_data.resample("ME").last().dropna()

	# Prepare CAPE data
	cape_df = cape_df[cape_df["Date"] >= start_date].copy()
	cape_series = cape_df.set_index("Date")["CAPE"]

	# Align dates: for each CAPE month, find closest US10Y
	erp_records = []
	for date, cape_val in cape_series.items():
		if pd.isna(cape_val) or cape_val <= 0:
			continue

		# Find closest US10Y date
		date_ts = pd.Timestamp(date)
		us10y_idx = us10y_monthly.index.get_indexer([date_ts], method="nearest")
		if len(us10y_idx) == 0 or us10y_idx[0] < 0 or us10y_idx[0] >= len(us10y_monthly):
			continue

		us10y_val = float(us10y_monthly.iloc[us10y_idx[0]])
		if pd.isna(us10y_val):
			continue

		earnings_yield = (1.0 / cape_val) * 100  # percentage
		erp = earnings_yield - us10y_val  # percentage points

		erp_records.append(
			{
				"date": date_ts,
				"cape": float(cape_val),
				"earnings_yield": earnings_yield,
				"us10y": us10y_val,
				"erp": erp,
			}
		)

	if not erp_records:
		error_json("No aligned ERP data could be computed")
		return

	erp_df = pd.DataFrame(erp_records).set_index("date").sort_index()

	# Current values
	latest = erp_df.iloc[-1]
	current_erp = float(latest["erp"])
	current_cape = float(latest["cape"])
	current_ey = float(latest["earnings_yield"])
	current_us10y = float(latest["us10y"])
	implied_pe = (1.0 / (current_us10y / 100)) if current_us10y > 0 else None

	# Signal classification
	classification, description, svb = classify_erp(current_erp)

	# Historical context
	erp_series = erp_df["erp"]
	erp_mean = float(erp_series.mean())
	erp_std = float(erp_series.std())
	erp_z = (current_erp - erp_mean) / erp_std if erp_std > 0 else 0.0
	erp_pctl = float((erp_series < current_erp).sum() / len(erp_series) * 100)

	erp_min_idx = erp_series.idxmin()
	erp_min_val = float(erp_series.min())
	erp_min_date = str(erp_min_idx.date()) if hasattr(erp_min_idx, "date") else str(erp_min_idx)

	# Recent ERP history (last 24 months)
	erp_history = {}
	for idx in erp_series.tail(24).index:
		date_str = str(idx.date()) if hasattr(idx, "date") else str(idx)
		erp_history[date_str] = round(float(erp_series.loc[idx]), 4)

	# Interpretation
	if current_erp < 0:
		interp = (
			f"DANGER: ERP is {current_erp:.2f}% -- stocks offer {abs(current_erp):.2f}% LESS than "
			f"risk-free bonds. CAPE at {current_cape:.1f} with US10Y at {current_us10y:.2f}% creates "
			f"negative equity risk premium. This is only historically justified during bubble phases "
			f"(e.g., dot-com 1999-2000)."
		)
	elif current_erp < 1.0:
		interp = (
			f"CAUTION: ERP is only {current_erp:.2f}% -- very thin margin over bonds. "
			f"A {1.0 - current_erp:.1f}% rate increase would make bonds more attractive than stocks."
		)
	else:
		interp = (
			f"ERP at {current_erp:.2f}% is in {classification} range. "
			f"Stocks offer {current_erp:.2f}% premium over {current_us10y:.2f}% Treasury yield."
		)

	result = {
		"date": str(erp_df.index[-1].date()) if hasattr(erp_df.index[-1], "date") else str(erp_df.index[-1]),
		"current": {
			"cape": round(current_cape, 2),
			"earnings_yield": round(current_ey, 4),
			"us10y": round(current_us10y, 2),
			"erp": round(current_erp, 4),
			"implied_pe_from_rate": round(implied_pe, 2) if implied_pe else None,
		},
		"signal": {
			"classification": classification,
			"description": description,
			"stocks_vs_bonds": svb,
		},
		"historical_context": {
			"erp_percentile": round(erp_pctl, 2),
			"erp_z_score": round(erp_z, 4),
			"erp_mean": round(erp_mean, 4),
			"erp_min": round(erp_min_val, 4),
			"erp_min_date": erp_min_date,
			"data_points": len(erp_series),
		},
		"erp_history": erp_history,
		"interpretation": interp,
	}
	output_json(result)


def main():
	parser = argparse.ArgumentParser(description="Equity Risk Premium (ERP) analysis")
	sub = parser.add_subparsers(dest="command", required=True)

	sp = sub.add_parser("erp", help="Compute ERP = (1/CAPE) - US10Y")
	sp.add_argument("--period", default="25y", help="Historical period (10y, 25y, 50y, max)")
	sp.add_argument("--refresh", action="store_true", help="Force refresh cached CAPE data")
	sp.set_defaults(func=cmd_erp)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
