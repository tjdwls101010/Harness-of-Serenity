"""Post-processing helpers for Serenity pipeline outputs.

Functions that compress, summarize, or trim raw module data
before it is included in the final pipeline response.
"""


def _merge_earnings(earnings_dates, earnings_surprise):
	"""Merge earnings_dates and earnings_surprise into unified earnings object.

	Restructures flat surprise entries from cmd_surprise into nested schema:
	- eps sub-object: estimate, actual, surprise_pct, pct_skipped_reason, beat, yoy_pct, qoq_pct
	- revenue sub-object: actual, yoy_pct, qoq_pct
	- post_er_* fields remain at top level

	Returns:
		dict with next_report, surprise_history (nested), consecutive_beats,
		avg_surprise_pct, cockroach_effect
	"""
	result = {}

	# Next report from earnings_dates
	if isinstance(earnings_dates, dict) and not earnings_dates.get("error"):
		dates_col = earnings_dates.get("Earnings Date", {})
		eps_est_col = earnings_dates.get("EPS Estimate", {})
		if isinstance(dates_col, dict) and dates_col:
			first_key = next(iter(dates_col), None)
			if first_key is not None:
				result["next_report"] = {
					"date": dates_col.get(first_key),
					"eps_estimate": eps_est_col.get(first_key) if isinstance(eps_est_col, dict) else None,
				}

	# Surprise history from earnings_surprise — restructure flat → nested
	surprise = earnings_surprise if isinstance(earnings_surprise, dict) and not earnings_surprise.get("error") else {}
	history = surprise.get("history") or surprise.get("surprise_history") or []

	nested_history = []
	if isinstance(history, list):
		for entry in history[:8]:
			if not isinstance(entry, dict):
				continue
			nested_entry = {
				"date": entry.get("date"),
				"eps": {
					"estimate": entry.get("estimate"),
					"actual": entry.get("actual"),
					"surprise_pct": entry.get("surprise_pct"),
					"pct_skipped_reason": entry.get("pct_skipped_reason"),
					"beat": entry.get("beat"),
					"yoy_pct": entry.get("eps_yoy_pct"),
					"qoq_pct": entry.get("eps_qoq_pct"),
				},
				"revenue": {
					"actual": entry.get("revenue"),
					"yoy_pct": entry.get("revenue_yoy_pct"),
					"qoq_pct": entry.get("revenue_qoq_pct"),
				},
				"post_er_gap": entry.get("post_er_gap"),
				"post_er_return_1d": entry.get("post_er_return_1d"),
				"post_er_return_5d": entry.get("post_er_return_5d"),
			}
			nested_history.append(nested_entry)

	result["surprise_history"] = nested_history
	result["consecutive_beats"] = surprise.get("consecutive_beats")
	result["avg_surprise_pct"] = surprise.get("avg_surprise_pct")

	# Cockroach effect classification
	beats = surprise.get("consecutive_beats")
	if isinstance(beats, (int, float)):
		if beats >= 4:
			result["cockroach_effect"] = "strong"
		elif beats >= 2:
			result["cockroach_effect"] = "moderate"
		else:
			result["cockroach_effect"] = "weak"
	else:
		result["cockroach_effect"] = "unknown"

	return result


