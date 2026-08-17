from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest

from serenity_core.providers.base import ProviderEnvelope
from serenity_core.raw_cache import RawPayloadConflictError, RawPayloadStore, cache_provider_raw_payloads


FROZEN_NOW = datetime(2026, 8, 17, tzinfo=timezone.utc)


def available_envelope(raw_content: bytes = b'{"response":"exact bytes"}') -> ProviderEnvelope:
    return ProviderEnvelope.available(
        provider="fixture",
        provider_version="v1",
        source_uri="https://fixture.test/provider",
        raw_content=raw_content,
        data={"record": "fixture"},
        fetched_at=FROZEN_NOW,
        request={"id": "fixture"},
    )


def unavailable_envelope(raw_content: bytes | None = None) -> ProviderEnvelope:
    return ProviderEnvelope.unavailable(
        provider="fixture",
        provider_version="v1",
        source_uri="https://fixture.test/provider",
        fetched_at=FROZEN_NOW,
        request={"id": "missing"},
        status="unavailable",
        reason="transport error",
        raw_content=raw_content,
    )


def test_raw_payload_store_writes_the_exact_independent_bytes_at_the_hash_path(tmp_path) -> None:
    raw_content = b"binary\x00payload\xff"
    envelope = available_envelope(raw_content)

    result = RawPayloadStore(tmp_path).cache(envelope)

    digest = hashlib.sha256(raw_content).hexdigest()
    assert result.status == "stored"
    assert result.content_sha256 == digest
    assert result.path == tmp_path / "sha256" / digest
    assert result.path.read_bytes() == raw_content
    assert result.to_dict() == {"status": "stored", "content_sha256": digest, "cache_path": str(result.path)}


def test_raw_payload_store_deduplicates_an_identical_envelope(tmp_path) -> None:
    store = RawPayloadStore(tmp_path)
    envelope = available_envelope()

    first = store.cache(envelope)
    second = store.cache(envelope)

    assert first.status == "stored"
    assert second.status == "already_present"
    assert second.path == first.path
    assert second.path.read_bytes() == b'{"response":"exact bytes"}'


def test_raw_payload_store_detects_a_tampered_existing_payload_as_a_conflict(tmp_path) -> None:
    store = RawPayloadStore(tmp_path)
    envelope = available_envelope()
    result = store.cache(envelope)
    result.path.write_bytes(b"tampered")

    with pytest.raises(RawPayloadConflictError, match="content hash does not match"):
        store.cache(envelope)


def test_raw_payload_store_returns_an_explicit_no_raw_result_for_nonavailable_without_a_response(tmp_path) -> None:
    result = RawPayloadStore(tmp_path).cache(unavailable_envelope())

    assert result.status == "no_raw_payload"
    assert result.content_sha256 is None
    assert result.path is None
    assert result.to_dict() == {"status": "no_raw_payload", "content_sha256": None, "cache_path": None}


def test_raw_payload_store_retains_a_raw_error_response_from_a_nonavailable_envelope(tmp_path) -> None:
    raw_content = b'{"error":"maintenance"}'

    result = RawPayloadStore(tmp_path).cache(unavailable_envelope(raw_content))

    assert result.status == "stored"
    assert result.path is not None
    assert result.path.read_bytes() == raw_content


def test_cache_provider_raw_payloads_is_the_batch_seam_for_live_envelopes(tmp_path) -> None:
    results = cache_provider_raw_payloads([available_envelope(), unavailable_envelope()], root=tmp_path)

    assert [result.status for result in results] == ["stored", "no_raw_payload"]


def test_cache_provider_raw_payloads_persists_every_endpoint_payload_cited_by_facts(tmp_path) -> None:
    quote_raw = b'{"endpoint":"quote"}'
    fundamentals_raw = b'{"endpoint":"fundamentals"}'
    quote_sha = hashlib.sha256(quote_raw).hexdigest()
    fundamentals_sha = hashlib.sha256(fundamentals_raw).hexdigest()
    envelope = ProviderEnvelope.available(
        provider="yfinance",
        provider_version="test",
        source_uri="https://query1.finance.yahoo.com/v10/finance/quoteSummary/NVDA",
        raw_content=quote_raw,
        raw_payloads={fundamentals_sha: fundamentals_raw},
        data={
            "facts": {
                "price": {"raw_content_sha256": quote_sha},
                "total_revenue": {"raw_content_sha256": fundamentals_sha},
            }
        },
        fetched_at=FROZEN_NOW,
        request={"ticker": "NVDA"},
    )

    results = cache_provider_raw_payloads([envelope], root=tmp_path)

    assert [result.content_sha256 for result in results] == [quote_sha, fundamentals_sha]
    assert [result.path.read_bytes() for result in results if result.path is not None] == [quote_raw, fundamentals_raw]
    assert hashlib.sha256(quote_raw + fundamentals_raw).hexdigest() not in {result.content_sha256 for result in results}
    assert "endpoint" not in repr(envelope)
    assert "endpoint" not in json.dumps(envelope.to_dict())
