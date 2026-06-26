"""Deterministic data fetch for the evidence-only pipeline.

The strict split this file enforces: **code loads, the agent judges.** Everything
here is pure I/O — it runs the data modules (yfinance numbers, SEC narrative) in
parallel and hands back their RAW output. It computes no regime, no score, no flag,
no archetype, no verdict. The one transform it does is mechanical reshaping that the
evidence layer needs (pop quarterly financials into a revenue trajectory) — never a
judgment.

Why no regime classification lives here (the deliberate omission): the legacy
`_classify_macro_regime` collapsed a dozen gauges into a single `regime`/`risk_level`
label inside the code. That label is exactly the kind of judgment that drifts
run-to-run and silently inverts a call — so it is the agent's, formed from the raw
gauges this module returns, never the pipeline's.
"""

from __future__ import annotations

import concurrent.futures
import os
import sys

from ._runner import _run_script

# The hyperscaler CapEx cascade is, in the doctrine, *the* tell for whether the AI
# trade continues — so the macro read surfaces each name's reported CapEx and the
# module's own slope label (deterministic arithmetic on the series). It does NOT vote
# them into an aggregate "accelerating/decelerating" call; that synthesis is the agent's.
HYPERSCALERS = ("MSFT", "GOOG", "META", "AMZN")

# Macro gauge scripts — raw evidence only (no regime synthesis on top).
_MACRO_SCRIPTS = {
	"net_liquidity": ("modules/net_liquidity.py", ["net-liquidity", "--limit", "10"]),
	"vix_curve": ("modules/vix_curve.py", ["analyze"]),
	"fedwatch": ("modules/fedwatch.py", []),
	"yield_curve": ("modules/rates.py", ["yield-curve", "--limit", "5"]),
	"erp": ("modules/erp.py", ["erp"]),
	"fear_greed": ("modules/fear_greed.py", []),
	"dxy": ("modules/dxy.py", []),
	"bdi": ("modules/bdi.py", []),
	"breakeven_inflation": ("modules/inflation.py", ["breakeven-inflation", "--maturity", "10y", "--limit", "5"]),
	"nominal_rates": ("modules/rates.py", ["yield-curve", "--maturities", "10y", "--limit", "5"]),
}


def _run_parallel(specs: dict, max_workers: int = 10) -> dict:
	"""Run a {name: (path, args[, timeout])} map of scripts concurrently."""
	with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
		futures = {}
		for name, spec in specs.items():
			path, args = spec[0], spec[1]
			timeout = spec[2] if len(spec) > 2 else 60
			futures[name] = executor.submit(_run_script, path, args, timeout)
		return {name: future.result() for name, future in futures.items()}


def _latest_value(series_block) -> float | None:
	"""Most-recent non-null value out of a {series_id: {date: value}} block."""
	if not isinstance(series_block, dict):
		return None
	for _sid, vals in series_block.items():
		if isinstance(vals, dict) and not vals.get("error"):
			for _date, v in sorted(vals.items(), reverse=True):
				if v is not None:
					return v
	return None


def _real_rate(macro_results: dict) -> float | None:
	"""Real rate = latest nominal 10y − latest 10y breakeven inflation. Arithmetic, not
	a judgment — the agent reads what a positive/negative real rate means for the regime."""
	nominal = _latest_value((macro_results.get("nominal_rates") or {}).get("data"))
	breakeven = _latest_value((macro_results.get("breakeven_inflation") or {}).get("data"))
	if isinstance(nominal, (int, float)) and isinstance(breakeven, (int, float)):
		return round(nominal - breakeven, 4)
	return None


def fetch_hyperscaler_capex() -> dict:
	"""Per-name reported CapEx + the module's slope label for each hyperscaler. RAW: no
	aggregate vote, no 'the AI trade is on' verdict — that read is the agent's."""
	specs = {t: ("modules/capex_tracker.py", ["track", t, "--quarters", "4"]) for t in HYPERSCALERS}
	results = _run_parallel(specs)
	out = {}
	for t in HYPERSCALERS:
		res = results.get(t) or {}
		if isinstance(res, dict) and not res.get("error"):
			symbols = res.get("symbols") or []
			sym = symbols[0] if symbols else {}
			out[t] = {
				"latest_capex": sym.get("latest_capex"),
				"avg_capex": sym.get("avg_capex"),
				"direction": sym.get("direction"),
				"quarters": sym.get("quarters"),
			}
		else:
			out[t] = {"error": (res or {}).get("error", "unavailable")}
	return out


