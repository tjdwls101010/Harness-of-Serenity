from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from serenity_core.outcomes import OutcomesError, OutcomesStore
from serenity_core.runtime import canonical_hash


ROOT = Path(__file__).resolve().parents[3]
PROSPECTIVE_SCHEMA = json.loads((ROOT / "schemas" / "prospective-record-1.schema.json").read_text(encoding="utf-8"))


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def finalized_decision(root: Path) -> dict:
    """Create a schema/hash-valid immutable final decision fixture."""
    run_id = "run-abc12345"
    decision = {
        "schema_id": "urn:serenity:schema:research-decision:1",
        "decision_id": "decision-nvda-0001",
        "run_id": run_id,
        "lineage_id": "lineage-nvda",
        "version": 1,
        "action": "ENTER_ON_TRIGGER",
        "as_of": "2026-08-17",
        "created_at": "2026-08-17T00:00:00Z",
        "scope": {"kind": "single-name", "subjects": ["NVDA"]},
        "thesis": "Demand remains durable, but entry needs revision stabilization.",
        "materiality": "material",
        "priced_in": {"included": ["current AI demand"], "not_included": ["networking mix"]},
        "strongest_bear_case": "Customer digestion could create a revenue air pocket.",
        "falsifiers": ["Two consecutive quarters of data-center estimate cuts."],
        "hypothesis_ids": ["hyp-abc12345"],
        "evidence_result_ids": ["result-abc12345"],
        "required_evidence": [{"evidence_result_id": "result-abc12345", "purpose": "Verify the entry trigger.", "action_critical": True}],
        "lens_results": [{"lens_result_id": "lens-result-abc12345", "validity": "valid", "fact_refs": ["fact-market-cap", "fact-forward-revenue"]}],
        "conditions": [
            {
                "condition_id": "condition-revisions-stable",
                "condition": "Forward estimates stop falling",
                "primary": True,
                "observable": {"field": "forward_revenue_revision_30d", "operator": "gte", "value": 0, "unit": "fraction"},
                "evidence_ref": {"evidence_result_id": "result-abc12345", "source_uri": "https://evidence.example/result-abc12345", "canonical_id": "fixture-result-abc12345"},
                "expires_at": "2026-11-17T00:00:00Z",
                "on_met_state": "REASSESS_REQUIRED",
                "status": "unmet",
            }
        ],
        "vehicle": {"kind": "common-stock", "ticker": "NVDA"},
        "conviction": "medium",
        "uncertainty": "Forward revisions may lag a customer digestion cycle.",
    }
    decision["finalized_at"] = "2026-08-17T12:00:00Z"
    decision["content_hash"] = canonical_hash(decision)
    version_dir = root / "records" / "decisions" / decision["lineage_id"] / "v001"
    write_json(version_dir / "decision.json", decision)
    pointer = {
        "lineage_id": decision["lineage_id"],
        "version": decision["version"],
        "decision_id": decision["decision_id"],
        "decision_content_hash": decision["content_hash"],
        "record_dir": "records/decisions/lineage-nvda/v001",
        "updated_at": "2026-08-17T12:00:00Z",
    }
    pointer["content_hash"] = canonical_hash(pointer)
    write_json(version_dir.parent / "current.json", pointer)
    return decision


def unsaved_finalized_claim() -> dict:
    return {
        "schema_id": "urn:serenity:schema:research-decision:1",
        "decision_id": "decision-nvda-0001",
        "lineage_id": "lineage-nvda",
        "action": "ENTER_ON_TRIGGER",
        "as_of": "2026-08-17",
        "conditions": [{"condition": "Forward estimates stop falling", "status": "unmet"}],
        "falsifiers": ["Two consecutive quarters of data-center estimate cuts."],
        "finalized_at": "2026-08-17T12:00:00Z",
    }


