from __future__ import annotations

import json
from hashlib import sha256
from urllib.error import HTTPError
from datetime import datetime, timezone
from typing import Any

import pytest

from serenity_core.identity import IdentityResolver
from serenity_core.providers.openfigi import OpenFigiProvider
from serenity_core.providers.sec import SecIdentityProvider
from serenity_core.snapshot import build_security_snapshot


COMPANY_TICKERS_URI = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URI = "https://data.sec.gov/submissions/CIK0000320193.json"
OPENFIGI_URI = "https://api.openfigi.com/v3/mapping"


def fixed_clock() -> datetime:
    return datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


class FixtureHttp:
    def __init__(self, *, gets: dict[str, bytes], post_response: bytes) -> None:
        self.gets = gets
        self.post_response = post_response

    def get(self, uri: str, headers: dict[str, str]) -> bytes:
        assert headers["User-Agent"]
        return self.gets[uri]

    def post(self, uri: str, body: bytes, headers: dict[str, str]) -> bytes:
        assert uri == OPENFIGI_URI
        assert headers["Content-Type"] == "application/json"
        assert json.loads(body) == [{"idType": "TICKER", "idValue": "AAPL", "exchCode": "US"}]
        return self.post_response


def providers(
    *,
    submission: dict[str, Any] | None = None,
    openfigi_response: list[dict[str, Any]] | None = None,
) -> tuple[SecIdentityProvider, OpenFigiProvider]:
    http = FixtureHttp(
        gets={
            COMPANY_TICKERS_URI: json.dumps(
                {
                    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
                    "1": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
                }
            ).encode(),
            SUBMISSIONS_URI: json.dumps(
                submission
                or {
                    "cik": "0000320193",
                    "name": "Apple Inc.",
                    "tickers": ["AAPL"],
                    "exchanges": ["Nasdaq"],
                    "website": "https://www.apple.com/",
                    "investorWebsite": "https://investor.apple.com/",
                }
            ).encode(),
        },
        post_response=json.dumps(
            openfigi_response
            or [
                {
                    "data": [
                        {
                            "figi": "BBG000B9XRY4",
                            "ticker": "AAPL",
                            "exchCode": "US",
                            "name": "APPLE INC",
                            "marketSector": "Equity",
                            "securityType": "Common Stock",
                        }
                    ]
                }
            ]
        ).encode(),
    )
    return (
        SecIdentityProvider(http_get=http.get, clock=fixed_clock, user_agent="Serenity research contact@domain.test"),
        OpenFigiProvider(http_post=http.post, clock=fixed_clock),
    )


def test_resolver_pins_sec_identity_and_openfigi_corroboration_with_raw_provenance() -> None:
    sec, openfigi = providers()

    resolution = IdentityResolver(sec=sec, openfigi=openfigi).resolve("aapl").to_dict()

    assert resolution["status"] == "available"
    assert resolution["identity"] == {
        "ticker": "AAPL",
        "cik": "0000320193",
        "official_name": "Apple Inc.",
        "exchange": "Nasdaq",
        "listing_country": "US",
        "figi": "BBG000B9XRY4",
        "security_type": "Common Stock",
        "issuer_domains": ["investor.apple.com", "www.apple.com"],
    }
    assert resolution["degradations"] == []
    assert [envelope["provider"] for envelope in resolution["provider_envelopes"]] == [
        "sec.company_tickers",
        "sec.submissions",
        "openfigi.mapping",
    ]
    assert all(envelope["source"]["content_sha256"] for envelope in resolution["provider_envelopes"])
    assert resolution["provider_envelopes"][0]["source"]["content_sha256"] == sha256(
        json.dumps(
            {
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
                "1": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
            }
        ).encode()
    ).hexdigest()
    assert resolution["provider_envelopes"][0]["data"]["record"] == {
        "cik_str": 320193,
        "ticker": "AAPL",
        "title": "Apple Inc.",
    }
    assert resolution["provider_envelopes"][1]["data"]["record"]["exchanges"] == ["Nasdaq"]
    assert resolution["provider_envelopes"][2]["data"]["record"]["figi"] == "BBG000B9XRY4"