def fetch_macro(include_capex: bool = True) -> dict:
	"""Raw macro gauges only — NO regime/risk_level classification (that is the agent's
	read of these gauges). Returns a flat dict the evidence layer passes through as
	`macro_inputs`. Deliberately not keyed under `signals` — `signals` is a reserved
	judgment word the evidence sanitizer strips."""
	results = _run_parallel(_MACRO_SCRIPTS)

	# Raw gauges only. Deliberately NOT emitted: vix_regime / bdi_demand / dxy_strength —
	# those are the source modules collapsing a number into a risk-state WORD ("panic",
	# "Extremely High"). That naming-the-meaning is the agent's read, not the code's; the
	# raw level + z-score below carry the same information without the baked-in conclusion.
	gauges: dict = {
		"erp_pct": (results.get("erp") or {}).get("current", {}).get("erp"),
		"vix_spot": (results.get("vix_curve") or {}).get("vix_spot"),
		"vix_structure": (results.get("vix_curve") or {}).get("structure_type"),  # contango/backwardation = sign of spread, a fact
		"net_liq_direction": (results.get("net_liquidity") or {}).get("net_liquidity", {}).get("direction"),
		"fear_greed": (results.get("fear_greed") or {}).get("current", {}).get("score"),
		"fedwatch_next_meeting": (results.get("fedwatch") or {}).get("next_meeting"),
		"fedwatch_probabilities": (results.get("fedwatch") or {}).get("probabilities"),
	}

	bdi = results.get("bdi") or {}
	if not bdi.get("error"):
		gauges["bdi_z_score"] = bdi.get("statistics", {}).get("z_score")
	dxy = results.get("dxy") or {}
	if not dxy.get("error"):
		gauges["dxy_z_score"] = dxy.get("statistics", {}).get("z_score")

	real_rate = _real_rate(results)
	if real_rate is not None:
		gauges["real_rate"] = real_rate

	if include_capex:
		gauges["hyperscaler_capex"] = fetch_hyperscaler_capex()

	# Drop gauges that came back fully empty so the agent sees a clean None vs a noisy
	# half-null — but keep zeros/false (those are real readings).
	return {k: v for k, v in gauges.items() if v is not None}


def _fetch_l4(ticker: str) -> dict:
	"""Fundamental + market-structure numbers the evidence layer consumes. Note `info`
	deliberately does NOT request `longBusinessSummary` — prose belongs to the SEC
	narrative subagent, not a yfinance blurb."""
	specs = {
		"info": ("modules/info.py", ["get-info-fields", ticker,
			"sector", "industry", "marketCap", "enterpriseValue",
			"currentPrice", "beta",
			"fiftyTwoWeekLow", "fiftyTwoWeekHigh",
			"fiftyDayAverage", "twoHundredDayAverage",
			"sharesOutstanding", "floatShares", "shortPercentOfFloat",
			"totalRevenue", "bookValue", "totalCash",
			"grossMargins", "operatingMargins",
			"heldPercentInsiders", "heldPercentInstitutions"]),
		"sbc_analyzer": ("modules/sbc_analyzer.py", ["get-sbc", ticker]),
		"forward_pe": ("modules/forward_pe.py", ["calculate", ticker]),
		"debt_structure": ("modules/debt_structure.py", ["analyze", ticker]),
		"institutional_quality": ("modules/institutional_quality.py", ["score", ticker]),
		"no_growth_valuation": ("modules/no_growth_valuation.py", ["calculate", ticker]),
		"margin_tracker": ("modules/margin_tracker.py", ["track", ticker]),
		"iv_context": ("modules/iv_context.py", ["analyze", ticker]),
		"rs_ranking": ("modules/rs_ranking.py", ["score", ticker]),
		"capex_trend": ("modules/capex_tracker.py", ["track", ticker, "--quarters", "8"]),
		"quarterly_financials": ("modules/financials.py", ["get-income-stmt", ticker, "--freq", "quarterly"]),
	}
	results = _run_parallel(specs)

	# Mechanical reshape (not judgment): the revenue trajectory the evidence layer reads
	# is enriched inside the financials module's output.
	fin = results.pop("quarterly_financials", None)
	if isinstance(fin, dict) and not fin.get("error"):
		results["revenue_trajectory"] = fin.get("revenue_trajectory", {})

	# Flatten the analyzed name's own CapEx series to the first symbol, mirroring the
	# hyperscaler shape. The module's `direction` is deterministic arithmetic on the
	# series (slope sign), the same class of fact as a QoQ change — not a verdict.
	cap = results.pop("capex_trend", None)
	if isinstance(cap, dict) and not cap.get("error"):
		syms = cap.get("symbols") or []
		results["capex"] = syms[0] if syms else {}
	return results