def _clean_analyst_revisions(data, earnings_estimate=None, revenue_estimate=None):
	"""Merge eps_revisions, eps_trend, growth_estimates, earnings_estimate,
	and revenue_estimate into horizon-based structure with nested eps/revenue sub-objects.

	Converts column-oriented yfinance data into per-horizon objects with
	computed trend direction and net revision counts.

	Args:
		data: Raw analyst_revisions output (eps_revisions, eps_trend, growth_estimates)
		earnings_estimate: Optional earnings estimate data (avg, low, high, yearAgoEps, growth per horizon)
		revenue_estimate: Optional revenue estimate data (avg, low, high, yearAgoRevenue, growth per horizon)
	"""
	if not isinstance(data, dict) or data.get("error"):
		return data

	eps_rev = data.get("eps_revisions") or {}
	eps_trend = data.get("eps_trend") or {}

	# Normalize estimate data (handle error responses)
	if isinstance(earnings_estimate, dict) and earnings_estimate.get("error"):
		earnings_estimate = None
	if isinstance(revenue_estimate, dict) and revenue_estimate.get("error"):
		revenue_estimate = None

	horizons = ("0q", "+1q", "0y", "+1y")
	by_horizon = {}

	total_up_7d = 0
	total_down_7d = 0
	total_up_30d = 0
	total_down_30d = 0
	rising_count = 0
	falling_count = 0
	comparable_count = 0

	# Pre-extract column dicts (eps_trend)
	trend_current = eps_trend.get("current", {}) if isinstance(eps_trend, dict) else {}
	trend_7d = eps_trend.get("7daysAgo", {}) if isinstance(eps_trend, dict) else {}
	trend_30d = eps_trend.get("30daysAgo", {}) if isinstance(eps_trend, dict) else {}
	trend_90d = eps_trend.get("90daysAgo", {}) if isinstance(eps_trend, dict) else {}

	# Pre-extract column dicts (eps_revisions)
	up7_col = eps_rev.get("upLast7days", {}) if isinstance(eps_rev, dict) else {}
	down7_col = eps_rev.get("downLast7days", {}) if isinstance(eps_rev, dict) else {}
	up30_col = eps_rev.get("upLast30days", {}) if isinstance(eps_rev, dict) else {}
	down30_col = eps_rev.get("downLast30days", {}) if isinstance(eps_rev, dict) else {}

	# Pre-extract earnings_estimate columns
	ee_avg = earnings_estimate.get("avg", {}) if isinstance(earnings_estimate, dict) else {}
	ee_low = earnings_estimate.get("low", {}) if isinstance(earnings_estimate, dict) else {}
	ee_high = earnings_estimate.get("high", {}) if isinstance(earnings_estimate, dict) else {}
	ee_yago = earnings_estimate.get("yearAgoEps", {}) if isinstance(earnings_estimate, dict) else {}
	ee_growth = earnings_estimate.get("growth", {}) if isinstance(earnings_estimate, dict) else {}

	# Pre-extract revenue_estimate columns
	re_avg = revenue_estimate.get("avg", {}) if isinstance(revenue_estimate, dict) else {}
	re_low = revenue_estimate.get("low", {}) if isinstance(revenue_estimate, dict) else {}
	re_high = revenue_estimate.get("high", {}) if isinstance(revenue_estimate, dict) else {}
	re_growth = revenue_estimate.get("growth", {}) if isinstance(revenue_estimate, dict) else {}

	for h in horizons:
		# Build eps sub-object
		eps_entry = {}
		if isinstance(trend_current, dict) and h in trend_current:
			eps_entry["current"] = trend_current[h]
		if isinstance(trend_7d, dict) and h in trend_7d:
			eps_entry["7d_ago"] = trend_7d[h]
		if isinstance(trend_30d, dict) and h in trend_30d:
			eps_entry["30d_ago"] = trend_30d[h]
		if isinstance(trend_90d, dict) and h in trend_90d:
			eps_entry["90d_ago"] = trend_90d[h]

		# EPS low/high/yoy_pct from earnings_estimate
		if isinstance(ee_low, dict) and h in ee_low:
			eps_entry["low"] = ee_low[h]
		if isinstance(ee_high, dict) and h in ee_high:
			eps_entry["high"] = ee_high[h]
		if isinstance(ee_growth, dict) and h in ee_growth:
			g = ee_growth[h]
			eps_entry["yoy_pct"] = round(g * 100, 2) if isinstance(g, (int, float)) else None

		# eps_revisions fields
		if isinstance(up7_col, dict) and h in up7_col:
			val = up7_col[h] or 0
			eps_entry["up_7d"] = up7_col[h]
			total_up_7d += val
		if isinstance(down7_col, dict) and h in down7_col:
			val = down7_col[h] or 0
			eps_entry["down_7d"] = down7_col[h]
			total_down_7d += val
		if isinstance(up30_col, dict) and h in up30_col:
			val = up30_col[h] or 0
			eps_entry["up_30d"] = up30_col[h]
			total_up_30d += val
		if isinstance(down30_col, dict) and h in down30_col:
			val = down30_col[h] or 0
			eps_entry["down_30d"] = down30_col[h]
			total_down_30d += val

		# Build revenue sub-object from revenue_estimate
		rev_entry = {}
		if isinstance(re_avg, dict) and h in re_avg:
			rev_entry["avg"] = re_avg[h]
		if isinstance(re_low, dict) and h in re_low:
			rev_entry["low"] = re_low[h]
		if isinstance(re_high, dict) and h in re_high:
			rev_entry["high"] = re_high[h]
		if isinstance(re_growth, dict) and h in re_growth:
			g = re_growth[h]
			rev_entry["yoy_pct"] = round(g * 100, 2) if isinstance(g, (int, float)) else None

		# Build horizon entry with nested eps/revenue
		horizon_entry = {}
		if eps_entry:
			horizon_entry["eps"] = eps_entry
		if rev_entry:
			horizon_entry["revenue"] = rev_entry

		if horizon_entry:
			by_horizon[h] = horizon_entry

		# trend_direction: compare eps current vs 30d_ago per horizon
		eps_cur = eps_entry.get("current")
		eps_30d_val = eps_entry.get("30d_ago")
		if isinstance(eps_cur, (int, float)) and isinstance(eps_30d_val, (int, float)):
			comparable_count += 1
			if eps_cur > eps_30d_val:
				rising_count += 1
			elif eps_cur < eps_30d_val:
				falling_count += 1

	# Majority rule for trend_direction
	if comparable_count > 0 and rising_count > comparable_count / 2:
		trend_direction = "rising"
	elif comparable_count > 0 and falling_count > comparable_count / 2:
		trend_direction = "falling"
	else:
		trend_direction = "stable"

	return {
		"by_horizon": by_horizon,
		"trend_direction": trend_direction,
		"net_revisions_7d": total_up_7d - total_down_7d,
		"net_revisions_30d": total_up_30d - total_down_30d,
		"thresholds": {
			"rising": "majority horizons eps current > eps 30d_ago",
			"falling": "majority horizons eps current < eps 30d_ago",
			"stable": "mixed",
		},
	}
