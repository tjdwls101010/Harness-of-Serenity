#!/usr/bin/env python3
"""Federal Reserve Economic Data (FRED) interest rate and yield curve data access.

Provides access to FRED's comprehensive interest rate datasets including Federal Funds Rate,
Treasury yields, SOFR, TIPS, mortgage rates, and international bond yields. Data includes
both current values and historical time series with metadata for analysis.

Args:
	series_id (str): FRED series identifier (e.g., "DFF" for Fed Funds, "DGS10" for 10Y Treasury)
	--start-date (str): Start date for time series in YYYY-MM-DD format (optional)
	--end-date (str): End date for time series in YYYY-MM-DD format (optional)
	--limit (int): Maximum number of observations to return, most recent first (optional)
	--series-type (str): Category filter for specific rate series (e.g., "effective_rate", "all")
	--maturities (str): Comma-separated maturity terms for yield curve (e.g., "2y,10y,30y")

Returns:
	dict: {
		"data": {
			"SERIES_ID": {
				"YYYY-MM-DD": float,  # Date-keyed observations
				...
			},
			...
		},
		"metadata": {
			"SERIES_ID": {
				"title": str,                    # Full series description
				"units": str,                    # Rate measurement unit (Percent, Basis Points)
				"frequency": str,                # Daily, Weekly, Monthly, Quarterly
				"seasonal_adjustment": str,      # Adjustment type (NSA, SA)
				"last_updated": str              # Last FRED database update timestamp
			},
			...
		}
	}

Example:
	>>> python rates.py fed-funds --series-type effective_rate --limit 5
	{
		"data": {
			"DFF": {
				"2026-02-05": 4.33,
				"2026-02-04": 4.33,
				"2026-02-03": 4.33
			}
		},
		"metadata": {
			"DFF": {
				"title": "Federal Funds Effective Rate",
				"units": "Percent",
				"frequency": "Daily",
				"seasonal_adjustment": "Not Seasonally Adjusted",
				"last_updated": "2026-02-05 07:31:03-06:00"
			}
		}
	}

	>>> python rates.py yield-curve --maturities 2y,10y --limit 30
	>>> python rates.py sofr --series-type avg_30d
	>>> python rates.py tips --maturity 10y
	>>> python rates.py mortgage --rate-type 30y_fixed
	>>> python rates.py yield-spread --country1 us --maturity1 10y --country2 korea --maturity2 10y

Use Cases:
	- Monitor Federal Reserve policy rate changes and forward guidance signals
	- Analyze yield curve shape for recession indicators (2y-10y inversion)
	- Track SOFR transition from LIBOR for derivative pricing
	- Calculate real yields using TIPS for inflation-adjusted returns
	- Compare international sovereign bond spreads for capital flow analysis
	- Build term structure models using complete Treasury yield curve
	- Monitor mortgage rate trends for housing market forecasts

Notes:
	- FRED API key required: Set FRED_API_KEY in .env file (https://fred.stlouisfed.org/docs/api/api_key.html)
	- Rate limits: 120 requests per minute per API key
	- Data delays: Daily series update at 4:30 PM CT, weekly/monthly series update on publication schedule
	- Seasonal adjustment: NSA (Not Seasonally Adjusted) for rates, SA (Seasonally Adjusted) for economic indicators
	- Yield curve maturities: 1m, 3m, 6m, 1y, 2y, 3y, 5y, 7y, 10y, 20y, 30y available
	- International data: Limited coverage (Korea 10Y and 3M available, expand via custom series_id)
	- TIPS interpretation: Real yields = Nominal - Breakeven Inflation Expectations
	- Fed Funds: Effective rate (DFF) reflects actual market rates, Target (DFEDTARU/DFEDTARL) shows policy bounds

See Also:
	- fred/inflation.py: Breakeven inflation rates for real yield calculation
	- fred/policy.py: Fed balance sheet and policy uncertainty indicators
	- fed/fedwatch.py: Market-implied FOMC rate change probabilities
	- macro/interest_rate_models.py: Term structure and yield curve modeling
"""

import argparse
import os
import sys

# Adjust path for utils module access
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from fredapi import Fred
from utils import output_json, safe_run

FRED_API_KEY = os.getenv("FRED_API_KEY")


def get_fred_client():
	"""Get FRED API client with API key."""
	if not FRED_API_KEY:
		raise ValueError("FRED_API_KEY environment variable is required")
	return Fred(api_key=FRED_API_KEY)


