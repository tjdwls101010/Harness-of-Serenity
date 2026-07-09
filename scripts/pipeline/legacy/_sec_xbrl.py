"""Deterministic SEC supply-chain NUMBERS, straight from XBRL via edgartools.

This replaces the sec-analyzer dependency entirely. It extracts FOUR objective
quantities the supply-chain read turns on — customer/segment revenue concentration,
geographic revenue, inventory composition, and unconditional purchase obligations —
by parsing the filing's standardized US-GAAP XBRL tags. No LLM, no OpenRouter, no
extraction schema: same inputs → same output, every value reproduced from the filing
or omitted. The RELATIONSHIP NARRATIVE (named customers/suppliers, financing structure)
is NOT here — that adaptive prose reading is the `serenity-filings` subagent's job; this
module is only the numbers.

Logic ported faithfully from the deterministic half of the prior sec-analyzer
(`extract_xbrl`); the non-deterministic LLM half (`extract`) is dropped.
"""

from __future__ import annotations

import os
import re
import sys
from typing import Any

_NUMERIC_VALUE_COL = "_numeric_value"
_RESOLVED_DATE_COL = "_resolved_date"
_GEO_AXIS_COL = "dim_srt_StatementGeographicalAxis"
_MAJOR_CUSTOMERS_COL = "dim_srt_MajorCustomersAxis"
_BENCHMARK_COL = "dim_us-gaap_ConcentrationRiskByBenchmarkAxis"
_COUNTRY_MAP = {
	"US": "United States", "CN": "China", "JP": "Japan", "TW": "Taiwan",
	"KR": "South Korea", "DE": "Germany", "GB": "United Kingdom", "IN": "India",
}
_INVENTORY_CONCEPTS = (
	("InventoryRawMaterialsAndSupplies", "raw_materials"),
	("InventoryRawMaterials", "raw_materials"),
	("InventoryWorkInProcess", "work_in_progress"),
	("InventoryFinishedGoods", "finished_goods"),
	("InventoryFinishedGoodsAndWorkInProcess", "finished_goods"),
)
_PURCHASE_OBLIGATION_TIMEFRAMES = (
	("BalanceSheetAmount", "total"),
	("FirstAnniversary", "year 1"),
	("SecondAnniversary", "year 2"),
	("ThirdAnniversary", "year 3"),
	("FourthAnniversary", "year 4"),
	("FifthAnniversary", "year 5"),
	("AfterFiveYears", "after year 5"),
)
_DEFAULT_IDENTITY = "Harness Research chunghun1@naver.com"


def _setup_identity() -> None:
	identity = os.environ.get("EDGAR_IDENTITY")
	if not identity:
		try:
			from dotenv import load_dotenv
			load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"))
			identity = os.environ.get("EDGAR_IDENTITY")
		except Exception:  # noqa: BLE001
			pass
	from edgar import set_identity
	set_identity(identity or _DEFAULT_IDENTITY)


# ---------------------------------------------------------------------------
# text / frame helpers
# ---------------------------------------------------------------------------

def _xbrl_text(value: Any) -> str | None:
	if value is None:
		return None
	text = str(value).strip()
	if not text or text.lower() in {"nan", "nat", "none", "<na>"}:
		return None
	return text


def _xbrl_text_column(df, column: str):
	import pandas as pd
	if column not in df.columns:
		return pd.Series(pd.NA, index=df.index, dtype="string")
	return df[column].astype("string")


def _prepare_xbrl_facts(df):
	import pandas as pd
	df = df.copy()
	if "numeric_value" in df.columns:
		df[_NUMERIC_VALUE_COL] = pd.to_numeric(df["numeric_value"], errors="coerce")
	else:
		df[_NUMERIC_VALUE_COL] = pd.Series([pd.NA] * len(df), index=df.index, dtype="Float64")
	resolved_date = pd.Series(pd.NA, index=df.index, dtype="string")
	for column in ("period_end", "period_instant"):
		if column in df.columns:
			resolved_date = resolved_date.combine_first(df[column].astype("string"))
	df[_RESOLVED_DATE_COL] = resolved_date
	return df


def _latest_rows_by_date(rows, date_column: str = _RESOLVED_DATE_COL):
	if len(rows) == 0 or date_column not in rows.columns:
		return rows.iloc[0:0]
	dates = rows[date_column].dropna()
	if len(dates) == 0:
		return rows.iloc[0:0]
	return rows[rows[date_column] == dates.max()]


def _member_set(df, column: str) -> set:
	return {text for value in _xbrl_text_column(df, column).dropna() if (text := _xbrl_text(value))}


def _not_dimensioned(df):
	if "is_dimensioned" in df.columns:
		is_dim = _xbrl_text_column(df, "is_dimensioned").str.lower()
		return is_dim.isna() | is_dim.isin({"false", "0"})
	return _xbrl_text_column(df, "dimension").isna() & _xbrl_text_column(df, "member").isna()


