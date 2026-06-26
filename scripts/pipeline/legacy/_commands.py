"""Serenity pipeline command implementations."""

import concurrent.futures
import os
from datetime import datetime, timedelta

from utils import output_json, safe_run

from .._runner import _run_script
from ._health import _extract_health_gates
from .._bottleneck import _build_l3_bottleneck
from .._postprocess import (
	_merge_earnings, _clean_analyst_revisions,
)
from ._macro import _classify_macro_regime
from ._control import (
	_build_materiality_signals, _build_causal_bridge,
	_build_priced_in_assessment, _build_institutional_flow, _build_expression_layer,
)
from ._signals import (
	derive_core_signals, _classify_dilution,
)

def _extract_sec_supply_chain(ticker):
	"""Extract the enum-first supply-chain classification via sec-analyzer,
	supplemented with deterministic XBRL quantities (purchase obligations,
	geographic revenue, inventory, customer concentration)."""
	try:
		import os
		from dotenv import load_dotenv
		_env = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
			os.path.dirname(os.path.abspath(__file__))))), ".env")
		load_dotenv(_env)
		from sec_analyzer import extract as _sec_extract
		from pipeline._bottleneck import SerenitySupplyChain as _SCPreset
		result = _sec_extract(ticker, preset=_SCPreset)
	except Exception as e:
		import sys
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
		import sys
		print(f"[sec-analyzer] XBRL supplement failed: {e}", file=sys.stderr)

	# Graded signal count (drives _health.py SEC_SC_available/partial). Counts
	# only enums that carry positive signal — 'unknown'/'not_applicable'/
	# 'undisclosed' are non-signals.
	signal = 0
	for k in ("input_dependency", "customer_concentration", "geographic_risk", "designed_out_exposure"):
		v = classification.get(k)
		if v and v not in ("unknown", "not_applicable", "undisclosed"):
			signal += 1
	if classification.get("capacity_constrained"):
		signal += 1
	if classification.get("critical_input"):
		signal += 1

	return {
		"data": {
			"filing": filing,
			"classification": classification,
			"xbrl": xbrl,
			"extraction_stats": {
				"total_matches": signal,
				"mode": "llm_enum",
			},
		},
		"metadata": {"symbol": ticker, "form": filing.get("form", "10-K")},
	}


