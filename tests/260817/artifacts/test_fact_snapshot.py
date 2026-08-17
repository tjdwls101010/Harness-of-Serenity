from __future__ import annotations

import pytest

from serenity_v2.schema import validate_document
from serenity_v2.snapshot import SnapshotBlockedError, SnapshotIntegrityError, build_security_snapshot, validate_security_snapshot


def run_manifest(*, cutoff: str | None = None) -> dict:
    source_policy = {"policy_id": "test-policy", "allow_network": False}
    if cutoff is not None:
        source_policy["historical_cutoff"] = cutoff
    return {
        "schema_id": "urn:serenity:schema:run-manifest:2",
        "run_id": "run-nvda",
        "as_of": "2026-08-17",
        "source_policy": source_policy,
    }


def identity_resolution(*, status: str = "available", ticker: str = "NVDA") -> dict:
    return {
        "schema_id": "urn:serenity:identity-resolution:1",
        "status": status,
        "identity": {
            "ticker": ticker,
            "cik": "0001045810",
            "official_name": "NVIDIA Corporation",
            "exchange": "Nasdaq",
            "listing_country": "US",
            "figi": "BBG000BBJQV0",
            "security_type": "Common Stock",
        },
    }


def market_envelope(*, ticker: str = "NVDA", facts: dict | None = None, available_at: str = "2026-08-17T12:00:00Z") -> dict:
    return {
        "schema_id": "urn:serenity:schema:provider-envelope:1",
        "provider": "yfinance",
        "provider_version": "test-yf",
        "request_id": "req-market-nvda",
        "status": "available",
        "fetched_at": "2026-08-17T12:00:00Z",
        "source": {
            "uri": "https://query1.finance.yahoo.com/v10/finance/quoteSummary/NVDA",
            "content_sha256": "a" * 64,
        },
        "temporal": {
            "effective_at": "2026-08-17",
            "observed_at": "2026-08-17",
            "available_at": available_at,
            "source_version": "test-yf",
        },
        "data": {
            "identity": {"ticker": ticker, "name": "NVIDIA Corporation", "exchange": "NMS"},
            "facts": facts
            or {
                "market_cap": {
                    "availability": "available",
                    "value": 4_200_000_000_000,
                    "source_path": "fast_info.market_cap",
                    "effective_at": "2026-08-17",
                    "observed_at": "2026-08-17",
                    "available_at": available_at,
                }
            },
        },
    }


def rs_envelope() -> dict:
    return {
        "schema_id": "urn:serenity:schema:provider-envelope:1",
        "provider": "ibd-rs-rating",
        "provider_version": "0.3.0",
        "request_id": "req-rs-nvda",
        "status": "available",
        "fetched_at": "2026-08-17T12:00:00Z",
        "source": {"uri": "https://example.test/rs/NVDA", "content_sha256": "b" * 64},
        "temporal": {
            "effective_at": "2026-08-14",
            "observed_at": "2026-08-14",
            "available_at": "2026-08-17T12:00:00Z",
            "source_version": "2026-08-14",
        },
        "data": {
            "ticker": "NVDA",
            "record_date": "2026-08-14",
            "rs_raw": 1.2345,
            "rs_rating": 93,
            "fields": {
                "rs_raw": {
                    "availability": "available",
                    "source_path": "rs.get.rs_raw",
                    "effective_at": "2026-08-14",
                    "observed_at": "2026-08-14",
                    "available_at": "2026-08-17T12:00:00Z",
                },
                "rs_rating": {
                    "availability": "available",
                    "source_path": "rs.get.rs_rating",
                    "effective_at": "2026-08-14",
                    "observed_at": "2026-08-14",
                    "available_at": "2026-08-17T12:00:00Z",
                },
            },
        },
    }