def test_identity_resolution_carries_three_private_raw_payloads_into_schema_valid_snapshot_provenance() -> None:
    sec, openfigi = providers()

    resolution = IdentityResolver(sec=sec, openfigi=openfigi).resolve("AAPL")
    source_envelopes = [envelope.to_dict() for envelope in resolution.provider_envelopes]
    snapshot = build_security_snapshot(
        {
            "schema_id": "urn:serenity:schema:run-manifest:2",
            "run_id": "run-aapl",
            "as_of": "2026-08-17",
            "source_policy": {"policy_id": "test-policy", "allow_network": False},
        },
        resolution,
        {
            "schema_id": "urn:serenity:schema:provider-envelope:1",
            "provider": "fixture.market",
            "provider_version": "1",
            "request_id": "req-fixture-market",
            "status": "available",
            "fetched_at": "2026-08-17T12:00:00Z",
            "source": {"uri": "https://example.test/market/AAPL", "content_sha256": "f" * 64},
            "temporal": {
                "effective_at": "2026-08-17",
                "observed_at": "2026-08-17",
                "available_at": "2026-08-17T12:00:00Z",
                "source_version": "fixture-1",
            },
            "data": {
                "identity": {"ticker": "AAPL"},
                "facts": {
                    "market_cap": {
                        "availability": "available",
                        "value": 3_000_000_000_000,
                        "effective_at": "2026-08-17",
                        "observed_at": "2026-08-17",
                        "available_at": "2026-08-17T12:00:00Z",
                    }
                },
            },
        },
    )

    assert [envelope["provider"] for envelope in source_envelopes] == [
        "sec.company_tickers",
        "sec.submissions",
        "openfigi.mapping",
    ]
    assert [entry["raw_content_sha256"] for entry in snapshot["identity"]["provenance"]] == [
        sha256(
            json.dumps(
                {
                    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
                    "1": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
                }
            ).encode()
        ).hexdigest(),
        sha256(
                json.dumps(
                    {
                        "cik": "0000320193",
                        "name": "Apple Inc.",
                        "tickers": ["AAPL"],
                        "exchanges": ["Nasdaq"],
                        "website": "https://www.apple.com/",
                        "investorWebsite": "https://investor.apple.com/",
                    }
                ).encode()
        ).hexdigest(),
        sha256(
            json.dumps(
                [
                    {
                        "data": [
                            {
                                "figi": "BBG000B9XRY4",
                                "ticker": "AAPL",
                                "exchCode": "US",
                                "name": "APPLE INC",
                                "marketSector": "Equity",
                                "securityType": "Common Stock",
                            }
                        ]
                    }
                ]
            ).encode()
        ).hexdigest(),
    ]
    assert snapshot["identity"]["provenance"] == [
        {
            "provider": "sec.company_tickers",
            "source_uri": COMPANY_TICKERS_URI,
            "raw_content_sha256": source_envelopes[0]["source"]["content_sha256"],
            "request_id": source_envelopes[0]["request_id"],
            "transform_version": "sec-identity/1",
        },
        {
            "provider": "sec.submissions",
            "source_uri": SUBMISSIONS_URI,
            "raw_content_sha256": source_envelopes[1]["source"]["content_sha256"],
            "request_id": source_envelopes[1]["request_id"],
            "transform_version": "sec-identity/1",
        },
        {
            "provider": "openfigi.mapping",
            "source_uri": OPENFIGI_URI,
            "raw_content_sha256": source_envelopes[2]["source"]["content_sha256"],
            "request_id": source_envelopes[2]["request_id"],
            "transform_version": "openfigi-mapping/1",
        },
    ]
    expected_payloads = {
        sha256(
            json.dumps(
                {
                    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
                    "1": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
                }
            ).encode()
            ).hexdigest(): json.dumps(
            {
                "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
                "1": {"cik_str": 1652044, "ticker": "GOOGL", "title": "Alphabet Inc."},
            }
            ).encode(),
            sha256(
                json.dumps(
                    {
                        "cik": "0000320193",
                        "name": "Apple Inc.",
                        "tickers": ["AAPL"],
                        "exchanges": ["Nasdaq"],
                        "website": "https://www.apple.com/",
                        "investorWebsite": "https://investor.apple.com/",
                    }
                ).encode()
            ).hexdigest(): json.dumps(
                {
                    "cik": "0000320193",
                    "name": "Apple Inc.",
                    "tickers": ["AAPL"],
                    "exchanges": ["Nasdaq"],
                    "website": "https://www.apple.com/",
                    "investorWebsite": "https://investor.apple.com/",
                }
            ).encode(),
        sha256(
            json.dumps(
                [
                    {
                        "data": [
                            {
                                "figi": "BBG000B9XRY4",
                                "ticker": "AAPL",
                                "exchCode": "US",
                                "name": "APPLE INC",
                                "marketSector": "Equity",
                                "securityType": "Common Stock",
                            }
                        ]
                    }
                ]
            ).encode()
        ).hexdigest(): json.dumps(
            [
                {
                    "data": [
                        {
                            "figi": "BBG000B9XRY4",
                            "ticker": "AAPL",
                            "exchCode": "US",
                            "name": "APPLE INC",
                            "marketSector": "Equity",
                            "securityType": "Common Stock",
                        }
                    ]
                }
            ]
        ).encode(),
    }
    assert dict(resolution.raw_payloads) == expected_payloads


