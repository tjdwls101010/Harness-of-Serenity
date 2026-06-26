"""SEC supply-chain EVIDENCE extraction for the Serenity pipeline.

sec-analyzer runs an LLM over the filing, so anything it returns carries per-run
variance. That makes it the wrong place to compute a verdict: a judgment (is this a
bottleneck? what is the moat? is the funding dilutive? which archetype?) belongs to
the analyst reasoning from the evidence + doctrine — not to a structured-output enum
that can drift run-to-run and mislead. So this module extracts only OBJECTIVE,
relationship-centric FACTS as prose — who the company does business with and where,
what it depends on, how it is financed — plus the deterministic XBRL quantities. The
job here is to surface the filing's own words and numbers (the objective signal a web
search would bury under promotional spin); the analyst forms every judgment on top.
"""

from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# SEC Supply Chain Evidence Schema (objective prose + XBRL; no judgment enums)
# ---------------------------------------------------------------------------

class SerenitySupplyChain(BaseModel):
	"""Objective relationship-evidence extracted from a SEC filing — facts, not verdicts."""

	__prompt__: ClassVar[str] = """\
You are reading a SEC filing to extract OBJECTIVE FACTS for an investment analyst.
Do NOT judge, rate, score, or classify — extract what the filing actually says, in plain
prose, with the names and NUMBERS it discloses. The analyst forms every judgment; your only
job is to give them the filing's unbiased facts (the objective signal a web search would
bury under company/analyst promotion). One to three sentences per field; "" only if the
filing is genuinely silent. Do not pad, do not infer beyond the text.

Filing company: {company_name}

company_relationships — who the company does business with and HOW MUCH: key CUSTOMERS,
  SUPPLIERS, and PARTNERS, with names and the degree (% of revenue, $ value, contract term)
  where disclosed, or the aggregate / anonymized disclosure if that is all there is
  (e.g. "top 5 customers = 29% of revenue, no single >10%"; "sole-sources InP wafers from
  Sumitomo"; "Microsoft anchor, ~$17B multi-year contract"). Quote the filing.

country_exposure — where the company manufactures, sells, and sources, BY COUNTRY, with %
  or $ where disclosed, plus any export-control / tariff / sanction exposure the filing
  flags (e.g. "62% of revenue from China; fabs in China and Taiwan; flags US export-control
  risk on China shipments").

critical_inputs — the key input(s) the company itself depends on to operate, and the named
  source(s) if disclosed (e.g. "6N laser-grade InP poly-crystal sourced from two Japanese
  suppliers; high-purity gallium"). Quote it; the deeper and more concentrated, the more it
  matters to record.

financing_facts — how the company is capitalized and funds its build, WITH NUMBERS: recent
  equity raises / ATM programs (size, and vs market cap if statable), convertibles (coupon,
  size, maturity), debt (terms), customer prepayments, and material offtake / supply
  contracts (counterparty, $/volume, term) — e.g. "$6B at-market ATM ≈ 28% of market cap;
  $3B 0%-coupon convertible due 2030; 5-yr take-or-pay with Acme $1.2B". "" if silent.

Extract from this filing:

{filing_text}
"""

	company_relationships: str = ""
	country_exposure: str = ""
	critical_inputs: str = ""
	financing_facts: str = ""


# ---------------------------------------------------------------------------
# Constants (objective XBRL reinforcement only)
# ---------------------------------------------------------------------------

# Region risk for the objective XBRL geographic-revenue flag.
_HIGH_RISK_REGIONS = {"taiwan", "china", "hong kong", "mainland china"}

# Mag7 names: a direct Mag7 counterparty insulates the filer from intermediary /
# neocloud credit contagion (V3 financial dimension). Surfaced as an objective flag.
_MAG7_NAMES = {"microsoft", "msft", "google", "alphabet", "googl", "meta",
			   "amazon", "amzn", "apple", "aapl", "nvidia", "nvda"}


# ---------------------------------------------------------------------------
# Evidence dossier (the agent-facing consolidation of filing facts)
# ---------------------------------------------------------------------------

