"""Client-record adapter for the owned ``ibd-rs-rating`` library."""

from __future__ import annotations

import math
from hashlib import sha256
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from typing import Any

from .base import ProviderEnvelope


RawTransport = Callable[[str, str | None], bytes]


def _default_client() -> Any:
    from rs_rating import RS

    return RS()


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _normalise(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    try:
        missing = value != value
    except (TypeError, ValueError):
        missing = False
    if missing is True or str(missing) == "<NA>":
        return None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, datetime):
        return _utc_iso(value)
    if isinstance(value, date):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return _normalise(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, Mapping):
        return {str(key): _normalise(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_normalise(item) for item in value]
    return str(value)


def _field(
    value: Any,
    *,
    source_path: str,
    record_date: str | None,
    fetched_at: str,
    source_uri: str,
    raw_content_sha256: str,
) -> dict[str, Any]:
    normalised = _normalise(value)
    return {
        "availability": "invalid" if value is not None and normalised is None else ("available" if normalised is not None else "not_disclosed"),
        "value": normalised,
        "raw_value": normalised,
        "source_path": source_path,
        "effective_at": record_date,
        "observed_at": record_date,
        "available_at": fetched_at,
        "fetched_at": fetched_at,
        "source_uri": source_uri,
        "raw_content_sha256": raw_content_sha256,
    }


def _valid_record_date(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        return None


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


class RsRatingProvider:
    """Fetch an ungraded rating record from the owned library's public client."""

    def __init__(
        self,
        *,
        client: Any | None = None,
        raw_transport: RawTransport | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        provider_version: str = "0.3.0",
    ) -> None:
        self._client = client if client is not None else _default_client()
        self._raw_transport = raw_transport
        self._clock = clock
        self._provider_version = provider_version

    def fetch(self, ticker: str, *, as_of: str | None = None) -> ProviderEnvelope:
        requested_ticker = ticker.upper()
        fetched_at = _utc_iso(self._clock())
        source_uri = "https://qgoytloruyjtyasypesv.supabase.co/rest/v1/rs"
        request = {"ticker": requested_ticker, "date": as_of}
        try:
            record = self._client.get(requested_ticker, date=as_of)
        except Exception as exc:
            return ProviderEnvelope.unavailable(
                provider="ibd-rs-rating",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="unavailable",
                reason=str(exc),
                available_at=fetched_at,
            )
        if not record:
            return ProviderEnvelope.unavailable(
                provider="ibd-rs-rating",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="not_disclosed",
                reason="no RS record returned",
                available_at=fetched_at,
            )

        if not isinstance(record, Mapping):
            return ProviderEnvelope.unavailable(
                provider="ibd-rs-rating",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="invalid",
                reason="RS record is not an object",
                available_at=fetched_at,
            )
        record_ticker = record.get("ticker")
        if not isinstance(record_ticker, str) or not record_ticker.strip():
            return ProviderEnvelope.unavailable(
                provider="ibd-rs-rating",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="invalid",
                reason="RS record ticker is malformed",
                available_at=fetched_at,
            )
        if record_ticker.upper() != requested_ticker:
            return ProviderEnvelope.unavailable(
                provider="ibd-rs-rating",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="conflict",
                reason="RS record ticker does not match requested ticker",
                available_at=fetched_at,
            )
        record_date = _valid_record_date(record.get("date"))
        if record_date is None:
            return ProviderEnvelope.unavailable(
                provider="ibd-rs-rating",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="invalid",
                reason="RS record date is malformed",
                available_at=fetched_at,
            )
        if not _finite_number(record.get("rs_raw")):
            return ProviderEnvelope.unavailable(
                provider="ibd-rs-rating",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="invalid",
                reason="RS record rs_raw is not a finite number",
                available_at=fetched_at,
            )

        if self._raw_transport is None:
            return ProviderEnvelope.unavailable(
                provider="ibd-rs-rating",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="unavailable",
                reason="RS client does not expose exact raw response bytes; inject raw_transport",
                available_at=fetched_at,
            )
        try:
            raw_content = self._raw_transport(requested_ticker, as_of)
        except Exception as exc:
            return ProviderEnvelope.unavailable(
                provider="ibd-rs-rating",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="unavailable",
                reason=f"RS raw payload unavailable: {exc}",
                available_at=fetched_at,
            )
        if not isinstance(raw_content, bytes):
            return ProviderEnvelope.unavailable(
                provider="ibd-rs-rating",
                provider_version=self._provider_version,
                source_uri=source_uri,
                fetched_at=fetched_at,
                request=request,
                status="invalid",
                reason="RS raw transport must return bytes",
                available_at=fetched_at,
            )

        raw_content_sha256 = sha256(raw_content).hexdigest()
        data = {
            "ticker": _normalise(record_ticker),
            "record_date": record_date,
            "rs_raw": _normalise(record.get("rs_raw")),
            "rs_rating": _normalise(record.get("rs_rating")),
            "fields": {
                "ticker": _field(record.get("ticker"), source_path="rs.get.ticker", record_date=record_date, fetched_at=fetched_at, source_uri=source_uri, raw_content_sha256=raw_content_sha256),
                "record_date": _field(record.get("date"), source_path="rs.get.date", record_date=record_date, fetched_at=fetched_at, source_uri=source_uri, raw_content_sha256=raw_content_sha256),
                "rs_raw": _field(record.get("rs_raw"), source_path="rs.get.rs_raw", record_date=record_date, fetched_at=fetched_at, source_uri=source_uri, raw_content_sha256=raw_content_sha256),
                "rs_rating": _field(record.get("rs_rating"), source_path="rs.get.rs_rating", record_date=record_date, fetched_at=fetched_at, source_uri=source_uri, raw_content_sha256=raw_content_sha256),
            },
            "client_view": _normalise(dict(record)),
        }
        return ProviderEnvelope.available(
            provider="ibd-rs-rating",
            provider_version=self._provider_version,
            source_uri=source_uri,
            raw_content=raw_content,
            data=data,
            fetched_at=fetched_at,
            request=request,
            effective_at=record_date,
            observed_at=record_date,
            available_at=fetched_at,
            source_version=record_date,
        )