def fetch_series(series_ids, start_date=None, end_date=None, limit=None):
	"""Fetch multiple FRED series and return combined data with metadata."""
	fred = get_fred_client()

	if isinstance(series_ids, str):
		series_ids = [series_ids]

	results = {}
	metadata = {}

	for series_id in series_ids:
		try:
			# Get series data
			data = fred.get_series(series_id, observation_start=start_date, observation_end=end_date)

			# Apply limit if specified
			if limit and len(data) > limit:
				data = data.tail(limit)

			# Convert to dict with date strings as keys
			results[series_id] = {str(idx.date()): float(val) if val == val else None for idx, val in data.items()}

			# Get series info for metadata
			info = fred.get_series_info(series_id)
			metadata[series_id] = {
				"title": info.get("title", ""),
				"units": info.get("units", ""),
				"frequency": info.get("frequency", ""),
				"seasonal_adjustment": info.get("seasonal_adjustment", ""),
				"last_updated": str(info.get("last_updated", "")),
			}
		except Exception as e:
			results[series_id] = {"error": str(e)}
			metadata[series_id] = {"error": str(e)}

	return {"data": results, "metadata": metadata}


# FRED Series IDs for rates
FED_FUNDS_SERIES = {
	"effective_rate": "DFF",
	"target_upper": "DFEDTARU",
	"target_lower": "DFEDTARL",
	"monthly_avg": "FEDFUNDS",
}

YIELD_CURVE_SERIES = {
	"1m": "DGS1MO",
	"3m": "DGS3MO",
	"6m": "DGS6MO",
	"1y": "DGS1",
	"2y": "DGS2",
	"3y": "DGS3",
	"5y": "DGS5",
	"7y": "DGS7",
	"10y": "DGS10",
	"20y": "DGS20",
	"30y": "DGS30",
}

SOFR_SERIES = {
	"rate": "SOFR",
	"avg_30d": "SOFR30DAYAVG",
	"avg_90d": "SOFR90DAYAVG",
	"avg_180d": "SOFR180DAYAVG",
	"index": "SOFRINDEX",
}

TIPS_SERIES = {
	"5y": "DFII5",
	"7y": "DFII7",
	"10y": "DFII10",
	"20y": "DFII20",
	"30y": "DFII30",
}

MORTGAGE_SERIES = {
	"30y_fixed": "MORTGAGE30US",
	"15y_fixed": "MORTGAGE15US",
	"5y_arm": "MORTGAGE5US",
}

INTERNATIONAL_YIELD_SERIES = {
	"korea_10y": "IRLTLT01KRM156N",  # Korea 10Y Government Bond Yield (Monthly)
	"korea_3m": "IR3TIB01KRM156N",  # Korea 3M Interbank Rate (Monthly)
}


@safe_run
def cmd_fed_funds(args):
	"""Get Federal Funds Rate data."""
	series_to_fetch = []

	if args.series_type == "all":
		series_to_fetch = list(FED_FUNDS_SERIES.values())
	elif args.series_type in FED_FUNDS_SERIES:
		series_to_fetch = [FED_FUNDS_SERIES[args.series_type]]
	else:
		series_to_fetch = [FED_FUNDS_SERIES["effective_rate"]]

	result = fetch_series(series_to_fetch, start_date=args.start_date, end_date=args.end_date, limit=args.limit)
	output_json(result)


@safe_run
def cmd_yield_curve(args):
	"""Get Treasury Yield Curve data."""
	if args.maturities:
		maturities = [m.strip() for m in args.maturities.split(",")]
		series_to_fetch = [YIELD_CURVE_SERIES[m] for m in maturities if m in YIELD_CURVE_SERIES]
	else:
		series_to_fetch = list(YIELD_CURVE_SERIES.values())

	result = fetch_series(series_to_fetch, start_date=args.start_date, end_date=args.end_date, limit=args.limit)
	output_json(result)


@safe_run
def cmd_sofr(args):
	"""Get SOFR (Secured Overnight Financing Rate) data."""
	series_to_fetch = []

	if args.series_type == "all":
		series_to_fetch = list(SOFR_SERIES.values())
	elif args.series_type in SOFR_SERIES:
		series_to_fetch = [SOFR_SERIES[args.series_type]]
	else:
		series_to_fetch = [SOFR_SERIES["rate"]]

	result = fetch_series(series_to_fetch, start_date=args.start_date, end_date=args.end_date, limit=args.limit)
	output_json(result)