def _format_member(member: Any, *, country_map: bool = False) -> str | None:
	text = _xbrl_text(member)
	if text is None:
		return None
	label = text.split(":")[-1].replace("Member", "")
	label = re.sub(r"([a-z])([A-Z])", r"\1 \2", label)
	if country_map:
		label = _COUNTRY_MAP.get(label, label)
	return label


def _format_amount(amount: float) -> str:
	return f"${amount/1e9:.1f}B" if amount >= 1e9 else f"${amount/1e6:.0f}M"


# ---------------------------------------------------------------------------
# the four mappers (ported verbatim in logic)
# ---------------------------------------------------------------------------

def _map_revenue_concentration(df) -> list[dict]:
	concept = _xbrl_text_column(df, "concept")
	conc = df[concept.str.contains("ConcentrationRiskPercentage", case=False, na=False) & df[_NUMERIC_VALUE_COL].notna()]
	if len(conc) == 0:
		return []
	benchmark = _xbrl_text_column(conc, _BENCHMARK_COL)
	conc = conc[
		benchmark.str.contains(r"SalesRevenueNet|Revenue", case=False, na=False, regex=True)
		& ~benchmark.str.contains("AccountsReceivable", case=False, na=False, regex=True)
	]
	conc = _latest_rows_by_date(conc)
	if len(conc) == 0:
		return []
	geographic_members = _member_set(df, _GEO_AXIS_COL)
	entries, seen = [], set()
	for _, row in conc.iterrows():
		customer_member = _xbrl_text(row.get(_MAJOR_CUSTOMERS_COL))
		if customer_member is None or customer_member in geographic_members:
			continue
		if _xbrl_text(row.get(_GEO_AXIS_COL)) is not None:
			continue
		name = _format_member(customer_member)
		if name is None or name in seen:
			continue
		seen.add(name)
		entries.append({
			"entity": name,
			"revenue_pct": round(float(row[_NUMERIC_VALUE_COL]) * 100, 2),
			"source": "xbrl",
			"end_date": _xbrl_text(row.get(_RESOLVED_DATE_COL)) or "",
		})
	return entries


def _find_total_revenue(df, latest_date: str | None) -> float | None:
	concept = _xbrl_text_column(df, "concept")
	period_type = _xbrl_text_column(df, "period_type").str.lower()
	geo_member = _xbrl_text_column(df, _GEO_AXIS_COL)
	not_dim = _not_dimensioned(df)
	excluded = concept.str.contains(r"TextBlock|Policy|Description|Percentage|Cost", case=False, na=False, regex=True)
	for pattern in ("RevenueFromContractWithCustomer", r"^us-gaap:Revenues$"):
		rows = df[
			concept.str.contains(pattern, case=False, na=False, regex=True)
			& ~excluded & not_dim & geo_member.isna()
			& period_type.eq("duration") & df[_NUMERIC_VALUE_COL].notna()
		]
		rows = rows[rows[_RESOLVED_DATE_COL] == latest_date] if latest_date is not None else _latest_rows_by_date(rows)
		if len(rows) > 0:
			return float(rows[_NUMERIC_VALUE_COL].max())
	return None


def _map_geographic_revenue(df) -> list[dict]:
	if _GEO_AXIS_COL not in df.columns:
		return []
	concept = _xbrl_text_column(df, "concept")
	period_type = _xbrl_text_column(df, "period_type").str.lower()
	geo_member = _xbrl_text_column(df, _GEO_AXIS_COL)
	excluded = concept.str.contains(r"TextBlock|Policy|Description|Percentage|Cost", case=False, na=False, regex=True)
	geo = df[
		geo_member.notna() & concept.str.contains("Revenue", case=False, na=False)
		& ~excluded & period_type.eq("duration") & df[_NUMERIC_VALUE_COL].notna()
	]
	geo = _latest_rows_by_date(geo)
	if len(geo) == 0:
		return []
	latest_date = _xbrl_text(geo[_RESOLVED_DATE_COL].dropna().max())
	total_revenue = _find_total_revenue(df, latest_date)
	entries, seen = [], set()
	for _, row in geo.iterrows():
		region = _format_member(row.get(_GEO_AXIS_COL), country_map=True)
		if region is None:
			continue
		amount = float(row[_NUMERIC_VALUE_COL])
		end_date = _xbrl_text(row.get(_RESOLVED_DATE_COL)) or ""
		key = (region, end_date)
		if key in seen:
			continue
		seen.add(key)
		entries.append({
			"region": region,
			"revenue_pct": round(amount / total_revenue * 100, 2) if total_revenue else None,
			"revenue_amount": _format_amount(amount),
			"source": "xbrl",
			"end_date": end_date,
		})
	return entries


