from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Iterable, Mapping


PROVIDER_SCHEMA_ID = "urn:serenity:schema:provider-envelope:1"
AVAILABLE_STATES = (
    "available",
    "not_disclosed",
    "not_applicable",
    "unavailable",
    "invalid",
    "not_requested",
    "stale",
    "conflict",
)
NON_AVAILABLE_STATES = tuple(state for state in AVAILABLE_STATES if state != "available")


def _iso(value: datetime | str | None) -> str | None:
    if value is None or isinstance(value, str):
        return value
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _raw_content_sha256(raw_content: bytes) -> str:
    if not isinstance(raw_content, bytes):
        raise TypeError("raw_content must be bytes")
    return hashlib.sha256(raw_content).hexdigest()


def _freeze_raw_payloads(
    raw_content: bytes | None, raw_payloads: Mapping[str, bytes] | None
) -> Mapping[str, bytes]:
    payloads: dict[str, bytes] = {}
    if raw_content is not None:
        payloads[_raw_content_sha256(raw_content)] = raw_content
    if raw_payloads is not None:
        for content_sha256, payload in raw_payloads.items():
            if not isinstance(content_sha256, str) or _raw_content_sha256(payload) != content_sha256:
                raise ValueError("raw_payloads digest does not match its exact bytes")
            payloads[content_sha256] = payload
    return MappingProxyType(payloads)


