from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest

from serenity_v2.providers.base import AVAILABLE_STATES, ProviderEnvelope, exclude_after_cutoff
from serenity_v2.schema import validate_document


def test_available_envelope_preserves_source_hash_and_distinct_time_axes() -> None:
    provider_envelope = ProviderEnvelope.available(
        provider="sec",
        provider_version="submissions-v1",
        source_uri="https://data.sec.gov/submissions/CIK0000320193.json",
        raw_content=b'{"name":"Apple Inc."}',
        data={"name": "Apple Inc."},
        effective_at="2026-06-27",
        period_start="2026-03-30",
        period_end="2026-06-27",
        observed_at="2026-06-27",
        available_at="2026-07-31T20:00:00Z",
        fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        source_version="0000320193-26-000079",
        request={"cik": "0000320193"},
    )
    envelope = provider_envelope.to_dict()

    assert envelope["schema_id"] == "urn:serenity:schema:provider-envelope:1"
    assert envelope["status"] == "available"
    assert envelope["source"]["content_sha256"] == "45ca42cbc77705d2a70c445a1a2e2f5817d37a4f50cc192113ceb20ad64cc5ac"
    assert envelope["temporal"] == {
        "effective_at": "2026-06-27",
        "period_start": "2026-03-30",
        "period_end": "2026-06-27",
        "observed_at": "2026-06-27",
        "available_at": "2026-07-31T20:00:00Z",
        "source_version": "0000320193-26-000079",
    }
    assert envelope["request_id"].startswith("req-")
    assert envelope["fetched_at"] == "2026-08-17T00:00:00Z"
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_available_rejects_non_byte_raw_content() -> None:
    with pytest.raises(TypeError, match="raw_content must be bytes"):
        ProviderEnvelope.available(
            provider="sec",
            provider_version="submissions-v1",
            source_uri="https://data.sec.gov/submissions/CIK0000320193.json",
            raw_content='{"name":"Apple Inc."}',  # type: ignore[arg-type]
            data={"name": "Apple Inc."},
            fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
            request={"cik": "0000320193"},
        )


def test_provider_envelope_never_serializes_or_reprs_private_raw_bytes() -> None:
    envelope = ProviderEnvelope.available(
        provider="fixture",
        provider_version="v1",
        source_uri="https://fixture.test/provider",
        raw_content=b"private-raw-token",
        data={"record": "safe"},
        fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        request={"id": "fixture"},
    )

    assert "private-raw-token" not in repr(envelope)
    assert "private-raw-token" not in json.dumps(envelope.to_dict())


def test_private_raw_bytes_must_match_the_serialized_source_hash_on_every_output() -> None:
    envelope = ProviderEnvelope.available(
        provider="fixture",
        provider_version="v1",
        source_uri="https://fixture.test/provider",
        raw_content=b"raw-response",
        data={"record": "safe"},
        fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        request={"id": "fixture"},
    )
    envelope.value["source"]["content_sha256"] = "a" * 64

    with pytest.raises(ValueError, match="does not match private raw_content"):
        envelope.to_dict()


def test_declared_private_raw_payload_hashes_must_match_their_exact_bytes() -> None:
    with pytest.raises(ValueError, match="raw_payloads digest does not match"):
        ProviderEnvelope.available(
            provider="fixture",
            provider_version="v1",
            source_uri="https://fixture.test/provider",
            raw_content=b"quote-response",
            raw_payloads={"a" * 64: b"fundamentals-response"},
            data={"record": "safe"},
            fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
            request={"id": "fixture"},
        )


