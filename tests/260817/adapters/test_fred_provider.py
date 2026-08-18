from __future__ import annotations

import json
from hashlib import sha256
from datetime import datetime, timezone

from serenity_core.providers.fred import FredHttpResponse, FredProvider
from serenity_core.schema import validate_document


def test_observations_use_the_knowably_visible_vintage_and_exclude_later_revision() -> None:
    requested: dict[str, str] = {}
    raw_response = json.dumps(
        {
            "observations": [
                {
                    "date": "2026-06-01",
                    "value": "4.0",
                    "realtime_start": "2026-06-15",
                    "realtime_end": "9999-12-31",
                    "vintage": "2026-06-15",
                },
                {
                    "date": "2026-06-01",
                    "value": "3.8",
                    "realtime_start": "2026-08-01",
                    "realtime_end": "9999-12-31",
                    "vintage": "2026-08-01",
                },
            ]
        }
    ).encode()

    def http_get(url: str, params: dict[str, str]) -> bytes:
        assert url == "https://api.stlouisfed.org/fred/series/observations"
        requested.update(params)
        return raw_response

    provider = FredProvider(
        api_key="test-key",
        http_get=http_get,
        clock=lambda: datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc),
    )

    envelopes = provider.observations("DGS10", cutoff="2026-07-01T00:00:00Z")

    assert requested == {
        "api_key": "test-key",
        "file_type": "json",
        "series_id": "DGS10",
        "realtime_start": "2026-06-29",
        "realtime_end": "2026-06-29",
    }
    assert len(envelopes) == 1
    envelope = envelopes[0].to_dict()
    assert envelope["status"] == "available"
    assert envelope["data"]["observation"] == {
        "date": "2026-06-01",
        "value": "4.0",
        "realtime_start": "2026-06-15",
        "realtime_end": "9999-12-31",
        "vintage": "2026-06-15",
    }
    assert envelope["source"]["content_sha256"] == sha256(raw_response).hexdigest()
    assert envelope["temporal"] == {
        "effective_at": "2026-06-01",
        "period_start": "2026-06-01",
        "period_end": "2026-06-01",
        "observed_at": "2026-06-01",
        "available_at": "2026-06-17T00:00:00Z",
        "source_version": "2026-06-15",
    }
    assert envelope["parse"] == {
        "status": "parsed",
        "transform_version": "alfred-v1",
        "message": "ALFRED availability bound is realtime_start + 2 days at 00:00:00Z; policy-derived global date upper bound, actual release time unknown",
    }
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_same_day_cutoff_never_converts_a_vintage_date_to_midnight_utc() -> None:
    raw_response = b'{"observations":[{"date":"2026-06-01","value":"4.0","realtime_start":"2026-06-15","realtime_end":"9999-12-31"}]}'
    requested: dict[str, str] = {}

    def http_get(_url: str, params: dict[str, str]) -> FredHttpResponse:
        requested.update(params)
        return FredHttpResponse(status=200, body=raw_response)

    provider = FredProvider(api_key="test-key", http_get=http_get, clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc))

    envelope = provider.observations("DGS10", cutoff="2026-06-15T20:00:00Z")[0].to_dict()

    assert requested["realtime_start"] == "2026-06-13"
    assert envelope["status"] == "unavailable"
    assert envelope["temporal"]["available_at"] is None
    assert envelope["source"]["content_sha256"] == sha256(raw_response).hexdigest()
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_date_only_cutoff_on_vintage_day_stays_unavailable() -> None:
    raw_response = b'{"observations":[{"date":"2026-06-01","value":"4.0","realtime_start":"2026-06-15","realtime_end":"9999-12-31"}]}'
    provider = FredProvider(
        api_key="test-key",
        http_get=lambda _url, _params: FredHttpResponse(status=200, body=raw_response),
        clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    envelope = provider.observations("DGS10", cutoff="2026-06-15")[0].to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["temporal"]["available_at"] is None
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_exact_global_date_upper_bound_makes_date_only_vintage_available() -> None:
    raw_response = b'{"observations":[{"date":"2026-06-01","value":"4.0","realtime_start":"2026-06-15","realtime_end":"9999-12-31"}]}'
    provider = FredProvider(
        api_key="test-key",
        http_get=lambda _url, _params: FredHttpResponse(status=200, body=raw_response),
        clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    envelope = provider.observations("DGS10", cutoff="2026-06-17T00:00:00Z")[0].to_dict()

    assert envelope["status"] == "available"
    assert envelope["temporal"]["available_at"] == "2026-06-17T00:00:00Z"
    assert envelope["data"]["observation"]["value"] == "4.0"
    assert envelope["source"]["content_sha256"] == sha256(raw_response).hexdigest()
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_date_only_cutoff_one_day_after_vintage_stays_unavailable() -> None:
    raw_response = b'{"observations":[{"date":"2026-06-01","value":"4.0","realtime_start":"2026-06-15","realtime_end":"9999-12-31"}]}'
    provider = FredProvider(
        api_key="test-key",
        http_get=lambda _url, _params: FredHttpResponse(status=200, body=raw_response),
        clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    envelope = provider.observations("DGS10", cutoff="2026-06-16")[0].to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["temporal"]["available_at"] is None
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_date_only_cutoff_two_days_after_vintage_is_available() -> None:
    raw_response = b'{"observations":[{"date":"2026-06-01","value":"4.0","realtime_start":"2026-06-15","realtime_end":"9999-12-31"}]}'
    provider = FredProvider(
        api_key="test-key",
        http_get=lambda _url, _params: FredHttpResponse(status=200, body=raw_response),
        clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    envelope = provider.observations("DGS10", cutoff="2026-06-17")[0].to_dict()

    assert envelope["status"] == "available"
    assert envelope["temporal"]["available_at"] == "2026-06-17T00:00:00Z"
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_missing_api_key_is_a_typed_unavailable_envelope() -> None:
    provider = FredProvider(
        api_key="",
        http_get=lambda _url, _params: (_ for _ in ()).throw(AssertionError("must not request")),
        clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    envelopes = provider.observations("DGS10", cutoff="2026-07-01")

    assert [envelope.to_dict()["status"] for envelope in envelopes] == ["unavailable"]
    assert envelopes[0].to_dict()["error"] == {"reason": "FRED_API_KEY is not configured"}


def test_provider_fault_is_a_typed_unavailable_envelope() -> None:
    def unavailable_http(_url: str, _params: dict[str, str]) -> bytes:
        raise OSError("network down")

    provider = FredProvider(
        api_key="test-key",
        http_get=unavailable_http,
        clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    envelopes = provider.observations("DGS10", cutoff="2026-07-01")

    assert [envelope.to_dict()["status"] for envelope in envelopes] == ["unavailable"]
    assert envelopes[0].to_dict()["error"] == {"reason": "FRED request failed: network down"}


def test_no_observation_at_cutoff_is_a_typed_unavailable_envelope() -> None:
    provider = FredProvider(
        api_key="test-key",
        http_get=lambda _url, _params: b'{"observations": []}',
        clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    envelopes = provider.observations("DGS10", cutoff="2026-07-01")

    assert [envelope.to_dict()["status"] for envelope in envelopes] == ["unavailable"]
    assert envelopes[0].to_dict()["error"] == {"reason": "FRED returned no observations available at the cutoff"}


def test_invalid_json_response_keeps_received_raw_provenance() -> None:
    raw_response = b"not-json"
    provider = FredProvider(
        api_key="test-key",
        http_get=lambda _url, _params: FredHttpResponse(status=200, body=raw_response),
        clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    envelope = provider.observations("DGS10", cutoff="2026-07-01")[0].to_dict()

    assert envelope["status"] == "invalid"
    assert envelope["source"] == {
        "uri": "https://api.stlouisfed.org/fred/series/observations",
        "content_sha256": sha256(raw_response).hexdigest(),
        "parameters": {
            "file_type": "json",
            "series_id": "DGS10",
            "realtime_start": "2026-06-29",
            "realtime_end": "2026-06-29",
        },
        "http_status": 200,
    }
    assert envelope["parse"] == {
        "status": "failed",
        "transform_version": "alfred-v1",
        "message": "FRED returned invalid JSON",
    }
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_api_error_response_keeps_raw_hash_and_known_http_status() -> None:
    raw_response = b'{"error_code":400,"error_message":"bad series"}'
    provider = FredProvider(
        api_key="test-key",
        http_get=lambda _url, _params: FredHttpResponse(status=400, body=raw_response),
        clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    envelope = provider.observations("NOPE", cutoff="2026-07-01")[0].to_dict()

    assert envelope["status"] == "unavailable"
    assert envelope["source"]["content_sha256"] == sha256(raw_response).hexdigest()
    assert envelope["source"]["http_status"] == 400
    assert envelope["source"]["parameters"]["series_id"] == "NOPE"
    assert envelope["parse"] == {"status": "parsed", "transform_version": "alfred-v1"}
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_invalid_response_shape_keeps_received_raw_provenance() -> None:
    raw_response = b'{"observations":"not-a-list"}'
    provider = FredProvider(
        api_key="test-key",
        http_get=lambda _url, _params: FredHttpResponse(status=200, body=raw_response),
        clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc),
    )

    envelope = provider.observations("DGS10", cutoff="2026-07-01")[0].to_dict()

    assert envelope["status"] == "invalid"
    assert envelope["source"]["content_sha256"] == sha256(raw_response).hexdigest()
    assert envelope["source"]["parameters"]["realtime_end"] == "2026-06-29"
    assert envelope["source"]["http_status"] == 200
    assert envelope["parse"]["status"] == "failed"
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_transport_and_unconfigured_paths_have_no_raw_response_hash() -> None:
    def unavailable_http(_url: str, _params: dict[str, str]) -> bytes:
        raise OSError("network down")

    providers = (
        FredProvider(api_key="", clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc)),
        FredProvider(api_key="test-key", http_get=unavailable_http, clock=lambda: datetime(2026, 8, 17, tzinfo=timezone.utc)),
    )

    for provider in providers:
        envelope = provider.observations("DGS10", cutoff="2026-07-01")[0].to_dict()
        assert envelope["source"]["content_sha256"] is None
        validate_document(envelope, "urn:serenity:schema:provider-envelope:1")


def test_requested_vintage_lags_the_cutoff_by_the_policy_availability_bound() -> None:
    """FRED clamps realtime_start to the queried vintage date, so asking for the
    cutoff's own vintage guarantees a bound two days past the cutoff -- every
    observation unavailable, always. Ask instead for the newest vintage the
    policy says was knowably visible by the cutoff."""

    requested: dict[str, str] = {}

    def http_get(_url: str, params: dict[str, str]) -> bytes:
        requested.update(params)
        return b'{"observations":[{"date":"2026-06-01","value":"4.0","realtime_start":"2026-08-16","realtime_end":"2026-08-16"}]}'

    provider = FredProvider(api_key="test-key", http_get=http_get, clock=lambda: datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc))

    envelope = provider.observations("DGS10", cutoff="2026-08-18T23:59:59Z")[0].to_dict()

    assert requested["realtime_start"] == "2026-08-16"
    assert requested["realtime_end"] == "2026-08-16"
    assert envelope["status"] == "available"
    assert envelope["temporal"]["available_at"] == "2026-08-18T00:00:00Z"


def test_an_observation_window_bounds_what_one_request_turns_into_evidence() -> None:
    requested: dict[str, str] = {}

    def http_get(_url: str, params: dict[str, str]) -> bytes:
        requested.update(params)
        return b'{"observations":[{"date":"2026-08-03","value":"4.7","realtime_start":"2026-08-16","realtime_end":"2026-08-16"}]}'

    provider = FredProvider(api_key="test-key", http_get=http_get, clock=lambda: datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc))

    provider.observations("DGS10", cutoff="2026-08-18T23:59:59Z", observation_start="2026-08-01", observation_end="2026-08-18")

    assert requested["observation_start"] == "2026-08-01"
    assert requested["observation_end"] == "2026-08-18"
