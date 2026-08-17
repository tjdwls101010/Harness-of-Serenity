"""OpenFIGI mapping adapter with typed absence and source provenance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.request import Request, urlopen

from serenity_v2.providers.base import ProviderEnvelope


OPENFIGI_MAPPING_URI = "https://api.openfigi.com/v3/mapping"
HttpPost = Callable[[str, bytes, dict[str, str]], bytes]
Clock = Callable[[], datetime | str]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def default_http_post(uri: str, body: bytes, headers: dict[str, str]) -> bytes:
    request = Request(uri, data=body, headers=headers, method="POST")
    with urlopen(request, timeout=30) as response:  # nosec B310 - fixed OpenFIGI endpoint
        return response.read()


@dataclass(frozen=True)
class OpenFigiLookup:
    ticker: str
    envelope: dict[str, Any]
    provider_envelope: ProviderEnvelope
    record: dict[str, Any] | None


class OpenFigiProvider:
    """Look up a US ticker without converting the mapping into an investment judgment."""

    def __init__(self, *, http_post: HttpPost = default_http_post, clock: Clock = utc_now) -> None:
        self._http_post = http_post
        self._clock = clock

    def lookup(self, ticker: str, *, exchange_code: str = "US") -> OpenFigiLookup:
        normalized_ticker = ticker.strip().upper()
        request = {"ticker": normalized_ticker, "exchange_code": exchange_code}
        query = [{"idType": "TICKER", "idValue": normalized_ticker, "exchCode": exchange_code}]
        body = json.dumps(query, separators=(",", ":")).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        try:
            raw_content = self._http_post(OPENFIGI_MAPPING_URI, body, headers)
            response = json.loads(raw_content)
        except Exception as exc:  # external provider boundary
            provider_envelope = ProviderEnvelope.unavailable(
                provider="openfigi.mapping",
                provider_version="v3",
                source_uri=OPENFIGI_MAPPING_URI,
                fetched_at=self._clock(),
                request=request,
                status="unavailable",
                reason=f"OpenFIGI mapping unavailable: {exc}",
                identity_bindings={"ticker": normalized_ticker},
                parse={"status": "not_parsed", "transform_version": "openfigi-mapping/1"},
            )
            return OpenFigiLookup(
                ticker=normalized_ticker,
                record=None,
                envelope=provider_envelope.to_dict(),
                provider_envelope=provider_envelope,
            )
        record = self._first_record(response)
        if record is None:
            provider_envelope = ProviderEnvelope.unavailable(
                provider="openfigi.mapping",
                provider_version="v3",
                source_uri=OPENFIGI_MAPPING_URI,
                fetched_at=self._clock(),
                request=request,
                status="not_disclosed",
                reason="no mapping returned",
                raw_content=raw_content,
                identity_bindings={"ticker": normalized_ticker},
                parse={"status": "parsed", "transform_version": "openfigi-mapping/1"},
            )
            return OpenFigiLookup(
                ticker=normalized_ticker,
                record=None,
                envelope=provider_envelope.to_dict(),
                provider_envelope=provider_envelope,
            )
        provider_envelope = ProviderEnvelope.available(
            provider="openfigi.mapping",
            provider_version="v3",
            source_uri=OPENFIGI_MAPPING_URI,
            raw_content=raw_content,
            data={"ticker": normalized_ticker, "exchange_code": exchange_code, "record": record},
            fetched_at=self._clock(),
            request=request,
            identity_bindings={"ticker": normalized_ticker},
            parse={"status": "parsed", "transform_version": "openfigi-mapping/1"},
        )
        return OpenFigiLookup(
            ticker=normalized_ticker,
            record=record,
            envelope=provider_envelope.to_dict(),
            provider_envelope=provider_envelope,
        )

    @staticmethod
    def _first_record(response: Any) -> dict[str, Any] | None:
        if not isinstance(response, list) or not response or not isinstance(response[0], dict):
            return None
        records = response[0].get("data")
        if not isinstance(records, list) or not records or not isinstance(records[0], dict):
            return None
        return records[0]