def _map_inventory_composition(df) -> list[dict]:
	concept = _xbrl_text_column(df, "concept")
	candidate = concept.str.contains(r"^us-gaap:InventoryNet$", case=False, na=False, regex=True)
	for suffix, _ in _INVENTORY_CONCEPTS:
		candidate = candidate | concept.str.contains(suffix, case=False, na=False, regex=True)
	period_instant = _xbrl_text_column(df, "period_instant")
	latest_rows = _latest_rows_by_date(
		df[candidate & period_instant.notna() & df[_NUMERIC_VALUE_COL].notna()], "period_instant")
	if len(latest_rows) == 0:
		return []
	latest_concept = _xbrl_text_column(latest_rows, "concept")
	total_rows = latest_rows[latest_concept.str.contains(r"^us-gaap:InventoryNet$", case=False, na=False, regex=True)]
	denominator = float(total_rows[_NUMERIC_VALUE_COL].max()) if len(total_rows) > 0 else None
	entries, seen = [], set()
	for suffix, category in _INVENTORY_CONCEPTS:
		if category in seen:
			continue
		rows = latest_rows[_xbrl_text_column(latest_rows, "concept").str.contains(suffix, case=False, na=False, regex=True)]
		if len(rows) == 0:
			continue
		amount = float(rows.iloc[0][_NUMERIC_VALUE_COL])
		entries.append({
			"category": category,
			"amount": _format_amount(amount),
			"source": "xbrl",
			"pct_of_total": round(amount / denominator * 100, 2) if denominator else None,
		})
		seen.add(category)
	return entries


def _map_purchase_obligations(df) -> list[dict]:
	concept = _xbrl_text_column(df, "concept")
	po_rows = df[
		concept.str.contains("UnrecordedUnconditionalPurchaseObligation", case=False, na=False)
		& ~concept.str.contains(r"TextBlock|Policy", case=False, na=False, regex=True)
		& _xbrl_text_column(df, "period_instant").notna() & df[_NUMERIC_VALUE_COL].notna()
	]
	po_rows = _latest_rows_by_date(po_rows, "period_instant")
	if len(po_rows) == 0:
		return []
	entries = []
	for _, row in po_rows.iterrows():
		concept_name = str(row["concept"])
		timeframe = ""
		for fragment, label in _PURCHASE_OBLIGATION_TIMEFRAMES:
			if fragment in concept_name:
				timeframe = label
				break
		entries.append({
			"obligation_type": "unconditional purchase obligation",
			"amount": _format_amount(float(row[_NUMERIC_VALUE_COL])),
			"timeframe": timeframe,
			"source": "xbrl",
		})
	return entries


# ---------------------------------------------------------------------------
# public entry
# ---------------------------------------------------------------------------

def extract_supply_chain_xbrl(ticker: str, form: str = "10-K") -> dict:
	"""The four deterministic XBRL supply-chain quantities for a ticker's latest `form`.

	Returns {"filing": {...metadata...}, "data": {revenue_concentration, geographic_revenue,
	inventory_composition, purchase_obligations}, "xbrl_available": bool}. Empty categories
	are omitted. Any failure (SEC unreachable, no XBRL) degrades to xbrl_available=False with
	empty data — never a fabricated number."""
	try:
		_setup_identity()
		from edgar import Company
		c = Company(ticker.upper())
		if getattr(c, "not_found", False):
			return {"filing": {}, "data": {}, "xbrl_available": False, "error": "company_not_found"}
		filing = c.latest(form)
		metadata = {
			"company": getattr(filing, "company", None) or _getattr_safe(c, "name"),
			"cik": _getattr_safe(c, "cik"),
			"form": getattr(filing, "form", form),
			"filing_date": str(getattr(filing, "filing_date", "")) or None,
			"accession_no": getattr(filing, "accession_no", None),
		}
	except Exception as e:  # noqa: BLE001
		print(f"[sec-xbrl] filing fetch failed: {e}", file=sys.stderr)
		return {"filing": {}, "data": {}, "xbrl_available": False, "error": str(e)}

	try:
		xbrl = filing.xbrl()
		if xbrl is None:
			return {"filing": metadata, "data": {}, "xbrl_available": False}
		df = xbrl.facts.to_dataframe()
		if df is None or len(df) == 0:
			return {"filing": metadata, "data": {}, "xbrl_available": False}
		df = _prepare_xbrl_facts(df)
	except Exception as e:  # noqa: BLE001
		print(f"[sec-xbrl] XBRL parse failed: {e}", file=sys.stderr)
		return {"filing": metadata, "data": {}, "xbrl_available": False, "error": str(e)}

	data = {}
	for key, fn in (
		("revenue_concentration", _map_revenue_concentration),
		("geographic_revenue", _map_geographic_revenue),
		("inventory_composition", _map_inventory_composition),
		("purchase_obligations", _map_purchase_obligations),
	):
		try:
			entries = fn(df)
		except Exception as e:  # noqa: BLE001
			print(f"[sec-xbrl] {key} map failed: {e}", file=sys.stderr)
			entries = []
		if entries:
			data[key] = entries

	return {"filing": metadata, "data": data, "xbrl_available": True}


def _getattr_safe(obj, name):
	try:
		return getattr(obj, name, None)
	except Exception:  # noqa: BLE001
		return None
