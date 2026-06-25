#!/usr/bin/env python3
"""Earnings Surprise Analysis: surprise history, post-ER drift, cockroach effect.

Analyzes earnings surprise patterns including beat/miss history, post-earnings
price reactions (gap, 1-day return, 5-day return), and the cockroach effect
(consecutive beats predicting future beats).

Commands:
    history: Get earnings surprise history and post-earnings drift signals

Args:
    symbol (str): Ticker symbol (e.g., "AAPL", "NVDA", "META")

Returns:
    For history:
        dict: {
            "symbol": str,
            "surprise_history": [{
                "date": str, "estimate": float, "actual": float,
                "surprise_pct": float, "pct_skipped_reason": str,
                "beat": bool,
                "eps_yoy_pct": float, "eps_qoq_pct": float,
                "revenue": float, "revenue_yoy_pct": float, "revenue_qoq_pct": float,
                "post_er_return_1d": float,
                "post_er_return_5d": float, "post_er_gap": float
            }],
            "consecutive_beats": int,
            "avg_surprise_pct": float,
            "avg_surprise_method": str,
            "cockroach_effect": str,
            "total_quarters_analyzed": int
        }

Example:
    >>> python surprise.py history NVDA
    {
        "symbol": "NVDA",
        "surprise_history": [
            {
                "date": "2025-11-20",
                "estimate": 0.81,
                "actual": 0.89,
                "surprise_pct": 9.88,
                "beat": true,
                "post_er_return_1d": 3.25,
                "post_er_return_5d": 5.12,
                "post_er_gap": 2.10
            }
        ],
        "consecutive_beats": 4,
        "avg_surprise_pct": 8.45,
        "cockroach_effect": "strong",
        "total_quarters_analyzed": 8
    }

Use Cases:
    - Identify cockroach effect (one surprise predicts more)
    - Measure post-earnings drift magnitude
    - Track earnings predictability for position sizing

Notes:
    - Post-Earnings Drift: market underreacts to earnings surprises
    - Surprise % set to null when |estimate| < 0.05 (near-zero denominator floor)
    - Average surprise uses trimmed mean (top/bottom 10% removed) when 5+ data points available

See Also:
    - growth.py: EPS/sales acceleration and margin expansion analysis
    - analysis.py: Analyst estimate revision trends (get-revisions)
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import yfinance as yf
from utils import error_json, output_json, safe_run


def _enrich_post_er_reactions(ticker, surprises):
    """Add post-earnings price reaction fields to each surprise entry.

    For each earnings date, fetches surrounding price data and calculates:
    - post_er_return_1d: return from pre-ER close to next day close (%)
    - post_er_return_5d: return from pre-ER close to 5th trading day close (%)
    - post_er_gap: gap from pre-ER close to next day open (%)

    Modifies surprises list in-place. Sets fields to None if data unavailable.
    """
    from datetime import timedelta

    import pandas as pd

    if not surprises:
        return

    # Parse all earnings dates
    er_dates = []
    for s in surprises:
        try:
            dt = pd.Timestamp(s["date"])
            er_dates.append(dt)
        except (ValueError, TypeError):
            er_dates.append(None)

    # Find date range for a single batch history fetch
    valid_dates = [d for d in er_dates if d is not None]
    if not valid_dates:
        for s in surprises:
            s["post_er_return_1d"] = None
            s["post_er_return_5d"] = None
            s["post_er_gap"] = None
        return

    earliest = min(valid_dates) - timedelta(days=5)
    latest = max(valid_dates) + timedelta(days=15)

    # Fetch price history in one batch call
    try:
        hist = ticker.history(start=earliest, end=latest, auto_adjust=False)
    except Exception:
        hist = None

    if hist is None or hist.empty:
        for s in surprises:
            s["post_er_return_1d"] = None
            s["post_er_return_5d"] = None
            s["post_er_gap"] = None
        return

    # Normalize index to date-only for reliable comparison
    hist.index = hist.index.normalize()
    if hist.index.tz is not None:
        hist.index = hist.index.tz_localize(None)

    for i, s in enumerate(surprises):
        er_dt = er_dates[i]
        if er_dt is None:
            s["post_er_return_1d"] = None
            s["post_er_return_5d"] = None
            s["post_er_gap"] = None
            continue

        try:
            er_dt_norm = pd.Timestamp(er_dt).normalize()

            # Find pre-ER close: last trading day on or before earnings date
            mask_on_or_before = hist.index <= er_dt_norm
            if not mask_on_or_before.any():
                s["post_er_return_1d"] = None
                s["post_er_return_5d"] = None
                s["post_er_gap"] = None
                continue

            pre_er_idx = hist.index[mask_on_or_before][-1]
            pre_er_close = float(hist.loc[pre_er_idx, "Close"])

            if pre_er_close <= 0:
                s["post_er_return_1d"] = None
                s["post_er_return_5d"] = None
                s["post_er_gap"] = None
                continue

            # Trading days after earnings date
            mask_after = hist.index > er_dt_norm
            days_after = hist.index[mask_after]

            # post_er_gap: next trading day open vs pre-ER close
            if len(days_after) >= 1:
                next_day = days_after[0]
                next_open = float(hist.loc[next_day, "Open"])
                s["post_er_gap"] = round((next_open / pre_er_close - 1) * 100, 2)
            else:
                s["post_er_gap"] = None

            # post_er_return_1d: next trading day close vs pre-ER close
            if len(days_after) >= 1:
                next_day = days_after[0]
                next_close = float(hist.loc[next_day, "Close"])
                s["post_er_return_1d"] = round((next_close / pre_er_close - 1) * 100, 2)
            else:
                s["post_er_return_1d"] = None

            # post_er_return_5d: 5th trading day close vs pre-ER close
            if len(days_after) >= 5:
                day5 = days_after[4]
                day5_close = float(hist.loc[day5, "Close"])
                s["post_er_return_5d"] = round((day5_close / pre_er_close - 1) * 100, 2)
            else:
                s["post_er_return_5d"] = None

        except (KeyError, IndexError, TypeError, ValueError):
            s["post_er_return_1d"] = None
            s["post_er_return_5d"] = None
            s["post_er_gap"] = None


@safe_run
def cmd_history(args):
    """Get earnings surprise history and post-earnings drift signals.

    Uses get_earnings_dates(limit=20) for up to 8 quarters of EPS data,
    enriched with revenue from quarterly_income_stmt and EPS/Revenue YoY/QoQ growth.
    """
    import pandas as pd

    symbol = args.symbol.upper()
    ticker = yf.Ticker(symbol)

    # Get earnings dates (replaces get_earnings_history for broader coverage)
    try:
        earnings_dates = ticker.get_earnings_dates(limit=20)
    except Exception:
        earnings_dates = None

    if earnings_dates is None or (hasattr(earnings_dates, "empty") and earnings_dates.empty):
        error_json(f"No earnings history available for {symbol}")

    # Filter to reported results only (future entries have NaN Reported EPS)
    ed = earnings_dates.dropna(subset=["Reported EPS"])
    if ed.empty:
        error_json(f"No reported earnings available for {symbol}")

    # Sort by date descending (most recent first)
    ed = ed.sort_index(ascending=False)

    # Build surprise entries from earnings_dates
    surprises = []
    for idx, row in ed.iterrows():
        try:
            est_f = float(row.get("EPS Estimate")) if pd.notna(row.get("EPS Estimate")) else None
            act_f = float(row["Reported EPS"])
            if act_f != act_f:  # NaN check
                continue
        except (ValueError, TypeError):
            continue

        if est_f is not None and est_f != est_f:  # NaN check on estimate
            est_f = None

        surprise_pct = None
        pct_skipped_reason = None
        beat = None

        if est_f is not None:
            if abs(est_f) < 0.05:
                surprise_pct = None
                pct_skipped_reason = "estimate_near_zero"
            else:
                surprise_pct = round(((act_f - est_f) / abs(est_f) * 100), 2)
                pct_skipped_reason = None
            beat = act_f > est_f

        date_str = str(idx.date()) if hasattr(idx, "date") else str(idx)
        surprises.append({
            "date": date_str,
            "estimate": est_f,
            "actual": act_f,
            "surprise_pct": surprise_pct,
            "pct_skipped_reason": pct_skipped_reason,
            "beat": beat,
        })

    # EPS YoY/QoQ growth calculation
    for i, entry in enumerate(surprises):
        current_eps = entry["actual"]
        # QoQ: compare with previous quarter (index i+1, since list is descending)
        if i + 1 < len(surprises):
            prior_eps = surprises[i + 1]["actual"]
            if prior_eps is not None and abs(prior_eps) >= 0.01:
                entry["eps_qoq_pct"] = round(((current_eps - prior_eps) / abs(prior_eps)) * 100, 2)
            else:
                entry["eps_qoq_pct"] = None
        else:
            entry["eps_qoq_pct"] = None
        # YoY: compare with same quarter 4 entries back
        if i + 4 < len(surprises):
            prior_eps = surprises[i + 4]["actual"]
            if prior_eps is not None and abs(prior_eps) >= 0.01:
                entry["eps_yoy_pct"] = round(((current_eps - prior_eps) / abs(prior_eps)) * 100, 2)
            else:
                entry["eps_yoy_pct"] = None
        else:
            entry["eps_yoy_pct"] = None

    # Revenue enrichment from quarterly_income_stmt
    try:
        qi = ticker.quarterly_income_stmt
        if qi is not None and not qi.empty:
            revenue_metric = next(
                (m for m in ["TotalRevenue", "Total Revenue"] if m in qi.index), None
            )
            if revenue_metric:
                rev_series = qi.loc[revenue_metric].sort_index(ascending=False)
                rev_dates = list(rev_series.index)
                rev_values = list(rev_series.values)

                # Match each surprise entry to nearest income_stmt quarter (+-45 days)
                for entry in surprises:
                    try:
                        entry_dt = pd.Timestamp(entry["date"])
                    except (ValueError, TypeError):
                        entry["revenue"] = None
                        entry["revenue_yoy_pct"] = None
                        entry["revenue_qoq_pct"] = None
                        continue

                    best_match_idx = None
                    best_delta = None
                    for ri, rd in enumerate(rev_dates):
                        rd_ts = pd.Timestamp(rd)
                        delta = abs((entry_dt - rd_ts).days)
                        if delta <= 45 and (best_delta is None or delta < best_delta):
                            best_delta = delta
                            best_match_idx = ri

                    if best_match_idx is not None:
                        rev_val = rev_values[best_match_idx]
                        if pd.notna(rev_val):
                            entry["revenue"] = float(rev_val)
                            # Revenue QoQ
                            if best_match_idx + 1 < len(rev_values):
                                prior_rev = rev_values[best_match_idx + 1]
                                if pd.notna(prior_rev) and abs(float(prior_rev)) > 0:
                                    entry["revenue_qoq_pct"] = round(
                                        ((float(rev_val) - float(prior_rev)) / abs(float(prior_rev))) * 100, 2
                                    )
                                else:
                                    entry["revenue_qoq_pct"] = None
                            else:
                                entry["revenue_qoq_pct"] = None
                            # Revenue YoY
                            if best_match_idx + 4 < len(rev_values):
                                prior_rev = rev_values[best_match_idx + 4]
                                if pd.notna(prior_rev) and abs(float(prior_rev)) > 0:
                                    entry["revenue_yoy_pct"] = round(
                                        ((float(rev_val) - float(prior_rev)) / abs(float(prior_rev))) * 100, 2
                                    )
                                else:
                                    entry["revenue_yoy_pct"] = None
                            else:
                                entry["revenue_yoy_pct"] = None
                        else:
                            entry["revenue"] = None
                            entry["revenue_yoy_pct"] = None
                            entry["revenue_qoq_pct"] = None
                    else:
                        entry["revenue"] = None
                        entry["revenue_yoy_pct"] = None
                        entry["revenue_qoq_pct"] = None
            else:
                for entry in surprises:
                    entry["revenue"] = None
                    entry["revenue_yoy_pct"] = None
                    entry["revenue_qoq_pct"] = None
        else:
            for entry in surprises:
                entry["revenue"] = None
                entry["revenue_yoy_pct"] = None
                entry["revenue_qoq_pct"] = None
    except Exception:
        for entry in surprises:
            entry.setdefault("revenue", None)
            entry.setdefault("revenue_yoy_pct", None)
            entry.setdefault("revenue_qoq_pct", None)

    # Cap to 8 quarters
    surprises = surprises[:8]

    # Enrich with post-ER price reaction data
    _enrich_post_er_reactions(ticker, surprises)

    # Consecutive beats
    consecutive_beats = 0
    for s in surprises:
        if s.get("beat"):
            consecutive_beats += 1
        else:
            break

    # Average surprise (trimmed mean with empty-slice fallback)
    valid_surprises = [s["surprise_pct"] for s in surprises if s["surprise_pct"] is not None]
    if len(valid_surprises) >= 5:
        # Trimmed mean: remove top and bottom 10%
        import numpy as np
        sorted_vals = sorted(valid_surprises)
        trim_count = max(1, len(sorted_vals) // 10)
        trimmed = sorted_vals[trim_count:-trim_count]
        if not trimmed:
            # Fallback: trimming removed all values (small sample edge case)
            trimmed = sorted_vals
            avg_surprise_method = "simple_mean_fallback"
        else:
            avg_surprise_method = "trimmed_mean"
        avg_surprise = round(float(np.mean(trimmed)), 2)
    else:
        avg_surprise = round(sum(valid_surprises) / len(valid_surprises), 2) if valid_surprises else 0
        avg_surprise_method = "simple_mean"

    # Cockroach effect assessment
    if consecutive_beats >= 4:
        cockroach = "strong"
    elif consecutive_beats >= 2:
        cockroach = "moderate"
    else:
        cockroach = "none"

    output_json(
        {
            "symbol": symbol,
            "surprise_history": surprises,
            "consecutive_beats": consecutive_beats,
            "avg_surprise_pct": avg_surprise,
            "avg_surprise_method": avg_surprise_method,
            "cockroach_effect": cockroach,
            "total_quarters_analyzed": len(surprises),
        }
    )


def main():
    parser = argparse.ArgumentParser(description="Earnings Surprise Analysis")
    sub = parser.add_subparsers(dest="command", required=True)

    # history
    sp = sub.add_parser("history", help="Get earnings surprise history")
    sp.add_argument("symbol", help="Ticker symbol")
    sp.set_defaults(func=cmd_history)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