@safe_run
def cmd_tips(args):
	"""Get TIPS (Treasury Inflation-Protected Securities) Yields."""
	series_to_fetch = []

	if args.maturity == "all":
		series_to_fetch = list(TIPS_SERIES.values())
	elif args.maturity in TIPS_SERIES:
		series_to_fetch = [TIPS_SERIES[args.maturity]]
	else:
		series_to_fetch = [TIPS_SERIES["10y"]]

	result = fetch_series(series_to_fetch, start_date=args.start_date, end_date=args.end_date, limit=args.limit)
	output_json(result)


@safe_run
def cmd_mortgage(args):
	"""Get Mortgage Rates data."""
	series_to_fetch = []

	if args.rate_type == "all":
		series_to_fetch = list(MORTGAGE_SERIES.values())
	elif args.rate_type in MORTGAGE_SERIES:
		series_to_fetch = [MORTGAGE_SERIES[args.rate_type]]
	else:
		series_to_fetch = [MORTGAGE_SERIES["30y_fixed"], MORTGAGE_SERIES["15y_fixed"]]

	result = fetch_series(series_to_fetch, start_date=args.start_date, end_date=args.end_date, limit=args.limit)
	output_json(result)


@safe_run
def cmd_international_yield(args):
	"""Get International Government Bond Yields."""
	series_to_fetch = []

	if args.country == "korea":
		if args.maturity == "all":
			series_to_fetch = list(INTERNATIONAL_YIELD_SERIES.values())
		elif args.maturity == "10y":
			series_to_fetch = [INTERNATIONAL_YIELD_SERIES["korea_10y"]]
		elif args.maturity == "3m":
			series_to_fetch = [INTERNATIONAL_YIELD_SERIES["korea_3m"]]
		else:
			series_to_fetch = [INTERNATIONAL_YIELD_SERIES["korea_10y"]]
	else:
		series_to_fetch = [INTERNATIONAL_YIELD_SERIES["korea_10y"]]

	result = fetch_series(series_to_fetch, start_date=args.start_date, end_date=args.end_date, limit=args.limit)
	output_json(result)


@safe_run
def cmd_yield_spread(args):
	"""Calculate yield spread between two countries/maturities."""
	import numpy as np

	fred = get_fred_client()

	# Map country-maturity combinations to FRED series
	series_map = {
		"us_10y": "DGS10",
		"us_2y": "DGS2",
		"korea_10y": "IRLTLT01KRM156N",
		"korea_3m": "IR3TIB01KRM156N",
	}

	# Parse series keys
	series1_key = f"{args.country1}_{args.maturity1}"
	series2_key = f"{args.country2}_{args.maturity2}"

	if series1_key not in series_map or series2_key not in series_map:
		output_json({"error": f"Invalid country-maturity combination: {series1_key} or {series2_key}"})
		return

	# Fetch both series
	data1 = fred.get_series(series_map[series1_key], observation_start=args.start_date, observation_end=args.end_date)
	data2 = fred.get_series(series_map[series2_key], observation_start=args.start_date, observation_end=args.end_date)

	# Align dates
	common_idx = data1.index.intersection(data2.index)
	if len(common_idx) == 0:
		output_json({"error": "No overlapping dates between series"})
		return

	data1_aligned = data1.loc[common_idx]
	data2_aligned = data2.loc[common_idx]

	# Calculate spread
	spread = data1_aligned - data2_aligned

	# Apply limit if specified
	if args.limit and len(spread) > args.limit:
		spread = spread.tail(args.limit)
		data1_aligned = data1_aligned.tail(args.limit)
		data2_aligned = data2_aligned.tail(args.limit)

	# Statistics
	current_spread = float(spread.iloc[-1])
	mean_spread = float(spread.mean())
	std_spread = float(spread.std())
	z_score = (current_spread - mean_spread) / std_spread if std_spread > 0 else 0

	# Percentile ranking
	percentile = float(np.percentile(spread, 100 * (spread < current_spread).sum() / len(spread)))

	result = {
		"date": str(spread.index[-1].date()),
		"series1": {
			"name": series1_key,
			"fred_id": series_map[series1_key],
			"current_value": float(data1_aligned.iloc[-1]),
		},
		"series2": {
			"name": series2_key,
			"fred_id": series_map[series2_key],
			"current_value": float(data2_aligned.iloc[-1]),
		},
		"spread": {
			"current": round(current_spread, 4),
			"mean": round(mean_spread, 4),
			"std": round(std_spread, 4),
			"z_score": round(z_score, 4),
			"percentile": round(percentile, 2),
			"interpretation": "Extremely Wide"
			if z_score > 2
			else "Wide"
			if z_score > 1
			else "Normal"
			if abs(z_score) <= 1
			else "Narrow"
			if z_score > -2
			else "Extremely Narrow",
		},
		"data_points": len(spread),
		"recent_spread": {str(idx.date()): round(float(val), 4) for idx, val in spread.tail(20).items()},
	}
	output_json(result)


