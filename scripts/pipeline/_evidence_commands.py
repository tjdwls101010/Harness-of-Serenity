"""Evidence-only pipeline commands — the clean surface the harness actually uses.

Each command's whole job is to LOAD deterministic evidence and hand it to the agent.
None of them grade, rank, score, or classify: `analyze` returns the full single-name
evidence dossier, `macro` returns raw gauges, `discover` returns a side-by-side metric
table. The verdict, the regime read, the ranking — all the agent's, downstream of here.
"""

from __future__ import annotations

from utils import output_json, safe_run

from ._evidence import build_evidence, _macro_inputs
from ._fetch import fetch_macro, fetch_payload, _run_parallel


@safe_run
def cmd_analyze(args):
	"""Full single-name evidence: macro gauges + fundamentals + catalysts + SEC narrative,
	normalized into the evidence contract. No verdict — the agent gates, values, and rates."""
	ticker = args.ticker.upper()
	payload = fetch_payload(ticker, skip_macro=args.skip_macro)
	output_json(build_evidence(payload, ticker))


@safe_run
def cmd_macro(args):
	"""Raw macro gauges only — ERP, VIX term structure, net liquidity, rates/real-rate,
	fed-path odds, fear/greed, DXY, BDI, and the hyperscaler CapEx cascade. NO regime or
	risk-level label: the agent reads the regime off these gauges (doctrine boundary)."""
	gauges = fetch_macro(include_capex=not args.no_capex)
	output_json({
		"evidence_contract": {
			"kind": "serenity_macro_evidence",
			"judgment_owner": "agent",
			"code_role": "load_macro_gauges",
			"boundary": "Raw gauges only — no regime/risk_level/aggregate-CapEx verdict. The agent classifies the regime.",
		},
		"macro_inputs": _macro_inputs(gauges),
	})


# Comparator metrics — raw, side by side. Each is a yfinance/derived number, never a
# pass/fail gate; the agent ranks the names against each other from these.
_DISCOVER_SCRIPTS = {
	"info": ("modules/info.py", lambda t: ["get-info-fields", t,
		"sector", "industry", "marketCap", "currentPrice", "beta",
		"grossMargins", "operatingMargins", "fiftyTwoWeekLow", "fiftyTwoWeekHigh",
		"shortPercentOfFloat"]),
	"forward_pe": ("modules/forward_pe.py", lambda t: ["calculate", t]),
	"growth_profile": ("modules/growth.py", lambda t: ["profile", t]),
	"rs_ranking": ("modules/rs_ranking.py", lambda t: ["score", t]),
	"no_growth_valuation": ("modules/no_growth_valuation.py", lambda t: ["calculate", t]),
}


@safe_run
def cmd_discover(args):
	"""Side-by-side comparator across a ticker list — a routing table, NOT a ranking
	verdict. Fans out a few quantitative modules per name and returns each name's raw
	metrics so the agent can pick which to run full `analyze` on. No triage label, no
	sort-by-score: the power-law pick is the agent's."""
	tickers = [t.upper() for t in args.tickers]

	specs = {}
	for t in tickers:
		for name, (path, argfn) in _DISCOVER_SCRIPTS.items():
			specs[(t, name)] = (path, argfn(t), 60)
	jobs = _run_parallel(specs)

	def g(d, k):
		return d.get(k) if isinstance(d, dict) and not d.get("error") else None

	candidates = []
	missing_data = {}
	for t in tickers:
		info = jobs.get((t, "info")) or {}
		fpe = jobs.get((t, "forward_pe")) or {}
		gp = jobs.get((t, "growth_profile")) or {}
		rs = jobs.get((t, "rs_ranking")) or {}
		ngv = jobs.get((t, "no_growth_valuation")) or {}

		mc = g(info, "marketCap")
		price = g(info, "currentPrice")
		low52 = g(info, "fiftyTwoWeekLow")
		high52 = g(info, "fiftyTwoWeekHigh")
		gm = g(info, "grossMargins")
		mos = g(ngv, "margin_of_safety_pct")

		row = {
			"ticker": t,
			"sector": g(info, "sector"),
			"industry": g(info, "industry"),
			"marketCap": mc,
			"currentPrice": price,
			"forward_pe_1y": g(fpe, "forward_pe_1y"),
			"forward_pe_2y": g(fpe, "forward_pe_2y"),
			"peg_ratio": g(fpe, "peg_ratio"),
			"revenue_growth_yoy": g(fpe, "revenue_growth_yoy"),
			"gross_margin_pct": round(gm * 100, 1) if isinstance(gm, (int, float)) else None,
			"eps_accelerating": g(gp, "eps_accelerating"),
			"sales_accelerating": g(gp, "sales_accelerating"),
			"rs_rating": g(rs, "rs_rating"),
			"no_growth_mos_pct": round(mos, 1) if isinstance(mos, (int, float)) else None,
			"beta": g(info, "beta"),
			"pct_above_52w_low": round((price / low52 - 1) * 100, 1)
				if isinstance(price, (int, float)) and isinstance(low52, (int, float)) and low52 > 0 else None,
			"pct_below_52w_high": round((price / high52 - 1) * 100, 1)
				if isinstance(price, (int, float)) and isinstance(high52, (int, float)) and high52 > 0 else None,
			"short_pct_float": g(info, "shortPercentOfFloat"),
		}
		missing = [k for k, v in row.items() if v is None]
		if missing:
			missing_data[t] = missing
		candidates.append(row)

	output_json({
		"evidence_contract": {
			"kind": "serenity_discovery_comparator",
			"judgment_owner": "agent",
			"code_role": "load_comparison_metrics",
			"boundary": "A side-by-side metric table for routing, NOT a ranking verdict. No triage label — the agent picks which names to analyze.",
		},
		"candidates": candidates,
		"metric_definitions": {
			"peg_ratio": "forward P/E ÷ growth — <1 cheap vs growth, 1–2 fair, >2 rich. A high P/E alone is NOT a reject.",
			"rs_rating": "IBD-style 0–99 relative strength vs all US stocks over 12 months; higher = stronger leadership.",
			"no_growth_mos_pct": "margin of safety vs a ZERO-growth fair value; a negative number is NORMAL/expected for a growth name (the floor sits below price).",
			"eps_accelerating / sales_accelerating": "whether the growth-rate sequence is increasing — momentum context, not a gate.",
			"note": "These are inputs for the agent's power-law pick, not a screen that selects for you.",
		},
		"missing_data": missing_data,
		"metadata": {"total_candidates": len(candidates)},
	})
