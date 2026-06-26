"""Objective signal derivation for the Serenity pipeline.

This layer computes only what is DETERMINISTIC and OBJECTIVE from yfinance/XBRL data —
financial-health gates, a valuation lens (no-growth floor / PEG math), catalyst timing,
a yfinance-derived momentum/quality read, a dilution classification, and a few hand-off
flags — each carrying its basis. It does NOT judge whether a name is a winner: there is no
bottleneck/archetype score and no BUY/SELL grade here. The bottleneck, archetype, moat, and
funding-quality judgments — and the final call — are the analyst's, formed from the SEC
evidence_dossier (L3) plus the doctrine. The `objective_screen` is a triage/discover
comparator and a set of flags, never a verdict.
"""

import re
from datetime import datetime

from .._bottleneck import _build_l3_bottleneck
from ._health import _extract_health_gates


def _build_thesis_signals(l4_results, l5_results):
	"""Map L4/L5 (yfinance) results to thesis strengthening/weakening signals — objective
	momentum/quality data points, counted into a net direction the analyst reads."""
	l4 = l4_results or {}
	l5 = l5_results or {}
	strengthening = []
	weakening = []

	margin_tracker = l4.get("margin_tracker") or {}
	earnings_acc = l4.get("growth_profile") or {}
	margin_flag = str(margin_tracker.get("flag", ""))

	# Strengthening
	if "EXPANDING" in margin_flag.upper() and earnings_acc.get("sales_accelerating") is True:
		strengthening.append("pricing_power_confirmed")
	earnings_surprise = l5.get("earnings_surprise") or {}
	beats = earnings_surprise.get("consecutive_beats", 0)
	if isinstance(beats, (int, float)) and beats >= 3:
		strengthening.append("execution_validated")
	analyst_rev = l5.get("analyst_revisions") or {}
	if analyst_rev and not analyst_rev.get("error"):
		rev_dir = analyst_rev.get("trend_direction", "")
		if isinstance(rev_dir, str) and rev_dir.lower() == "rising":
			strengthening.append("street_catching_up")
	inst_quality = l4.get("institutional_quality") or {}
	io_score = inst_quality.get("io_quality_score")
	if isinstance(io_score, (int, float)) and io_score >= 7:
		strengthening.append("smart_money_accumulating")

	# Weakening
	if "COLLAPSE" in margin_flag.upper():
		weakening.append("pricing_power_eroding")
	sbc = l4.get("sbc_analyzer") or {}
	if str(sbc.get("flag", "")).lower() == "toxic" or str(sbc.get("dilution_flag", "")).lower() == "active_dilution":
		weakening.append("dilution_destroying_value")
	if earnings_acc.get("sales_accelerating") is False:
		sgr = earnings_acc.get("sales_growth_rates")
		if isinstance(sgr, list) and len(sgr) > 0 and isinstance(sgr[-1], (int, float)) and sgr[-1] < 0:
			weakening.append("demand_weakening")
	if isinstance(io_score, (int, float)) and io_score <= 3:
		weakening.append("institutional_exit")

	s_count, w_count = len(strengthening), len(weakening)
	net_direction = "strengthening" if s_count > w_count else "weakening" if w_count > s_count else "neutral"

	return {
		"strengthening": strengthening, "weakening": weakening, "net_direction": net_direction,
		"conviction_delta": s_count - w_count,
		"detail": {
			"margin_flag": margin_flag or None,
			"sales_accelerating": earnings_acc.get("sales_accelerating"),
			"consecutive_beats": beats if isinstance(beats, (int, float)) else None,
			"trend_direction": analyst_rev.get("trend_direction") if not analyst_rev.get("error") else None,
			"io_quality_score": io_score,
			"sbc_flag": sbc.get("flag") or sbc.get("dilution_flag"),
		},
	}


