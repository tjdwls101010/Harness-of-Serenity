from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from serenity_core.lens import run_lens


ROOT = Path(__file__).resolve().parents[3]
SPEC_SCHEMA = json.loads((ROOT / "schemas" / "lens-spec-1.schema.json").read_text(encoding="utf-8"))
RESULT_SCHEMA = json.loads((ROOT / "schemas" / "lens-result-1.schema.json").read_text(encoding="utf-8"))


def snapshot(*facts: dict) -> dict:
    return {
        "schema_id": "urn:serenity:schema:fact-snapshot:2",
        "snapshot_id": "snapshot-nvda",
        "run_id": "run-nvda",
        "as_of": "2026-08-17",
        "identity": {"ticker": "NVDA", "cik": "0001045810", "name": "NVIDIA CORP", "exchange": "Nasdaq"},
        "fetched_at": "2026-08-17T00:00:00Z",
        "facts": list(facts),
    }


def fact(fact_id: str, name: str, value: float | None, *, availability: str = "available", unit: str = "USD") -> dict:
    return {
        "fact_id": fact_id,
        "name": name,
        "availability": availability,
        "value": value,
        "unit": unit,
        "provider": "fixture",
        "request_id": "req-fixture",
        "effective_at": "2026-08-17",
        "observed_at": "2026-08-17",
        "available_at": "2026-08-17T00:00:00Z",
        "fetched_at": "2026-08-17T00:00:00Z",
        "source_version": "fixture-1",
    }


def spec(formula: str, inputs: list[tuple[str, str, str]], *, output_unit: str = "unitless") -> dict:
    document = {
        "schema_id": "urn:serenity:schema:lens-spec:1",
        "lens_id": "lens-fixture",
        "run_id": "run-nvda",
        "question": "What does this declared arithmetic imply?",
        "formula": formula,
        "inputs": [{"name": name, "fact_ref": fact_ref, "unit": unit} for name, fact_ref, unit in inputs],
        "output_unit": output_unit,
        "assumptions": [],
        "validity_constraints": ["All operands must resolve by fact_ref."],
    }
    Draft202012Validator(SPEC_SCHEMA).validate(document)
    return document


def assert_schema(result: dict) -> None:
    Draft202012Validator(RESULT_SCHEMA).validate(result)


def test_content_volume_resolves_each_operand_from_fact_refs_and_emits_reproducible_math() -> None:
    result = run_lens(
        spec(
            "content-volume",
            [("content_per_unit", "fact-content", "USD"), ("volume", "fact-volume", "USD"), ("market_cap", "fact-market-cap", "USD")],
            output_unit="fraction",
        ),
        snapshot(fact("fact-content", "content_per_unit", 40), fact("fact-volume", "annual_unit_volume", 100), fact("fact-market-cap", "market_cap", 1_000)),
    )

    assert_schema(result)
    assert result["validity"] == "valid"
    assert result["output"]["value"] == 4.0
    assert result["output"]["unit"] == "fraction"
    assert result["fact_refs"] == ["fact-content", "fact-market-cap", "fact-volume"]
    assert result["input_facts"][0]["value"] == 40
    assert result["output"]["expression"] == "content_per_unit * volume / market_cap"
    assert result["output"]["calculation_steps"][-1]["result"] == 4.0
    assert len(result["reproducibility_hash"]) == 64


def test_missing_fact_is_insufficient_evidence_not_an_exception() -> None:
    result = run_lens(
        spec("net-cash-after-atm", [("cash", "fact-cash", "USD"), ("atm_proceeds", "fact-atm", "USD"), ("debt", "fact-debt", "USD")]),
        snapshot(fact("fact-cash", "cash", 100), fact("fact-debt", "debt", 25)),
    )

    assert_schema(result)
    assert result["validity"] == "insufficient_evidence"
    assert result["output"]["value"] is None
    assert result["output"]["issues"] == [{"code": "fact_not_found", "fact_ref": "fact-atm"}]


