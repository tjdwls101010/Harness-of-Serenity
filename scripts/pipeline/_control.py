"""Control-layer builders for the Serenity pipeline.

Materiality signals, causal bridge, priced-in assessment,
institutional flow, and expression-layer logic.
"""

def _build_materiality_signals(l3_data, l4_results, l5_results):
	"""Compute materiality verdicts for L3 and L4 assessments.

	Returns supply_chain materiality (for L3) and margin/earnings
	materiality (for L4 assessment).
	"""
	l4 = l4_results or {}
	info = l4.get("info") or {}

	# 1. Supply-chain materiality — an OBJECTIVE presence read of the filing evidence
	# (the bottleneck JUDGMENT is the analyst's, from the evidence_dossier). "material"
	# when the filing actually discloses a critical input dependency or heavy controlled-
	# region exposure; "partial" for lighter relationship/geography disclosure; else "noise".
	l3 = l3_data or {}
	l3_inner = l3.get("data") or {}
	dossier = l3.get("evidence_dossier") or {}
	facts = dossier.get("filing_facts") or {}
	hr_pct = 0.0
	for e in (dossier.get("geographic_concentration") or []):
		if isinstance(e, dict):
			region = str(e.get("region", "")).lower()
			pct = e.get("revenue_pct")
			if isinstance(pct, (int, float)) and any(r in region for r in ("china", "taiwan", "hong kong")):
				hr_pct += pct

	if facts.get("critical_inputs") or hr_pct >= 30:
		supply_chain_verdict = "material"
	elif facts.get("company_relationships") or facts.get("country_exposure") or hr_pct >= 15:
		supply_chain_verdict = "partial"
	else:
		supply_chain_verdict = "noise"

	# SEC events verdict
	sec_events = l3_inner.get("sec_events") or []
	sec_events_verdict = "detected" if len(sec_events) > 0 else "none"

	# 2. Margin Materiality (from L4 margin_tracker)
	margin = l4.get("margin_tracker") or {}
	gross_margin = info.get("grossMargins")
	margin_flag = str(margin.get("flag", "")).upper()

	if "COLLAPSE" in margin_flag:
		margin_materiality = "high"
	elif "EXPANDING" in margin_flag and isinstance(gross_margin, (int, float)) and gross_margin > 0.5:
		margin_materiality = "high"
	elif "COMPRESSION" in margin_flag or "CONTRACTING" in margin_flag:
		margin_materiality = "moderate"
	else:
		margin_materiality = "low"

	# 3. Earnings Materiality (from L4/L5)
	ea = l4.get("growth_profile") or {}
	surprise = l5_results.get("earnings_surprise") or {} if l5_results else {}
	beats = surprise.get("consecutive_beats")
	sales_acc = ea.get("sales_accelerating")

	if (isinstance(beats, (int, float)) and beats >= 4) or sales_acc is True:
		earnings_materiality = "high"
	elif isinstance(beats, (int, float)) and beats >= 2:
		earnings_materiality = "moderate"
	else:
		earnings_materiality = "low"

	return {
		"supply_chain_verdict": supply_chain_verdict,
		"sec_events_verdict": sec_events_verdict,
		"margin_materiality": margin_materiality,
		"earnings_materiality": earnings_materiality,
	}



def _build_causal_bridge(l1_result, l3_data, l4_results, l5_results, capex_direction,
						   materiality, thesis_signals):
	"""Build flat causal bridge dashboard for verdict section."""
	l1 = l1_result if isinstance(l1_result, dict) else {}
	l4 = l4_results or {}
	l3 = l3_data or {}
	margin = l4.get("margin_tracker") or {}
	ngv = l4.get("no_growth_valuation") or {}
	surprise = (l5_results or {}).get("earnings_surprise") or {}
	ts = thesis_signals if isinstance(thesis_signals, dict) else {}
	mat = materiality if isinstance(materiality, dict) else {}

	# Earnings momentum
	beats = surprise.get("consecutive_beats")
	if isinstance(beats, (int, float)) and beats >= 4:
		earnings_momentum = "strong_beats"
	elif isinstance(beats, (int, float)) and beats >= 2:
		earnings_momentum = "moderate_beats"
	else:
		earnings_momentum = "weak"

	mos_pct = ngv.get("margin_of_safety_pct")

	return {
		"L1_regime": l1.get("regime", "unknown"),
		"L2_capex_direction": capex_direction or "unknown",
		"L3_materiality": mat.get("supply_chain_verdict", "unknown"),
		"L3_note": "bottleneck/archetype verdict is the analyst's — see L3_bottleneck.evidence_dossier",
		"L4_health_severity": None,  # filled by caller after health_gates
		"L4_margin_trend": str(margin.get("flag", "unknown")).upper(),
		"L4_valuation_gap_pct": round(mos_pct, 1) if isinstance(mos_pct, (int, float)) else None,
		"L5_earnings_momentum": earnings_momentum,
		"L5_thesis_direction": ts.get("net_direction", "unknown"),
	}


