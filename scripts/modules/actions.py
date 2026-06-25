#!/usr/bin/env python3
"""Corporate actions, earnings dates, calendar, and news.

Retrieve dividend payments, stock splits, capital gains distributions, earnings data,
earnings calendar, corporate event calendar, and company news via Yahoo Finance API.

Commands:
	get-dividends: Historical dividend payments with ex-dates
	get-splits: Stock split history and ratios
	get-capital-gains: Capital gains distributions (mutual funds/ETFs)
	get-actions: Combined dividends and splits
	get-earnings: Annual or quarterly earnings summary
	get-earnings-dates: Future and past earnings announcement dates
	get-calendar: Upcoming earnings, ex-dividend, and other corporate events
	get-news: Company news and press releases

Args:
	symbol (str): Ticker symbol (e.g., "AAPL", "MSFT", "SPY")
	--start (str): Start date for dividend filter (YYYY-MM-DD)
	--end (str): End date for dividend filter (YYYY-MM-DD)
	--freq (str): Earnings frequency (yearly/quarterly, default: yearly)
	--limit (int): Number of earnings dates to retrieve (default: 12)
	--count (int): Number of news articles (default: 10)
	--tab (str): News tab filter (news/all/press_releases, default: news)

Returns:
	dict: {
		"Date": str,              # Action date or announcement date
		"Dividends": float,       # Dividend amount per share
		"Stock Splits": str,      # Split ratio (e.g., "2:1")
		"Capital Gains": float,   # Capital gains per share
		"Revenue": float,         # Earnings revenue (for get-earnings)
		"Earnings": float,        # Earnings per share
		"title": str,             # News headline (for get-news)
		"publisher": str,         # News source
		"link": str               # News article URL
	}

Example:
	>>> python actions.py get-dividends AAPL --start 2024-01-01 --end 2024-12-31
	{
		"2024-02-09": {"Dividends": 0.24},
		"2024-05-10": {"Dividends": 0.24},
		"2024-08-12": {"Dividends": 0.25},
		"2024-11-08": {"Dividends": 0.25}
	}

	>>> python actions.py get-splits AAPL
	{
		"2014-06-09": {"Stock Splits": "7:1"},
		"2020-08-31": {"Stock Splits": "4:1"}
	}

	>>> python actions.py get-earnings MSFT --freq quarterly
	{
		"2025Q4": {"Revenue": 62026000000, "Earnings": 3.13},
		"2025Q3": {"Revenue": 65585000000, "Earnings": 3.30},
		"2025Q2": {"Revenue": 64727000000, "Earnings": 2.99}
	}

	>>> python actions.py get-earnings-dates AAPL --limit 4
	{
		"2026-01-29": {"Earnings Date": "2026-01-29", "EPS Estimate": 2.35},
		"2025-10-31": {"Earnings Date": "2025-10-31", "EPS Estimate": 1.59}
	}

	>>> python actions.py get-calendar SPY
	{
		"Earnings Date": "N/A",
		"Ex-Dividend Date": "2026-03-21",
		"Dividend Date": "2026-04-30"
	}

	>>> python actions.py get-news AAPL --count 5
	[
		{
			"title": "Apple announces new product line",
			"publisher": "Reuters",
			"link": "https://...",
			"providerPublishTime": 1704153600
		}
	]

Use Cases:
	- Dividend tracking for income portfolio management
	- Ex-dividend date calendar for dividend capture strategies
	- Earnings calendar integration for event-driven trading
	- News sentiment analysis and event detection
	- Corporate action adjustments for backtesting
	- Stock split history for price normalization

Notes:
	- Yahoo Finance API rate limits: ~2000 requests/hour
	- Dividend dates are ex-dividend dates (not payment dates)
	- Earnings dates may be estimates subject to change
	- News articles limited to recent 30-60 days
	- get-calendar returns next upcoming events only
	- Capital gains primarily applicable to mutual funds and ETFs
	- Earnings estimates may be null if not available

See Also:
	- price.py: Historical price data (use with --actions flag)
	- financials.py: Detailed earnings statements and metrics
	- info.py: Company metadata and business information
	- funds.py: Fund-specific distribution data
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pandas as pd
import yfinance as yf
from utils import output_json, safe_run


def _coerce_date(s):
	"""Parse an ISO/tz-aware or common date string to a date, else None."""
	if not isinstance(s, str) or not s.strip():
		return None
	try:
		return datetime.fromisoformat(s).date()
	except (ValueError, TypeError):
		pass
	for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%b %d, %Y"):
		try:
			return datetime.strptime(s.strip(), fmt).date()
		except (ValueError, TypeError):
			continue
	return None


def _num(v):
	"""Coerce a value (incl. numpy scalars) to float, or None if not finite."""
	try:
		f = float(v)
		return f if f == f else None
	except (TypeError, ValueError):
		return None


def _parse_days_to_next_earnings(earnings_dates_data):
	"""Days until the nearest FUTURE earnings date.

	yfinance get_earnings_dates puts the dates in the DataFrame INDEX, so after
	normalize() the dates become the KEYS of each column dict (e.g. "EPS Estimate":
	{"2026-08-26 16:00:00-04:00": 2.08, ...}) — there is no top-level "Earnings Date"
	column. Collect candidate date strings from an explicit "Earnings Date" column
	if one exists, otherwise from the index keys of the value columns.
	"""
	if not isinstance(earnings_dates_data, dict) or earnings_dates_data.get("error"):
		return None
	date_strs = set()
	explicit = earnings_dates_data.get("Earnings Date")
	if isinstance(explicit, dict):
		date_strs.update(v for v in explicit.values() if isinstance(v, str))
	for key, col in earnings_dates_data.items():
		if key in ("days_to_next", "error", "Earnings Date"):
			continue
		if isinstance(col, dict):
			date_strs.update(k for k in col.keys() if isinstance(k, str))
	today = datetime.now().date()
	min_days = None
	for s in date_strs:
		d = _coerce_date(s)
		if d is None:
			continue
		delta = (d - today).days
		if delta >= 0 and (min_days is None or delta < min_days):
			min_days = delta
	return min_days


def _aggregate_insider(symbol):
	"""12-month insider buy/sell aggregation + net direction.

	Combines insider_transactions (per-filing rows → 12m net VALUE) with
	insider_purchases (6m net-shares summary) into a compact summary the
	institutional-flow signal consumes. A CEO buying on the open market is a
	conviction vote; empty data returns 'no_data' (not 'unknown').
	"""
	ticker = yf.Ticker(symbol)
	buy_value = sell_value = 0.0
	buy_count = sell_count = 0
	cutoff = datetime.now().date() - timedelta(days=365)

	try:
		tx = ticker.insider_transactions
	except Exception:
		tx = None
	if isinstance(tx, pd.DataFrame) and not tx.empty:
		for _, row in tx.iterrows():
			start = _coerce_date(str(row.get("Start Date", "")))
			if start is not None and start < cutoff:
				continue
			# yfinance leaves "Transaction" blank; the buy/sell type lives in "Text"
			# (e.g. "Sale at price ...", "Purchase at price ..."). Read both to be safe.
			txt = (str(row.get("Text", "")) + " " + str(row.get("Transaction", ""))).lower()
			val = _num(row.get("Value")) or 0.0
			if "purchase" in txt or "buy" in txt:
				buy_value += val
				buy_count += 1
			elif "sale" in txt or "sell" in txt:
				sell_value += val
				sell_count += 1

	net_shares_6m = None
	try:
		ip = ticker.insider_purchases
		if isinstance(ip, pd.DataFrame) and not ip.empty:
			label_col = ip.columns[0]
			for _, row in ip.iterrows():
				if str(row.get(label_col, "")).startswith("Net Shares Purchased"):
					net_shares_6m = _num(row.get("Shares"))
					break
	except Exception:
		pass

	tx_count = buy_count + sell_count
	net_value = round(buy_value - sell_value, 2) if tx_count else None
	has_data = tx_count > 0 or net_shares_6m is not None

	if not has_data:
		net_direction = "no_data"
	else:
		basis = net_value if net_value is not None else net_shares_6m
		if basis is None or basis == 0:
			net_direction = "neutral"
		elif basis > 0:
			net_direction = "net_buying"
		else:
			net_direction = "net_selling"

	return {
		"summary": {
			"net_direction": net_direction,
			"net_value": net_value,
			"net_shares_6m": net_shares_6m,
			"buy_value_12m": round(buy_value, 2) if buy_count else None,
			"sell_value_12m": round(sell_value, 2) if sell_count else None,
			"buy_count_12m": buy_count,
			"sell_count_12m": sell_count,
		},
		"window": "12m transactions (net $ value) + 6m net shares; open-market buys are a conviction vote",
	}


@safe_run
def cmd_dividends(args):
	data = yf.Ticker(args.symbol).get_dividends()
	if args.start:
		start = pd.Timestamp(args.start)
		if data.index.tz is not None:
			start = start.tz_localize(data.index.tz)
		data = data[data.index >= start]
	if args.end:
		end = pd.Timestamp(args.end)
		if data.index.tz is not None:
			end = end.tz_localize(data.index.tz)
		data = data[data.index <= end]
	output_json(data)


@safe_run
def cmd_splits(args):
	output_json(yf.Ticker(args.symbol).get_splits())


@safe_run
def cmd_capital_gains(args):
	output_json(yf.Ticker(args.symbol).get_capital_gains())


@safe_run
def cmd_actions(args):
	output_json(yf.Ticker(args.symbol).get_actions())


@safe_run
def cmd_earnings(args):
	output_json(yf.Ticker(args.symbol).get_earnings(freq=args.freq))


@safe_run
def cmd_earnings_dates(args):
	from utils import normalize
	raw = yf.Ticker(args.symbol).get_earnings_dates(limit=args.limit)
	# Convert DataFrame to dict before enriching
	if isinstance(raw, pd.DataFrame):
		data = normalize(raw) if not raw.empty else {}
	elif isinstance(raw, dict):
		data = raw
	else:
		output_json(raw)
		return
	# Enrich with days_to_next field for pipeline consumption
	if isinstance(data, dict) and not data.get("error"):
		data["days_to_next"] = _parse_days_to_next_earnings(data)
	output_json(data)


@safe_run
def cmd_calendar(args):
	output_json(yf.Ticker(args.symbol).get_calendar())


@safe_run
def cmd_news(args):
	output_json(yf.Ticker(args.symbol).get_news(count=args.count, tab=args.tab))


@safe_run
def cmd_insider(args):
	output_json(_aggregate_insider(args.symbol))


def main():
	parser = argparse.ArgumentParser(description="Corporate actions, earnings, and news")
	sub = parser.add_subparsers(dest="command", required=True)

	# get-dividends
	sp = sub.add_parser("get-dividends")
	sp.add_argument("symbol")
	sp.add_argument("--start", default=None, help="Start date (YYYY-MM-DD)")
	sp.add_argument("--end", default=None, help="End date (YYYY-MM-DD)")
	sp.set_defaults(func=cmd_dividends)

	# get-splits
	sp = sub.add_parser("get-splits")
	sp.add_argument("symbol")
	sp.set_defaults(func=cmd_splits)

	# get-capital-gains
	sp = sub.add_parser("get-capital-gains")
	sp.add_argument("symbol")
	sp.set_defaults(func=cmd_capital_gains)

	# get-actions
	sp = sub.add_parser("get-actions")
	sp.add_argument("symbol")
	sp.set_defaults(func=cmd_actions)

	# get-earnings
	sp = sub.add_parser("get-earnings")
	sp.add_argument("symbol")
	sp.add_argument("--freq", choices=["yearly", "quarterly"], default="yearly")
	sp.set_defaults(func=cmd_earnings)

	# get-earnings-dates
	sp = sub.add_parser("get-earnings-dates")
	sp.add_argument("symbol")
	sp.add_argument("--limit", type=int, default=12)
	sp.set_defaults(func=cmd_earnings_dates)

	# get-calendar
	sp = sub.add_parser("get-calendar")
	sp.add_argument("symbol")
	sp.set_defaults(func=cmd_calendar)

	# get-news
	sp = sub.add_parser("get-news")
	sp.add_argument("symbol")
	sp.add_argument("--count", type=int, default=10)
	sp.add_argument("--tab", choices=["news", "all", "press_releases"], default="news")
	sp.set_defaults(func=cmd_news)

	# get-insider
	sp = sub.add_parser("get-insider")
	sp.add_argument("symbol")
	sp.set_defaults(func=cmd_insider)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