def test_resolver_keeps_sec_identity_when_openfigi_has_no_mapping() -> None:
    sec, openfigi = providers(openfigi_response=[{}])

    resolution = IdentityResolver(sec=sec, openfigi=openfigi).resolve("AAPL").to_dict()

    assert resolution["status"] == "available"
    assert resolution["identity"]["figi"] is None
    assert resolution["identity"]["security_type"] is None
    assert resolution["degradations"] == [
        {"provider": "openfigi.mapping", "status": "not_disclosed", "reason": "no mapping returned"}
    ]
    assert resolution["provider_envelopes"][-1]["status"] == "not_disclosed"


def test_resolver_marks_openfigi_ticker_or_exchange_mismatch_as_conflict() -> None:
    sec, openfigi = providers(
        openfigi_response=[
            {
                "data": [
                    {
                        "figi": "BBG000B9XRY4",
                        "ticker": "AAP",
                        "exchCode": "LN",
                        "marketSector": "Equity",
                        "securityType": "Common Stock",
                    }
                ]
            }
        ]
    )

    resolution = IdentityResolver(sec=sec, openfigi=openfigi).resolve("AAPL").to_dict()

    assert resolution["status"] == "conflict"
    assert resolution["identity"] is None
    assert resolution["rejection"] == {
        "code": "openfigi_ticker_exchange_conflict",
        "reason": "OpenFIGI mapping does not corroborate SEC ticker and US exchange",
        "category": "identity",
        "retryable": False,
    }
    assert resolution["provider_envelopes"][-1]["status"] == "available"


def test_resolver_rejects_non_us_listing_from_sec_submission() -> None:
    sec, openfigi = providers(
        submission={
            "cik": "0000320193",
            "name": "Apple Inc.",
            "tickers": ["AAPL"],
            "exchanges": ["London Stock Exchange"],
        }
    )

    resolution = IdentityResolver(sec=sec, openfigi=openfigi).resolve("AAPL").to_dict()

    assert resolution["status"] == "invalid"
    assert resolution["identity"] is None
    assert resolution["rejection"] == {
        "code": "non_us_listing",
        "reason": "SEC submission does not identify a US-listed exchange",
        "category": "identity",
        "retryable": False,
    }
    assert [envelope["provider"] for envelope in resolution["provider_envelopes"]] == [
        "sec.company_tickers",
        "sec.submissions",
    ]