def _classify_dilution(l4_results):
	"""Classify dilution as growth, value-destruction, or accounting illusion — objective
	math over yfinance SBC / FCF / revenue-growth. A hand-off the analyst overlays the 8-K
	structure on (the funded-vs-dilution read lives in the analyst's reasoning + the SEC
	financing_facts evidence, not here)."""
	l4 = l4_results or {}
	sbc = l4.get("sbc_analyzer") or {}
	ea = l4.get("growth_profile") or {}
	fpe = l4.get("forward_pe") or {}

	if sbc.get("error"):
		return {"classification": "unknown", "note": "SBC data unavailable"}

	sbc_pct = sbc.get("sbc_pct_revenue")
	reported_fcf = sbc.get("reported_fcf")
	real_fcf = sbc.get("real_fcf")
	shares_change = sbc.get("shares_change_qoq_pct")

	revenue_growth = None
	if isinstance(fpe, dict) and not fpe.get("error"):
		rg = fpe.get("revenue_growth_yoy")
		if isinstance(rg, (int, float)):
			revenue_growth = rg
	if revenue_growth is None and isinstance(ea, dict) and not ea.get("error"):
		sgr = ea.get("sales_growth_rates")
		if isinstance(sgr, list) and sgr:
			latest = sgr[-1] if isinstance(sgr[-1], (int, float)) else None
			if latest is not None:
				revenue_growth = latest

	sbc_pct_val = sbc_pct if isinstance(sbc_pct, (int, float)) else 0
	growth_val = revenue_growth if isinstance(revenue_growth, (int, float)) else 0

	if (isinstance(reported_fcf, (int, float)) and isinstance(real_fcf, (int, float))
		and reported_fcf > 0 and real_fcf < 0):
		classification = "accounting_illusion"
	elif growth_val > 25 and sbc_pct_val < 20:
		classification = "growth_dilution"
	elif growth_val < 5 and sbc_pct_val > 15:
		classification = "value_destruction"
	elif growth_val > 15 and sbc_pct_val < 30:
		classification = "acceptable"
	else:
		classification = "moderate_concern"

	return {
		"classification": classification,
		"revenue_growth_pct": round(growth_val, 1) if isinstance(growth_val, (int, float)) else None,
		"sbc_pct_revenue": sbc_pct,
		"reported_fcf": reported_fcf,
		"real_fcf": real_fcf,
		"shares_change_qoq_pct": shares_change,
		"note": "yfinance SBC/FCF/growth read — overlay the 8-K/424B financing STRUCTURE (the SEC financing_facts evidence) yourself; this does not see it.",
	}


def _check_sop_triggers(l4_results):
	"""Detect Sum-of-Parts valuation triggers from info — objective (cash-vs-MC, multi-segment
	disclosure). A hand-off: the analyst decides whether a SoP re-frame is warranted."""
	l4 = l4_results or {}
	info = l4.get("info") or {}
	debt_structure = l4.get("debt_structure") or {}
	triggers_found = []
	notes_parts = []

	conglomerate_keywords = ("conglomerate", "diversified", "holding", "industrial conglomerate")
	sector = str(info.get("sector", "")).lower()
	industry = str(info.get("industry", "")).lower()
	for kw in conglomerate_keywords:
		if kw in sector or kw in industry:
			triggers_found.append("conglomerate_classification")
			notes_parts.append("sector/industry classified as conglomerate or diversified")
			break

	summary = str(info.get("longBusinessSummary", ""))
	segment_keywords = ("subsidiary", "subsidiaries", "division", "divisions", "segment", "segments", "business unit")
	if sum(1 for kw in segment_keywords if kw in summary.lower()) >= 2:
		triggers_found.append("multi_segment_description")
		notes_parts.append("company description mentions multiple business segments")

	market_cap = info.get("marketCap")
	total_cash = info.get("totalCash") or debt_structure.get("total_cash")
	if isinstance(market_cap, (int, float)) and market_cap > 0 and isinstance(total_cash, (int, float)):
		cash_ratio = total_cash / market_cap
		if cash_ratio > 0.20:
			triggers_found.append("cash_exceeds_20pct_mc")
			notes_parts.append(f"cash exceeds 20% of market cap ({cash_ratio:.0%})")

	triggered = len(triggers_found) > 0
	note = ("SoP analysis may apply — " + " and ".join(notes_parts) + ".") if triggered else "No SoP triggers detected."
	return {"triggered": triggered, "triggers_found": triggers_found, "note": note}