def test_unavailable_fact_is_preserved_as_insufficient_evidence() -> None:
    result = run_lens(
        spec("pro-forma-fcf", [("revenue", "fact-revenue", "USD"), ("fcf_margin", "fact-margin", "fraction"), ("market_cap", "fact-market-cap", "USD")]),
        snapshot(fact("fact-revenue", "revenue", 100), fact("fact-margin", "fcf_margin", None, availability="not_disclosed", unit="fraction"), fact("fact-market-cap", "market_cap", 1_000)),
    )

    assert_schema(result)
    assert result["validity"] == "insufficient_evidence"
    assert result["input_facts"][1]["availability"] == "not_disclosed"
    assert result["output"]["issues"] == [{"code": "fact_not_available", "fact_ref": "fact-margin", "availability": "not_disclosed"}]


def test_conflicting_duplicate_or_mismatched_fact_is_invalid() -> None:
    result = run_lens(
        spec("net-cash-after-atm", [("cash", "fact-cash", "USD"), ("atm_proceeds", "fact-atm", "USD"), ("debt", "fact-debt", "USD")]),
        snapshot(fact("fact-cash", "cash", 100), fact("fact-cash", "cash", 125), fact("fact-atm", "atm_proceeds", 10), fact("fact-debt", "debt", 25)),
    )

    assert_schema(result)
    assert result["validity"] == "invalid"
    assert result["output"]["value"] is None
    assert result["output"]["issues"] == [{"code": "conflict", "reason": "duplicate_fact", "fact_ref": "fact-cash"}]


def test_unit_mismatch_is_invalid_and_keeps_the_source_fact_reference() -> None:
    result = run_lens(
        spec("net-cash-after-atm", [("cash", "fact-cash", "USD"), ("atm_proceeds", "fact-atm", "USD"), ("debt", "fact-debt", "USD")]),
        snapshot(fact("fact-cash", "cash", 100, unit="EUR"), fact("fact-atm", "atm_proceeds", 10), fact("fact-debt", "debt", 25)),
    )

    assert_schema(result)
    assert result["validity"] == "invalid"
    assert result["fact_refs"] == ["fact-atm", "fact-cash", "fact-debt"]
    assert result["output"]["issues"] == [{"code": "conflict", "reason": "unit_mismatch", "fact_ref": "fact-cash", "expected_unit": "USD", "actual_unit": "EUR"}]


def test_unsafe_custom_expression_is_invalid_without_evaluating_code() -> None:
    result = run_lens(
        spec("__import__('os').system('false')", [("cash", "fact-cash", "USD")]),
        snapshot(fact("fact-cash", "cash", 100)),
    )

    assert_schema(result)
    assert result["validity"] == "invalid"
    assert result["output"]["value"] is None
    assert result["output"]["issues"] == [{"code": "unsafe_expression", "message": "only numeric arithmetic is allowed"}]


def test_safe_custom_arithmetic_uses_only_the_referenced_fact_values() -> None:
    result = run_lens(
        spec("(cash + 12) / shares", [("cash", "fact-cash", "USD"), ("shares", "fact-shares", "shares")], output_unit="USD"),
        snapshot(fact("fact-cash", "cash", 88), fact("fact-shares", "shares", 4, unit="shares")),
    )

    assert_schema(result)
    assert result["validity"] == "valid"
    assert result["output"]["value"] == 25.0


@pytest.mark.parametrize(
    ("formula", "inputs", "facts", "expected"),
    [
        ("mw-irr", [("annual_cash_flow", "fact-cash-flow", "USD"), ("invested_capital", "fact-capital", "USD")], [fact("fact-cash-flow", "annual_cash_flow", 30), fact("fact-capital", "invested_capital", 120)], 0.25),
        ("replacement-cost", [("capacity", "fact-capacity", "MW"), ("replacement_cost_per_unit", "fact-cost", "USD"), ("market_cap", "fact-market-cap", "USD")], [fact("fact-capacity", "capacity", 4, unit="MW"), fact("fact-cost", "replacement_cost_per_unit", 50), fact("fact-market-cap", "market_cap", 1_000)], 0.2),
        ("pro-forma-fcf", [("revenue", "fact-revenue", "USD"), ("fcf_margin", "fact-margin", "fraction"), ("market_cap", "fact-market-cap", "USD")], [fact("fact-revenue", "revenue", 1000), fact("fact-margin", "fcf_margin", 0.2, unit="fraction"), fact("fact-market-cap", "market_cap", 1000)], 0.2),
        ("net-cash-after-atm", [("cash", "fact-cash", "USD"), ("atm_proceeds", "fact-atm", "USD"), ("debt", "fact-debt", "USD")], [fact("fact-cash", "cash", 100), fact("fact-atm", "atm_proceeds", 50), fact("fact-debt", "debt", 20)], 130),
        ("sum-of-parts", [("core", "fact-core", "USD"), ("option", "fact-option", "USD")], [fact("fact-core", "core_value", 80), fact("fact-option", "option_value", 20)], 100),
    ],
)
def test_supported_lenses_calculate_only_from_referenced_facts(formula: str, inputs: list[tuple[str, str, str]], facts: list[dict], expected: float) -> None:
    result = run_lens(spec(formula, inputs), snapshot(*facts))

    assert_schema(result)
    assert result["validity"] == "valid"
    assert result["output"]["value"] == expected


