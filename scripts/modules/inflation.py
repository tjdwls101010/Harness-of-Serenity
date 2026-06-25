#!/usr/bin/env python3
"""Federal Reserve Economic Data (FRED) inflation indicators and expectations data.

Provides access to FRED's inflation datasets including CPI, PCE, breakeven inflation rates,
and University of Michigan consumer sentiment/inflation expectations. Data includes both
headline and core measures with historical time series and metadata.

Args:
	series_id (str): FRED series identifier (e.g., "CPIAUCSL" for CPI, "PCEPI" for PCE)
	--start-date (str): Start date for time series in YYYY-MM-DD format (optional)
	--end-date (str): End date for time series in YYYY-MM-DD format (optional)
	--limit (int): Maximum number of observations to return, most recent first (optional)
	--series-type (str): Inflation measure type (e.g., "headline", "core", "all")
	--maturity (str): Breakeven inflation maturity (e.g., "5y", "10y", "5y_fwd_5y")
	--indicator (str): Michigan sentiment indicator type (e.g., "consumer_sentiment", "inflation_expectation")

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
				"units": str,                    # Measurement unit (Index, Percent, Level)
				"frequency": str,                # Monthly, Quarterly (CPI/PCE); Daily (Breakeven)
				"seasonal_adjustment": str,      # SA (Seasonally Adjusted) or NSA
				"last_updated": str              # Last FRED database update timestamp
			},
			...
		}
	}

Example:
	>>> python inflation.py cpi --series-type all --limit 12
	{
		"data": {
			"CPIAUCSL": {
				"2026-01-01": 315.245,
				"2025-12-01": 314.928
			},
			"CPILFESL": {
				"2026-01-01": 310.132,
				"2025-12-01": 309.845
			}
		},
		"metadata": {
			"CPIAUCSL": {
				"title": "Consumer Price Index for All Urban Consumers: All Items",
				"units": "Index 1982-1984=100",
				"frequency": "Monthly",
				"seasonal_adjustment": "Seasonally Adjusted"
			}
		}
	}

	>>> python inflation.py pce --series-type core
	>>> python inflation.py breakeven-inflation --maturity 10y
	>>> python inflation.py michigan --indicator inflation_expectation

Use Cases:
	- Track Federal Reserve's preferred inflation gauge (PCE) for policy expectations
	- Compare headline vs core inflation for transitory price pressure analysis
	- Monitor market-implied inflation expectations via breakeven rates
	- Assess consumer inflation sentiment for forward-looking indicators
	- Calculate real returns by adjusting nominal yields for inflation
	- Analyze CPI components for sector-specific price trends

Notes:
	- FRED API key required: Set FRED_API_KEY in .env file
	- Rate limits: 120 requests per minute per API key
	- Data delays: CPI released ~mid-month for previous month, PCE ~end-month, breakeven daily
	- CPI vs PCE: Fed targets PCE (broader coverage, chained weights), markets watch CPI (timely)
	- Core inflation excludes food and energy (less volatile, better policy signal)
	- Breakeven inflation: 10Y Treasury yield minus 10Y TIPS yield (market expectation)
	- Michigan survey: Consumer sentiment (UMCSENT), 1Y ahead inflation expectation (MICH)
	- 5Y forward 5Y breakeven (T5YIFR): Market expectation for inflation 5-10 years ahead

See Also:
	- fred/rates.py: TIPS yields for real return calculation
	- fred/policy.py: Fed balance sheet impact on inflation expectations
	- macro/inflation_models.py: Inflation forecasting and Phillips curve analysis
	- statistics/correlation.py: Inflation correlation with other macro variables
"""

import argparse
import os
import sys

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


# FRED Series IDs for inflation
CPI_SERIES = {
	"headline": "CPIAUCSL",
	"core": "CPILFESL",
	"headline_yoy": "CPIAUCNS",
}

PCE_SERIES = {
	"headline": "PCEPI",
	"core": "PCEPILFE",
	"headline_yoy": "PCEPI",
	"core_yoy": "PCEPILFE",
}

BREAKEVEN_INFLATION_SERIES = {
	"5y": "T5YIE",
	"10y": "T10YIE",
	"5y_fwd_5y": "T5YIFR",
}

MICHIGAN_SERIES = {
	"consumer_sentiment": "UMCSENT",
	"inflation_expectation": "MICH",
	"current_conditions": "UMCSENT",
	"expectations": "UMCSENT",
}


