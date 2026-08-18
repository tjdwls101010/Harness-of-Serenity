from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen

from serenity_core.providers.base import ProviderEnvelope


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"
FRED_PROVIDER_VERSION = "alfred-v1"
_AVAILABILITY_LAG_DAYS = 2
_FRED_EPOCH = "1776-07-04"
VINTAGE_MODES = ("active", "history")


@dataclass(frozen=True)
class FredHttpResponse:
    status: int
    body: bytes


HttpGet = Callable[[str, dict[str, str]], bytes | FredHttpResponse]
Clock = Callable[[], datetime]


def _default_http_get(url: str, params: dict[str, str]) -> FredHttpResponse:
    try:
        with urlopen(f"{url}?{urlencode(params)}", timeout=30) as response:  # noqa: S310
            return FredHttpResponse(status=response.status, body=response.read())
    except HTTPError as error:
        return FredHttpResponse(status=error.code, body=error.read())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _cutoff_boundary(cutoff: str) -> tuple[str, datetime]:
    """Return the newest ALFRED vintage knowably visible by the cutoff, and the cutoff.

    ALFRED echoes ``realtime_start`` as the queried vintage date, never the true
    first-release date, so asking for the cutoff's own vintage puts the
    availability bound two days past the cutoff and nothing is ever consumable.
    Asking for ``cutoff - 2 days`` is the same policy read from the other side:
    the newest vintage whose global date upper bound has already passed.
    """

    if not isinstance(cutoff, str) or not cutoff:
        raise ValueError("cutoff must be an ISO date or instant")
    try:
        if "T" in cutoff:
            instant = datetime.fromisoformat(cutoff.replace("Z", "+00:00"))
            if instant.tzinfo is None:
                instant = instant.replace(tzinfo=timezone.utc)
            cutoff_at = instant.astimezone(timezone.utc)
        else:
            cutoff_at = datetime.combine(date.fromisoformat(cutoff), time.max, tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError("cutoff must be an ISO date or instant") from error
    return (cutoff_at.date() - timedelta(days=_AVAILABILITY_LAG_DAYS)).isoformat(), cutoff_at


def _is_active_at(observation: Mapping[str, Any], cutoff: str) -> bool:
    realtime_start = observation.get("realtime_start")
    realtime_end = observation.get("realtime_end")
    if not _is_iso_date(realtime_start) or not _is_iso_date(realtime_end):
        return False
    return realtime_start <= cutoff <= realtime_end


def _was_published_by(observation: Mapping[str, Any], cutoff: str) -> bool:
    """Keep a vintage a reader at the cutoff could already have seen.

    This is ``_is_active_at`` without the upper bound. Dropping ``realtime_end``
    is the whole difference between the two capabilities: a revision superseded
    before the cutoff fails the active test precisely because it was replaced,
    which is the fact a revision history exists to record.
    """

    realtime_start = observation.get("realtime_start")
    return _is_iso_date(realtime_start) and realtime_start <= cutoff


def _is_iso_date(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _response_parts(response: bytes | FredHttpResponse) -> tuple[bytes, int | None]:
    if isinstance(response, FredHttpResponse):
        return response.body, response.status
    if isinstance(response, bytes):
        return response, None
    raise TypeError("FRED HTTP client must return bytes or FredHttpResponse")


def _availability_bound(realtime_start: str) -> tuple[str, datetime]:
    bound = datetime.combine(date.fromisoformat(realtime_start) + timedelta(days=_AVAILABILITY_LAG_DAYS), time.min, tzinfo=timezone.utc)
    return bound.isoformat(timespec="seconds").replace("+00:00", "Z"), bound


class FredProvider:
    """Preserve ALFRED vintage evidence without inventing an intraday release instant.

    ALFRED exposes ``realtime_start`` as a calendar date, not a release instant. The adapter records the raw date and treats the second following UTC midnight as a policy-derived global date upper bound, never as the actual release time. This falls strictly after the end of that civil date in every time zone. Cutoffs before the bound stay unavailable; a cutoff at or after it may consume the observation.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        http_get: HttpGet = _default_http_get,
        clock: Clock = _utc_now,
    ) -> None:
        self._api_key = api_key if api_key is not None else os.getenv("FRED_API_KEY")
        self._http_get = http_get
        self._clock = clock

    def observations(
        self,
        series_id: str,
        *,
        cutoff: str,
        observation_start: str | None = None,
        observation_end: str | None = None,
        vintages: str = "active",
    ) -> list[ProviderEnvelope]:
        fetched_at = self._clock()
        request: dict[str, Any] = {"series_id": series_id, "cutoff": cutoff, "vintages": vintages}
        if vintages not in VINTAGE_MODES:
            return [
                self._invalid(
                    request=request,
                    fetched_at=fetched_at,
                    reason="vintages must be 'active' (the vintage in force at the cutoff) or 'history' (every vintage published by then)",
                )
            ]
        try:
            vintage_date, cutoff_at = _cutoff_boundary(cutoff)
        except ValueError as error:
            return [self._invalid(request=request, fetched_at=fetched_at, reason=str(error))]

        if not self._api_key:
            return [
                ProviderEnvelope.unavailable(
                    provider="fred",
                    provider_version=FRED_PROVIDER_VERSION,
                    source_uri=FRED_OBSERVATIONS_URL,
                    fetched_at=fetched_at,
                    request=request,
                    status="unavailable",
                    reason="FRED_API_KEY is not configured",
                    parse={"status": "not_parsed", "transform_version": FRED_PROVIDER_VERSION},
                )
            ]

        params = {
            "api_key": self._api_key,
            "file_type": "json",
            "series_id": series_id,
            "realtime_start": _FRED_EPOCH if vintages == "history" else vintage_date,
            "realtime_end": vintage_date,
        }
        for name, window in (("observation_start", observation_start), ("observation_end", observation_end)):
            if isinstance(window, str) and window:
                params[name] = window
        request["params"] = {key: value for key, value in params.items() if key != "api_key"}
        try:
            raw_content, http_status = _response_parts(self._http_get(FRED_OBSERVATIONS_URL, params))
        except Exception as error:
            return [
                ProviderEnvelope.unavailable(
                    provider="fred",
                    provider_version=FRED_PROVIDER_VERSION,
                    source_uri=FRED_OBSERVATIONS_URL,
                    fetched_at=fetched_at,
                    request=request,
                    status="unavailable",
                    reason=f"FRED request failed: {error}",
                    source_parameters=request["params"],
                    parse={"status": "failed", "transform_version": FRED_PROVIDER_VERSION, "message": str(error)},
                )
            ]

        try:
            payload = json.loads(raw_content)
        except (TypeError, UnicodeDecodeError, json.JSONDecodeError):
            return [
                self._invalid(
                    request=request,
                    fetched_at=fetched_at,
                    reason="FRED returned invalid JSON",
                    raw_content=raw_content,
                    source_parameters=request["params"],
                    http_status=http_status,
                )
            ]
        if not isinstance(payload, dict):
            return [
                self._invalid(
                    request=request,
                    fetched_at=fetched_at,
                    reason="FRED response is not an object",
                    raw_content=raw_content,
                    source_parameters=request["params"],
                    http_status=http_status,
                )
            ]
        if "error_code" in payload:
            return [
                ProviderEnvelope.unavailable(
                    provider="fred",
                    provider_version=FRED_PROVIDER_VERSION,
                    source_uri=FRED_OBSERVATIONS_URL,
                    fetched_at=fetched_at,
                    request=request,
                    status="unavailable",
                    reason=f"FRED API error {payload.get('error_code')}: {payload.get('error_message', '')}".rstrip(),
                    raw_content=raw_content,
                    source_parameters=request["params"],
                    http_status=http_status,
                    parse={"status": "parsed", "transform_version": FRED_PROVIDER_VERSION},
                )
            ]
        if http_status is not None and not 200 <= http_status < 300:
            return [
                ProviderEnvelope.unavailable(
                    provider="fred",
                    provider_version=FRED_PROVIDER_VERSION,
                    source_uri=FRED_OBSERVATIONS_URL,
                    fetched_at=fetched_at,
                    request=request,
                    status="unavailable",
                    reason=f"FRED HTTP {http_status}",
                    raw_content=raw_content,
                    source_parameters=request["params"],
                    http_status=http_status,
                    parse={"status": "parsed", "transform_version": FRED_PROVIDER_VERSION},
                )
            ]

        observations = payload.get("observations")
        if not isinstance(observations, list):
            return [
                self._invalid(
                    request=request,
                    fetched_at=fetched_at,
                    reason="FRED response has no observations list",
                    raw_content=raw_content,
                    source_parameters=request["params"],
                    http_status=http_status,
                )
            ]

        envelopes: list[ProviderEnvelope] = []
        invalid_count = 0
        for observation in observations:
            if not isinstance(observation, dict):
                invalid_count += 1
                continue
            visible = _was_published_by if vintages == "history" else _is_active_at
            if not visible(observation, vintage_date):
                continue
            period = observation.get("date")
            realtime_start = observation.get("realtime_start")
            if not _is_iso_date(period) or not isinstance(realtime_start, str) or "value" not in observation:
                invalid_count += 1
                continue
            source_version = observation.get("vintage")
            if not isinstance(source_version, str) or not source_version:
                source_version = realtime_start
            available_at, bound_at = _availability_bound(realtime_start)
            if cutoff_at >= bound_at:
                envelopes.append(
                    ProviderEnvelope.available(
                        provider="fred",
                        provider_version=FRED_PROVIDER_VERSION,
                        source_uri=FRED_OBSERVATIONS_URL,
                        raw_content=raw_content,
                        data={"series_id": series_id, "observation": observation},
                        effective_at=period,
                        period_start=period,
                        period_end=period,
                        observed_at=period,
                        available_at=available_at,
                        source_version=source_version,
                        fetched_at=fetched_at,
                        request=request,
                        source_parameters=request["params"],
                        http_status=http_status,
                        parse={
                            "status": "parsed",
                            "transform_version": FRED_PROVIDER_VERSION,
                            "message": "ALFRED availability bound is realtime_start + 2 days at 00:00:00Z; policy-derived global date upper bound, actual release time unknown",
                        },
                    )
                )
            else:
                envelopes.append(
                    ProviderEnvelope.unavailable(
                        provider="fred",
                        provider_version=FRED_PROVIDER_VERSION,
                        source_uri=FRED_OBSERVATIONS_URL,
                        status="unavailable",
                        reason="ALFRED realtime_start is date-only; global date upper bound not reached",
                        raw_content=raw_content,
                        effective_at=period,
                        period_start=period,
                        period_end=period,
                        observed_at=period,
                        source_version=source_version,
                        fetched_at=fetched_at,
                        request=request,
                        source_parameters=request["params"],
                        http_status=http_status,
                        parse={
                            "status": "parsed",
                            "transform_version": FRED_PROVIDER_VERSION,
                            "message": "ALFRED realtime_start is date-only; policy-derived global date upper bound not reached, actual release time unknown",
                        },
                    )
                )
        if envelopes:
            return envelopes
        if invalid_count:
            return [
                self._invalid(
                    request=request,
                    fetched_at=fetched_at,
                    reason="FRED observations lack required vintage fields",
                    raw_content=raw_content,
                    source_parameters=request["params"],
                    http_status=http_status,
                )
            ]
        return [
            ProviderEnvelope.unavailable(
                provider="fred",
                provider_version=FRED_PROVIDER_VERSION,
                source_uri=FRED_OBSERVATIONS_URL,
                fetched_at=fetched_at,
                request=request,
                status="unavailable",
                reason="FRED returned no observations available at the cutoff",
                raw_content=raw_content,
                source_parameters=request["params"],
                http_status=http_status,
                parse={"status": "parsed", "transform_version": FRED_PROVIDER_VERSION},
            )
        ]

    def _invalid(
        self,
        *,
        request: dict[str, Any],
        fetched_at: datetime,
        reason: str,
        raw_content: bytes | None = None,
        source_parameters: Mapping[str, Any] | None = None,
        http_status: int | None = None,
    ) -> ProviderEnvelope:
        return ProviderEnvelope.unavailable(
            provider="fred",
            provider_version=FRED_PROVIDER_VERSION,
            source_uri=FRED_OBSERVATIONS_URL,
            fetched_at=fetched_at,
            request=request,
            status="invalid",
            reason=reason,
            raw_content=raw_content,
            source_parameters=source_parameters,
            http_status=http_status,
            parse={"status": "failed", "transform_version": FRED_PROVIDER_VERSION, "message": reason},
        )