def test_builds_a_schema_valid_snapshot_from_identity_and_market_evidence() -> None:
    snapshot = build_security_snapshot(run_manifest(), identity_resolution(), market_envelope())

    validate_document(snapshot, "urn:serenity:schema:fact-snapshot:2")
    assert snapshot["run_id"] == "run-nvda"
    assert snapshot["identity"] == {
        "requested_ticker": "NVDA",
        "ticker": "NVDA",
        "normalized_symbol": "NVDA",
        "cik": "0001045810",
        "figi": "BBG000BBJQV0",
        "name": "NVIDIA Corporation",
        "exchange": "Nasdaq",
        "listing_type": "common",
        "resolution_source": "sec+openfigi",
    }
    market_cap = next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")
    assert market_cap["value"] == 4_200_000_000_000
    assert market_cap["unit"] == "USD"
    assert market_cap["raw_content_sha256"] == "a" * 64
    assert market_cap["identity_bindings"] == {"ticker": "NVDA", "cik": "0001045810", "figi": "BBG000BBJQV0"}


def test_snapshot_preserves_sec_resolved_issuer_domains_for_later_ir_binding() -> None:
    resolution = identity_resolution()
    resolution["identity"]["issuer_domains"] = ["investor.nvidia.com", "www.nvidia.com"]

    snapshot = build_security_snapshot(run_manifest(), resolution, market_envelope())

    assert snapshot["identity"]["issuer_domains"] == ["investor.nvidia.com", "www.nvidia.com"]
    validate_document(snapshot, "urn:serenity:schema:fact-snapshot:2")
def test_historical_snapshot_excludes_facts_that_were_not_yet_available() -> None:
    snapshot = build_security_snapshot(
        run_manifest(cutoff="2026-08-16T23:59:59Z"),
        identity_resolution(),
        market_envelope(available_at="2026-08-17T12:00:00Z"),
    )

    market_cap = next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")
    assert market_cap["availability"] == "stale"
    assert market_cap["value"] is None
    assert market_cap["observed_at"] == "2026-08-17"


def test_unknown_temporal_axes_are_never_fabricated_from_run_or_fetch_time() -> None:
    market = market_envelope()
    market["temporal"] = {
        "effective_at": None,
        "observed_at": None,
        "available_at": None,
        "source_version": "test-yf",
    }
    market["data"]["facts"]["market_cap"].update(
        {"effective_at": None, "observed_at": None, "available_at": None}
    )

    snapshot = build_security_snapshot(run_manifest(), identity_resolution(), market)

    market_cap = next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")
    assert market_cap["availability"] == "invalid"
    assert market_cap["value"] is None
    assert market_cap["effective_at"] is None
    assert market_cap["observed_at"] is None
    assert market_cap["available_at"] is None


def test_missing_and_not_disclosed_market_fields_remain_explicit_null_facts() -> None:
    snapshot = build_security_snapshot(
        run_manifest(),
        identity_resolution(),
        market_envelope(
            facts={
                "forward_pe": {
                    "availability": "not_disclosed",
                    "value": None,
                    "source_path": "info.forwardPE",
                    "effective_at": "2026-08-17",
                    "observed_at": "2026-08-17",
                    "available_at": "2026-08-17T12:00:00Z",
                }
            }
        ),
    )

    facts = {fact["name"]: fact for fact in snapshot["facts"]}
    assert facts["forward_pe"]["availability"] == "not_disclosed"
    assert facts["forward_pe"]["value"] is None
    assert facts["market_cap"]["availability"] == "not_disclosed"
    assert facts["market_cap"]["value"] is None


def test_nonavailable_provider_facts_keep_time_axes_without_inventing_a_raw_hash() -> None:
    market = market_envelope()
    market["status"] = "unavailable"
    market["source"]["content_sha256"] = None
    market["data"] = None

    snapshot = build_security_snapshot(run_manifest(), identity_resolution(), market)

    market_cap = next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")
    assert market_cap["availability"] == "unavailable"
    assert market_cap["value"] is None
    assert market_cap["effective_at"] == "2026-08-17"
    assert "raw_content_sha256" not in market_cap
    validate_document(snapshot, "urn:serenity:schema:fact-snapshot:2")


