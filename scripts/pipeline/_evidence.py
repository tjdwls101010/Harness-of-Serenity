from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from ._bottleneck import _build_l3_bottleneck
from ._postprocess import _clean_analyst_revisions

type Json = None | bool | int | float | str | list[Json] | dict[str, Json]
type JsonObject = dict[str, Json]

FORBIDDEN_EVIDENCE_KEYS = {
	"objective_screen",
	"screen_score",
	"priced_in_assessment",
	"risk_score",
	"flow_assessment",
	"vehicle_menu",
	"verdict",
	"rating",
	"recommendation",
	"signals",
	"assessment",
	# Macro-regime judgments — never computed in code; stripped defensively in case a
	# legacy payload that still carries them is ever replayed through build_evidence.
	"regime",
	"risk_level",
	"regime_thresholds",
	"trend_direction",
}
FORBIDDEN_EVIDENCE_VALUES = {"BUY", "SELL", "STRONG_BUY", "MOONSHOT", "ACCUMULATE", "AVOID"}
FORBIDDEN_VALUE_PATTERN = re.compile(
	r"\b(strong[\s_-]*buy|buy|sell|accumulate|avoid|moonshot)\b",
	re.IGNORECASE,
)
FORBIDDEN_KEY_NORMALIZED = {
	re.sub(r"[^a-z0-9]", "", key.lower())
	for key in FORBIDDEN_EVIDENCE_KEYS
}
# Namespaced-judgment tokens: a key whose normalized form CONTAINS one of these is a
# judgment even when prefixed (vix_regime, macro_regime, vix_risk_level). Kept narrow so
# it can't nuke a legitimate field — no evidence key contains "regime"/"risklevel" as a
# substring, whereas "rating"/"recommendation" DO appear in real fields (rs_rating,
# recommendation_distribution) and so are matched exactly, never as substrings.
FORBIDDEN_KEY_SUBSTRINGS = ("regime", "risklevel")


def _key_is_forbidden(key: str) -> bool:
	norm = re.sub(r"[^a-z0-9]", "", key.lower())
	return norm in FORBIDDEN_KEY_NORMALIZED or any(tok in norm for tok in FORBIDDEN_KEY_SUBSTRINGS)


def _dict(value: object) -> JsonObject:
	return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Json]:
	return value if isinstance(value, list) else []


def _pick(source: JsonObject, keys: tuple[str, ...]) -> JsonObject:
	return {key: source[key] for key in keys if key in source and source[key] is not None}


def _sanitize(value: Json) -> Json:
	if isinstance(value, dict):
		return {
			key: sanitized
			for key, child in value.items()
			if not _key_is_forbidden(key)
			if (sanitized := _sanitize(child)) is not None
		}
	if isinstance(value, list):
		return [sanitized for child in value if (sanitized := _sanitize(child)) is not None]
	if isinstance(value, str) and FORBIDDEN_VALUE_PATTERN.search(value):
		return None
	return value


def _fixture_ticker(path: Path) -> str:
	return path.name.split(".", 1)[0].upper()


def _top_holders_without_labels(rows: Json) -> list[Json]:
	holders = []
	for row in _list(rows)[:10]:
		if isinstance(row, dict):
			holders.append(_pick(row, ("name", "shares")))
	return holders


def _macro_inputs(l1: object) -> Json:
	"""Raw macro gauges, sanitized — the agent classifies the regime; the code never
	labels it. Whatever the fetch layer hands up (a flat gauge dict) is passed through
	with any judgment key/value stripped defensively, so a stray `regime`/`risk_level`
	or a `BUY`-shaped string can never reach the agent disguised as evidence."""
	if not l1:
		return None
	sanitized = _sanitize(l1)
	return sanitized or None


def _by_horizon_view(revisions: object, earnings_estimate: object, revenue_estimate: object) -> Json:
	"""Collapse eps revisions/trend + earnings & revenue estimates into ONE per-horizon
	view (0q/+1q/0y/+1y), each horizon carrying its eps and revenue numbers plus the raw
	up/down revision counts. Drops `trend_direction` (+ the thresholds that define it):
	'rising/falling/stable' is a directional judgment, and the net-revision counts plus the
	horizon numbers are the raw evidence the agent reads the momentum from instead."""
	cleaned = _clean_analyst_revisions(
		revisions, earnings_estimate=earnings_estimate, revenue_estimate=revenue_estimate
	)
	if isinstance(cleaned, dict):
		cleaned.pop("trend_direction", None)
		cleaned.pop("thresholds", None)
	return cleaned