def _parse_days_to_earnings(l5_results):
	"""Days until the nearest FUTURE earnings date (fallback parser)."""
	if not isinstance(l5_results, dict):
		return None
	ed = l5_results.get("earnings_dates")
	if not isinstance(ed, dict) or ed.get("error"):
		return None
	date_strs = set()
	explicit = ed.get("Earnings Date")
	if isinstance(explicit, dict):
		date_strs.update(v for v in explicit.values() if isinstance(v, str))
	for key, col in ed.items():
		if key in ("days_to_next", "error", "Earnings Date"):
			continue
		if isinstance(col, dict):
			date_strs.update(k for k in col.keys() if isinstance(k, str))
	today = datetime.now().date()
	min_days = None
	for s in date_strs:
		d = None
		try:
			d = datetime.fromisoformat(s).date()
		except (ValueError, TypeError):
			for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%b %d, %Y"):
				try:
					d = datetime.strptime(s.strip(), fmt).date()
					break
				except (ValueError, TypeError):
					continue
		if d is None:
			continue
		delta = (d - today).days
		if delta >= 0 and (min_days is None or delta < min_days):
			min_days = delta
	return min_days


# Narrow set: design-win / qualification / offtake / multi-year supply events that actually
# move forward revenue — NOT routine 8-K prose.
_SEC_CATALYST_KEYWORDS = re.compile(
	r"design[\s-]?win|qualif|offtake|multi.?year\s+supply|supply\s+agreement|"
	r"long.?term\s+(?:supply|purchase)\s+agreement|strategic\s+partnership|capacity\s+expansion",
	re.IGNORECASE,
)
_SEC_CATALYST_ITEMS = ("1.01", "1.02")


def _recent_material_sec_catalyst(sec_sc_results):
	"""Return a material SEC/8-K catalyst type from recent events, else None. The bar: an 8-K
	material-agreement item code (1.01/1.02) OR a narrow phrase match flagged medium/high
	confidence. Objective (event metadata)."""
	if not isinstance(sec_sc_results, dict):
		return None
	events_raw = sec_sc_results.get("sec_events", {}) or {}
	if not isinstance(events_raw, dict) or events_raw.get("error"):
		return None
	events = events_raw.get("data", []) or []
	if not isinstance(events, list):
		return None
	for ev in events:
		if not isinstance(ev, dict):
			continue
		et = str(ev.get("event_type", ""))
		conf = str(ev.get("confidence", "")).lower()
		item_hit = any(et.strip().startswith(code) for code in _SEC_CATALYST_ITEMS)
		phrase_hit = bool(_SEC_CATALYST_KEYWORDS.search(f"{et} {ev.get('context', '')}"))
		if item_hit or (phrase_hit and conf in ("medium", "high")):
			return et or "material_sec_event"
	return None