def test_declared_evidence_refs_change_the_reproducibility_hash() -> None:
    """`_input_specs` dropped evidence_refs, so two specs citing different filings
    hashed identically. A chain back to an accession is only worth something if
    changing it changes the result's identity."""

    def spec(evidence_refs: list[str]) -> dict:
        return {
            "schema_id": "urn:serenity:schema:lens-spec:1",
            "lens_id": "lens-hash-check",
            "run_id": "run-abc12345",
            "question": "Does the declared evidence bind the hash?",
            "formula": "market_cap / market_cap",
            "output_unit": "multiple",
            "assumptions": ["Identity ratio isolates the hash."],
            "validity_constraints": ["One input only."],
            "inputs": [{"name": "market_cap", "fact_ref": "fact-market-cap", "unit": "USD", "evidence_refs": evidence_refs}],
        }

    snapshot = {
        "schema_id": "urn:serenity:schema:fact-snapshot:2",
        "fetched_at": "2026-08-17T00:00:00Z",
        "facts": [{"fact_id": "fact-market-cap", "availability": "available", "value": 4_000_000_000_000, "unit": "USD"}],
    }

    first = run_lens(spec(["evidence-result-aaaaaaaaaaaaaaaaaaaa"]), snapshot)
    second = run_lens(spec(["evidence-result-bbbbbbbbbbbbbbbbbbbb"]), snapshot)

    assert first["validity"] == "valid" and second["validity"] == "valid"
    assert first["reproducibility_hash"] != second["reproducibility_hash"]


def test_a_lens_unions_facts_across_every_snapshot_it_is_given() -> None:
    """Indexing one snapshot meant a lens could reach only the security snapshot's
    provider-derived numbers, never a fact derived from a filing's own XBRL."""

    security = {
        "schema_id": "urn:serenity:schema:fact-snapshot:2",
        "fetched_at": "2026-08-17T00:00:00Z",
        "facts": [{"fact_id": "fact-market-cap", "availability": "available", "value": 4_000_000_000_000, "unit": "USD"}],
    }
    derived = {
        "schema_id": "urn:serenity:schema:fact-snapshot:2",
        "fetched_at": "2026-05-20T20:35:52Z",
        "facts": [{"fact_id": "quarterly_revenue", "availability": "available", "value": 74_550_000_000, "unit": "USD"}],
    }
    spec = {
        "schema_id": "urn:serenity:schema:lens-spec:1",
        "lens_id": "lens-union",
        "run_id": "run-abc12345",
        "question": "What multiple does the filing's own revenue imply?",
        "formula": "market_cap / quarterly_revenue",
        "output_unit": "multiple",
        "assumptions": ["Quarterly revenue is not annualised."],
        "validity_constraints": ["Both facts share the USD unit."],
        "inputs": [
            {"name": "market_cap", "fact_ref": "fact-market-cap", "unit": "USD"},
            {"name": "quarterly_revenue", "fact_ref": "quarterly_revenue", "unit": "USD"},
        ],
    }

    result = run_lens(spec, [security, derived])

    assert result["validity"] == "valid"
    assert result["output"]["value"] > 0
    assert result["executed_at"] == "2026-08-17T00:00:00Z"
