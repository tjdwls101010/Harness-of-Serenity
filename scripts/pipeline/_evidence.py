from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from ._bottleneck import _build_l3_bottleneck

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
			if re.sub(r"[^a-z0-9]", "", key.lower()) not in FORBIDDEN_KEY_NORMALIZED
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


def _macro_signals(l1: object) -> Json:
	"""Raw macro gauges only — the agent classifies the regime; the code never labels it
	(no `regime`/`risk_level`/`regime_thresholds`, which are judgments)."""
	sig = _dict(l1).get("signals")
	return sig if isinstance(sig, dict) else None


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
	no verdict; this is the real valuation lens (peer/chain multiple banding)."""
	ev = info.get("enterpriseValue")
	rev = info.get("totalRevenue")
	fcf = sbc.get("real_fcf")
	out: JsonObject = {"enterprise_value": ev, "total_revenue": rev, "real_fcf": fcf}
	if isinstance(ev, (int, float)) and isinstance(rev, (int, float)) and rev:
		out["ev_to_revenue"] = round(ev / rev, 2)
	if isinstance(ev, (int, float)) and isinstance(fcf, (int, float)) and fcf:
		out["ev_to_fcf"] = round(ev / fcf, 1)
	return out


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
	l3 = _build_l3_bottleneck(sec_sc)

	return {
		"evidence_contract": {
			"kind": "serenity_evidence",
			"judgment_owner": "agent",
			"code_role": "load_and_normalize_evidence",
			"boundary": "No verdicts, portfolio actions, numeric conviction scores, or option vehicles.",
		},
		"ticker": ticker,
		"macro_inputs": _macro_signals(l1),
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
			"ev_multiples": _ev_multiples(info, sbc),
		},
		"market_structure_inputs": {
			"institutional_holders": {
				"total": inst.get("total_institutional_holders"),
				"top_holders": _top_holders_without_labels(inst.get("top_holders_classified")),
			},
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
			"earnings_history": _pick(
				earnings,
				("surprise_history", "consecutive_beats", "avg_surprise_pct", "total_quarters_analyzed"),
			),
			"analyst_revisions": _pick(
				revisions,
				("eps_revisions", "eps_trend", "growth_estimates"),
			),
			"earnings_estimate": _dict(l5.get("earnings_estimate")),
			"revenue_estimate": _dict(l5.get("revenue_estimate")),
		},
		"filing_evidence": {
			"dossier": _dict(l3).get("evidence_dossier"),
			"recent_events": _without(_dict(_dict(l3).get("data")).get("sec_events"), ("confidence",)),
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