def _build_objective_screen(l4_results, l5_results, health_severity_score, thesis_signals, sec_sc_results=None):
	"""Compute the OBJECTIVE screen — health, valuation, catalyst, momentum — each a
	deterministic read of yfinance/XBRL data with its basis. NOT a verdict: no bottleneck/
	archetype score, no BUY/SELL grade, no caps. The bottleneck/archetype/moat/funding call
	is the analyst's, from the L3 evidence_dossier + doctrine. The screen is a triage/discover
	comparator plus hand-off flags (pre_commercial, revenue_status, sop)."""
	l4 = l4_results if isinstance(l4_results, dict) else {}
	info_data = l4.get("info") or {}
	if isinstance(info_data, dict) and info_data.get("error"):
		info_data = {}
	fpe = l4.get("forward_pe") or {}
	if isinstance(fpe, dict) and fpe.get("error"):
		fpe = {}

	# Revenue status (tri-state) — distinguishes MISSING data from a confirmed pre-revenue name.
	revenue_status = "has_revenue"
	if isinstance(info_data, dict) and info_data:
		total_revenue = info_data.get("totalRevenue")
		if total_revenue is None:
			revenue_status = "data_insufficient"
		elif isinstance(total_revenue, (int, float)) and total_revenue <= 0:
			revenue_status = "confirmed_pre_revenue"
	else:
		revenue_status = "data_insufficient"

	components = {}

	# Health (0..25) — 5 yfinance financial-health gates.
	if isinstance(health_severity_score, (int, float)):
		hs_points = (health_severity_score / 5.0) * 25.0
		components["health"] = {"raw": health_severity_score, "max": 5.0, "points": round(hs_points, 2)}
	else:
		hs_points = 0.0
		components["health"] = {"raw": None, "max": 5.0, "points": 0.0, "note": "unavailable"}

	# Momentum/quality (0..15) — yfinance strengthening/weakening net direction.
	ts = thesis_signals if isinstance(thesis_signals, dict) else {}
	ts_dir = ts.get("net_direction", "neutral")
	ts_points = 15.0 if ts_dir == "strengthening" else 7.5 if ts_dir == "neutral" else 0.0
	components["momentum"] = {"direction": ts_dir, "points": round(ts_points, 2),
							  "strengthening": ts.get("strengthening"), "weakening": ts.get("weakening")}

	# Catalyst (0..10) — scheduled earnings OR a recent material SEC event.
	days = None
	if isinstance(l5_results, dict):
		ed = l5_results.get("earnings_dates")
		if isinstance(ed, dict) and not ed.get("error"):
			days = ed.get("days_to_next")
	if days is None:
		days = _parse_days_to_earnings(l5_results)
	earnings_pts = 10.0 if (days is not None and days <= 30) else 5.0 if (days is not None and days <= 60) else 0.0
	sec_catalyst = _recent_material_sec_catalyst(sec_sc_results)
	sec_pts = 7.0 if sec_catalyst else 0.0
	cat_points = max(earnings_pts, sec_pts)
	catalyst_type = "earnings_near" if (earnings_pts >= sec_pts and earnings_pts > 0) else (sec_catalyst if sec_pts > 0 else "none")
	components["catalyst"] = {"days_to_earnings": days, "sec_event": sec_catalyst,
							  "catalyst_type": catalyst_type, "points": round(cat_points, 2)}

	# Valuation (0..10) — PEG-first for growers, no-growth-floor MoS otherwise; objective math
	# with the lens named. The driver_proxy track hands the levered-IRR / contracted-backlog
	# computation to the analyst (the no-growth floor is the wrong lens for an asset-financed
	# grower — it fabricates an "overvalued" verdict the doctrine forbids).
	ngv = l4.get("no_growth_valuation") or {}
	if isinstance(ngv, dict) and ngv.get("error"):
		ngv = {}
	mos_pct = ngv.get("margin_of_safety_pct")
	rev_growth_v = fpe.get("revenue_growth_yoy")
	peg = fpe.get("peg_ratio")
	fpe1_v = fpe.get("forward_pe_1y")
	fpe2_v = fpe.get("forward_pe_2y")
	is_growth = isinstance(rev_growth_v, (int, float)) and rev_growth_v >= 15
	pe_contraction = isinstance(fpe1_v, (int, float)) and isinstance(fpe2_v, (int, float)) and fpe2_v < fpe1_v
	if is_growth and isinstance(peg, (int, float)) and peg > 0:
		val_points = 10.0 if peg < 1.0 else 6.0 if peg < 2.0 else 2.0
		if pe_contraction:
			val_points = min(10.0, val_points + 2.0)
		components["valuation"] = {"track": "peg", "peg_ratio": peg, "pe_contraction": pe_contraction,
								   "mos_pct_floor": round(mos_pct, 2) if isinstance(mos_pct, (int, float)) else None,
								   "points": round(val_points, 2)}
	elif is_growth and isinstance(mos_pct, (int, float)) and mos_pct < 0:
		val_points = 8.0 if rev_growth_v > 50 else 6.0 if rev_growth_v > 25 else 4.0
		components["valuation"] = {"track": "driver_proxy", "rev_growth_yoy": round(rev_growth_v, 1),
								   "mos_pct_floor": round(mos_pct, 2), "points": round(val_points, 2),
								   "note": "no-growth floor N/A (asset-financed / pre-profit grower) — growth-quality proxy; YOU compute & defend the levered-IRR / contracted-backlog band"}
	elif isinstance(mos_pct, (int, float)):
		val_points = 10.0 if mos_pct > 20 else 5.0 if mos_pct >= 0 else 0.0
		components["valuation"] = {"track": "no_growth_floor", "mos_pct": round(mos_pct, 2),
								   "is_growth": is_growth, "points": round(val_points, 2)}
	else:
		val_points = 0.0
		components["valuation"] = {"track": None, "mos_pct": None, "points": 0.0, "note": "unavailable"}

	screen_score = round(hs_points + ts_points + cat_points + val_points, 2)
	screen_max = 60.0  # health 25 + momentum 15 + catalyst 10 + valuation 10

	# Objective hand-off flags — NOT caps. The analyst weighs them against the evidence.
	op_margin = info_data.get("operatingMargins") if isinstance(info_data, dict) else None
	flags = {
		"revenue_status": revenue_status,
		"data_insufficient": revenue_status == "data_insufficient",
	}
	if isinstance(op_margin, (int, float)) and op_margin < -1.0:
		flags["pre_commercial"] = {
			"op_margin": round(op_margin, 3),
			"basis": ("operating losses EXCEED revenue (op margin < -100%) — there is no commercial "
					  "business to value yet; treat as speculative until YOU confirm a durable moat / a "
					  "real ramp from the evidence. yfinance TTM op-margin can also be pushed < -100% by a "
					  "one-time charge — check for non-recurring items before trusting it."),
		}
	if revenue_status == "confirmed_pre_revenue":
		flags["pre_revenue"] = {
			"basis": ("no revenue yet — investable only on a material catalyst (a design win / "
					  "qualification / named contract) and a moat YOU confirm; size as a moonshot."),
		}

	summary = (f"Objective screen {screen_score}/{screen_max} (health {round(hs_points,1)}/25 · "
			   f"momentum {round(ts_points,1)}/15 · catalyst {round(cat_points,1)}/10 · "
			   f"valuation {round(val_points,1)}/10). NOT a verdict — bottleneck / archetype / moat / "
			   f"funding and the rating are yours, from the L3 evidence_dossier + doctrine.")

	return {
		"screen_score": screen_score,
		"screen_max": screen_max,
		"components": components,
		"objective_flags": flags,
		"summary": summary,
		"note": ("This is an OBJECTIVE health/valuation/catalyst/momentum screen of yfinance/XBRL data, "
				 "NOT an investment verdict and NOT a bottleneck/archetype score. There is no BUY/SELL "
				 "grade and no cap: a low screen on a pre-commercial name, or a high screen on a no-moat "
				 "hot name, is for YOU to interpret against the SEC evidence_dossier and the doctrine."),
	}