def test_resolver_rejects_unknown_ticker_with_typed_sec_envelope() -> None:
    sec, openfigi = providers()

    resolution = IdentityResolver(sec=sec, openfigi=openfigi).resolve("NOPE").to_dict()

    assert resolution["status"] == "invalid"
    assert resolution["identity"] is None
    assert resolution["rejection"] == {
        "code": "unresolved_ticker",
        "reason": "ticker is not present in SEC company_tickers",
        "category": "identity",
        "retryable": False,
    }
    assert len(resolution["provider_envelopes"]) == 1
    assert resolution["provider_envelopes"][0]["status"] == "invalid"


def test_sec_provider_requires_an_explicit_user_agent_before_any_network_call(monkeypatch) -> None:
    calls: list[str] = []

    def unexpected_network(uri: str, headers: dict[str, str]) -> bytes:
        calls.append(uri)
        raise AssertionError("network must not be called without a SEC identity")

    monkeypatch.delenv("SERENITY_SEC_USER_AGENT", raising=False)
    lookup = SecIdentityProvider(http_get=unexpected_network, clock=fixed_clock).resolve("AAPL")

    assert calls == []
    assert lookup.rejection == {
        "code": "sec_user_agent_required",
        "reason": "SEC requests require user_agent or SERENITY_SEC_USER_AGENT",
        "category": "configuration",
        "retryable": False,
    }
    assert lookup.envelopes[0]["status"] == "unavailable"


def test_sec_provider_uses_the_documented_environment_user_agent(monkeypatch) -> None:
    seen_headers: list[dict[str, str]] = []

    def directory_only(uri: str, headers: dict[str, str]) -> bytes:
        seen_headers.append(headers)
        return json.dumps({}).encode()

    monkeypatch.setenv("SERENITY_SEC_USER_AGENT", "Serenity research contact@domain.test")
    monkeypatch.setenv("EDGAR_IDENTITY", "Legacy contact@domain.test")
    lookup = SecIdentityProvider(http_get=directory_only, clock=fixed_clock).resolve("AAPL")

    assert seen_headers == [{"Accept": "application/json", "User-Agent": "Serenity research contact@domain.test"}]
    assert lookup.rejection == {
        "code": "unresolved_ticker",
        "reason": "ticker is not present in SEC company_tickers",
        "category": "identity",
        "retryable": False,
    }


def test_sec_provider_accepts_legacy_edgar_identity_when_the_new_setting_is_missing(monkeypatch) -> None:
    seen_headers: list[dict[str, str]] = []

    def directory_only(uri: str, headers: dict[str, str]) -> bytes:
        seen_headers.append(headers)
        return json.dumps({}).encode()

    monkeypatch.delenv("SERENITY_SEC_USER_AGENT", raising=False)
    monkeypatch.setenv("EDGAR_IDENTITY", "Legacy contact@domain.test")
    lookup = SecIdentityProvider(http_get=directory_only, clock=fixed_clock).resolve("AAPL")

    assert seen_headers == [{"Accept": "application/json", "User-Agent": "Legacy contact@domain.test"}]
    assert lookup.rejection == {
        "code": "unresolved_ticker",
        "reason": "ticker is not present in SEC company_tickers",
        "category": "identity",
        "retryable": False,
    }


def test_sec_provider_prefers_an_injected_user_agent_over_environment_settings(monkeypatch) -> None:
    seen_headers: list[dict[str, str]] = []

    def directory_only(uri: str, headers: dict[str, str]) -> bytes:
        seen_headers.append(headers)
        return json.dumps({}).encode()

    monkeypatch.setenv("SERENITY_SEC_USER_AGENT", "Serenity environment@domain.test")
    monkeypatch.setenv("EDGAR_IDENTITY", "Legacy contact@domain.test")
    lookup = SecIdentityProvider(
        http_get=directory_only,
        clock=fixed_clock,
        user_agent="Serenity injected@domain.test",
    ).resolve("AAPL")

    assert seen_headers == [{"Accept": "application/json", "User-Agent": "Serenity injected@domain.test"}]
    assert lookup.rejection == {
        "code": "unresolved_ticker",
        "reason": "ticker is not present in SEC company_tickers",
        "category": "identity",
        "retryable": False,
    }