@safe_run
def cmd_macro(args):
	"""Level 1 Macro Regime Assessment.

	Runs macro scripts in parallel to assess the current risk environment.
	Classifies regime as risk_on, risk_off, or transitional.
	"""
	scripts = {
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

	with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
		futures = {
			name: executor.submit(_run_script, path, a)
			for name, (path, a) in scripts.items()
		}
		results = {name: future.result() for name, future in futures.items()}

	# Compute real rate from nominal - breakeven inflation (before regime classification)
	real_rate = None
	nominal_data = results.get("nominal_rates", {})
	breakeven_data = results.get("breakeven_inflation", {})
	try:
		nominal_series = nominal_data.get("data", {})
		breakeven_series = breakeven_data.get("data", {})
		nominal_val = None
		for _sid, vals in nominal_series.items():
			if isinstance(vals, dict) and not vals.get("error"):
				for _date, v in sorted(vals.items(), reverse=True):
					if v is not None:
						nominal_val = v
						break
				break
		breakeven_val = None
		for _sid, vals in breakeven_series.items():
			if isinstance(vals, dict) and not vals.get("error"):
				for _date, v in sorted(vals.items(), reverse=True):
					if v is not None:
						breakeven_val = v
						break
				break
		if isinstance(nominal_val, (int, float)) and isinstance(breakeven_val, (int, float)):
			real_rate = round(nominal_val - breakeven_val, 4)
			results["real_rate"] = real_rate
	except Exception:
		pass

	# Classify regime (after real_rate is available in results)
	classification = _classify_macro_regime(results)

	signals = {
		"erp_pct": results.get("erp", {}).get("current", {}).get("erp"),
		"vix_spot": results.get("vix_curve", {}).get("vix_spot"),
		"vix_regime": results.get("vix_curve", {}).get("regime"),
		"vix_structure": results.get("vix_curve", {}).get("structure_type"),
		"net_liq_direction": results.get("net_liquidity", {})
			.get("net_liquidity", {}).get("direction"),
		"fear_greed": results.get("fear_greed", {}).get("current", {}).get("score"),
		"fedwatch_next_meeting": results.get("fedwatch", {}).get("next_meeting"),
		"fedwatch_probabilities": results.get("fedwatch", {}).get("probabilities"),
	}

	# BDI/DXY z-score summaries only (no detailed recent_values)
	bdi = results.get("bdi", {})
	if not bdi.get("error"):
		signals["bdi_z_score"] = bdi.get("statistics", {}).get("z_score")
		signals["bdi_demand"] = bdi.get("shipping_demand")
	dxy = results.get("dxy", {})
	if not dxy.get("error"):
		signals["dxy_z_score"] = dxy.get("statistics", {}).get("z_score")
		signals["dxy_strength"] = dxy.get("dollar_strength")

	# Real rate
	if real_rate is not None:
		signals["real_rate"] = real_rate

	output = {
		"regime": classification["regime"],
		"risk_level": classification["risk_level"],
		"regime_thresholds": classification["regime_thresholds"],
		"signals": signals,
	}

	output_json(output)


@safe_run
def cmd_analyze(args):
	"""Full 6-Level Analysis for a single ticker.

	Auto-executes L1 (macro), L4 (fundamentals), L5 (catalysts).
	L2 (CapEx Flow) and L3 (Bottleneck) require agent context.
	L6 (Taxonomy) requires LLM classification.
	Extracts health gates from L4 results.
	"""
	ticker = args.ticker.upper()

	# --- Level 1: Macro Regime ---
	l1_result = None
	if not args.skip_macro:
		macro_scripts = {
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

		with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
			futures = {
				name: executor.submit(_run_script, path, a)
				for name, (path, a) in macro_scripts.items()
			}
			macro_results = {name: future.result() for name, future in futures.items()}

		# Compute real rate from nominal - breakeven inflation
		real_rate = None
		nominal_data = macro_results.get("nominal_rates", {})
		breakeven_data = macro_results.get("breakeven_inflation", {})
		try:
			nominal_series = nominal_data.get("data", {})
			breakeven_series = breakeven_data.get("data", {})
			nominal_val = None
			for _sid, vals in nominal_series.items():
				if isinstance(vals, dict) and not vals.get("error"):
					for _date, v in sorted(vals.items(), reverse=True):
						if v is not None:
							nominal_val = v
							break
					break
			breakeven_val = None
			for _sid, vals in breakeven_series.items():
				if isinstance(vals, dict) and not vals.get("error"):
					for _date, v in sorted(vals.items(), reverse=True):
						if v is not None:
							breakeven_val = v
							break
					break
			if isinstance(nominal_val, (int, float)) and isinstance(breakeven_val, (int, float)):
				real_rate = round(nominal_val - breakeven_val, 4)
				macro_results["real_rate"] = real_rate
		except Exception:
			pass

		classification = _classify_macro_regime(macro_results)
		signals = {
			"erp_pct": macro_results.get("erp", {}).get("current", {}).get("erp"),
			"vix_spot": macro_results.get("vix_curve", {}).get("vix_spot"),
			"vix_regime": macro_results.get("vix_curve", {}).get("regime"),
			"vix_structure": macro_results.get("vix_curve", {}).get("structure_type"),
			"net_liq_direction": macro_results.get("net_liquidity", {})
				.get("net_liquidity", {}).get("direction"),
			"fear_greed": macro_results.get("fear_greed", {}).get("current", {}).get("score"),
			"fedwatch_next_meeting": macro_results.get("fedwatch", {}).get("next_meeting"),
			"fedwatch_probabilities": macro_results.get("fedwatch", {}).get("probabilities"),
		}
		bdi = macro_results.get("bdi", {})
		if not bdi.get("error"):
			signals["bdi_z_score"] = bdi.get("statistics", {}).get("z_score")
			signals["bdi_demand"] = bdi.get("shipping_demand")
		dxy = macro_results.get("dxy", {})
		if not dxy.get("error"):
			signals["dxy_z_score"] = dxy.get("statistics", {}).get("z_score")
			signals["dxy_strength"] = dxy.get("dollar_strength")
		if real_rate is not None:
			signals["real_rate"] = real_rate
		l1_result = {
			"regime": classification["regime"],
			"risk_level": classification["risk_level"],
			"regime_thresholds": classification["regime_thresholds"],
			"signals": signals,
		}

	# --- Level 4: Position Construction (Fundamentals) ---
	l4_scripts = {
		"info": ("modules/info.py", ["get-info-fields", ticker,
			"sector", "industry", "marketCap", "enterpriseValue",
			"longBusinessSummary", "currentPrice", "beta",
			"fiftyTwoWeekLow", "fiftyTwoWeekHigh",
			"fiftyDayAverage", "twoHundredDayAverage",
			"sharesOutstanding", "floatShares", "shortPercentOfFloat",
			"totalRevenue", "bookValue", "totalCash",
			"grossMargins", "operatingMargins",
			"heldPercentInsiders", "heldPercentInstitutions"]),
		"insider_transactions": ("modules/actions.py", ["get-insider", ticker]),
		"growth_profile": ("modules/growth.py", ["profile", ticker]),
		"rs_ranking": ("modules/rs_ranking.py", ["score", ticker]),
		"sbc_analyzer": ("modules/sbc_analyzer.py", ["get-sbc", ticker]),
		"forward_pe": ("modules/forward_pe.py", ["calculate", ticker]),
		"debt_structure": ("modules/debt_structure.py", ["analyze", ticker]),
		"institutional_quality": ("modules/institutional_quality.py", ["score", ticker]),
		"no_growth_valuation": ("modules/no_growth_valuation.py", ["calculate", ticker]),
		"margin_tracker": ("modules/margin_tracker.py", ["track", ticker]),
		"iv_context": ("modules/iv_context.py", ["analyze", ticker]),
		"capex_trend": ("modules/capex_tracker.py", ["track", ticker, "--quarters", "8"]),
		"quarterly_financials": ("modules/financials.py", [
			"get-income-stmt", ticker, "--freq", "quarterly"]),
	}

	# --- Level 5: Catalyst Monitoring ---
	l5_scripts = {
		"earnings_dates": ("modules/actions.py", ["get-earnings-dates", ticker, "--limit", "8"]),
		"earnings_surprise": ("modules/surprise.py", ["history", ticker]),
		"analyst_recommendations": ("modules/analysis.py", ["get-recommendations-summary", ticker]),
		"analyst_price_targets": ("modules/analysis.py", ["get-analyst-price-targets", ticker]),
		"analyst_revisions": ("modules/analysis.py", ["get-revisions", ticker]),
		"earnings_estimate": ("modules/analysis.py", ["get-earnings-estimate", ticker]),
		"revenue_estimate": ("modules/analysis.py", ["get-revenue-estimate", ticker]),
	}

	# --- Hyperscaler CapEx Bridge (L2) ---
	hyperscaler_tickers = ["MSFT", "GOOG", "META", "AMZN"]
	hs_scripts = {
		f"hs_capex_{t}": ("modules/capex_tracker.py", ["track", t, "--quarters", "4"])
		for t in hyperscaler_tickers
	}

	# Run L4, L5, SEC events, and Hyperscaler CapEx in parallel
	# SEC supply chain uses sec-analyzer library (direct call, not script)
	all_scripts = {}
	all_scripts.update(l4_scripts)
	all_scripts.update(l5_scripts)
	all_scripts.update(hs_scripts)

	with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
		futures = {}
		for name, spec in all_scripts.items():
			path, a = spec[0], spec[1]
			t = spec[2] if len(spec) > 2 else 60
			futures[name] = executor.submit(_run_script, path, a, t)
		# SEC supply chain + events in parallel with scripts
		futures["sec_supply_chain"] = executor.submit(_extract_sec_supply_chain, ticker)
		futures["sec_events"] = executor.submit(
			_run_script, "modules/events.py",
			["events", ticker, "--limit", "5", "--days", "180"], 120)
		all_results = {name: future.result() for name, future in futures.items()}

	# Split results
	l4_results = {k: all_results[k] for k in l4_scripts}
	l5_results = {k: all_results[k] for k in l5_scripts}
	sec_sc_results = {
		"sec_supply_chain": all_results["sec_supply_chain"],
		"sec_events": all_results["sec_events"],
	}

	# --- Build Hyperscaler CapEx Bridge Signal ---
	hyperscaler_signal = None
	hs_directions = []
	for t in hyperscaler_tickers:
		hs_result = all_results.get(f"hs_capex_{t}", {})
		if not hs_result.get("error"):
			symbols_data = hs_result.get("symbols", [])
			sym_data = symbols_data[0] if symbols_data else {}
			direction = sym_data.get("direction", "unknown")
			if direction and direction != "unknown":
				hs_directions.append(direction)
	if hs_directions:
		hs_inc = sum(1 for d in hs_directions if d.lower() in ("increasing", "up", "accelerating"))
		hyperscaler_signal = {
			"aggregate_direction": "increasing" if hs_inc > len(hs_directions) / 2 else "decreasing" if hs_inc == 0 else "mixed",
			"increasing_count": hs_inc,
			"total_count": len(hs_directions),
		}

	# --- Post-processing ---
	# Revenue trajectory from quarterly financials (enriched by module)
	financials_raw = l4_results.pop("quarterly_financials", None)
	if financials_raw and not (isinstance(financials_raw, dict) and financials_raw.get("error")):
		l4_results["revenue_trajectory"] = financials_raw.get("revenue_trajectory", {})

	# Use compressed view from module output (removes symbol)
	ea_raw = l4_results.get("growth_profile")
	if ea_raw and not (isinstance(ea_raw, dict) and ea_raw.get("error")):
		compressed = ea_raw.get("compressed")
		if compressed:
			l4_results["growth_profile"] = compressed
		else:
			# Fallback: inline compress if module didn't provide compressed field
			l4_results["growth_profile"] = {
				"eps_accelerating": ea_raw.get("eps_accelerating"),
				"margin_expanding": ea_raw.get("margin_expanding"),
				"eps_growth_rates": ea_raw.get("eps_growth_rates", [])[:3],
				"data_quality": ea_raw.get("data_quality"),
			}

	# Move capex_trend from L4 to L2
	capex_data = l4_results.pop("capex_trend", None)

	# --- L2: Flatten capex data ---
	l2_capex_flow = {}
	if capex_data and not capex_data.get("error"):
		symbols_list = capex_data.get("symbols") or []
		if symbols_list:
			sym = symbols_list[0]
			l2_capex_flow["quarters"] = sym.get("quarters", [])
			l2_capex_flow["direction"] = sym.get("direction")
			l2_capex_flow["latest_capex"] = sym.get("latest_capex")
			l2_capex_flow["avg_capex"] = sym.get("avg_capex")
	l2_capex_flow["hyperscaler_signal"] = hyperscaler_signal
	capex_direction = l2_capex_flow.get("direction")

	# --- L3 + Health + Derived signals + Composite (deterministic core) ---
	# derive_core_signals is the SINGLE source of truth for the scoring layer;
	# the golden regression harness replays this exact function on frozen inputs.
	core = derive_core_signals(l1_result, l4_results, l5_results, sec_sc_results)
	l3_data = core["l3_data"]
	health_gates = core["health_gates"]
	thesis_signals = core["thesis_signals"]
	sop_triggers = core["sop_triggers"]
	dilution_classification = core["dilution_classification"]
	objective_screen = core["objective_screen"]

	# Optional capture hook for the golden regression harness — env-gated, a no-op
	# in normal runs. Freezes the scoring INPUTS (before any network-only output
	# enrichment) so they can be replayed offline through derive_core_signals.
	_cap_dir = os.environ.get("SERENITY_CAPTURE_DIR")
	if _cap_dir:
		from ._regression import capture_inputs
		capture_inputs(_cap_dir, ticker, l1_result, l4_results, l5_results, sec_sc_results)

	# Conditional SEC filing check for active dilution (network + output-only; it
	# never feeds the score, so it runs AFTER the deterministic core).
	sec_filing_result = None
	if health_gates.get("active_dilution") == "FLAG":
		sec_filing_result = _run_script(
			"modules/filings.py",
			[ticker, "--form", "S-3", "--limit", "5"]
		)
		if sec_filing_result and not sec_filing_result.get("error"):
			l4_results["sec_dilution_check"] = sec_filing_result

	# Materiality signals
	materiality = _build_materiality_signals(l3_data, l4_results, l5_results)
	priced_in = _build_priced_in_assessment(l4_results, l5_results)
	inst_flow = _build_institutional_flow(l4_results)
	expression = _build_expression_layer(l4_results)
	# Inline valuation frame (dual-valuation: no-growth floor + growth upside)
	valuation_frame = {}
	forward_pe_data = l4_results.get("forward_pe", {})
	ngv_data = l4_results.get("no_growth_valuation", {})
	if not ngv_data.get("error"):
		mos_v = ngv_data.get("margin_of_safety_pct")
		valuation_frame["no_growth_floor"] = {
			"fair_value": ngv_data.get("no_growth_fair_value"),
			"margin_of_safety_pct": mos_v,
			"floor_vs_price": "floor_above_price" if isinstance(mos_v, (int, float)) and mos_v > 0 else "floor_below_price",
			"note": "The no-growth floor prices in ZERO growth. For a growth name the floor sitting below price is EXPECTED/healthy — a downside anchor, NOT a kill signal.",
		}
	if not forward_pe_data.get("error"):
		fp1 = forward_pe_data.get("forward_pe_1y")
		fp2 = forward_pe_data.get("forward_pe_2y")
		fp_peg = forward_pe_data.get("peg_ratio")
		pe_assess = (
			"undervalued_vs_growth" if isinstance(fp_peg, (int, float)) and fp_peg < 1.0
			else "fairly_valued_vs_growth" if isinstance(fp_peg, (int, float)) and fp_peg < 2.0
			else "expensive_vs_growth" if isinstance(fp_peg, (int, float))
			else None
		)
		valuation_frame["growth_upside"] = {
			"forward_pe_1y": fp1,
			"forward_pe_2y": fp2,
			"peg_ratio": fp_peg,
			"revenue_growth_yoy": forward_pe_data.get("revenue_growth_yoy"),
			"pe_contraction": (isinstance(fp1, (int, float)) and isinstance(fp2, (int, float)) and fp2 < fp1),
			"assessment": pe_assess,
		}

	# Causal bridge (flat dashboard)
	causal_bridge = _build_causal_bridge(
		l1_result, l3_data, l4_results, l5_results,
		capex_direction, materiality, thesis_signals,
	)
	causal_bridge["L4_health_severity"] = health_gates.get("severity_score")
	# Objective SoP + dilution hand-offs surfaced in the valuation frame (not a verdict).
	valuation_frame["sop_triggers"] = sop_triggers
	valuation_frame["dilution_classification"] = dilution_classification

	# --- Build L3 materiality into L3 output ---
	l3_data["materiality"] = {
		"supply_chain_verdict": materiality.get("supply_chain_verdict"),
		"sec_events_verdict": materiality.get("sec_events_verdict"),
	}

	# === L4: Build 5-cluster structure ===
	info = l4_results.get("info") or {}
	fpe = l4_results.get("forward_pe") or {}
	ngv = l4_results.get("no_growth_valuation") or {}
	ea = l4_results.get("growth_profile") or {}
	sbc = l4_results.get("sbc_analyzer") or {}
	debt = l4_results.get("debt_structure") or {}
	margin = l4_results.get("margin_tracker") or {}
	iq = l4_results.get("institutional_quality") or {}
	iv = l4_results.get("iv_context") or {}
	rev_traj = l4_results.get("revenue_trajectory") or {}


	# Profile: key info fields (deduplicated)
	profile = {}
	for field in ("sector", "industry", "marketCap", "enterpriseValue",
				  "longBusinessSummary", "currentPrice", "beta",
				  "fiftyDayAverage", "twoHundredDayAverage",
				  "sharesOutstanding", "floatShares", "shortPercentOfFloat"):
		if field in info:
			profile[field] = info[field]
	# 52-week position as self-documenting percentages (§2.8)
	current_price = info.get("currentPrice")
	low52 = info.get("fiftyTwoWeekLow")
	high52 = info.get("fiftyTwoWeekHigh")
	if isinstance(current_price, (int, float)) and isinstance(low52, (int, float)) and low52 > 0:
		profile["price_vs_52w_low_pct"] = {
			"value": round((current_price / low52 - 1) * 100, 1),
			"unit": "% above 52-week low",
		}
	if isinstance(current_price, (int, float)) and isinstance(high52, (int, float)) and high52 > 0:
		profile["price_vs_52w_high_pct"] = {
			"value": round((current_price / high52 - 1) * 100, 1),
			"unit": "% below 52-week high",
		}

	# Valuation: forward_pe + no_growth_valuation (remove symbol, duplicates)
	valuation_cluster = {}
	if not fpe.get("error"):
		for k, v in fpe.items():
			if k not in ("symbol", "current_price", "valuation_gap", "gross_margin_pct", "error"):
				valuation_cluster[k] = v
	if not ngv.get("error"):
		ngv_clean = {}
		for k, v in ngv.items():
			if k not in ("symbol", "error"):
				ngv_clean[k] = v
		valuation_cluster["no_growth"] = ngv_clean

	# Earnings Growth: growth_profile + revenue_trajectory + sbc
	earnings_growth = {}
	if not ea.get("error"):
		ea_clean = {k: v for k, v in ea.items() if k not in ("symbol", "code33_status", "error")}
		earnings_growth.update(ea_clean)
	if rev_traj:
		earnings_growth["revenue_trajectory"] = rev_traj
	if not sbc.get("error"):
		sbc_clean = {}
		for k, v in sbc.items():
			if k not in ("symbol", "sbc_interpretation", "shares_outstanding_current",
						  "shares_change_qoq_pct", "error"):
				sbc_clean[k] = v
		earnings_growth["sbc"] = sbc_clean

	# Financial Health: debt_structure + margin_tracker + dilution classification
	financial_health = {}
	if not debt.get("error"):
		debt_clean = {k: v for k, v in debt.items()
					  if k not in ("symbol", "grade_interpretation", "error")}
		financial_health["debt"] = debt_clean
	if not margin.get("error"):
		margin_clean = {k: v for k, v in margin.items()
						if k not in ("symbol", "margin_interpretation", "error")}
		financial_health["margins"] = margin_clean
	dilution_class = _classify_dilution(l4_results)
	if dilution_class.get("classification") != "unknown":
		financial_health["dilution"] = dilution_class

	# Market Structure: rs_ranking + institutional_quality + iv_context + short_interest
	market_structure = {}
	rs = l4_results.get("rs_ranking") or {}
	if not rs.get("error"):
		market_structure["rs_detail"] = {
			"rs_rating": rs.get("rs_rating"),
			"unit": "IBD-style percentile rank 0-99 vs all US stocks over 12 months. 99 = strongest",
			"spy_rs": rs.get("spy_rs"),
			"history": rs.get("history"),
		}
	if not iq.get("error"):
		iq_clean = {k: v for k, v in iq.items()
					if k not in ("symbol", "io_interpretation", "error")}
		market_structure["institutional_quality"] = iq_clean
	if not iv.get("error"):
		iv_clean = {k: v for k, v in iv.items()
					if k not in ("symbol", "current_price", "interpretation", "error")}
		# iv_tier, iv_regime_shift, iv_tier_thresholds now included by module
		market_structure["iv_context"] = iv_clean
	# short_interest now included by info module when shortPercentOfFloat is requested
	short_interest = info.get("short_interest", {})
	if short_interest.get("contrarian_signal") != "unknown":
		market_structure["short_interest"] = short_interest

	# L4 Assessment: health_gates + market_positioning
	l4_assessment = {
		"health_gates": health_gates,
		"market_positioning": {
			"priced_in": priced_in,
			"institutional_flow": inst_flow,
			"expression": expression,
		},
		"margin_materiality": materiality.get("margin_materiality"),
		"earnings_materiality": materiality.get("earnings_materiality"),
	}

	l4_fundamentals = {
		"profile": profile,
		"valuation": valuation_cluster,
		"earnings_growth": earnings_growth,
		"financial_health": financial_health,
		"market_structure": market_structure,
		"assessment": l4_assessment,
	}

	# === L5: Build cleaned catalysts ===
	# Merge earnings_dates + earnings_surprise
	earnings = _merge_earnings(
		l5_results.get("earnings_dates"),
		l5_results.get("earnings_surprise"),
	)

	# Analyst consensus (row-oriented view now included by module)
	rec_raw = l5_results.get("analyst_recommendations")
	if isinstance(rec_raw, dict) and not rec_raw.get("error"):
		analyst_consensus = rec_raw.get("row_oriented", rec_raw)
	else:
		analyst_consensus = rec_raw

	# Clean analyst_revisions (enriched with forward estimates)
	analyst_revisions = _clean_analyst_revisions(
		l5_results.get("analyst_revisions"),
		earnings_estimate=l5_results.get("earnings_estimate"),
		revenue_estimate=l5_results.get("revenue_estimate"),
	)

	# Analyst price targets (pass through)
	analyst_price_targets = l5_results.get("analyst_price_targets")

	l5_catalysts = {
		"earnings": earnings,
		"analyst_consensus": analyst_consensus,
		"analyst_price_targets": analyst_price_targets,
		"analyst_revisions": analyst_revisions,
		"assessment": {
			"thesis_signals": thesis_signals,
		},
	}

	# === Verdict scaffold (objective only — the call itself is the analyst's) ===
	verdict = {
		"objective_screen": objective_screen,
		"valuation_frame": valuation_frame,
		"causal_bridge": causal_bridge,
	}

	# === Key-facts ledger — the load-bearing primitives, copied verbatim from the pipeline so the
	# agent cites and divides by THESE, never an eyeballed or recalled number (the cure for the
	# input-confabulation failure mode). A figure or catalyst absent here is absent from the data. ===
	_l3d = l3_data.get("data", {}) if isinstance(l3_data, dict) else {}
	_sec_ev = _l3d.get("sec_events") or []
	_scr = objective_screen if isinstance(objective_screen, dict) else {}
	_fpe = fpe if isinstance(fpe, dict) else {}
	key_facts = {
		"ticker": ticker,
		"market_cap": info.get("marketCap"),
		"current_price": info.get("currentPrice"),
		"shares_outstanding": info.get("sharesOutstanding"),
		"forward_pe_1y": _fpe.get("forward_pe_1y"),
		"peg_ratio": _fpe.get("peg_ratio"),
		"revenue_growth_yoy": _fpe.get("revenue_growth_yoy"),
		"objective_screen_score": _scr.get("screen_score"),
		"objective_screen_max": _scr.get("screen_max"),
		"objective_flags": _scr.get("objective_flags"),
		"recent_sec_events": [
			{"date": e.get("filing_date"), "event_type": e.get("event_type")}
			for e in _sec_ev if isinstance(e, dict)
		][:6],
		"note": ("Load-bearing primitives copied verbatim from the pipeline — cite market cap / price / "
				 "multiples and the objective flags from HERE, never eyeballed or recalled, and divide every "
				 "ratio by THIS market cap. objective_screen_score is a health/value/catalyst/momentum SCREEN, "
				 "NOT a verdict and NOT a bottleneck/archetype score — the bottleneck, archetype, moat, and "
				 "rating are YOURS, from L3_bottleneck.evidence_dossier + the doctrine. A figure or catalyst "
				 "not present here is not in the data (a null field means the data was silent, not zero)."),
	}

	# === Final Output: 9 top-level keys ===
	output = {
		"ticker": ticker,
		"key_facts": key_facts,
		"L1_macro": l1_result if l1_result else {"skipped": True},
		"L2_capex_flow": l2_capex_flow,
		"L3_bottleneck": l3_data,
		"L4_fundamentals": l4_fundamentals,
		"L5_catalysts": l5_catalysts,
		"verdict": verdict,
	}

	output_json(output)


@safe_run
def cmd_discover(args):
	"""Candidate comparator: run key quantitative metrics across a ticker list.

	Lightweight discovery triage — fans out a handful of existing modules per
	ticker in parallel and returns a comparison table so the agent can pick which
	names to run full `analyze` on. Sector-agnostic.
	"""
	tickers = [t.upper() for t in args.tickers]

	per_ticker_scripts = {
		"info": ("modules/info.py", lambda t: ["get-info-fields", t,
			"sector", "industry", "marketCap", "currentPrice", "beta",
			"grossMargins", "operatingMargins", "fiftyTwoWeekLow", "fiftyTwoWeekHigh",
			"shortPercentOfFloat"]),
		"forward_pe": ("modules/forward_pe.py", lambda t: ["calculate", t]),
		"growth_profile": ("modules/growth.py", lambda t: ["profile", t]),
		"rs_ranking": ("modules/rs_ranking.py", lambda t: ["score", t]),
		"no_growth_valuation": ("modules/no_growth_valuation.py", lambda t: ["calculate", t]),
	}

	# Fan out all (ticker, script) jobs in parallel
	jobs = {}
	with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
		futures = {}
		for t in tickers:
			for name, (path, argfn) in per_ticker_scripts.items():
				futures[(t, name)] = executor.submit(_run_script, path, argfn(t), 60)
		for key, fut in futures.items():
			jobs[key] = fut.result()

	def g(d, k):
		return d.get(k) if isinstance(d, dict) and not d.get("error") else None

	candidates = []
	missing_data = {}
	for t in tickers:
		info = jobs.get((t, "info"), {}) or {}
		fpe = jobs.get((t, "forward_pe"), {}) or {}
		gp = jobs.get((t, "growth_profile"), {}) or {}
		rs = jobs.get((t, "rs_ranking"), {}) or {}
		ngv = jobs.get((t, "no_growth_valuation"), {}) or {}

		mc = g(info, "marketCap")
		price = g(info, "currentPrice")
		low52 = g(info, "fiftyTwoWeekLow")
		high52 = g(info, "fiftyTwoWeekHigh")
		gm = g(info, "grossMargins")
		peg = g(fpe, "peg_ratio")
		rev_growth = g(fpe, "revenue_growth_yoy")
		rs_rating = g(rs, "rs_rating")
		mos = g(ngv, "margin_of_safety_pct")

		row = {
			"ticker": t,
			"sector": g(info, "sector"),
			"marketCap": mc,
			"currentPrice": price,
			"forward_pe_1y": g(fpe, "forward_pe_1y"),
			"forward_pe_2y": g(fpe, "forward_pe_2y"),
			"peg_ratio": peg,
			"revenue_growth_yoy": rev_growth,
			"gross_margin_pct": round(gm * 100, 1) if isinstance(gm, (int, float)) else None,
			"eps_accelerating": gp.get("eps_accelerating") if isinstance(gp, dict) and not gp.get("error") else None,
			"sales_accelerating": gp.get("sales_accelerating") if isinstance(gp, dict) and not gp.get("error") else None,
			"rs_rating": rs_rating,
			"no_growth_mos_pct": round(mos, 1) if isinstance(mos, (int, float)) else None,
			"beta": g(info, "beta"),
			"pct_above_52w_low": round((price / low52 - 1) * 100, 1) if isinstance(price, (int, float)) and isinstance(low52, (int, float)) and low52 > 0 else None,
			"pct_below_52w_high": round((price / high52 - 1) * 100, 1) if isinstance(price, (int, float)) and isinstance(high52, (int, float)) and high52 > 0 else None,
			"short_pct_float": g(info, "shortPercentOfFloat"),
		}

		# Triage (sector-agnostic, lightweight first pass)
		growthy = isinstance(rev_growth, (int, float)) and rev_growth > 20
		cheap_peg = peg is None or (isinstance(peg, (int, float)) and peg < 1.5)
		strong_rs = isinstance(rs_rating, (int, float)) and rs_rating >= 70
		if growthy and cheap_peg and strong_rs:
			triage, reason = "investigate", "growth>20% + PEG<1.5 (or n/a) + RS>=70 — run full analyze"
		elif (isinstance(rev_growth, (int, float)) and rev_growth > 15) or (isinstance(rs_rating, (int, float)) and rs_rating >= 50):
			triage, reason = "watch", "moderate growth or relative strength — secondary candidate"
		else:
			triage, reason = "pass", "no growth/momentum edge in quick screen"
		row["triage"] = triage
		row["triage_reason"] = reason

		missing = [k for k, v in row.items() if v is None and k not in ("triage", "triage_reason")]
		if missing:
			missing_data[t] = missing
		candidates.append(row)

	order = {"investigate": 0, "watch": 1, "pass": 2}
	candidates.sort(key=lambda r: (order.get(r["triage"], 3), -(r["rs_rating"] if isinstance(r["rs_rating"], (int, float)) else 0)))

	output_json({
		"candidates": candidates,
		"thresholds": {
			"triage_investigate": "revenue_growth_yoy > 20% AND (peg_ratio < 1.5 or n/a) AND rs_rating >= 70",
			"triage_watch": "revenue_growth_yoy > 15% OR rs_rating >= 50",
			"peg_ratio": "<1 undervalued vs growth, 1-2 fair, >2 expensive (high P/E alone is NOT a reject)",
			"rs_rating": "IBD-style 0-99 relative strength vs all US stocks; >=70 = leadership",
			"no_growth_mos_pct": "margin of safety vs the no-growth floor — negative is NORMAL/expected for a growth name",
		},
		"missing_data": missing_data,
		"metadata": {"total_candidates": len(candidates), "note": "first-pass triage only — run `analyze` on investigate/watch names for the full 6-level verdict"},
	})
