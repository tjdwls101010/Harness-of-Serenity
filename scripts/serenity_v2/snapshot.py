"""Deterministic assembly of a fact snapshot from typed provider evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlparse

from serenity_v2.schema import validate_document


FACT_SNAPSHOT_SCHEMA_ID = "urn:serenity:schema:fact-snapshot:2"
IDENTITY_PROVENANCE_PROVIDERS = ("sec.company_tickers", "sec.submissions", "openfigi.mapping")
MARKET_FIELD_NAMES = (
    "market_cap",
    "price",
    "shares_outstanding",
    "trailing_pe",
    "forward_pe",
    "peg_ratio",
    "price_to_sales",
    "enterprise_value",
    "enterprise_to_revenue",
    "enterprise_to_ebitda",
    "gross_margin",
    "operating_margin",
    "profit_margin",
    "revenue_growth",
    "earnings_growth",
    "total_revenue",
    "free_cash_flow",
    "operating_cash_flow",
    "ebitda",
    "capital_expenditure",
    "gross_profit",
    "operating_income",
    "net_income",
    "cost_of_revenue",
    "stock_based_compensation",
    "cash",
    "debt",
    "total_assets",
    "inventory",
    "diluted_shares",
)


class SnapshotBlockedError(ValueError):
    """A blocked identity is a lifecycle error, not a partial investment fact."""

    exit_code = 3

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class SnapshotIntegrityError(ValueError):
    """A persisted snapshot no longer matches its content-addressed identity."""


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _date(value: Any) -> str | None:
    if isinstance(value, str) and len(value) >= 10:
        candidate = value[:10]
        try:
            return date.fromisoformat(candidate).isoformat()
        except ValueError:
            return None
    return None


def _valid_instant(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        return datetime.fromisoformat(normalized).tzinfo is not None
    except ValueError:
        return False


def _valid_uri(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return bool(parsed.scheme and parsed.netloc)


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _is_after_cutoff(available_at: Any, cutoff: str | None) -> bool:
    if cutoff is None:
        return False
    if not isinstance(available_at, str):
        return True
    try:
        normalized_available = available_at[:-1] + "+00:00" if available_at.endswith("Z") else available_at
        normalized_cutoff = cutoff[:-1] + "+00:00" if cutoff.endswith("Z") else cutoff
        available_instant = datetime.fromisoformat(normalized_available)
        cutoff_instant = datetime.fromisoformat(normalized_cutoff)
    except ValueError:
        return True
    if available_instant.tzinfo is None:
        available_instant = available_instant.replace(tzinfo=timezone.utc)
    if cutoff_instant.tzinfo is None:
        cutoff_instant = cutoff_instant.replace(tzinfo=timezone.utc)
    return available_instant.astimezone(timezone.utc) > cutoff_instant.astimezone(timezone.utc)


def _identity_bindings(identity: Mapping[str, Any]) -> dict[str, str]:
    fields = {"ticker": identity.get("ticker"), "cik": identity.get("cik"), "figi": identity.get("figi")}
    return {name: value for name, value in fields.items() if isinstance(value, str) and value}


def _listing_type(security_type: Any) -> str | None:
    if not isinstance(security_type, str):
        return None
    normalized = security_type.lower()
    if "depositary" in normalized or "adr" in normalized:
        return "adr"
    if "etf" in normalized or "fund" in normalized:
        return "etf"
    if "common" in normalized or "ordinary" in normalized:
        return "common"
    return None


def _snapshot_identity(resolution: Mapping[str, Any]) -> dict[str, Any]:
    status = resolution.get("status")
    identity = resolution.get("identity")
    if status != "available" or not isinstance(identity, Mapping):
        rejection = resolution.get("rejection")
        code = rejection.get("code") if isinstance(rejection, Mapping) else None
        raise SnapshotBlockedError(str(code or "identity_unresolved"))
    if identity.get("listing_country") != "US":
        raise SnapshotBlockedError("non_us_listing")

    ticker = identity.get("ticker")
    name = identity.get("official_name") or identity.get("name")
    exchange = identity.get("exchange")
    if not all(isinstance(value, str) and value for value in (ticker, name, exchange)):
        raise SnapshotBlockedError("identity_incomplete")

    snapshot_identity: dict[str, Any] = {
        "requested_ticker": str(resolution.get("ticker") or ticker),
        "ticker": ticker,
        "normalized_symbol": ticker,
        "name": name,
        "exchange": exchange,
        "resolution_source": "sec+openfigi",
    }
    for field in ("cik", "figi"):
        value = identity.get(field)
        if isinstance(value, str) and value:
            snapshot_identity[field] = value
    issuer_domains = identity.get("issuer_domains")
    if issuer_domains is not None:
        if not isinstance(issuer_domains, list) or not issuer_domains or not all(isinstance(domain, str) and domain for domain in issuer_domains):
            raise SnapshotBlockedError("issuer_domains_invalid")
        snapshot_identity["issuer_domains"] = sorted(set(issuer_domains))
    security_type = identity.get("security_type")
    if not isinstance(security_type, str) or not security_type:
        raise SnapshotBlockedError("listing_type_unresolved")
    listing_type = _listing_type(security_type)
    if listing_type is None:
        raise SnapshotBlockedError("unsupported_listing_type")
    snapshot_identity["listing_type"] = listing_type
    return snapshot_identity


def _as_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        candidate = to_dict()
        if isinstance(candidate, Mapping):
            return candidate
    raise TypeError("provider envelope must be a mapping or expose to_dict()")


def _identity_resolution_parts(value: Any) -> tuple[Mapping[str, Any], tuple[Mapping[str, Any], ...]]:
    resolution = _as_mapping(value)
    provider_envelopes = getattr(value, "provider_envelopes", ())
    if provider_envelopes is None:
        provider_envelopes = ()
    if not isinstance(provider_envelopes, tuple):
        raise TypeError("identity provider_envelopes must be a tuple")
    return resolution, tuple(_as_mapping(envelope) for envelope in provider_envelopes)


def _identity_provenance(envelopes: tuple[Mapping[str, Any], ...]) -> list[dict[str, str]]:
    if not envelopes:
        return []
    providers = tuple(envelope.get("provider") for envelope in envelopes)
    if providers != IDENTITY_PROVENANCE_PROVIDERS:
        raise SnapshotBlockedError("identity_provenance_incomplete")
    references: list[dict[str, str]] = []
    for envelope in envelopes:
        source = envelope.get("source")
        parse = envelope.get("parse")
        if (
            envelope.get("status") != "available"
            or not isinstance(source, Mapping)
            or not _valid_uri(source.get("uri"))
            or not _valid_sha256(source.get("content_sha256"))
            or not isinstance(envelope.get("request_id"), str)
            or not isinstance(parse, Mapping)
            or parse.get("status") != "parsed"
            or not isinstance(parse.get("transform_version"), str)
            or not parse["transform_version"]
        ):
            raise SnapshotBlockedError("identity_provenance_invalid")
        references.append(
            {
                "provider": str(envelope["provider"]),
                "source_uri": str(source["uri"]),
                "raw_content_sha256": str(source["content_sha256"]),
                "request_id": str(envelope["request_id"]),
                "transform_version": str(parse["transform_version"]),
            }
        )
    return references


def _provider_ticker(envelope: Mapping[str, Any]) -> str | None:
    data = envelope.get("data")
    if not isinstance(data, Mapping):
        return None
    identity = data.get("identity")
    if isinstance(identity, Mapping) and isinstance(identity.get("ticker"), str):
        return identity["ticker"]
    ticker = data.get("ticker")
    return ticker if isinstance(ticker, str) else None


def _assert_provider_identity(envelope: Mapping[str, Any], identity: Mapping[str, Any]) -> None:
    provided = _provider_ticker(envelope)
    expected = identity["ticker"]
    if provided is not None and provided.upper() != expected.upper():
        raise SnapshotBlockedError("provider_ticker_conflict")


def _source_version(envelope: Mapping[str, Any]) -> str:
    temporal = envelope.get("temporal")
    if isinstance(temporal, Mapping) and isinstance(temporal.get("source_version"), str) and temporal["source_version"]:
        return temporal["source_version"]
    value = envelope.get("provider_version")
    return value if isinstance(value, str) and value else "unknown"


def _fact_from_provider(
    *,
    name: str,
    field: Mapping[str, Any],
    envelope: Mapping[str, Any],
    identity_bindings: dict[str, str],
    historical_cutoff: str | None,
) -> dict[str, Any]:
    temporal = envelope.get("temporal") if isinstance(envelope.get("temporal"), Mapping) else {}
    status = field.get("availability")
    availability = status if isinstance(status, str) else str(envelope.get("status", "unavailable"))
    value = field.get("value") if availability == "available" else None
    effective_at = _date(field.get("effective_at") or temporal.get("effective_at"))
    observed_at = _date(field.get("observed_at") or temporal.get("observed_at"))
    available_at = field.get("available_at") or temporal.get("available_at")
    source = envelope.get("source") if isinstance(envelope.get("source"), Mapping) else {}
    source_uri = source.get("uri")
    raw_hash = source.get("content_sha256")
    if availability == "available" and (
        value is None
        or effective_at is None
        or observed_at is None
        or not _valid_instant(available_at)
        or not _valid_uri(source_uri)
        or not _valid_sha256(raw_hash)
        or not identity_bindings
    ):
        availability = "invalid"
        value = None
    if availability == "available" and _is_after_cutoff(available_at, historical_cutoff):
        availability = "stale"
        value = None
    fetched_at = envelope.get("fetched_at")
    fact: dict[str, Any] = {
        "name": name,
        "availability": availability,
        "value": value,
        "unit": _unit(name, field.get("unit")),
        "provider": envelope["provider"],
        "request_id": envelope["request_id"],
        "effective_at": effective_at,
        "observed_at": observed_at,
        "available_at": available_at,
        "fetched_at": fetched_at,
        "source_version": _source_version(envelope),
        "identity_bindings": identity_bindings,
    }
    period_start = _date(field.get("period_start") or temporal.get("period_start"))
    period_end = _date(field.get("period_end") or temporal.get("period_end"))
    if period_start is not None:
        fact["period_start"] = period_start
    if period_end is not None:
        fact["period_end"] = period_end
    if _valid_uri(source_uri):
        fact["source_uri"] = source_uri
    if _valid_sha256(raw_hash):
        fact["raw_content_sha256"] = raw_hash
    fact["fact_id"] = f"fact-{_canonical_hash(fact)[:20]}"
    return fact


def _unit(name: str, provider_unit: Any) -> str:
    if isinstance(provider_unit, str) and provider_unit:
        return provider_unit
    if name in {
        "market_cap",
        "enterprise_value",
        "total_revenue",
        "free_cash_flow",
        "operating_cash_flow",
        "capital_expenditure",
        "gross_profit",
        "operating_income",
        "net_income",
        "cost_of_revenue",
        "stock_based_compensation",
        "ebitda",
        "cash",
        "debt",
        "total_assets",
        "inventory",
    }:
        return "USD"
    if name in {"price"}:
        return "USD/share"
    if name in {"shares_outstanding", "diluted_shares", "diluted_average_shares"}:
        return "shares"
    if name.endswith("margin") or name.endswith("growth"):
        return "fraction"
    return "unknown"


def validate_security_snapshot(snapshot: Mapping[str, Any]) -> None:
    """Validate schema plus the reproducible snapshot and content-hash identities."""
    document = dict(snapshot)
    validate_document(document, FACT_SNAPSHOT_SCHEMA_ID)
    content_hash = document.get("content_hash")
    content_payload = dict(document)
    content_payload.pop("content_hash", None)
    if content_hash != _canonical_hash(content_payload):
        raise SnapshotIntegrityError("snapshot content_hash does not match its payload")
    id_payload = dict(content_payload)
    snapshot_id = id_payload.pop("snapshot_id", None)
    expected_snapshot_id = f"snapshot-{_canonical_hash(id_payload)[:20]}"
    if snapshot_id != expected_snapshot_id:
        raise SnapshotIntegrityError("snapshot_id does not match its payload")


def build_security_snapshot(
    run_manifest: Mapping[str, Any],
    identity_resolution: Mapping[str, Any] | Any,
    market_envelope: Mapping[str, Any] | Any,
    rs_envelope: Mapping[str, Any] | Any | None = None,
) -> dict[str, Any]:
    """Build a validated, provenance-complete snapshot without ranking or judgment."""
    as_of = run_manifest["as_of"]
    resolution, identity_envelopes = _identity_resolution_parts(identity_resolution)
    identity = _snapshot_identity(resolution)
    provenance = _identity_provenance(identity_envelopes)
    if provenance:
        identity["provenance"] = provenance
    market = _as_mapping(market_envelope)
    _assert_provider_identity(market, identity)
    data = market.get("data")
    fields = data.get("facts") if isinstance(data, Mapping) else None
    if not isinstance(fields, Mapping):
        fields = {}
    bindings = _identity_bindings(identity)
    source_policy = run_manifest.get("source_policy")
    historical_cutoff = source_policy.get("historical_cutoff") if isinstance(source_policy, Mapping) else None
    missing_status = "not_disclosed" if market.get("status") == "available" else str(market.get("status", "unavailable"))
    market_fields = {
        name: fields.get(name, {"availability": missing_status, "value": None})
        for name in sorted(set(MARKET_FIELD_NAMES) | {name for name in fields if isinstance(name, str)})
    }
    facts = [
        _fact_from_provider(
            name=name,
            field=field,
            envelope=market,
            identity_bindings=bindings,
            historical_cutoff=historical_cutoff,
        )
        for name, field in market_fields.items()
        if isinstance(name, str) and isinstance(field, Mapping)
    ]
    if rs_envelope is not None:
        rs = _as_mapping(rs_envelope)
        _assert_provider_identity(rs, identity)
        rs_data = rs.get("data")
        rs_fields = rs_data.get("fields") if isinstance(rs_data, Mapping) else None
        if isinstance(rs_fields, Mapping):
            facts.extend(
                _fact_from_provider(
                    name=name,
                    field={**field, "value": rs_data.get(name)} if "value" not in field and isinstance(rs_data, Mapping) else field,
                    envelope=rs,
                    identity_bindings=bindings,
                    historical_cutoff=historical_cutoff,
                )
                for name, field in rs_fields.items()
                if isinstance(name, str) and isinstance(field, Mapping) and name not in {"ticker", "record_date"}
            )
    facts.sort(key=lambda fact: (fact["name"], fact["fact_id"]))
    fetched_at = max(str(fact["fetched_at"]) for fact in facts)
    snapshot: dict[str, Any] = {
        "schema_id": FACT_SNAPSHOT_SCHEMA_ID,
        "run_id": run_manifest["run_id"],
        "as_of": as_of,
        "identity": identity,
        "fetched_at": fetched_at,
        "facts": facts,
    }
    content_hash = _canonical_hash(snapshot)
    snapshot["snapshot_id"] = f"snapshot-{content_hash[:20]}"
    snapshot["content_hash"] = _canonical_hash(snapshot)
    validate_security_snapshot(snapshot)
    return snapshot