@dataclass(frozen=True)
class ProviderEnvelope:
    value: dict[str, Any]
    _raw_content: bytes | None = field(default=None, repr=False, compare=False)
    _raw_payloads: Mapping[str, bytes] = field(default_factory=lambda: MappingProxyType({}), repr=False, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "_raw_payloads", _freeze_raw_payloads(self._raw_content, self._raw_payloads))
        self._validate()

    def _validate(self) -> None:
        from serenity_v2.schema import validate_document

        validate_document(self.value, PROVIDER_SCHEMA_ID)
        if self._raw_content is not None:
            source = self.value["source"]
            if source["content_sha256"] != _raw_content_sha256(self._raw_content):
                raise ValueError("source.content_sha256 does not match private raw_content")

    def with_document(self, document: dict[str, Any]) -> "ProviderEnvelope":
        """Return a schema-validated serialized replacement without dropping private raw bytes."""
        return ProviderEnvelope(document, self._raw_content, self._raw_payloads)

    @classmethod
    def available(
        cls,
        *,
        provider: str,
        provider_version: str,
        source_uri: str,
        raw_content: bytes,
        data: Any,
        fetched_at: datetime | str,
        request: dict[str, Any],
        effective_at: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
        observed_at: str | None = None,
        available_at: str | None = None,
        source_version: str | None = None,
        raw_payloads: Mapping[str, bytes] | None = None,
        source_parameters: Mapping[str, Any] | None = None,
        http_status: int | None = None,
        identity_bindings: Mapping[str, str] | None = None,
        parse: Mapping[str, Any] | None = None,
    ) -> "ProviderEnvelope":
        return cls._build(
            provider=provider,
            provider_version=provider_version,
            source_uri=source_uri,
            raw_content=raw_content,
            raw_payloads=raw_payloads,
            data=data,
            fetched_at=fetched_at,
            request=request,
            status="available",
            error=None,
            effective_at=effective_at,
            period_start=period_start,
            period_end=period_end,
            observed_at=observed_at,
            available_at=available_at,
            source_version=source_version,
            source_parameters=source_parameters,
            http_status=http_status,
            identity_bindings=identity_bindings,
            parse=parse,
        )

    @classmethod
    def unavailable(
        cls,
        *,
        provider: str,
        provider_version: str,
        source_uri: str,
        fetched_at: datetime | str,
        request: dict[str, Any],
        status: str,
        reason: str,
        effective_at: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
        observed_at: str | None = None,
        available_at: str | None = None,
        source_version: str | None = None,
        raw_content: bytes | None = None,
        raw_payloads: Mapping[str, bytes] | None = None,
        source_parameters: Mapping[str, Any] | None = None,
        http_status: int | None = None,
        identity_bindings: Mapping[str, str] | None = None,
        parse: Mapping[str, Any] | None = None,
    ) -> "ProviderEnvelope":
        if status not in NON_AVAILABLE_STATES:
            raise ValueError(f"availability must be one of {NON_AVAILABLE_STATES}, got {status!r}")
        return cls._build(
            provider=provider,
            provider_version=provider_version,
            source_uri=source_uri,
            raw_content=raw_content,
            raw_payloads=raw_payloads,
            data=None,
            fetched_at=fetched_at,
            request=request,
            status=status,
            error={"reason": reason},
            effective_at=effective_at,
            period_start=period_start,
            period_end=period_end,
            observed_at=observed_at,
            available_at=available_at,
            source_version=source_version,
            source_parameters=source_parameters,
            http_status=http_status,
            identity_bindings=identity_bindings,
            parse=parse,
        )

    @classmethod
    def _build(
        cls,
        *,
        provider: str,
        provider_version: str,
        source_uri: str,
        raw_content: bytes | None,
        raw_payloads: Mapping[str, bytes] | None,
        data: Any,
        fetched_at: datetime | str,
        request: dict[str, Any],
        status: str,
        error: dict[str, Any] | None,
        effective_at: str | None,
        period_start: str | None,
        period_end: str | None,
        observed_at: str | None,
        available_at: str | None,
        source_version: str | None,
        source_parameters: Mapping[str, Any] | None,
        http_status: int | None,
        identity_bindings: Mapping[str, str] | None,
        parse: Mapping[str, Any] | None,
    ) -> "ProviderEnvelope":
        if status not in AVAILABLE_STATES:
            raise ValueError(f"unknown availability state: {status!r}")
        if status == "available" and not isinstance(raw_content, bytes):
            raise TypeError("raw_content must be bytes")
        content_sha256 = _raw_content_sha256(raw_content) if raw_content is not None else None
        frozen_raw_payloads = _freeze_raw_payloads(raw_content, raw_payloads)
        request_id = f"req-{_canonical_hash({'provider': provider, 'request': request})[:16]}"
        normalized_available_at = _iso(fetched_at) if status == "available" and available_at is None else available_at
        value: dict[str, Any] = {
            "schema_id": PROVIDER_SCHEMA_ID,
            "provider": provider,
            "provider_version": provider_version,
            "request_id": request_id,
            "status": status,
            "fetched_at": _iso(fetched_at),
            "source": {"uri": source_uri, "content_sha256": content_sha256},
            "temporal": {
                "effective_at": effective_at,
                "period_start": period_start,
                "period_end": period_end,
                "observed_at": observed_at,
                "available_at": normalized_available_at,
                "source_version": source_version,
            },
            "data": data,
        }
        if error is not None:
            value["error"] = error
        if source_parameters is not None:
            value["source"]["parameters"] = dict(source_parameters)
        if http_status is not None:
            value["source"]["http_status"] = http_status
        if identity_bindings is not None:
            value["identity_bindings"] = dict(identity_bindings)
        if parse is not None:
            value["parse"] = dict(parse)
        return cls(value, raw_content, frozen_raw_payloads)

    def to_dict(self) -> dict[str, Any]:
        self._validate()
        return json.loads(json.dumps(self.value, ensure_ascii=False))


def _parse_instant(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def exclude_after_cutoff(envelopes: Iterable[dict[str, Any]], cutoff: str) -> list[dict[str, Any]]:
    cutoff_at = _parse_instant(cutoff)
    included: list[dict[str, Any]] = []
    for envelope in envelopes:
        available_at = (envelope.get("temporal") or {}).get("available_at")
        if isinstance(available_at, str):
            try:
                if _parse_instant(available_at) <= cutoff_at:
                    included.append(envelope)
            except ValueError:
                continue
    return included