@pytest.mark.parametrize("status", tuple(state for state in AVAILABLE_STATES if state != "available"))
def test_each_non_available_state_is_a_schema_valid_typed_error(status: str) -> None:
    envelope = ProviderEnvelope.unavailable(
        provider="openfigi",
        provider_version="v3",
        source_uri="https://api.openfigi.com/v3/mapping",
        fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        request={"ticker": "NOPE"},
        status=status,
        reason="no mapping returned",
        raw_content=b'{"error":"no mapping returned"}',
        source_parameters={"idType": "TICKER"},
        http_status=404,
        identity_bindings={"ticker": "NOPE"},
        parse={"status": "failed", "transform_version": "openfigi-v3", "message": "mapping failed"},
    ).to_dict()

    assert set(AVAILABLE_STATES) == {
        "available",
        "not_disclosed",
        "not_applicable",
        "unavailable",
        "invalid",
        "not_requested",
        "stale",
        "conflict",
    }
    assert envelope["status"] == status
    assert envelope["data"] is None
    assert envelope["error"] == {"reason": "no mapping returned"}
    assert envelope["source"]["content_sha256"] == hashlib.sha256(b'{"error":"no mapping returned"}').hexdigest()
    assert envelope["source"]["parameters"] == {"idType": "TICKER"}
    assert envelope["source"]["http_status"] == 404
    assert envelope["identity_bindings"] == {"ticker": "NOPE"}
    assert envelope["parse"]["status"] == "failed"
    assert all(key in envelope["temporal"] for key in ("effective_at", "observed_at", "available_at", "source_version"))
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_unavailable_without_a_response_uses_a_null_hash() -> None:
    envelope = ProviderEnvelope.unavailable(
        provider="openfigi",
        provider_version="v3",
        source_uri="https://api.openfigi.com/v3/mapping",
        fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        request={"ticker": "NOPE"},
        status="unavailable",
        reason="transport error",
    ).to_dict()

    assert envelope["source"]["content_sha256"] is None
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")

    repeated_request = ProviderEnvelope.unavailable(
        provider="openfigi",
        provider_version="v3",
        source_uri="https://api.openfigi.com/v3/mapping",
        fetched_at=datetime(2026, 8, 18, tzinfo=timezone.utc),
        request={"ticker": "NOPE"},
        status="not_disclosed",
        reason="no mapping returned",
    ).to_dict()
    assert repeated_request["request_id"] == envelope["request_id"]


def test_direct_provider_envelope_construction_cannot_bypass_schema_validation() -> None:
    with pytest.raises(ValueError, match="provider-envelope:1"):
        ProviderEnvelope({"schema_id": "urn:serenity:schema:provider-envelope:1"})


def test_cutoff_filter_uses_available_at_not_observation_date() -> None:
    before = ProviderEnvelope.available(
        provider="fred",
        provider_version="alfred-v1",
        source_uri="https://api.stlouisfed.org/fred/series/observations",
        raw_content=b"before",
        data={"date": "2026-06-01", "value": "4.0"},
        observed_at="2026-06-01",
        available_at="2026-06-15T00:00:00Z",
        fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        request={"series_id": "DGS10"},
        source_version="2026-06-15",
    ).to_dict()
    revised_later = ProviderEnvelope.available(
        provider="fred",
        provider_version="alfred-v1",
        source_uri="https://api.stlouisfed.org/fred/series/observations",
        raw_content=b"after",
        data={"date": "2026-06-01", "value": "3.8"},
        observed_at="2026-06-01",
        available_at="2026-08-01T00:00:00Z",
        fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        request={"series_id": "DGS10"},
        source_version="2026-08-01",
    ).to_dict()

    assert exclude_after_cutoff([before, revised_later], "2026-07-01T00:00:00Z") == [before]


def test_cutoff_filter_skips_malformed_available_timestamps() -> None:
    valid = ProviderEnvelope.available(
        provider="fred",
        provider_version="alfred-v1",
        source_uri="https://api.stlouisfed.org/fred/series/observations",
        raw_content=b"valid",
        data={"date": "2026-06-01", "value": "4.0"},
        observed_at="2026-06-01",
        available_at="2026-06-15T00:00:00Z",
        fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        request={"series_id": "DGS10"},
        source_version="2026-06-15",
    ).to_dict()
    malformed = {**valid, "temporal": {**valid["temporal"], "available_at": "definitely-not-a-timestamp"}}

    assert exclude_after_cutoff([malformed, valid], "2026-07-01T00:00:00Z") == [valid]


def test_unavailable_rejects_an_unknown_status() -> None:
    with pytest.raises(ValueError, match="availability"):
        ProviderEnvelope.unavailable(
            provider="x",
            provider_version="1",
            source_uri="https://example.test",
            fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
            request={},
            status="missing",
            reason="bad",
        )
