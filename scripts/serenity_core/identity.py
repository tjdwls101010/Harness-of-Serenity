"""US-listed security identity reconciliation over source-pinned provider records."""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from serenity_core.providers.base import ProviderEnvelope
from serenity_core.providers.openfigi import OpenFigiProvider
from serenity_core.providers.sec import SecIdentityProvider


US_EXCHANGE_MARKERS = ("NASDAQ", "NYSE", "AMERICAN", "ARCA", "CBOE", "OTC", "IEX")


@dataclass(frozen=True)
class IdentityResolution:
    value: dict[str, Any]
    _provider_envelopes: tuple[ProviderEnvelope, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.value, ensure_ascii=False))

    @property
    def provider_envelopes(self) -> tuple[ProviderEnvelope, ...]:
        """Exact source envelopes retained for runtime-only raw-payload caching."""
        return self._provider_envelopes

    @property
    def raw_payloads(self) -> Mapping[str, bytes]:
        """Return a digest-keyed read-only union of exact source response bytes."""
        payloads: dict[str, bytes] = {}
        for envelope in self._provider_envelopes:
            payloads.update(envelope._raw_payloads)
        return MappingProxyType(payloads)


class IdentityResolver:
    """Resolve a US-listed identity and surface evidence failures without a verdict."""

    def __init__(self, *, sec: SecIdentityProvider, openfigi: OpenFigiProvider) -> None:
        self._sec = sec
        self._openfigi = openfigi

    def resolve(self, ticker: str) -> IdentityResolution:
        normalized_ticker = ticker.strip().upper()
        sec_lookup = self._sec.resolve(normalized_ticker)
        envelopes = [*sec_lookup.envelopes]
        provider_envelopes = [*sec_lookup.provider_envelopes]
        if sec_lookup.rejection is not None:
            return self._rejected(
                normalized_ticker,
                envelopes,
                provider_envelopes,
                status="invalid",
                rejection=sec_lookup.rejection,
            )
        if sec_lookup.exchange is None or not self._is_us_exchange(sec_lookup.exchange):
            return self._rejected(
                normalized_ticker,
                envelopes,
                provider_envelopes,
                status="invalid",
                rejection={
                    "code": "non_us_listing",
                    "reason": "SEC submission does not identify a US-listed exchange",
                    "category": "identity",
                    "retryable": False,
                },
            )

        figi_lookup = self._openfigi.lookup(normalized_ticker)
        envelopes.append(figi_lookup.envelope)
        provider_envelopes.append(figi_lookup.provider_envelope)
        if figi_lookup.record is None:
            error = figi_lookup.envelope.get("error") or {}
            return IdentityResolution(
                {
                    "schema_id": "urn:serenity:identity-resolution:1",
                    "status": "available",
                    "identity": self._identity(sec_lookup, figi=None, security_type=None),
                    "degradations": [
                        {
                            "provider": figi_lookup.envelope["provider"],
                            "status": figi_lookup.envelope["status"],
                            "reason": error.get("reason", "OpenFIGI mapping unavailable"),
                        }
                    ],
                    "provider_envelopes": envelopes,
                },
                tuple(provider_envelopes),
            )
        if not self._corroborates(normalized_ticker, figi_lookup.record):
            return self._rejected(
                normalized_ticker,
                envelopes,
                provider_envelopes,
                status="conflict",
                rejection={
                    "code": "openfigi_ticker_exchange_conflict",
                    "reason": "OpenFIGI mapping does not corroborate SEC ticker and US exchange",
                    "category": "identity",
                    "retryable": False,
                },
            )
        return IdentityResolution(
            {
                "schema_id": "urn:serenity:identity-resolution:1",
                "status": "available",
                "identity": self._identity(
                    sec_lookup,
                    figi=self._string_or_none(figi_lookup.record.get("figi")),
                    security_type=self._string_or_none(figi_lookup.record.get("securityType")),
                ),
                "degradations": [],
                "provider_envelopes": envelopes,
            },
            tuple(provider_envelopes),
        )

    @staticmethod
    def _is_us_exchange(exchange: str) -> bool:
        uppercase_exchange = exchange.upper()
        return any(marker in uppercase_exchange for marker in US_EXCHANGE_MARKERS)

    @staticmethod
    def _corroborates(ticker: str, record: dict[str, Any]) -> bool:
        mapped_ticker = IdentityResolver._string_or_none(record.get("ticker"))
        mapped_exchange = IdentityResolver._string_or_none(record.get("exchCode"))
        market_sector = IdentityResolver._string_or_none(record.get("marketSector"))
        security_type = IdentityResolver._string_or_none(record.get("securityType"))
        return (
            mapped_ticker is not None
            and mapped_ticker.upper() == ticker
            and mapped_exchange == "US"
            and market_sector == "Equity"
            and security_type is not None
        )

    @staticmethod
    def _identity(sec_lookup: Any, *, figi: str | None, security_type: str | None) -> dict[str, Any]:
        identity: dict[str, Any] = {
            "ticker": sec_lookup.ticker,
            "cik": sec_lookup.cik,
            "official_name": sec_lookup.official_name,
            "exchange": sec_lookup.exchange,
            "listing_country": "US",
            "figi": figi,
            "security_type": security_type,
        }
        # An issuer that files no website is a disclosure absence, not a broken identity: the key
        # stays out entirely so no issuer-IR domain is ever authorized for it.
        if sec_lookup.issuer_domains:
            identity["issuer_domains"] = list(sec_lookup.issuer_domains)
        return identity

    @staticmethod
    def _rejected(
        ticker: str,
        envelopes: list[dict[str, Any]],
        provider_envelopes: list[ProviderEnvelope],
        *,
        status: str,
        rejection: dict[str, Any],
    ) -> IdentityResolution:
        return IdentityResolution(
            {
                "schema_id": "urn:serenity:identity-resolution:1",
                "status": status,
                "identity": None,
                "degradations": [],
                "rejection": rejection,
                "provider_envelopes": envelopes,
                "ticker": ticker,
            },
            tuple(provider_envelopes),
        )

    @staticmethod
    def _string_or_none(value: Any) -> str | None:
        return value if isinstance(value, str) and value else None