def main():
	"""Main CLI entry point."""
	parser = argparse.ArgumentParser(description="FRED Interest Rate Data Commands")
	sub = parser.add_subparsers(dest="command", required=True)

	# fed-funds
	sp = sub.add_parser("fed-funds", help="Get Federal Funds Rate data")
	sp.add_argument(
		"--series-type",
		default="effective_rate",
		choices=["effective_rate", "target_upper", "target_lower", "monthly_avg", "all"],
	)
	sp.add_argument("--start-date", default=None, help="Start date (YYYY-MM-DD)")
	sp.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD)")
	sp.add_argument("--limit", type=int, default=None, help="Limit number of observations")
	sp.set_defaults(func=cmd_fed_funds)

	# yield-curve
	sp = sub.add_parser("yield-curve", help="Get Treasury Yield Curve data")
	sp.add_argument("--maturities", default=None, help="Comma-separated maturities (e.g., 2y,10y,30y)")
	sp.add_argument("--start-date", default=None, help="Start date (YYYY-MM-DD)")
	sp.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD)")
	sp.add_argument("--limit", type=int, default=None, help="Limit number of observations")
	sp.set_defaults(func=cmd_yield_curve)

	# sofr
	sp = sub.add_parser("sofr", help="Get SOFR (Secured Overnight Financing Rate) data")
	sp.add_argument("--series-type", default="rate", choices=["rate", "avg_30d", "avg_90d", "avg_180d", "index", "all"])
	sp.add_argument("--start-date", default=None, help="Start date (YYYY-MM-DD)")
	sp.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD)")
	sp.add_argument("--limit", type=int, default=None, help="Limit number of observations")
	sp.set_defaults(func=cmd_sofr)

	# tips
	sp = sub.add_parser("tips", help="Get TIPS (Treasury Inflation-Protected Securities) Yields")
	sp.add_argument("--maturity", default="10y", choices=["5y", "7y", "10y", "20y", "30y", "all"])
	sp.add_argument("--start-date", default=None, help="Start date (YYYY-MM-DD)")
	sp.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD)")
	sp.add_argument("--limit", type=int, default=None, help="Limit number of observations")
	sp.set_defaults(func=cmd_tips)

	# mortgage
	sp = sub.add_parser("mortgage", help="Get Mortgage Rates data")
	sp.add_argument("--rate-type", default="30y_fixed", choices=["30y_fixed", "15y_fixed", "5y_arm", "all"])
	sp.add_argument("--start-date", default=None, help="Start date (YYYY-MM-DD)")
	sp.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD)")
	sp.add_argument("--limit", type=int, default=None, help="Limit number of observations")
	sp.set_defaults(func=cmd_mortgage)

	# international-yield
	sp = sub.add_parser("international-yield", help="Get International Government Bond Yields")
	sp.add_argument("--country", default="korea", choices=["korea"], help="Country")
	sp.add_argument("--maturity", default="10y", choices=["10y", "3m", "all"], help="Maturity")
	sp.add_argument("--start-date", default=None, help="Start date (YYYY-MM-DD)")
	sp.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD)")
	sp.add_argument("--limit", type=int, default=None, help="Limit number of observations")
	sp.set_defaults(func=cmd_international_yield)

	# yield-spread
	sp = sub.add_parser("yield-spread", help="Calculate yield spread between two countries/maturities")
	sp.add_argument("--country1", default="us", choices=["us", "korea"], help="First country")
	sp.add_argument("--maturity1", default="10y", choices=["10y", "2y", "3m"], help="First maturity")
	sp.add_argument("--country2", default="korea", choices=["us", "korea"], help="Second country")
	sp.add_argument("--maturity2", default="10y", choices=["10y", "2y", "3m"], help="Second maturity")
	sp.add_argument("--start-date", default=None, help="Start date (YYYY-MM-DD)")
	sp.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD)")
	sp.add_argument("--limit", type=int, default=None, help="Limit number of observations")
	sp.set_defaults(func=cmd_yield_spread)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