def measured_checkpoint(observation_id: str, as_of: str, price: float) -> dict:
    provenance = {"provider": "fixture", "source_version": as_of}
    return {
        "observation_id": observation_id,
        "as_of": as_of,
        "subject_price": {"availability": "available", "value": price, "currency": "USD", "provenance": provenance},
        "benchmark_return": {"availability": "available", "value": 0.02, "unit": "fraction", "provenance": provenance},
        "mechanism_evidence": {"availability": "available", "value": "Mechanism unchanged.", "summary": "Mechanism unchanged.", "provenance": provenance},
        "falsifier_state": {"availability": "available", "value": "not_triggered", "state": "not_triggered", "provenance": provenance},
    }


def test_registering_a_finalized_decision_preserves_its_prospective_contract(tmp_path: Path) -> None:
    decision = finalized_decision(tmp_path)
    record = OutcomesStore(tmp_path).register(
        decision,
        benchmark={"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust"},
        checkpoint_schedule=[{"kind": "earnings", "due_on": "2026-11-18"}],
    )

    assert record["schema_id"] == "urn:serenity:schema:prospective-record:1"
    assert record["record_id"].startswith("prospective-")
    assert record["decision"] == {
        "decision_id": "decision-nvda-0001",
        "lineage_id": "lineage-nvda",
        "version": 1,
        "decision_content_hash": decision["content_hash"],
        "current_pointer_hash": json.loads(
            (tmp_path / "records" / "decisions" / "lineage-nvda" / "current.json").read_text(encoding="utf-8")
        )["content_hash"],
        "action": "ENTER_ON_TRIGGER",
        "as_of": "2026-08-17",
        "entry_conditions": [{"condition": "Forward estimates stop falling", "status": "unmet"}],
        "falsifiers": ["Two consecutive quarters of data-center estimate cuts."],
    }
    assert record["benchmark"] == {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust"}
    assert record["checkpoint_schedule"] == [{"kind": "earnings", "due_on": "2026-11-18"}]
    assert record["condition_hit_is_trade"] is False
    assert record["observations"] == []
    Draft202012Validator(PROSPECTIVE_SCHEMA).validate(record)


def test_explicit_refresh_appends_separate_measurements_without_inferring_a_trade(tmp_path: Path) -> None:
    store = OutcomesStore(tmp_path)
    registered = store.register(
        finalized_decision(tmp_path),
        benchmark={"ticker": "SPY"},
        checkpoint_schedule=[{"kind": "earnings", "due_on": "2026-11-18"}],
    )

    refreshed = store.refresh(
        registered["record_id"],
        observation={
            "observation_id": "nvda-2026-09-17-close",
            "as_of": "2026-09-17",
            "subject_price": {
                "availability": "available",
                "value": 184.23,
                "currency": "USD",
                "provenance": {"provider": "fixture-price", "source_version": "close-2026-09-17"},
            },
            "benchmark_return": {
                "availability": "available",
                "value": 0.041,
                "unit": "fraction",
                "provenance": {"provider": "fixture-price", "source_version": "close-2026-09-17"},
            },
            "mechanism_evidence": {
                "availability": "available",
                "value": "Hyperscaler capex guidance remained intact.",
                "summary": "Hyperscaler capex guidance remained intact.",
                "provenance": {"provider": "fixture-filing", "source_version": "accession-1"},
            },
            "falsifier_state": {
                "availability": "available",
                "value": "not_triggered",
                "state": "not_triggered",
                "provenance": {"provider": "fixture-analyst", "source_version": "review-1"},
            },
            "condition_hits": [{"condition": "Forward estimates stop falling", "hit": True}],
        },
    )

    observation = refreshed["observations"][-1]
    assert observation["subject_price"]["value"] == 184.23
    assert observation["benchmark_return"]["value"] == 0.041
    assert observation["mechanism_evidence"]["summary"] == "Hyperscaler capex guidance remained intact."
    assert observation["falsifier_state"]["state"] == "not_triggered"
    assert observation["condition_hit_is_trade"] is False
    assert refreshed["condition_hit_is_trade"] is False
    assert "trade" not in observation
    assert store.read(registered["record_id"]) == refreshed
    Draft202012Validator(PROSPECTIVE_SCHEMA).validate(refreshed)


def test_refreshes_form_a_tamper_evident_hash_chain(tmp_path: Path) -> None:
    store = OutcomesStore(tmp_path)
    registered = store.register(finalized_decision(tmp_path), benchmark={"ticker": "SPY"}, checkpoint_schedule=[])
    first = store.refresh(registered["record_id"], observation=measured_checkpoint("nvda-week-1", "2026-08-24", 181.0))
    second = store.refresh(registered["record_id"], observation=measured_checkpoint("nvda-week-2", "2026-08-31", 188.0))

    assert first["observations"][0]["previous_event_hash"] == registered["content_hash"]
    assert second["observations"][1]["previous_event_hash"] == first["observations"][0]["event_hash"]
    assert len(second["observations"][1]["event_hash"]) == 64


def test_unavailable_measurements_are_retained_with_their_provenance(tmp_path: Path) -> None:
    store = OutcomesStore(tmp_path)
    registered = store.register(finalized_decision(tmp_path), benchmark={"ticker": "SPY"}, checkpoint_schedule=[])
    unavailable = {"availability": "unavailable", "value": None, "reason": "fixture outage", "provenance": {"provider": "fixture", "source_version": "1"}}

    refreshed = store.refresh(
        registered["record_id"],
        observation={
            "observation_id": "nvda-outage-1",
            "as_of": "2026-09-01",
            "subject_price": unavailable,
            "benchmark_return": unavailable,
            "mechanism_evidence": unavailable,
            "falsifier_state": unavailable,
        },
    )

    for field in ("subject_price", "benchmark_return", "mechanism_evidence", "falsifier_state"):
        assert refreshed["observations"][0][field]["availability"] == "unavailable"
        assert refreshed["observations"][0][field]["provenance"]["provider"] == "fixture"
        assert refreshed["observations"][0][field]["value"] is None


def test_every_measurement_uses_an_explicit_value_even_when_it_is_unavailable(tmp_path: Path) -> None:
    store = OutcomesStore(tmp_path)
    registered = store.register(finalized_decision(tmp_path), benchmark={"ticker": "SPY"}, checkpoint_schedule=[])
    incomplete = measured_checkpoint("nvda-incomplete-1", "2026-09-01", 181.0)
    incomplete["mechanism_evidence"].pop("value")

    with pytest.raises(OutcomesError, match="requires an explicit value"):
        store.refresh(registered["record_id"], observation=incomplete)


def test_repeating_an_observation_is_idempotent_but_a_conflicting_duplicate_is_rejected(tmp_path: Path) -> None:
    store = OutcomesStore(tmp_path)
    registered = store.register(finalized_decision(tmp_path), benchmark={"ticker": "SPY"}, checkpoint_schedule=[])
    checkpoint = measured_checkpoint("nvda-week-1", "2026-08-24", 181.0)

    once = store.refresh(registered["record_id"], observation=checkpoint)
    repeated = store.refresh(registered["record_id"], observation=checkpoint)

    assert repeated == once
    assert len(repeated["observations"]) == 1

    conflicting = measured_checkpoint("nvda-week-1", "2026-08-24", 179.0)
    with pytest.raises(OutcomesError, match="conflicting duplicate observation") as failure:
        store.refresh(registered["record_id"], observation=conflicting)
    assert (failure.value.code, failure.value.exit_code) == ("persistence_conflict", 5)


def test_registration_rejects_an_arbitrary_json_claiming_to_be_finalized(tmp_path: Path) -> None:
    with pytest.raises(OutcomesError, match="immutable decision") as failure:
        OutcomesStore(tmp_path).register(unsaved_finalized_claim(), benchmark={"ticker": "SPY"}, checkpoint_schedule=[])

    assert (failure.value.code, failure.value.exit_code) == ("usage_or_schema", 2)


def test_registration_rejects_schema_invalid_benchmark_and_checkpoint_schedule(tmp_path: Path) -> None:
    decision = finalized_decision(tmp_path)

    with pytest.raises(OutcomesError, match="prospective record fails schema validation") as failure:
        OutcomesStore(tmp_path).register(decision, benchmark={"ticker": "spy"}, checkpoint_schedule=[])
    assert (failure.value.code, failure.value.exit_code) == ("usage_or_schema", 2)

    with pytest.raises(OutcomesError, match="prospective record fails schema validation"):
        OutcomesStore(tmp_path).register(decision, benchmark={"ticker": "SPY"}, checkpoint_schedule=[{"kind": "earnings"}])


def test_tampered_root_record_blocks_read_and_refresh(tmp_path: Path) -> None:
    store = OutcomesStore(tmp_path)
    registered = store.register(finalized_decision(tmp_path), benchmark={"ticker": "SPY"}, checkpoint_schedule=[])
    record_path = tmp_path / "records" / "prospective" / registered["record_id"] / "record.json"
    tampered = json.loads(record_path.read_text(encoding="utf-8"))
    tampered["benchmark"]["ticker"] = "QQQ"
    write_json(record_path, tampered)

    with pytest.raises(OutcomesError, match="root content hash") as failure:
        store.read(registered["record_id"])
    assert (failure.value.code, failure.value.exit_code) == ("persistence_conflict", 5)
    with pytest.raises(OutcomesError, match="root content hash"):
        store.refresh(registered["record_id"], observation=measured_checkpoint("nvda-tampered", "2026-09-01", 181.0))


def test_tampered_observation_stream_blocks_read_and_prevents_another_append(tmp_path: Path) -> None:
    store = OutcomesStore(tmp_path)
    registered = store.register(finalized_decision(tmp_path), benchmark={"ticker": "SPY"}, checkpoint_schedule=[])
    store.refresh(registered["record_id"], observation=measured_checkpoint("nvda-week-1", "2026-08-24", 181.0))
    stream_path = tmp_path / "records" / "prospective" / registered["record_id"] / "observations.jsonl"
    tampered = json.loads(stream_path.read_text(encoding="utf-8"))
    tampered["subject_price"]["value"] = 1.0
    write_json(stream_path, tampered)

    with pytest.raises(OutcomesError, match="hash chain") as failure:
        store.read(registered["record_id"])
    assert (failure.value.code, failure.value.exit_code) == ("persistence_conflict", 5)
    with pytest.raises(OutcomesError, match="hash chain"):
        store.refresh(registered["record_id"], observation=measured_checkpoint("nvda-week-2", "2026-08-31", 188.0))
    assert len(stream_path.read_text(encoding="utf-8").splitlines()) == 1


def test_missing_prospective_record_is_a_typed_lifecycle_error(tmp_path: Path) -> None:
    with pytest.raises(OutcomesError, match="prospective record is missing") as failure:
        OutcomesStore(tmp_path).read("prospective-does-not-exist")

    assert (failure.value.code, failure.value.exit_code) == ("record_not_found", 3)


def test_missing_immutable_decision_record_is_a_typed_persistence_error(tmp_path: Path) -> None:
    decision = finalized_decision(tmp_path)
    (tmp_path / "records" / "decisions" / "lineage-nvda" / "v001" / "decision.json").unlink()

    with pytest.raises(OutcomesError, match="immutable decision is missing") as failure:
        OutcomesStore(tmp_path).register(decision, benchmark={"ticker": "SPY"}, checkpoint_schedule=[])

    assert (failure.value.code, failure.value.exit_code) == ("persistence_conflict", 5)