def _build_priced_in_assessment(l4_results, l5_results):
	"""Compute priced-in risk assessment from L4/L5 data.

	Composite score 0-100:
	- Higher score = more priced in (less upside)
	- Lower score = less priced in (more opportunity)
	"""
	l4 = l4_results or {}
	l5 = l5_results or {}
	info = l4.get("info") or {}

	signals = {}
	risk_score = 0.0

	# Signal 1: 52W Range Position (0-100)
	current = info.get("currentPrice")
	low52 = info.get("fiftyTwoWeekLow")
	high52 = info.get("fiftyTwoWeekHigh")
	range_pct = None
	if all(isinstance(v, (int, float)) for v in [current, low52, high52]) and high52 > low52:
		range_pct = round((current - low52) / (high52 - low52) * 100, 1)
		signals["52w_range_pct"] = range_pct
		if range_pct > 80:
			risk_score += 18
		elif range_pct > 60:
			risk_score += 10
		elif range_pct < 20:
			risk_score -= 5
	else:
		signals["52w_range_pct"] = None

	# Signal 2: Price vs 50d MA
	ma50 = info.get("fiftyDayAverage")
	if isinstance(current, (int, float)) and isinstance(ma50, (int, float)) and ma50 > 0:
		ma50_gap = round((current - ma50) / ma50 * 100, 1)
		signals["price_vs_50d_ma_pct"] = ma50_gap
		if ma50_gap > 20:
			risk_score += 12
		elif ma50_gap > 10:
			risk_score += 6
	else:
		signals["price_vs_50d_ma_pct"] = None

	# Signal 3: Price vs 200d MA
	ma200 = info.get("twoHundredDayAverage")
	if isinstance(current, (int, float)) and isinstance(ma200, (int, float)) and ma200 > 0:
		ma200_gap = round((current - ma200) / ma200 * 100, 1)
		signals["price_vs_200d_ma_pct"] = ma200_gap
		if ma200_gap > 30:
			risk_score += 15
		elif ma200_gap > 15:
			risk_score += 8
	else:
		signals["price_vs_200d_ma_pct"] = None

	# Signal 4: Short Interest
	si = info.get("shortPercentOfFloat")
	signals["short_interest_pct"] = round(si * 100, 1) if isinstance(si, (int, float)) else None
	if isinstance(si, (int, float)):
		if si < 0.03:
			risk_score += 8
		elif si > 0.15:
			risk_score -= 5

	# Signal 5: Analyst Price Target Gap
	pt_data = l5.get("analyst_price_targets") or {}
	mean_target = pt_data.get("mean") or pt_data.get("targetMeanPrice")
	if isinstance(current, (int, float)) and isinstance(mean_target, (int, float)) and current > 0:
		target_gap = round((mean_target - current) / current * 100, 1)
		signals["analyst_target_gap_pct"] = target_gap
		if target_gap < 5:
			risk_score += 18
		elif target_gap < 15:
			risk_score += 10
		elif target_gap > 40:
			risk_score -= 5
	else:
		signals["analyst_target_gap_pct"] = None

	# Signal 6: Revision Direction
	rev_data = l5.get("analyst_revisions") or {}
	rev_dir = rev_data.get("trend_direction", "unknown") if not rev_data.get("error") else "unknown"
	signals["revision_direction"] = rev_dir
	if rev_dir == "rising":
		risk_score += 12
	elif rev_dir == "falling":
		risk_score -= 8

	# Signal 7: Revision Magnitude — from by_horizon.0y eps change
	rev_magnitude = None
	by_horizon = rev_data.get("by_horizon", {})
	horizon_0y = by_horizon.get("0y", {})
	eps_cur = horizon_0y.get("eps_current") if isinstance(horizon_0y, dict) else None
	eps_30d = horizon_0y.get("eps_30d_ago") if isinstance(horizon_0y, dict) else None
	# Fallback: try nested eps sub-object (enriched revision format)
	if eps_cur is None and isinstance(horizon_0y, dict):
		eps_obj = horizon_0y.get("eps", {})
		if isinstance(eps_obj, dict):
			eps_cur = eps_obj.get("current")
			eps_30d = eps_obj.get("30d_ago")
	if isinstance(eps_cur, (int, float)) and isinstance(eps_30d, (int, float)) and eps_30d != 0:
		rev_magnitude = round((eps_cur - eps_30d) / abs(eps_30d) * 100, 2)
	signals["revision_magnitude"] = rev_magnitude

	# Revision magnitude weight: large revisions amplify priced-in score
	rev_magnitude_weight = 0
	net_rev_7d = rev_data.get("net_revisions_7d")
	net_rev_30d = rev_data.get("net_revisions_30d")
	if isinstance(net_rev_7d, (int, float)) and isinstance(net_rev_30d, (int, float)):
		total_net = net_rev_7d + net_rev_30d
		if total_net > 5:
			rev_magnitude_weight = 8  # strong positive revisions = more priced in
		elif total_net > 2:
			rev_magnitude_weight = 4
		elif total_net < -3:
			rev_magnitude_weight = -5  # negative revisions = less priced in
	signals["revision_magnitude_weight"] = rev_magnitude_weight
	risk_score += rev_magnitude_weight

	# Signal 8: IO Quality Score
	io_data = l4.get("institutional_quality") or {}
	io_score = io_data.get("io_quality_score")
	signals["io_quality_score"] = io_score
	if isinstance(io_score, (int, float)):
		if io_score >= 8:
			risk_score += 12
		elif io_score >= 6:
			risk_score += 6
		elif io_score <= 3:
			risk_score -= 5

	# Signal 9: ER Proximity Stale — estimates become stale near earnings
	er_proximity_stale = False
	if isinstance(l5, dict):
		ed = l5.get("earnings_dates")
		if isinstance(ed, dict) and not ed.get("error"):
			# Use days_to_next from module output (enriched by actions.py)
			days_to_er = ed.get("days_to_next")
			if days_to_er is None:
				# Fallback: parse manually
				from ._signals import _parse_days_to_earnings
				days_to_er = _parse_days_to_earnings(l5)
			if isinstance(days_to_er, (int, float)) and days_to_er <= 7:
				er_proximity_stale = True
				risk_score -= 5  # reduce priced-in confidence when ER imminent
	signals["er_proximity_stale"] = er_proximity_stale

	# Clamp and classify
	risk_score = max(0, min(100, round(risk_score)))

	if risk_score >= 55:
		assessment = "fully_priced_in"
	elif risk_score >= 30:
		assessment = "partially_priced_in"
	else:
		assessment = "not_priced_in"

	return {
		"risk_score": risk_score,
		"assessment": assessment,
		"signals": signals,
		"signal_weights": {
			"52w_range_position": "+18 (>80%) / +10 (>60%) / -5 (<20%)",
			"price_vs_50d_ma": "+12 (>20% above) / +6 (>10%)",
			"price_vs_200d_ma": "+15 (>30% above) / +8 (>15%)",
			"short_interest": "+8 (<3%) / -5 (>15%)",
			"analyst_target_gap": "+18 (<5% to target) / +10 (<15%) / -5 (>40%)",
			"revision_direction": "+12 (up) / -8 (down)",
			"revision_magnitude": "+8 (net>5) / +4 (net>2) / -5 (net<-3)",
			"io_quality": "+12 (>=8) / +6 (>=6) / -5 (<=3)",
			"er_proximity_stale": "-5 (ER within 7 days — estimates may be stale)",
			"total_range": "0-100, clamped",
			"assessment_thresholds": {"fully_priced_in": ">=55", "partially_priced_in": ">=30", "not_priced_in": "<30"},
		},
	}


