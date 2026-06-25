#!/usr/bin/env python3
"""CME FedWatch Tool - FOMC rate change probabilities from Fed Funds futures.

Uses the `cme-fedwatch` PyPI library (https://pypi.org/project/cme-fedwatch/) which
computes probabilities from actual CME 30-Day Fed Funds Futures settlement prices
and FRED EFFR data. More accurate and reliable than HTML scraping.

Args:
	None (no command-line arguments required)

Returns:
	dict: {
		"next_meeting": str,					 # Date of next FOMC meeting (YYYY-MM-DD)
		"data_as_of": str,					   # Current timestamp
		"current_rate_bps": int,				 # Current target rate midpoint in basis points
		"probabilities": {
			"cut": float,						# Probability of rate cut (percent)
			"hold": float,					   # Probability of no change (percent)
			"hike": float						# Probability of rate hike (percent)
		},
		"interpretation": str,				   # Human-readable interpretation
		"rate_scenarios": [
			{
				"rate_bps": int,				 # Target rate scenario in basis points
				"rate_pct": str,				 # Rate as percentage range
				"delta_bps": int,				# Change from current rate (basis points)
				"probability": float			 # Scenario probability (percent)
			},
			...
		]
	}

Example:
	>>> python fedwatch.py
	{"next_meeting": "2026-04-29", "probabilities": {"cut": 0.0, "hold": 84.0, "hike": 16.0}, ...}

Notes:
	- Powered by cme-fedwatch library (pip install cme-fedwatch)
	- Data sources: CME Group (futures settlements), FRED (EFFR + target rate)
	- Probabilities based on daily settlement prices, not live mid-prices
"""

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from cme_fedwatch import get_probabilities

from utils import output_json, safe_run


def _parse_rate_range(rate_range: str) -> int:
	"""Parse rate range string like '3.50%-3.75%' to midpoint in basis points."""
	parts = rate_range.replace("%", "").split("-")
	low = float(parts[0])
	high = float(parts[1]) if len(parts) > 1 else low
	return int((low + high) / 2 * 100)


@safe_run
def cmd_fedwatch(args):
	"""Fetch FOMC rate probabilities via cme-fedwatch library."""
	data = get_probabilities("next")

	meeting = data["meetings"][0]
	current_target = data["current_target"]
	current_bps = _parse_rate_range(current_target)

	# Aggregate probabilities into cut/hold/hike
	cut = hold = hike = 0.0
	rate_scenarios = []
	for rate_range, prob in sorted(meeting["probabilities"].items()):
		scenario_bps = _parse_rate_range(rate_range)
		delta_bps = scenario_bps - current_bps

		if rate_range < current_target:
			cut += prob
		elif rate_range == current_target:
			hold += prob
		else:
			hike += prob

		rate_scenarios.append({
			"rate_bps": scenario_bps,
			"rate_pct": rate_range,
			"delta_bps": delta_bps,
			"probability": round(prob, 1),
		})

	# Interpretation
	probs = {"cut": round(cut, 1), "hold": round(hold, 1), "hike": round(hike, 1)}
	dominant = max(probs, key=probs.get)
	dominant_pct = probs[dominant]

	if dominant == "hold":
		interpretation = f"High Probability Hold Expected ({dominant_pct}%)"
	elif dominant == "cut":
		interpretation = f"Rate Cut Expected ({dominant_pct}%)"
	else:
		interpretation = f"Rate Hike Expected ({dominant_pct}%)"

	result = {
		"next_meeting": meeting["date"],
		"data_as_of": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
		"current_rate_bps": current_bps,
		"effr": data["effr"],
		"current_target": current_target,
		"probabilities": probs,
		"interpretation": interpretation,
		"rate_scenarios": rate_scenarios,
	}

	output_json(result)


if __name__ == "__main__":
	parser = argparse.ArgumentParser(description="CME FedWatch - FOMC rate probabilities")
	args = parser.parse_args()
	cmd_fedwatch(args)
