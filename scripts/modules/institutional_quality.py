#!/usr/bin/env python3
"""Institutional Ownership Quality Scorer rating holder quality 1-10 based on type classification.

Classifies institutional holders into categories (passive, long-only, hedge, quant/market-maker)
and computes a weighted quality score. Higher scores indicate ownership dominated by patient,
long-term capital; lower scores indicate short-term or momentum-driven holders.

Args:
				symbol (str): Stock ticker symbol (e.g., "NBIS", "AAPL", "MSFT")
				command (str): One of score, compare

Returns:
				dict: Structure varies by command, typical fields include:
				{
								"symbol": str,                  # Ticker symbol
								"io_quality_score": float,      # Weighted quality score 1-10
								"total_institutional_holders": int,
								"classified_breakdown": {
												"passive_pct": float,       # Percentage of shares held by passive/index funds
												"long_only_pct": float,     # Percentage held by quality active managers
												"hedge_pct": float,         # Percentage held by hedge funds
												"quant_mm_pct": float,      # Percentage held by quant/market-maker firms
												"unclassified_pct": float   # Percentage held by unclassified holders
								},
								"top_holders_classified": [
												{
																"name": str,            # Holder name
																"shares": int,          # Share count
																"type": str             # PASSIVE, LONG_ONLY, HEDGE, QUANT_MM, UNCLASSIFIED
												}
								],
								"interpretation": str,          # Human-readable quality assessment
								"io_thresholds": str,           # Static: score range descriptions
								"io_interpretation": str        # Dynamic: context-aware reading with breakdown detail
				}

Example:
				>>> python institutional_quality.py score NBIS
				{
								"symbol": "NBIS",
								"io_quality_score": 7.2,
								"total_institutional_holders": 150,
								"classified_breakdown": {
												"passive_pct": 18.5,
												"long_only_pct": 15.2,
												"hedge_pct": 8.1,
												"quant_mm_pct": 3.4,
												"unclassified_pct": 54.8
								},
								"top_holders_classified": [
												{"name": "Vanguard Group Inc", "shares": 5000000, "type": "PASSIVE"}
								],
								"interpretation": "Strong passive/index fund support with quality active managers"
				}

				>>> python institutional_quality.py compare NBIS AAPL
				{
								"symbol_a": { ... },
								"symbol_b": { ... },
								"comparison": "AAPL has higher institutional quality (8.1 vs 7.2)"
				}

Use Cases:
				- Ownership quality screening: Filter stocks by institutional holder quality
				- Smart money tracking: Identify stocks with high long-only active manager ownership
				- Risk assessment: Stocks dominated by quant/hedge holders may face faster selloffs
				- Momentum vs value: Passive-heavy ownership suggests index inclusion stability

Notes:
				- Classification relies on keyword matching against holder names
				- Some holders may be misclassified if their name does not contain known keywords
				- Holder data from yfinance may not include all institutional holders
				- Shares held by each category are used for weighting, not holder count
				- Score is capped between 1 and 10

See Also:
				- analysis.py: Analyst recommendations and price targets
				- no_growth_valuation.py: Stress-test valuation without growth assumptions
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import yfinance as yf

# Support both standalone execution and module imports
try:
	from ..utils import error_json, output_json, safe_run
except ImportError:
	from utils import error_json, output_json, safe_run

# --- Holder classification dictionaries ---

PASSIVE_KEYWORDS = [
	"Vanguard",
	"BlackRock",
	"State Street",
	"iShares",
	"SPDR",
	"Schwab",
	"Index",
	"Northern Trust",
	"Geode Capital",
	"Dimensional",
	"SSGA",
	"Invesco S&P",
]

LONG_ONLY_KEYWORDS = [
	"Fidelity",
	"T. Rowe Price",
	"Baron",
	"Wellington",
	"Capital Research",
	"Capital Group",
	"Dodge & Cox",
	"American Funds",
	"JPMorgan",
	"JPMORGAN",
	"Morgan Stanley",
	"Goldman Sachs",
	"UBS",
	"Wells Fargo",
	"Invesco",
	"AllianceBernstein",
	"Neuberger Berman",
	"PIMCO",
	"Putnam",
	"Nuveen",
	"Franklin Templeton",
	"Norges Bank",
]

HEDGE_KEYWORDS = [
	"Tiger Global",
	"Coatue",
	"D1 Capital",
	"Dragoneer",
	"Lone Pine",
	"Viking",
	"Whale Rock",
	"Altimeter",
	"Jericho Capital",
	"Maverick Capital",
	"Third Point",
	"Pershing Square",
	"Elliott",
	"Soros",
	"Appaloosa",
	"Bridgewater",
]

QUANT_MM_KEYWORDS = [
	"Jane Street",
	"Citadel",
	"Two Sigma",
	"Susquehanna",
	"Renaissance",
	"DE Shaw",
	"Millennium",
	"Point72",
	"Virtu",
	"AQR",
	"Acadian",
	"WorldQuant",
	"Man Group",
]

CATEGORY_SCORES = {
	"PASSIVE": 10,
	"LONG_ONLY": 8,
	"HEDGE": 6,
	"QUANT_MM": 3,
	"UNCLASSIFIED": 5,
}


def _classify_holder(name):
	"""Classify a holder name into a category by keyword matching."""
	upper = name.upper()
	for kw in PASSIVE_KEYWORDS:
		if kw.upper() in upper:
			return "PASSIVE"
	for kw in LONG_ONLY_KEYWORDS:
		if kw.upper() in upper:
			return "LONG_ONLY"
	for kw in HEDGE_KEYWORDS:
		if kw.upper() in upper:
			return "HEDGE"
	for kw in QUANT_MM_KEYWORDS:
		if kw.upper() in upper:
			return "QUANT_MM"
	return "UNCLASSIFIED"


def _interpret_score(score):
	"""Return human-readable interpretation of the quality score."""
	if score >= 8:
		return "Excellent: dominated by passive/index and quality active managers"
	if score >= 6:
		return "Strong passive/index fund support with quality active managers"
	if score >= 4:
		return "Mixed institutional quality"
	return "Weak: dominated by short-term traders"


def _build_io_interpretation(score, breakdown):
	"""Build dynamic interpretation of IO quality score with breakdown context."""
	if score is None:
		return "No institutional data available to assess ownership quality."
	dom_key = max(breakdown, key=lambda k: breakdown[k])
	dom_name = dom_key.replace("_pct", "").replace("_", " ")
	dom_val = breakdown[dom_key]
	if score >= 8:
		return (f"Score {score} — excellent institutional backing, {dom_name} dominant ({dom_val}%). "
				"Quality holders less likely to panic-sell on noise.")
	if score >= 6:
		return (f"Score {score} — strong active institutional support, {dom_name} leading ({dom_val}%). "
				"Stable holder base supports price on pullbacks.")
	if score >= 4:
		return (f"Score {score} — mixed institutional quality, {dom_name} leading ({dom_val}%). "
				"Monitor for holder turnover during volatility.")
	return (f"Score {score} — weak institutional support, {dom_name} dominant ({dom_val}%). "
			"High risk of rapid exits during drawdowns.")


def _compute_quality(symbol):
	"""Compute institutional quality data for a single symbol."""
	ticker = yf.Ticker(symbol)
	holders_df = ticker.get_institutional_holders()

	if holders_df is None or holders_df.empty:
		return {
			"symbol": symbol,
			"io_quality_score": None,
			"total_institutional_holders": 0,
			"classified_breakdown": {
				"passive_pct": 0.0,
				"long_only_pct": 0.0,
				"hedge_pct": 0.0,
				"quant_mm_pct": 0.0,
				"unclassified_pct": 0.0,
			},
			"top_holders_classified": [],
			"interpretation": "No institutional holder data available",
		}

	# Determine column names (yfinance may vary casing)
	holder_col = None
	shares_col = None
	for col in holders_df.columns:
		if col.lower() in ("holder", "name"):
			holder_col = col
		if col.lower() in ("shares", "share"):
			shares_col = col

	if holder_col is None or shares_col is None:
		error_json(f"Unexpected holder DataFrame columns: {list(holders_df.columns)}")

	# Classify each holder
	classified = []
	for _, row in holders_df.iterrows():
		name = str(row[holder_col])
		shares = int(row[shares_col]) if row[shares_col] is not None else 0
		category = _classify_holder(name)
		classified.append({"name": name, "shares": shares, "type": category})

	total_holders = len(classified)
	total_shares = sum(h["shares"] for h in classified)

	if total_shares == 0:
		return {
			"symbol": symbol,
			"io_quality_score": None,
			"total_institutional_holders": total_holders,
			"classified_breakdown": {
				"passive_pct": 0.0,
				"long_only_pct": 0.0,
				"hedge_pct": 0.0,
				"quant_mm_pct": 0.0,
				"unclassified_pct": 0.0,
			},
			"top_holders_classified": classified,
			"interpretation": "Zero total shares reported",
		}

	# Aggregate shares by category
	category_shares = {"PASSIVE": 0, "LONG_ONLY": 0, "HEDGE": 0, "QUANT_MM": 0, "UNCLASSIFIED": 0}
	for h in classified:
		category_shares[h["type"]] += h["shares"]

	# Weighted average score
	weighted_sum = sum(CATEGORY_SCORES[cat] * shares for cat, shares in category_shares.items())
	quality_score = weighted_sum / total_shares
	quality_score = round(min(10, max(1, quality_score)), 1)

	# Percentage breakdown
	breakdown = {
		"passive_pct": round(category_shares["PASSIVE"] / total_shares * 100, 1),
		"long_only_pct": round(category_shares["LONG_ONLY"] / total_shares * 100, 1),
		"hedge_pct": round(category_shares["HEDGE"] / total_shares * 100, 1),
		"quant_mm_pct": round(category_shares["QUANT_MM"] / total_shares * 100, 1),
		"unclassified_pct": round(category_shares["UNCLASSIFIED"] / total_shares * 100, 1),
	}

	# Sort holders by shares descending
	top_holders = sorted(classified, key=lambda h: h["shares"], reverse=True)

	return {
		"symbol": symbol,
		"io_quality_score": quality_score,
		"total_institutional_holders": total_holders,
		"classified_breakdown": breakdown,
		"top_holders_classified": top_holders,
		"thresholds": {
			"9-10": "passive/index dominant",
			"7-8": "long-only active dominant",
			"5-6": "mixed/hedge",
			"3-4": "quant/MM dominant",
			"1-2": "no institutional support",
		},
	}


@safe_run
def cmd_score(args):
	result = _compute_quality(args.symbol)
	output_json(result)


@safe_run
def cmd_compare(args):
	result_a = _compute_quality(args.symbol1)
	result_b = _compute_quality(args.symbol2)

	score_a = result_a["io_quality_score"]
	score_b = result_b["io_quality_score"]

	if score_a is None and score_b is None:
		comparison = "No institutional data available for either symbol"
	elif score_a is None:
		comparison = f"Only {args.symbol2} has institutional data (score: {score_b})"
	elif score_b is None:
		comparison = f"Only {args.symbol1} has institutional data (score: {score_a})"
	elif score_a > score_b:
		comparison = f"{args.symbol1} has higher institutional quality ({score_a} vs {score_b})"
	elif score_b > score_a:
		comparison = f"{args.symbol2} has higher institutional quality ({score_b} vs {score_a})"
	else:
		comparison = f"Both have equal institutional quality ({score_a})"

	output_json(
		{
			"symbol_a": result_a,
			"symbol_b": result_b,
			"comparison": comparison,
		}
	)


def main():
	parser = argparse.ArgumentParser(description="Institutional ownership quality scorer")
	sub = parser.add_subparsers(dest="command", required=True)

	sp_score = sub.add_parser("score")
	sp_score.add_argument("symbol")
	sp_score.set_defaults(func=cmd_score)

	sp_compare = sub.add_parser("compare")
	sp_compare.add_argument("symbol1")
	sp_compare.add_argument("symbol2")
	sp_compare.set_defaults(func=cmd_compare)

	args = parser.parse_args()
	args.func(args)


if __name__ == "__main__":
	main()
