from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = ROOT / "schemas"

EXPECTED_SCHEMAS = {
    "run-manifest-2.schema.json": "urn:serenity:schema:run-manifest:2",
    "fact-snapshot-2.schema.json": "urn:serenity:schema:fact-snapshot:2",
    "provider-envelope-1.schema.json": "urn:serenity:schema:provider-envelope:1",
    "evidence-catalog-1.schema.json": "urn:serenity:schema:evidence-catalog:1",
    "evidence-request-1.schema.json": "urn:serenity:schema:evidence-request:1",
    "evidence-result-1.schema.json": "urn:serenity:schema:evidence-result:1",
    "hypothesis-ledger-1.schema.json": "urn:serenity:schema:hypothesis-ledger:1",
    "lens-spec-1.schema.json": "urn:serenity:schema:lens-spec:1",
    "lens-result-1.schema.json": "urn:serenity:schema:lens-result:1",
    "media-review-output.schema.json": "urn:serenity:schema:media-review-output:1",
    "method-claim-synthesis.schema.json": "urn:serenity:schema:method-claim-synthesis:1",
    "method-coding-output.schema.json": "urn:serenity:schema:method-coding-output:1",
    "sector-graph-1.schema.json": "urn:serenity:schema:sector-graph:1",
    "research-decision-1.schema.json": "urn:serenity:schema:research-decision:1",
    "prospective-record-1.schema.json": "urn:serenity:schema:prospective-record:1",
    "qa-case-1.schema.json": "urn:serenity:schema:qa-case:1",
    "qa-result-1.schema.json": "urn:serenity:schema:qa-result:1",
    "candidate-result-1.schema.json": "urn:serenity:schema:candidate-result:1",
}