def _without(rows: Json, drop: tuple[str, ...]) -> list[Json]:
	"""List of dicts with the given (judgment) keys stripped from each row."""
	out: list[Json] = []
	for row in _list(rows):
		if isinstance(row, dict):
			out.append({k: v for k, v in row.items() if k not in drop})
		else:
			out.append(row)
	return out


def _ev_multiples(info: JsonObject, sbc: JsonObject) -> JsonObject:
	"""EV/Rev and EV/FCF — raw multiples the agent bands against peers/chain. Arithmetic only,
	no verdict; this is the real valuation lens (peer/chain multiple banding). EV/FCF is
	emitted ONLY for a positive FCF: a negative 'multiple' is a division artifact, not a
	comparable — for a cash-burner the agent reaches for EV/Rev or net-cash-after-ATM, and
	the raw (negative) real_fcf is preserved here and in sbc_and_dilution regardless."""
	ev = info.get("enterpriseValue")
	rev = info.get("totalRevenue")
	fcf = sbc.get("real_fcf")
	out: JsonObject = {"enterprise_value": ev, "total_revenue": rev, "real_fcf": fcf}
	if isinstance(ev, (int, float)) and isinstance(rev, (int, float)) and rev:
		out["ev_to_revenue"] = round(ev / rev, 2)
	if isinstance(ev, (int, float)) and isinstance(fcf, (int, float)) and fcf > 0:
		out["ev_to_fcf"] = round(ev / fcf, 1)
	return out


def _next_report(earnings_dates: object) -> Json:
	"""The next scheduled earnings date + consensus EPS — the days-to-earnings the CSP /
	earnings-gap timing rule turns on. A date and an estimate, no judgment."""
	ed = _dict(earnings_dates)
	dates_col = ed.get("Earnings Date")
	eps_col = ed.get("EPS Estimate")
	if not isinstance(dates_col, dict) or not dates_col:
		return None
	first = next(iter(dates_col), None)
	if first is None:
		return None
	return {
		"date": dates_col.get(first),
		"eps_estimate": eps_col.get(first) if isinstance(eps_col, dict) else None,
	}


def _absence_flags(l3: JsonObject) -> Json:
	"""The L3 objective absence/presence flags (high-risk-region revenue %, named Mag7
	counterparty, no-recent-material-event) — surfaced as FACTS only. The editorial
	`signal` prose each flag carried ('more likely fear than fundamental', the V3 tag) is
	dropped: that read is the agent's, the flag's type + objective value is the evidence."""
	flags = _list(l3.get("absence_evidence_flags"))
	out = [{k: v for k, v in f.items() if k != "signal"} for f in flags if isinstance(f, dict)]
	return out or None