def _build_evidence_dossier(evidence, xbrl):
	"""Consolidate the filing's objective EVIDENCE — the prose relationship facts plus the
	deterministic XBRL quantities — into one agent-facing block. These are the filing's own
	words and numbers; a relationship, country share, or contract absent here is absent from
	the filing, so the analyst must not assert one from memory."""
	evidence = evidence if isinstance(evidence, dict) else {}
	xbrl = xbrl if isinstance(xbrl, dict) else {}

	def _list(key):
		v = xbrl.get(key)
		return v if isinstance(v, list) and v else None

	geo = _list("geographic_revenue")
	if geo:
		geo = sorted([e for e in geo if isinstance(e, dict)],
					 key=lambda e: e.get("revenue_pct") if isinstance(e.get("revenue_pct"), (int, float)) else 0,
					 reverse=True)

	facts = {
		"company_relationships": evidence.get("company_relationships") or None,
		"country_exposure": evidence.get("country_exposure") or None,
		"critical_inputs": evidence.get("critical_inputs") or None,
		"financing_facts": evidence.get("financing_facts") or None,
	}
	facts = {k: v for k, v in facts.items() if v}

	return {
		"filing_facts": facts or None,
		"geographic_concentration": geo,
		"customer_concentration": _list("revenue_concentration"),
		"inventory_mix": _list("inventory_composition"),
		"purchase_obligations": _list("purchase_obligations"),
		"note": ("Deterministic XBRL NUMBERS from the filing — geographic & customer revenue "
				 "concentration, inventory mix, purchase obligations. A share/figure not listed here "
				 "is not in the XBRL; do not assert one from memory (a null field means the filing was "
				 "silent). For the relationship NARRATIVE — named customers/suppliers/partners, "
				 "critical-input sourcing, financing structure (ATM/convertible/offtake) — invoke the "
				 "`serenity-filings` subagent; the pipeline no longer extracts prose (that adaptive "
				 "read is the subagent's). The bottleneck / archetype / moat / funding-quality "
				 "judgments are YOURS — derive them from these numbers + the subagent's facts + the doctrine."),
	}


# ---------------------------------------------------------------------------
# L3 builder (evidence only — no pre-score, no verdict)
# ---------------------------------------------------------------------------

def _build_l3_bottleneck(sec_sc_results):
	"""Build the L3 SEC-evidence output: the filing's objective relationship facts + XBRL +
	recent events, consolidated into an evidence_dossier with a few objective flags. No
	pre-score and no verdict — the bottleneck / archetype judgment is the analyst's, formed
	from this evidence."""
	sec_sc_raw = sec_sc_results.get("sec_supply_chain", {})
	sec_events_raw = sec_sc_results.get("sec_events", {})

	sc_inner = sec_sc_raw.get("data") if isinstance(sec_sc_raw, dict) else None
	sc_inner = sc_inner or {}
	evidence = sc_inner.get("classification") if isinstance(sc_inner, dict) else None
	xbrl = sc_inner.get("xbrl") if isinstance(sc_inner, dict) else None
	filing = sc_inner.get("filing") if isinstance(sc_inner, dict) else None

	evidence = evidence if isinstance(evidence, dict) else {}
	xbrl = xbrl if isinstance(xbrl, dict) else {}

	has_sc_data = bool(
		any(evidence.get(k) for k in ("company_relationships", "country_exposure",
									  "critical_inputs", "financing_facts"))
		or xbrl
	)
	has_events = bool(
		sec_events_raw and not sec_events_raw.get("error")
		and len(sec_events_raw.get("data", [])) > 0
	)

	cleaned_sc = None
	if has_sc_data:
		cleaned_sc = {"filing": filing, "evidence": evidence, "xbrl": xbrl}

	cleaned_events = []
	if has_events:
		for ev in (sec_events_raw.get("data") or []):
			cleaned_events.append({
				"filing_date": ev.get("filing_date"),
				"event_type": ev.get("event_type"),
				"context": ev.get("context"),
				"confidence": ev.get("confidence"),
			})

	# Objective absence/presence flags — from the filing facts + XBRL, never from a judgment
	# enum. Each is a hand-off the analyst resolves, not a verdict.
	flags = []
	if has_sc_data:
		if not has_events:
			flags.append({
				"type": "no_recent_material_sec_event",
				"signal": "no fundamental change on file — a selloff here is more likely fear than fundamental (check §5)",
			})
		hr_pct = 0.0
		for e in (xbrl.get("geographic_revenue") or []):
			if isinstance(e, dict):
				region = str(e.get("region", "")).lower()
				pct = e.get("revenue_pct")
				if isinstance(pct, (int, float)) and any(hr in region for hr in _HIGH_RISK_REGIONS):
					hr_pct += pct
		if hr_pct >= 15:
			flags.append({
				"type": "high_risk_region_revenue", "value_pct": round(hr_pct, 1),
				"signal": "export-control / tariff exposure — weigh the moat-vs-hostage net yourself",
			})
		rel_text = str(evidence.get("company_relationships") or "").lower()
		mag7 = [m for m in _MAG7_NAMES if m in rel_text]
		if mag7:
			flags.append({
				"type": "mag7_named_counterparty", "matched": mag7[:5],
				"signal": "a direct Mag7 contract is insulated from intermediary/neocloud credit contagion (V3)",
			})

	result = {
		"data": {"sec_supply_chain": cleaned_sc, "sec_events": cleaned_events},
		"absence_evidence_flags": flags,
	}
	if has_sc_data:
		result["evidence_dossier"] = _build_evidence_dossier(evidence, xbrl)
	return result