def load(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_schema_set_is_versioned_and_each_schema_is_valid_draft_2020_12() -> None:
    assert {path.name for path in SCHEMA_DIR.glob("*.schema.json")} == set(EXPECTED_SCHEMAS)
    for filename, schema_id in EXPECTED_SCHEMAS.items():
        schema = load(filename)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"] == schema_id
        Draft202012Validator.check_schema(schema)


def test_provider_envelope_requires_explicit_availability_and_four_time_axes() -> None:
    schema = load("provider-envelope-1.schema.json")
    valid = {
        "schema_id": "urn:serenity:schema:provider-envelope:1",
        "provider": "sec",
        "provider_version": "submissions-v1",
        "request_id": "req-abc12345",
        "status": "available",
        "fetched_at": "2026-08-17T00:00:00Z",
        "source": {"uri": "https://data.sec.gov/submissions/CIK0000320193.json", "content_sha256": "a" * 64},
        "temporal": {
            "effective_at": "2026-06-27",
            "period_start": "2026-03-30",
            "period_end": "2026-06-27",
            "observed_at": "2026-06-27",
            "available_at": "2026-07-31T20:00:00Z",
            "source_version": "0000320193-26-000079",
        },
        "data": {"ticker": "AAPL"},
    }
    Draft202012Validator(schema).validate(valid)

    missing_availability = {key: value for key, value in valid.items() if key != "status"}
    assert list(Draft202012Validator(schema).iter_errors(missing_availability))

    stale_shape = {**valid, "temporal": {"observed_at": "2026-06-27"}}
    assert list(Draft202012Validator(schema).iter_errors(stale_shape))

    unknown_status = {**valid, "status": "missing"}
    assert list(Draft202012Validator(schema).iter_errors(unknown_status))

    non_available = {
        **valid,
        "status": "unavailable",
        "data": None,
        "source": {**valid["source"], "content_sha256": None, "http_status": 503},
        "error": {"reason": "upstream unavailable", "retryable": True},
    }
    Draft202012Validator(schema).validate(non_available)

    malformed_error = {**non_available, "error": {"reason": 503}}
    assert list(Draft202012Validator(schema).iter_errors(malformed_error))

    available_error = {**valid, "error": {"reason": "must not be present"}}
    assert list(Draft202012Validator(schema).iter_errors(available_error))


@pytest.mark.parametrize(
    ("status", "value", "is_valid"),
    [("available", 42, True), ("available", None, False), ("not_disclosed", None, True), ("unavailable", 42, False)],
)
def test_fact_snapshot_never_uses_null_without_an_explicit_non_available_state(status, value, is_valid) -> None:
    schema = load("fact-snapshot-2.schema.json")
    document = {
        "schema_id": "urn:serenity:schema:fact-snapshot:2",
        "snapshot_id": "snapshot-abc12345",
        "run_id": "run-abc12345",
        "as_of": "2026-08-17",
        "identity": {"ticker": "NVDA", "cik": "0001045810", "name": "NVIDIA CORP", "exchange": "Nasdaq", "listing_type": "common"},
        "fetched_at": "2026-08-17T00:00:00Z",
        "content_hash": "b" * 64,
        "facts": [
            {
                "fact_id": "fact-abc12345",
                "name": "market_cap",
                "availability": status,
                "value": value,
                "unit": "USD",
                "provider": "yfinance",
                "request_id": "req-abc12345",
                "effective_at": "2026-08-17",
                "observed_at": "2026-08-17",
                "available_at": "2026-08-17T00:00:00Z",
                "fetched_at": "2026-08-17T00:00:00Z",
                "source_version": "1.4.1",
                "source_uri": "https://query1.finance.yahoo.com/v10/finance/quoteSummary/NVDA",
                "raw_content_sha256": "a" * 64,
                "identity_bindings": {"ticker": "NVDA"},
            }
        ],
    }
    errors = list(Draft202012Validator(schema).iter_errors(document))
    assert (not errors) is is_valid, errors


def test_fact_snapshot_available_facts_require_actual_temporal_and_source_provenance() -> None:
    schema = load("fact-snapshot-2.schema.json")
    base = {
        "schema_id": "urn:serenity:schema:fact-snapshot:2",
        "snapshot_id": "snapshot-abc12345",
        "run_id": "run-abc12345",
        "as_of": "2026-08-17",
        "identity": {"ticker": "NVDA", "name": "NVIDIA CORP", "exchange": "Nasdaq", "listing_type": "common"},
        "fetched_at": "2026-08-17T00:00:00Z",
        "content_hash": "c" * 64,
        "facts": [
            {
                "fact_id": "fact-abc12345",
                "name": "market_cap",
                "availability": "available",
                "value": 42,
                "unit": "USD",
                "provider": "yfinance",
                "request_id": "req-abc12345",
                "effective_at": "2026-08-17",
                "observed_at": "2026-08-17",
                "available_at": "2026-08-17T00:00:00Z",
                "fetched_at": "2026-08-17T00:00:00Z",
                "source_version": "1.4.1",
                "source_uri": "https://query1.finance.yahoo.com/v10/finance/quoteSummary/NVDA",
                "raw_content_sha256": "a" * 64,
                "identity_bindings": {"ticker": "NVDA"},
            }
        ],
    }
    Draft202012Validator(schema).validate(base)

    missing_available_at = {**base, "facts": [{**base["facts"][0], "available_at": None}]}
    assert list(Draft202012Validator(schema).iter_errors(missing_available_at))

    unknown_non_available = {
        **base,
        "facts": [
            {
                **base["facts"][0],
                "availability": "unavailable",
                "value": None,
                "effective_at": None,
                "observed_at": None,
                "available_at": None,
            }
        ],
    }
    Draft202012Validator(schema).validate(unknown_non_available)


def test_numeric_target_is_forbidden_without_a_valid_reproducible_lens() -> None:
    schema = load("research-decision-1.schema.json")
    base = {
        "schema_id": "urn:serenity:schema:research-decision:1",
        "decision_id": "decision-abc12345",
        "run_id": "run-abc12345",
        "lineage_id": "lineage-nvda",
        "version": 1,
        "as_of": "2026-08-17",
        "created_at": "2026-08-17T00:00:00Z",
        "scope": {"kind": "single-name", "subjects": ["NVDA"]},
        "action": "ENTER_ON_TRIGGER",
        "thesis": "Demand persists, but the price requires a measurable entry condition.",
        "materiality": "material",
        "priced_in": {"included": ["current AI growth"], "not_included": ["incremental networking mix"]},
        "strongest_bear_case": "Customer concentration turns capex digestion into a revenue air pocket.",
        "falsifiers": ["Two consecutive quarters of datacenter estimate cuts."],
        "hypothesis_ids": ["hyp-abc12345"],
        "evidence_result_ids": ["result-abc12345"],
        "required_evidence": [
            {
                "evidence_result_id": "result-abc12345",
                "purpose": "Verify the entry trigger.",
                "action_critical": True,
            }
        ],
        "lens_results": [
            {
                "lens_result_id": "lens-result-abc12345",
                "validity": "invalid",
                "fact_refs": ["fact-market-cap", "fact-forward-revenue"],
            }
        ],
        "conditions": [
            {
                "condition_id": "condition-revisions-stable",
                "condition": "Forward revenue revisions stabilize.",
                "primary": True,
                "observable": {"field": "forward_revenue_revision_30d", "operator": "gte", "value": 0, "unit": "fraction"},
                "evidence_ref": {
                    "evidence_result_id": "result-abc12345",
                    "source_uri": "https://evidence.example/result-abc12345",
                    "canonical_id": "fixture-result-abc12345",
                },
                "expires_at": "2026-11-17T00:00:00Z",
                "on_met_state": "REASSESS_REQUIRED",
                "status": "unmet",
            }
        ],
        "vehicle": {"kind": "common-stock", "ticker": "NVDA"},
        "conviction": "medium",
        "uncertainty": "Forward revisions may not capture delayed customer digestion.",
    }
    Draft202012Validator(schema).validate(base)

    with_target = {
        **base,
        "numeric_target": {
            "value": 210.0,
            "currency": "USD",
            "timeframe": "12m",
            "lens_result_id": "lens-result-abc12345",
            "lens_validity": "invalid",
            "fact_refs": ["fact-market-cap", "fact-forward-revenue"],
        },
    }
    assert list(Draft202012Validator(schema).iter_errors(with_target))

    with_target["numeric_target"]["lens_validity"] = "valid"
    Draft202012Validator(schema).validate(with_target)


def test_prospective_record_binds_an_immutable_decision_and_current_pointer() -> None:
    schema = load("prospective-record-1.schema.json")
    document = {
        "schema_id": "urn:serenity:schema:prospective-record:1",
        "record_id": "prospective-nvda-0001",
        "content_hash": "a" * 64,
        "registered_at": "2026-08-17T00:00:00Z",
        "decision": {
            "decision_id": "decision-nvda-0001",
            "lineage_id": "lineage-nvda",
            "version": 1,
            "decision_content_hash": "b" * 64,
            "current_pointer_hash": "c" * 64,
            "action": "ENTER_ON_TRIGGER",
            "as_of": "2026-08-17",
            "entry_conditions": [{"condition": "Forward estimates stabilize.", "status": "unmet"}],
            "falsifiers": ["Two estimate-cut quarters."],
        },
        "benchmark": {"ticker": "SPY"},
        "checkpoint_schedule": [],
        "condition_hit_is_trade": False,
        "observations": [],
    }
    Draft202012Validator(schema).validate(document)

    missing_lineage = {**document, "decision": {key: value for key, value in document["decision"].items() if key != "lineage_id"}}
    assert list(Draft202012Validator(schema).iter_errors(missing_lineage))

    malformed_decision_hash = {
        **document,
        "decision": {**document["decision"], "decision_content_hash": "not-a-content-hash"},
    }
    assert list(Draft202012Validator(schema).iter_errors(malformed_decision_hash))

    malformed_pointer_hash = {
        **document,
        "decision": {**document["decision"], "current_pointer_hash": "c" * 63},
    }
    assert list(Draft202012Validator(schema).iter_errors(malformed_pointer_hash))


def test_qa_result_requires_a_verdict_for_each_reported_invariant() -> None:
    schema = load("qa-result-1.schema.json")
    document = {
        "schema_id": "urn:serenity:schema:qa-result:1",
        "result_id": "qa-result-0001",
        "case_id": "qa-case-0001",
        "mode": "deterministic",
        "executed_at": "2026-08-17T00:00:00Z",
        "counts": {
            "passed": 1,
            "failed": 0,
            "total": 1,
            "denominator": "one expected invariant",
            "wilson_interval": {"lower": 0.2, "upper": 1.0},
        },
        "failure_taxonomy": [],
        "evidence_refs": ["evidence-qa-0001"],
        "reviewer_outcome": "pass",
        "reviewer": "codex-cleanroom",
        "invariant_results": [
            {
                "invariant": "Identity remains pinned.",
                "outcome": "pass",
                "evidence_refs": ["evidence-qa-0001"],
                "rationale": "The isolated packet resolves one consistent issuer identity.",
            }
        ],
    }
    Draft202012Validator(schema).validate(document)

    missing_invariant_results = {key: value for key, value in document.items() if key != "invariant_results"}
    assert list(Draft202012Validator(schema).iter_errors(missing_invariant_results))

    malformed_item = {
        **document,
        "invariant_results": [
            {"invariant": "Identity remains pinned.", "outcome": "pass", "evidence_refs": ["evidence-qa-0001"]}
        ],
    }
    assert list(Draft202012Validator(schema).iter_errors(malformed_item))