def _build_institutional_flow(l4_results):
	"""Extract institutional flow signals from L4 data."""
	l4 = l4_results or {}

	# Insider direction
	insider = l4.get("insider_transactions") or {}
	insider_summary = insider.get("summary") or {}
	insider_direction = insider_summary.get("net_direction", "unknown")
	insider_net_value = insider_summary.get("net_value")

	# IO quality
	io = l4.get("institutional_quality") or {}
	io_score = io.get("io_quality_score")
	io_assessment = (
		"strong_accumulation" if isinstance(io_score, (int, float)) and io_score >= 8
		else "healthy" if isinstance(io_score, (int, float)) and io_score >= 5
		else "weak" if isinstance(io_score, (int, float))
		else "unknown"
	)

	# IV signal
	iv = l4.get("iv_context") or {}
	iv_percentile = iv.get("iv_percentile") or iv.get("percentile") or iv.get("iv_rank")
	iv_regime = (
		"elevated" if isinstance(iv_percentile, (int, float)) and iv_percentile > 70
		else "depressed" if isinstance(iv_percentile, (int, float)) and iv_percentile < 30
		else "normal" if isinstance(iv_percentile, (int, float))
		else "unknown"
	)

	# Composite flow assessment
	flow_signals = []
	# Insider BUYING is signal (cluster buys precede re-rates). Insider SELLING is
	# extreme noise — sales happen for taxes, diversification, pre-set 10b5-1 plans —
	# so it never drives a bearish read here (the "insider sells = bad" fallacy). The
	# raw direction still rides along in insider_signal for the agent to judge.
	if insider_direction == "net_buying":
		flow_signals.append("insider_accumulation")
	if io_assessment == "strong_accumulation":
		flow_signals.append("institutional_conviction")
	if io_assessment == "weak":
		flow_signals.append("institutional_exit_risk")

	flow_assessment = (
		"positive" if "insider_accumulation" in flow_signals or "institutional_conviction" in flow_signals
		else "negative" if "institutional_exit_risk" in flow_signals
		else "neutral"
	)

	return {
		"flow_assessment": flow_assessment,
		"insider_signal": insider_direction,
		"institutional_signal": io_assessment,
		"iv_signal": iv_regime,
	}