def test_rs_fields_keep_the_library_record_date_and_raw_values_without_a_threshold() -> None:
    snapshot = build_security_snapshot(run_manifest(), identity_resolution(), market_envelope(), rs_envelope())

    facts = {fact["name"]: fact for fact in snapshot["facts"]}
    assert facts["rs_raw"]["value"] == 1.2345
    assert facts["rs_raw"]["effective_at"] == "2026-08-14"
    assert facts["rs_raw"]["observed_at"] == "2026-08-14"
    assert facts["rs_rating"]["value"] == 93
    assert facts["rs_rating"]["source_version"] == "2026-08-14"
    assert "leadership" not in snapshot
    assert "threshold" not in snapshot


def test_provider_ticker_collision_hard_blocks_the_snapshot_with_exit_three() -> None:
    with pytest.raises(SnapshotBlockedError) as raised:
        build_security_snapshot(run_manifest(), identity_resolution(), market_envelope(ticker="AMD"))

    assert raised.value.exit_code == 3
    assert raised.value.reason == "provider_ticker_conflict"


@pytest.mark.parametrize(
    ("security_type", "reason"),
    [(None, "listing_type_unresolved"), ("Warrant", "unsupported_listing_type")],
)
def test_snapshot_blocks_an_unresolved_or_unsupported_listing_type(security_type: str | None, reason: str) -> None:
    resolution = identity_resolution()
    resolution["identity"]["security_type"] = security_type

    with pytest.raises(SnapshotBlockedError) as raised:
        build_security_snapshot(run_manifest(), resolution, market_envelope())

    assert raised.value.exit_code == 3
    assert raised.value.reason == reason


def test_statement_units_are_explicit_and_provider_units_win_over_the_default_mapping() -> None:
    snapshot = build_security_snapshot(
        run_manifest(),
        identity_resolution(),
        market_envelope(
            facts={
                "gross_profit": {
                    "availability": "available",
                    "value": 12_500_000_000,
                    "unit": "USDm",
                    "effective_at": "2026-07-31",
                    "observed_at": "2026-07-31",
                    "available_at": "2026-08-14T12:00:00Z",
                },
                "operating_income": {
                    "availability": "available",
                    "value": 8_000_000_000,
                    "effective_at": "2026-07-31",
                    "observed_at": "2026-07-31",
                    "available_at": "2026-08-14T12:00:00Z",
                },
                "diluted_shares": {
                    "availability": "available",
                    "value": 24_000_000_000,
                    "effective_at": "2026-07-31",
                    "observed_at": "2026-07-31",
                    "available_at": "2026-08-14T12:00:00Z",
                },
                "provider_specific_numeric": {
                    "availability": "available",
                    "value": 5,
                    "effective_at": "2026-07-31",
                    "observed_at": "2026-07-31",
                    "available_at": "2026-08-14T12:00:00Z",
                },
            }
        ),
    )

    facts = {fact["name"]: fact for fact in snapshot["facts"]}
    assert facts["gross_profit"]["unit"] == "USDm"
    assert facts["operating_income"]["unit"] == "USD"
    assert facts["diluted_shares"]["unit"] == "shares"
    assert facts["provider_specific_numeric"]["unit"] == "unknown"


def test_identical_evidence_produces_stable_sorted_fact_and_snapshot_hashes() -> None:
    first = build_security_snapshot(run_manifest(), identity_resolution(), market_envelope(), rs_envelope())
    second = build_security_snapshot(run_manifest(), identity_resolution(), market_envelope(), rs_envelope())

    assert first == second
    assert first["snapshot_id"] == "snapshot-af92df817a52b6583a7b"
    assert first["content_hash"] == "783e314c6680d37e08f1879e34f5c3d4138a449fef53d9d7f74ad995658694cb"
    assert first["facts"] == sorted(first["facts"], key=lambda fact: (fact["name"], fact["fact_id"]))


def test_snapshot_integrity_validation_rejects_a_tampered_fixture() -> None:
    snapshot = build_security_snapshot(run_manifest(), identity_resolution(), market_envelope())
    validate_security_snapshot(snapshot)
    next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")["value"] = 123

    with pytest.raises(SnapshotIntegrityError, match="content_hash"):
        validate_security_snapshot(snapshot)