def build_evidence(payload: JsonObject, ticker: str) -> JsonObject:
	l1 = payload.get("l1")
	l4 = _dict(payload.get("l4"))
	l5 = _dict(payload.get("l5"))
	sec_sc = _dict(payload.get("sec_sc"))

	info = _dict(l4.get("info"))
	sbc = _dict(l4.get("sbc_analyzer"))
	debt = _dict(l4.get("debt_structure"))
	forward_pe = _dict(l4.get("forward_pe"))
	no_growth = _dict(l4.get("no_growth_valuation"))
	margin = _dict(l4.get("margin_tracker"))
	iv = _dict(l4.get("iv_context"))
	inst = _dict(l4.get("institutional_quality"))
	revenue = _dict(l4.get("revenue_trajectory"))
	earnings = _dict(l5.get("earnings_surprise"))
	revisions = _dict(l5.get("analyst_revisions"))
	rs = _dict(l4.get("rs_ranking"))
	capex = _dict(l4.get("capex"))
	short_int = _dict(info.get("short_interest"))
	recs = _dict(l5.get("analyst_recommendations"))
	insider_raw = _dict(l5.get("insider_flow"))
	insider = _dict(insider_raw.get("summary"))
	l3 = _dict(_build_l3_bottleneck(sec_sc))

	return {
		"evidence_contract": {
			"kind": "serenity_evidence",
			"judgment_owner": "agent",
			"code_role": "load_and_normalize_evidence",
			"boundary": "No verdicts, portfolio actions, numeric conviction scores, option vehicles, or a regime/risk_level label — the macro_inputs gauges are raw; the agent classifies the regime.",
		},
		"ticker": ticker,
		"macro_inputs": _macro_inputs(l1),
		"key_facts": _pick(
			info,
			(
				"sector",
				"industry",
				"marketCap",
				"enterpriseValue",
				"currentPrice",
				"beta",
				"fiftyTwoWeekLow",
				"fiftyTwoWeekHigh",
				"fiftyDayAverage",
				"twoHundredDayAverage",
				"sharesOutstanding",
				"floatShares",
				"shortPercentOfFloat",
				"totalRevenue",
				"bookValue",
				"totalCash",
				"grossMargins",
				"operatingMargins",
				"heldPercentInsiders",
				"heldPercentInstitutions",
			),
		),
		"fundamental_inputs": {
			"revenue_trajectory": revenue.get("revenue_by_quarter"),
			"margins": _pick(
				margin,
				(
					"quarters_analyzed",
					"latest_quarter",
					"gross_margin_qoq_change",
					"operating_margin_qoq_change",
					"gross_margin_yoy_change",
					"operating_margin_yoy_change",
					"trajectory",
				),
			),
			"sbc_and_dilution": _pick(
				sbc,
				(
					"sbc_annual",
					"sbc_pct_revenue",
					"reported_fcf",
					"real_fcf",
					"shares_outstanding_current",
					"shares_outstanding_prior_quarter",
					"shares_change_qoq_pct",
					"total_dilution_annual_pct",
				),
			),
			"debt_and_cash": _pick(
				debt,
				(
					"total_debt",
					"cash_and_equivalents",
					"net_debt",
					"total_assets",
					"inventory",
					"market_cap",
					"net_debt_to_mcap",
					"total_revenue",
					"interest_expense",
					"interest_pct_revenue",
					"debt_to_equity",
					"implied_interest_rate",
					"interest_coverage_ratio",
					"interest_coverage_metric",
				),
			),
			"capex": _pick(capex, ("quarters", "latest_capex", "avg_capex", "direction")),
		},
		"valuation_inputs": {
			"forward_pe": _pick(
				forward_pe,
				(
					"current_price",
					"forward_pe_1y",
					"forward_pe_2y",
					"peg_ratio",
					"peg_ratio_unit",
					"eps_growth_rate_used",
					"revenue_growth_yoy",
					"gross_margin_pct",
				),
			),
			"no_growth": _pick(
				no_growth,
				(
					"current_revenue",
					"net_margin_pct",
					"implied_earnings",
					"no_growth_pe_multiple",
					"no_growth_fair_value",
					"current_market_cap",
					"margin_of_safety_pct",
					"negative_earnings",
				),
			),
			"analyst_price_targets": _dict(l5.get("analyst_price_targets")),
			"recommendation_distribution": recs.get("row_oriented") or (recs or None),
			"ev_multiples": _ev_multiples(info, sbc),
		},
		"market_structure_inputs": {
			"institutional_holders": {
				"total": inst.get("total_institutional_holders"),
				"top_holders": _top_holders_without_labels(inst.get("top_holders_classified")),
			},
			"relative_strength": _pick(rs, ("rs_rating", "spy_rs", "history")),
			"short_interest_depth": _pick(short_int, ("days_to_cover", "si_trend")),
			"insider_flow": _pick(
				insider,
				("net_value", "net_shares_6m", "buy_value_12m", "sell_value_12m", "buy_count_12m", "sell_count_12m"),
			),
			"volatility": _pick(
				iv,
				(
					"current_price",
					"iv30",
					"iv30_annual_high",
					"iv30_annual_low",
					"iv_rank",
					"hv30_annual_high",
					"hv30_annual_low",
					"iv_vs_hv_spread",
					"hv30_current",
					"typical_daily_move_pct",
					"iv_rv_ratio",
				),
			),
		},
		"catalyst_inputs": {
			"next_report": _next_report(l5.get("earnings_dates")),
			"earnings_history": _pick(
				earnings,
				("surprise_history", "consecutive_beats", "avg_surprise_pct", "total_quarters_analyzed"),
			),
			"estimate_revisions": _by_horizon_view(
				revisions,
				l5.get("earnings_estimate"),
				l5.get("revenue_estimate"),
			),
		},
		"filing_evidence": {
			"dossier": l3.get("evidence_dossier"),
			"absence_evidence_flags": _absence_flags(l3),
			"recent_events": _without(_dict(_dict(l3.get("data")).get("sec_events")), ("confidence",)),
		},
	}


def cmd_evidence(args) -> None:
	fixture = Path(args.fixture)
	with fixture.open(encoding="utf-8") as handle:
		payload = json.load(handle)
	if not isinstance(payload, dict):
		raise ValueError("fixture must contain a JSON object")
	ticker = (args.ticker or _fixture_ticker(fixture)).upper()
	json.dump(build_evidence(payload, ticker), sys.stdout, ensure_ascii=False, indent=2)
	print()
