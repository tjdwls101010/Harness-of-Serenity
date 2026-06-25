#!/usr/bin/env python3
"""Growth Profile Analysis: EPS/sales acceleration, margin trends.

Analyzes earnings growth patterns to detect acceleration in EPS, sales, and
margin expansion across quarterly financial data. Provides both detailed
profile analysis and trend-level acceleration data.

Commands:
    profile: Analyze growth profile (EPS/sales acceleration, margin expansion)
    trends: Analyze quarterly EPS and sales growth acceleration trends

Args:
    symbol (str): Ticker symbol (e.g., "AAPL", "NVDA", "META")

Returns:
    For profile:
        dict: {
            "symbol": str,
            "eps_accelerating": bool,
            "eps_improving": bool,
            "sales_accelerating": bool,
            "sales_improving": bool,
            "margin_expanding": bool,
            "margin_data_quality": str,
            "quarters_analyzed": int,
            "eps_growth_rates": [float],
            "sales_growth_rates": [float],
            "margin_values_pct": [float],
            "compressed": dict,
            "data_quality": str,
            "thresholds": {
                "accelerating": str,
                "margin_expansion": str,
                "margin_min_change_ppt": float
            }
        }

    For trends:
        dict: {
            "symbol": str,
            "eps_acceleration": [{"quarter": str, "growth_rate": float, "accelerating": bool, "improving": bool}],
            "sales_acceleration": [{"quarter": str, "growth_rate": float, "accelerating": bool, "improving": bool}],
            "overall_trend": str
        }

Example:
    >>> python growth.py profile NVDA
    {
        "symbol": "NVDA",
        "eps_accelerating": true,
        "eps_improving": true,
        "sales_accelerating": true,
        "sales_improving": true,
        "margin_expanding": true,
        "margin_data_quality": "full",
        "eps_growth_rates": [25.3, 38.5, 52.1],
        "sales_growth_rates": [18.2, 28.7, 42.3]
    }

    >>> python growth.py trends AAPL
    {
        "symbol": "AAPL",
        "eps_acceleration": [
            {"quarter": "2025Q4", "growth_rate": 12.5, "accelerating": true, "improving": true},
            {"quarter": "2025Q3", "growth_rate": 8.2, "accelerating": false, "improving": false}
        ],
        "overall_trend": "accelerating"
    }

Use Cases:
    - Detect earnings-driven acceleration for stock selection
    - Track earnings momentum for position management
    - Monitor margin expansion as a quality signal

Notes:
    - EPS growth rates compare to same quarter prior year (YoY)
    - Margin expansion uses gross or operating margin trend
    - Margin expansion requires 3+ consecutive quarters with >= 0.5 ppt improvement each
    - Data quality levels: full (3+ quarters), partial (2 quarters), minimal (0-1 quarters)
    - accelerating: each quarter's growth rate > prior quarter's growth rate (rate of change)
    - improving: trajectory getting better (rates becoming less negative or more positive)

See Also:
    - surprise.py: Earnings surprise history and post-ER drift signals
    - analysis.py: Analyst estimate revision trends (get-revisions)
    - trend_template.py: Trend Template check (price-based qualification)
    - stage_analysis.py: Stage classification (technical context)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import yfinance as yf
from utils import error_json, output_json, safe_run


def _get_quarterly_financials(symbol):
    """Retrieve quarterly income statement data and earnings dates.

    Tries ticker.quarterly_income_stmt first for broader historical coverage
    (8+ quarters), falls back to get_income_stmt(freq="quarterly") if unavailable.
    """
    ticker = yf.Ticker(symbol)

    # Try quarterly_income_stmt for more historical quarters
    income = None
    try:
        qi = ticker.quarterly_income_stmt
        if qi is not None and not qi.empty and len(qi.columns) >= 4:
            income = qi
    except Exception:
        pass

    # Fallback to standard API
    if income is None or income.empty:
        income = ticker.get_income_stmt(freq="quarterly")

    return ticker, income


def _get_eps_growth_from_earnings_dates(ticker, limit=12):
    """Extract YoY EPS growth from earnings_dates (up to 12 quarters).

    earnings_dates provides more historical EPS data than income statements.
    Returns list of (quarter_label, growth_rate) tuples, most recent first.
    """
    try:
        ed = ticker.get_earnings_dates(limit=limit)
    except Exception:
        return []

    if ed is None or ed.empty or "Reported EPS" not in ed.columns:
        return []

    # Filter rows with actual reported EPS
    ed = ed.dropna(subset=["Reported EPS"])
    if len(ed) < 5:  # Need at least 5 quarters for 1 YoY comparison
        return []

    # Sort by date descending
    ed = ed.sort_index(ascending=False)
    eps_values = list(zip(ed.index, ed["Reported EPS"]))

    results = []
    for i in range(len(eps_values)):
        current_date, current_eps = eps_values[i]
        # Find same quarter prior year (4 quarters back)
        yoy_idx = i + 4
        if yoy_idx < len(eps_values):
            prior_date, prior_eps = eps_values[yoy_idx]
            if prior_eps != 0:
                growth = ((current_eps / prior_eps) - 1) * 100
                label = str(current_date.date()) if hasattr(current_date, "date") else str(current_date)
                results.append((label, round(growth, 2)))

    return results


def _extract_growth_series(income_df, metric_name):
    """Extract YoY growth rates for a metric across quarters.

    Returns list of (quarter_label, growth_rate) tuples, most recent first.
    """
    if income_df is None or income_df.empty:
        return []

    # income_df columns are dates, rows are metrics
    if metric_name not in income_df.index:
        return []

    values = income_df.loc[metric_name]
    # Sort by date descending (most recent first)
    values = values.sort_index(ascending=False)

    results = []
    dates = list(values.index)

    for i, date in enumerate(dates):
        current_val = values[date]
        if current_val is None or (hasattr(current_val, "__class__") and current_val != current_val):
            continue

        # Find same quarter from prior year (4 quarters back)
        yoy_idx = i + 4
        if yoy_idx < len(dates):
            prior_val = values[dates[yoy_idx]]
            if (
                prior_val is not None
                and prior_val != 0
                and not (hasattr(prior_val, "__class__") and prior_val != prior_val)
            ):
                growth = ((float(current_val) / float(prior_val)) - 1) * 100
                quarter_label = str(date.date()) if hasattr(date, "date") else str(date)
                results.append((quarter_label, round(growth, 2)))

    return results


def _is_accelerating(growth_rates, min_quarters=3):
    """Check if growth rates are accelerating (each quarter's rate > prior quarter's rate).

    Acceleration means the rate of change is improving, regardless of sign.
    Example: -20% -> -10% -> +5% IS acceleration (improving trajectory).

    growth_rates: list of (quarter, rate) tuples, most recent first.
    Returns (is_accelerating, is_improving, rates_used).
      - accelerating: each rate > prior rate (rate of change improvement)
      - improving: same as accelerating (rates becoming less negative or more positive)
    """
    if len(growth_rates) < min_quarters:
        return False, False, []

    # Take most recent min_quarters
    recent = growth_rates[:min_quarters]
    rates = [r[1] for r in recent]

    # Accelerating means each quarter's growth > the previous quarter's growth
    # Since list is most-recent-first, rates[0] > rates[1] > rates[2]
    accelerating = all(rates[i] > rates[i + 1] for i in range(len(rates) - 1))

    # Improving: trajectory getting better (rates becoming less negative or more positive)
    # Same check as accelerating -- each rate > prior rate regardless of sign
    improving = accelerating

    return accelerating, improving, rates


def _assess_data_quality(eps_count, sales_count):
    """Assess earnings data completeness for analysis reliability."""
    min_count = min(eps_count, sales_count)
    if min_count >= 3:
        return "full"
    elif min_count >= 2:
        return "partial"
    else:
        return "minimal"


# Minimum margin change in percentage points to count as real expansion
_MARGIN_MIN_CHANGE_PPT = 0.5


@safe_run
def cmd_profile(args):
    """Analyze growth profile: EPS/sales acceleration, margin expansion."""
    symbol = args.symbol.upper()
    ticker, income = _get_quarterly_financials(symbol)

    if income is None or income.empty:
        error_json(f"No quarterly financial data available for {symbol}")

    # EPS acceleration: prefer earnings_dates (12+ quarters) over income statement (5 quarters)
    eps_growth = _get_eps_growth_from_earnings_dates(ticker)
    eps_metric = "Reported EPS (earnings_dates)"
    if not eps_growth:
        # Fallback to income statement
        eps_metric = next(
            (
                m
                for m in ["DilutedEPS", "Diluted EPS", "BasicEPS", "Basic EPS", "NetIncome", "Net Income"]
                if m in income.index
            ),
            "NetIncome",
        )
        eps_growth = _extract_growth_series(income, eps_metric)
    eps_acc, eps_improving, eps_rates = _is_accelerating(eps_growth)

    # Sales acceleration
    sales_metric = next(
        (m for m in ["TotalRevenue", "Total Revenue", "OperatingRevenue", "Operating Revenue"] if m in income.index),
        "TotalRevenue",
    )
    sales_growth = _extract_growth_series(income, sales_metric)
    sales_acc, sales_improving, sales_rates = _is_accelerating(sales_growth)

    # Margin expansion (gross margin or operating margin)
    # Require 3+ consecutive quarters with >= 0.5 ppt improvement
    margin_expanding = False
    margin_data_quality = "full"
    margin_values = []
    gp_metric = next((m for m in ["GrossProfit", "Gross Profit"] if m in income.index), None)
    if gp_metric is not None and sales_metric in income.index:
        gross_profit = income.loc[gp_metric].sort_index(ascending=False)
        revenue = income.loc[sales_metric].sort_index(ascending=False)
        for i in range(min(5, len(gross_profit))):
            gp = gross_profit.iloc[i]
            rev = revenue.iloc[i]
            if gp is not None and rev is not None and rev != 0:
                gp_f = float(gp) if not (hasattr(gp, "__class__") and gp != gp) else 0
                rev_f = float(rev) if not (hasattr(rev, "__class__") and rev != rev) else 1
                if rev_f != 0:
                    margin_values.append(round(gp_f / rev_f * 100, 2))

        if len(margin_values) >= 4:
            # Need 3+ consecutive quarters of margin improvement with >= 0.5 ppt change
            # margin_values is most-recent-first, so margin_values[i] > margin_values[i+1]
            # means most recent margin > prior margin
            consecutive_expansions = 0
            for i in range(len(margin_values) - 1):
                change = margin_values[i] - margin_values[i + 1]
                if change >= _MARGIN_MIN_CHANGE_PPT:
                    consecutive_expansions += 1
                else:
                    break
            margin_expanding = consecutive_expansions >= 3
            margin_data_quality = "full"
        elif len(margin_values) >= 3:
            # 3 values = only 2 comparisons possible, cannot reach 3 consecutive
            consecutive_expansions = 0
            for i in range(len(margin_values) - 1):
                change = margin_values[i] - margin_values[i + 1]
                if change >= _MARGIN_MIN_CHANGE_PPT:
                    consecutive_expansions += 1
                else:
                    break
            margin_expanding = False  # Cannot have 3+ consecutive with only 2 comparisons
            margin_data_quality = "insufficient"
        else:
            margin_data_quality = "insufficient"
    else:
        margin_data_quality = "insufficient"

    full_result = {
        "symbol": symbol,
        "eps_accelerating": eps_acc,
        "eps_improving": eps_improving,
        "eps_growth_rates": eps_rates,
        "eps_quarters": [q[0] for q in eps_growth[:3]] if eps_growth else [],
        "sales_accelerating": sales_acc,
        "sales_improving": sales_improving,
        "sales_growth_rates": sales_rates,
        "sales_quarters": [q[0] for q in sales_growth[:3]] if sales_growth else [],
        "margin_expanding": margin_expanding,
        "margin_data_quality": margin_data_quality,
        "margin_values_pct": margin_values[:5] if margin_values else [],
        "quarters_analyzed": min(len(eps_growth), len(sales_growth)),
        "data_quality": _assess_data_quality(len(eps_growth), len(sales_growth)),
        "thresholds": {
            "accelerating": "3 consecutive quarters with increasing YoY growth rate",
            "margin_expansion": "3+ consecutive quarters with >= 0.5 ppt margin improvement",
        },
    }

    # Add compressed view for pipeline consumption
    compressed = {
        "eps_accelerating": eps_acc,
        "margin_expanding": margin_expanding,
        "eps_growth_rates": eps_rates[:3],
        "data_quality": full_result["data_quality"],
    }
    if sales_rates:
        compressed["sales_accelerating"] = sales_acc
        compressed["sales_growth_rates"] = sales_rates[:3]
    full_result["compressed"] = compressed

    output_json(full_result)


@safe_run
def cmd_trends(args):
    """Analyze quarterly EPS and sales growth acceleration trends."""
    symbol = args.symbol.upper()
    ticker, income = _get_quarterly_financials(symbol)

    if income is None or income.empty:
        error_json(f"No quarterly financial data available for {symbol}")

    # EPS acceleration: prefer earnings_dates (12+ quarters) over income statement
    eps_growth = _get_eps_growth_from_earnings_dates(ticker)
    eps_metric = "Reported EPS (earnings_dates)"
    if not eps_growth:
        eps_metric = next(
            (
                m
                for m in ["DilutedEPS", "Diluted EPS", "BasicEPS", "Basic EPS", "NetIncome", "Net Income"]
                if m in income.index
            ),
            "NetIncome",
        )
        eps_growth = _extract_growth_series(income, eps_metric)

    eps_results = []
    for i, (quarter, rate) in enumerate(eps_growth):
        if i + 1 < len(eps_growth):
            acc = rate > eps_growth[i + 1][1]
            imp = acc  # improving = same as accelerating (rate of change improvement)
        else:
            acc = None
            imp = None
        eps_results.append(
            {
                "quarter": quarter,
                "growth_rate_yoy": rate,
                "accelerating": acc,
                "improving": imp,
            }
        )

    # Sales acceleration
    sales_metric = next(
        (m for m in ["TotalRevenue", "Total Revenue", "OperatingRevenue", "Operating Revenue"] if m in income.index),
        "TotalRevenue",
    )
    sales_growth = _extract_growth_series(income, sales_metric)

    sales_results = []
    for i, (quarter, rate) in enumerate(sales_growth):
        if i + 1 < len(sales_growth):
            acc = rate > sales_growth[i + 1][1]
            imp = acc
        else:
            acc = None
            imp = None
        sales_results.append(
            {
                "quarter": quarter,
                "growth_rate_yoy": rate,
                "accelerating": acc,
                "improving": imp,
            }
        )

    # Overall trend
    if len(eps_results) >= 2:
        recent_eps_acc = eps_results[0].get("accelerating", False)
        recent_sales_acc = sales_results[0].get("accelerating", False) if sales_results else False
        if recent_eps_acc and recent_sales_acc:
            overall = "strongly_accelerating"
        elif recent_eps_acc or recent_sales_acc:
            overall = "accelerating"
        elif eps_results[0]["growth_rate_yoy"] > 0:
            overall = "growing_but_decelerating"
        else:
            overall = "declining"
    else:
        overall = "insufficient_data"

    output_json(
        {
            "symbol": symbol,
            "eps_metric_used": eps_metric,
            "eps_acceleration": eps_results,
            "sales_metric_used": sales_metric,
            "sales_acceleration": sales_results,
            "overall_trend": overall,
            "thresholds": {
                "accelerating": "current quarter growth rate > prior quarter growth rate (sign-agnostic)",
                "improving": "rates becoming less negative or more positive",
            },
        }
    )


def main():
    parser = argparse.ArgumentParser(description="Growth Profile Analysis")
    sub = parser.add_subparsers(dest="command", required=True)

    # profile
    sp = sub.add_parser("profile", help="Analyze growth profile (EPS/sales acceleration, margins)")
    sp.add_argument("symbol", help="Ticker symbol")
    sp.set_defaults(func=cmd_profile)

    # trends
    sp = sub.add_parser("trends", help="Analyze earnings acceleration trends")
    sp.add_argument("symbol", help="Ticker symbol")
    sp.set_defaults(func=cmd_trends)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