@safe_run
def cmd_cpi(args):
	"""Get Consumer Price Index data."""
	series_to_fetch = []

	if args.series_type == "all":
		series_to_fetch = list(CPI_SERIES.values())
	elif args.series_type in CPI_SERIES:
		series_to_fetch = [CPI_SERIES[args.series_type]]
	else:
		series_to_fetch = [CPI_SERIES["headline"], CPI_SERIES["core"]]

	result = fetch_series(series_to_fetch, start_date=args.start_date, end_date=args.end_date, limit=args.limit)
	output_json(result)


@safe_run
def cmd_pce(args):
	"""Get Personal Consumption Expenditures data."""
	series_to_fetch = []

	if args.series_type == "all":
		series_to_fetch = list(set(PCE_SERIES.values()))
	elif args.series_type in PCE_SERIES:
		series_to_fetch = [PCE_SERIES[args.series_type]]
	else:
		series_to_fetch = [PCE_SERIES["headline"], PCE_SERIES["core"]]

	result = fetch_series(series_to_fetch, start_date=args.start_date, end_date=args.end_date, limit=args.limit)
	output_json(result)


@safe_run
def cmd_breakeven_inflation(args):
	"""Get Breakeven Inflation Rates (market-based inflation expectations)."""
	series_to_fetch = []

	if args.maturity == "all":
		series_to_fetch = list(BREAKEVEN_INFLATION_SERIES.values())
	elif args.maturity in BREAKEVEN_INFLATION_SERIES:
		series_to_fetch = [BREAKEVEN_INFLATION_SERIES[args.maturity]]
	else:
		series_to_fetch = [BREAKEVEN_INFLATION_SERIES["5y"], BREAKEVEN_INFLATION_SERIES["10y"]]

	result = fetch_series(series_to_fetch, start_date=args.start_date, end_date=args.end_date, limit=args.limit)
	output_json(result)


@safe_run
def cmd_michigan(args):
	"""Get University of Michigan Consumer Sentiment data."""
	series_to_fetch = []

	if args.indicator == "all":
		series_to_fetch = list(set(MICHIGAN_SERIES.values()))
	elif args.indicator in MICHIGAN_SERIES:
		series_to_fetch = [MICHIGAN_SERIES[args.indicator]]
	else:
		series_to_fetch = [MICHIGAN_SERIES["consumer_sentiment"], MICHIGAN_SERIES["inflation_expectation"]]

	result = fetch_series(series_to_fetch, start_date=args.start_date, end_date=args.end_date, limit=args.limit)
	output_json(result)


def add_common_args(parser):
	"""Add common arguments to a subparser."""
	parser.add_argument("--start-date", default=None, help="Start date (YYYY-MM-DD format)")
	parser.add_argument("--end-date", default=None, help="End date (YYYY-MM-DD format)")
	parser.add_argument("--limit", type=int, default=None, help="Number of observations to return (most recent)")


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="FRED Inflation Data Commands")
	subparsers = parser.add_subparsers(dest="command")

	# CPI
	cpi_parser = subparsers.add_parser("cpi", help="Get CPI data")
	cpi_parser.add_argument("--series-type", default="headline", help="headline, core, or all")
	add_common_args(cpi_parser)

	# PCE
	pce_parser = subparsers.add_parser("pce", help="Get PCE data")
	pce_parser.add_argument("--series-type", default="headline", help="headline, core, or all")
	add_common_args(pce_parser)

	# Breakeven Inflation
	be_parser = subparsers.add_parser("breakeven-inflation", help="Get Breakeven Inflation Rates")
	be_parser.add_argument("--maturity", default="10y", help="5y, 10y, 5y_fwd_5y, or all")
	add_common_args(be_parser)

	# Michigan
	mi_parser = subparsers.add_parser("michigan", help="Get Michigan Consumer Sentiment data")
	mi_parser.add_argument("--indicator", default="all", help="consumer_sentiment, inflation_expectation, or all")
	add_common_args(mi_parser)

	args = parser.parse_args()
	cmds = {"cpi": cmd_cpi, "pce": cmd_pce, "breakeven-inflation": cmd_breakeven_inflation, "michigan": cmd_michigan}
	if args.command in cmds:
		cmds[args.command](args)
	else:
		parser.print_help()