def _build_expression_layer(l4_results):
	"""Read the OBJECTIVE IV regime and hand the analyst the vehicle MENU keyed to it. The
	vehicle choice also turns on CONVICTION (bullish vs neutral), which is the analyst's call,
	not the pipeline's — so this gives the IV-driven options and lets the analyst pick on the
	verdict it forms from the evidence + doctrine."""
	l4 = l4_results or {}
	iv = l4.get("iv_context") or {}

	iv_percentile = iv.get("iv_percentile") or iv.get("percentile") or iv.get("iv_rank")

	if not isinstance(iv_percentile, (int, float)):
		regime = "unknown"
		menu = "IV data unavailable — default to shares."
	elif iv_percentile > 70:
		regime = "elevated"
		menu = (f"IV elevated ({iv_percentile}th pctl): if your verdict is bullish -> sell cash-secured "
				f"puts (harvest the fear vol for a better entry); if neutral/weak -> covered calls for income.")
	elif iv_percentile < 30:
		regime = "depressed"
		menu = (f"IV depressed ({iv_percentile}th pctl): if HIGH conviction -> LEAPS for cheap leverage; "
				f"otherwise -> shares (LEAPS need conviction the screen can't supply).")
	else:
		regime = "neutral"
		menu = f"IV neutral ({iv_percentile}th pctl) -> shares (no clear vol edge); never sell CSPs into earnings week."

	return {
		"iv_regime": regime,
		"iv_percentile": iv_percentile if isinstance(iv_percentile, (int, float)) else None,
		"vehicle_menu": menu,
		"note": "Vehicle depends on YOUR conviction (bullish/neutral), not a pipeline grade — pick from the menu on the verdict you form.",
	}