def test_sec_directory_http_error_is_reported_as_a_retryable_availability_failure() -> None:
    def blocked(uri: str, headers: dict[str, str]) -> bytes:
        raise HTTPError(uri, 403, "Forbidden", {}, None)

    lookup = SecIdentityProvider(
        http_get=blocked,
        clock=fixed_clock,
        user_agent="Serenity research contact@domain.test",
    ).resolve("AAPL")

    assert lookup.rejection == {
        "code": "sec_directory_unavailable",
        "reason": "SEC company_tickers could not be loaded",
        "category": "availability",
        "retryable": True,
        "http_status": 403,
        "detail": "SEC company_tickers unavailable: HTTP Error 403: Forbidden",
    }
    assert lookup.envelopes[0]["status"] == "unavailable"
    assert lookup.envelopes[0]["source"]["http_status"] == 403


def sec_provider(gets: dict[str, bytes]) -> SecIdentityProvider:
    def get(uri: str, headers: dict[str, str]) -> bytes:
        assert headers["User-Agent"]
        if uri not in gets:
            raise HTTPError(uri, 503, "Service Unavailable", {}, None)
        return gets[uri]

    return SecIdentityProvider(http_get=get, clock=fixed_clock, user_agent="Serenity research contact@domain.test")


APPLE_DIRECTORY = json.dumps({"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}}).encode()


def submissions(**overrides: Any) -> bytes:
    record = {"cik": "0000320193", "name": "Apple Inc.", "tickers": ["AAPL"], "exchanges": ["Nasdaq"]}
    record.update(overrides)
    return json.dumps(record).encode()


@pytest.mark.parametrize(
    ("gets", "expected_code", "expected_category", "expected_retryable"),
    [
        ({COMPANY_TICKERS_URI: json.dumps({}).encode()}, "unresolved_ticker", "identity", False),
        (
            {COMPANY_TICKERS_URI: json.dumps({"0": {"cik_str": "not-a-cik", "ticker": "AAPL"}}).encode()},
            "invalid_sec_cik",
            "identity",
            False,
        ),
        ({COMPANY_TICKERS_URI: APPLE_DIRECTORY}, "sec_submission_unavailable", "availability", True),
        (
            {COMPANY_TICKERS_URI: APPLE_DIRECTORY, SUBMISSIONS_URI: submissions(cik="0000000001")},
            "sec_submission_cik_conflict",
            "identity",
            False,
        ),
        (
            {COMPANY_TICKERS_URI: APPLE_DIRECTORY, SUBMISSIONS_URI: submissions(tickers=["MSFT"])},
            "sec_submission_ticker_conflict",
            "identity",
            False,
        ),
        (
            {COMPANY_TICKERS_URI: APPLE_DIRECTORY, SUBMISSIONS_URI: submissions(exchanges=[])},
            "invalid_sec_submission",
            "identity",
            False,
        ),
    ],
)
def test_every_sec_rejection_states_whether_retrying_can_help(
    gets: dict[str, bytes], expected_code: str, expected_category: str, expected_retryable: bool
) -> None:
    lookup = sec_provider(gets).resolve("AAPL")

    assert lookup.rejection is not None
    assert lookup.rejection["code"] == expected_code
    assert lookup.rejection["category"] == expected_category
    assert lookup.rejection["retryable"] is expected_retryable


def test_a_missing_sec_contact_identity_is_a_configuration_failure_not_an_outage(monkeypatch) -> None:
    monkeypatch.delenv("SERENITY_SEC_USER_AGENT", raising=False)
    monkeypatch.delenv("EDGAR_IDENTITY", raising=False)

    def unexpected_network(uri: str, headers: dict[str, str]) -> bytes:
        raise AssertionError("network must not be called without a SEC identity")

    lookup = SecIdentityProvider(http_get=unexpected_network, clock=fixed_clock).resolve("AAPL")

    assert lookup.rejection is not None
    assert lookup.rejection["category"] == "configuration"
    assert lookup.rejection["retryable"] is False