def _fetch_l5(ticker: str) -> dict:
	"""Catalyst numbers: earnings surprises and analyst estimate revisions. Raw module
	output — the evidence layer merges the revision horizons; the agent reads momentum."""
	specs = {
		"earnings_surprise": ("modules/surprise.py", ["history", ticker]),
		"earnings_dates": ("modules/actions.py", ["get-earnings-dates", ticker, "--limit", "8"]),
		"analyst_price_targets": ("modules/analysis.py", ["get-analyst-price-targets", ticker]),
		"analyst_recommendations": ("modules/analysis.py", ["get-recommendations-summary", ticker]),
		"analyst_revisions": ("modules/analysis.py", ["get-revisions", ticker]),
		"earnings_estimate": ("modules/analysis.py", ["get-earnings-estimate", ticker]),
		"revenue_estimate": ("modules/analysis.py", ["get-revenue-estimate", ticker]),
		"insider_flow": ("modules/actions.py", ["get-insider", ticker]),
	}
	return _run_parallel(specs)


def _extract_sec_supply_chain(ticker: str) -> dict:
	"""SEC supply-chain EVIDENCE: relationship prose + deterministic XBRL quantities
	(geographic revenue, customer concentration, inventory, purchase obligations).

	NOTE — this still routes the narrative through sec-analyzer (an LLM over the filing),
	which is exactly the non-determinism the architecture is moving OFF: the edgartools
	rework will pull the XBRL numbers deterministically here and hand the narrative to the
	`serenity-filings` subagent. Kept for now so the active path is self-contained and the
	SEC evidence keeps flowing. On any failure it returns an error dict — the evidence
	layer reads a silent/failed filing as null, never as a fabricated fact."""
	try:
		from dotenv import load_dotenv
		_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
			os.path.dirname(os.path.abspath(__file__))))), ".env")
		load_dotenv(_env)
		from sec_analyzer import extract as _sec_extract
		from pipeline._bottleneck import SerenitySupplyChain as _SCPreset
		result = _sec_extract(ticker, preset=_SCPreset)
	except Exception as e:
		print(f"[sec-analyzer] extraction failed: {e}", file=sys.stderr)
		return {"error": f"sec-analyzer extraction failed: {e}"}

	classification = result.get("data", {}) or {}
	filing = result.get("filing", {}) or {}

	# Deterministic XBRL supplement (optional — never required; failure is silent).
	xbrl = {}
	try:
		from sec_analyzer import extract_xbrl as _sec_xbrl
		xres = _sec_xbrl(ticker, form=filing.get("form", "10-K"))
		if xres and xres.get("xbrl_available"):
			xbrl = xres.get("data", {}) or {}
	except Exception as e:
		print(f"[sec-analyzer] XBRL supplement failed: {e}", file=sys.stderr)

	return {
		"data": {
			"filing": filing,
			"classification": classification,
			"xbrl": xbrl,
		},
		"metadata": {"symbol": ticker, "form": filing.get("form", "10-K")},
	}


def _fetch_sec(ticker: str) -> dict:
	"""SEC narrative + events. Degrades to error dicts when SEC is unreachable — the
	evidence layer treats a silent filing as null, never as a fabricated fact."""
	specs = {
		"sec_events": ("modules/events.py", ["events", ticker, "--limit", "5", "--days", "180"], 120),
	}
	results = _run_parallel(specs)
	return {
		"sec_supply_chain": _extract_sec_supply_chain(ticker),
		"sec_events": results.get("sec_events", {}),
	}


def fetch_payload(ticker: str, skip_macro: bool = False) -> dict:
	"""Assemble the full evidence payload `{l1, l4, l5, sec_sc}` that `build_evidence`
	consumes. Pure data load — every judgment is downstream of this, in the agent."""
	ticker = ticker.upper()
	l1 = None if skip_macro else fetch_macro(include_capex=True)
	with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
		f_l4 = executor.submit(_fetch_l4, ticker)
		f_l5 = executor.submit(_fetch_l5, ticker)
		f_sec = executor.submit(_fetch_sec, ticker)
		l4 = f_l4.result()
		l5 = f_l5.result()
		sec_sc = f_sec.result()
	return {"l1": l1, "l4": l4, "l5": l5, "sec_sc": sec_sc}