def derive_core_signals(l1_result, l4_results, l5_results, sec_sc_results):
	"""Run the OBJECTIVE deterministic layer on already-gathered pipeline inputs: the SEC
	evidence (L3), health gates, momentum signals, dilution classification, SoP triggers, and
	the objective screen. cmd_analyze calls it on live results; the regression harness calls it
	on FROZEN results so an objective-signal change is tested deterministically.

	Network-free: same inputs always yield the same output. There is no bottleneck/archetype
	verdict here — that judgment is the analyst's, from l3_data['evidence_dossier'] + doctrine.
	"""
	l3_data = _build_l3_bottleneck(sec_sc_results)
	health_gates = _extract_health_gates(l4_results)
	thesis_signals = _build_thesis_signals(l4_results, l5_results)
	dilution_classification = _classify_dilution(l4_results)
	sop_triggers = _check_sop_triggers(l4_results)
	objective_screen = _build_objective_screen(
		l4_results, l5_results, health_gates.get("severity_score"), thesis_signals, sec_sc_results,
	)
	return {
		"l3_data": l3_data,
		"health_gates": health_gates,
		"thesis_signals": thesis_signals,
		"dilution_classification": dilution_classification,
		"sop_triggers": sop_triggers,
		"objective_screen": objective_screen,
	}
