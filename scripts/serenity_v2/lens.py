"""Deterministic, fact-referenced valuation lens calculations."""

from __future__ import annotations

import ast
import hashlib
import json
import math
from collections.abc import Mapping
from typing import Any


LENS_RESULT_SCHEMA_ID = "urn:serenity:schema:lens-result:1"
BUILT_IN_FORMULAS = {
    "content-volume": (("content_per_unit", "volume", "market_cap"), "content_per_unit * volume / market_cap"),
    "mw-irr": (("annual_cash_flow", "invested_capital"), "annual_cash_flow / invested_capital"),
    "replacement-cost": (("capacity", "replacement_cost_per_unit", "market_cap"), "capacity * replacement_cost_per_unit / market_cap"),
    "pro-forma-fcf": (("revenue", "fcf_margin", "market_cap"), "revenue * fcf_margin / market_cap"),
    "net-cash-after-atm": (("cash", "atm_proceeds", "debt"), "cash + atm_proceeds - debt"),
}


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _issue(code: str, **details: Any) -> dict[str, Any]:
    return {"code": code, **details}


def _safe_expression(expression: str, names: set[str]) -> ast.Expression | None:
    try:
        parsed = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError):
        return None

    for node in ast.walk(parsed):
        if isinstance(node, (ast.Expression, ast.Load, ast.operator, ast.unaryop)):
            continue
        if isinstance(node, ast.Constant):
            if _numeric(node.value):
                continue
            return None
        if isinstance(node, ast.Name):
            if node.id in names:
                continue
            return None
        if isinstance(node, ast.BinOp):
            if isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod)):
                continue
            return None
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, (ast.UAdd, ast.USub)):
                continue
            return None
        return None
    return parsed


def _evaluate(node: ast.AST, values: Mapping[str, float]) -> float:
    if isinstance(node, ast.Expression):
        return _evaluate(node.body, values)
    if isinstance(node, ast.Constant) and _numeric(node.value):
        return float(node.value)
    if isinstance(node, ast.Name):
        return values[node.id]
    if isinstance(node, ast.UnaryOp):
        operand = _evaluate(node.operand, values)
        if isinstance(node.op, ast.UAdd):
            return operand
        if isinstance(node.op, ast.USub):
            return -operand
    if isinstance(node, ast.BinOp):
        left = _evaluate(node.left, values)
        right = _evaluate(node.right, values)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
    raise ValueError("unsupported arithmetic node")


def _input_specs(spec: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw_inputs = spec.get("inputs")
    if not isinstance(raw_inputs, list):
        return []
    inputs: list[dict[str, Any]] = []
    for item in raw_inputs:
        if not isinstance(item, Mapping):
            continue
        name = item.get("name")
        fact_ref = item.get("fact_ref")
        unit = item.get("unit")
        if isinstance(name, str) and isinstance(fact_ref, str) and isinstance(unit, str):
            inputs.append({"name": name, "fact_ref": fact_ref, "unit": unit})
    return inputs


def _fact_index(snapshot: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    indexed: dict[str, list[Mapping[str, Any]]] = {}
    facts = snapshot.get("facts")
    if not isinstance(facts, list):
        return indexed
    for fact in facts:
        if isinstance(fact, Mapping) and isinstance(fact.get("fact_id"), str):
            indexed.setdefault(fact["fact_id"], []).append(fact)
    return indexed


def _resolve_inputs(spec: Mapping[str, Any], snapshot: Mapping[str, Any]) -> tuple[dict[str, float], list[dict[str, Any]], list[str], list[dict[str, Any]], str]:
    input_specs = _input_specs(spec)
    if not input_specs:
        return {}, [], [], [_issue("invalid_inputs", message="inputs must be a non-empty lens-spec input array")], "invalid"

    facts = _fact_index(snapshot)
    values: dict[str, float] = {}
    input_facts: list[dict[str, Any]] = []
    fact_refs: list[str] = []
    issues: list[dict[str, Any]] = []
    validity = "valid"

    for input_spec in input_specs:
        name = input_spec["name"]
        fact_ref = input_spec["fact_ref"]
        expected_unit = input_spec["unit"]
        fact_refs.append(fact_ref)
        candidates = facts.get(fact_ref, [])
        if len(candidates) == 0:
            input_facts.append({"fact_ref": fact_ref, "availability": "unavailable", "value": None, "unit": expected_unit})
            issues.append(_issue("fact_not_found", fact_ref=fact_ref))
            if validity == "valid":
                validity = "insufficient_evidence"
            continue
        if len(candidates) != 1:
            input_facts.append({"fact_ref": fact_ref, "availability": "conflict", "value": None, "unit": expected_unit})
            issues.append(_issue("conflict", reason="duplicate_fact", fact_ref=fact_ref))
            validity = "invalid"
            continue

        fact = candidates[0]
        availability = fact.get("availability")
        actual_unit = fact.get("unit")
        value = fact.get("value")
        input_facts.append({"fact_ref": fact_ref, "availability": availability, "value": value, "unit": actual_unit if isinstance(actual_unit, str) else expected_unit})
        if availability != "available":
            issues.append(_issue("fact_not_available", fact_ref=fact_ref, availability=availability))
            if validity == "valid":
                validity = "insufficient_evidence"
            continue
        if actual_unit != expected_unit:
            issues.append(_issue("conflict", reason="unit_mismatch", fact_ref=fact_ref, expected_unit=expected_unit, actual_unit=actual_unit))
            validity = "invalid"
            continue
        if not _numeric(value):
            issues.append(_issue("fact_not_numeric", fact_ref=fact_ref))
            validity = "invalid"
            continue
        if name in values and values[name] != float(value):
            issues.append(_issue("conflict", reason="input_name_collision", input=name))
            validity = "invalid"
            continue
        values[name] = float(value)

    return values, input_facts, sorted(set(fact_refs)), issues, validity


def _formula(spec: Mapping[str, Any], values: Mapping[str, float]) -> tuple[str | None, list[dict[str, Any]]]:
    raw_formula = spec.get("formula")
    if not isinstance(raw_formula, str):
        return None, [_issue("unsafe_expression", message="only numeric arithmetic is allowed")]
    if raw_formula == "sum-of-parts":
        if not values:
            return None, [_issue("invalid_inputs", message="sum-of-parts requires at least one input")]
        return " + ".join(values), []
    built_in = BUILT_IN_FORMULAS.get(raw_formula)
    if built_in is not None:
        names, expression = built_in
        missing = [name for name in names if name not in values]
        if missing:
            return expression, [_issue("required_input_missing", inputs=missing)]
        return expression, []
    return raw_formula, []


def _executed_at(snapshot: Mapping[str, Any]) -> str:
    fetched_at = snapshot.get("fetched_at")
    return fetched_at if isinstance(fetched_at, str) else "1970-01-01T00:00:00Z"


def _result(
    spec: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    *,
    validity: str,
    input_facts: list[dict[str, Any]],
    fact_refs: list[str],
    expression: str | None,
    values: Mapping[str, float],
    issues: list[dict[str, Any]],
    value: float | None,
) -> dict[str, Any]:
    output_unit = spec.get("output_unit") if isinstance(spec.get("output_unit"), str) else "unitless"
    steps = [{"operation": "resolve", "input": name, "value": number} for name, number in values.items()]
    if value is not None:
        steps.append({"operation": "evaluate", "expression": expression, "result": value})
    output = {"expression": expression, "calculation_steps": steps, "value": value, "unit": output_unit, "issues": issues}
    reproducible = {
        "lens_id": spec.get("lens_id"),
        "run_id": spec.get("run_id"),
        "formula": spec.get("formula"),
        "inputs": _input_specs(spec),
        "input_facts": input_facts,
        "fact_refs": fact_refs,
        "output": output,
        "validity": validity,
    }
    reproducibility_hash = _canonical_hash(reproducible)
    lens_id = spec.get("lens_id") if isinstance(spec.get("lens_id"), str) else "lens-invalid"
    run_id = spec.get("run_id") if isinstance(spec.get("run_id"), str) else "run-invalid"
    result: dict[str, Any] = {
        "schema_id": LENS_RESULT_SCHEMA_ID,
        "lens_result_id": f"lens-result-{reproducibility_hash[:16]}",
        "lens_id": lens_id,
        "run_id": run_id,
        "validity": validity,
        "input_facts": input_facts,
        "fact_refs": fact_refs,
        "output": output,
        "output_unit": output_unit,
        "reproducibility_hash": reproducibility_hash,
        "executed_at": _executed_at(snapshot),
    }
    if issues:
        result["error"] = "; ".join(issue["code"] for issue in issues)
    return result


def run_lens(lens_spec: dict[str, Any], fact_snapshot: dict[str, Any]) -> dict[str, Any]:
    """Execute a declared lens without accepting unreferenced numeric inputs.

    Every failure is returned as a schema-shaped typed result.  This keeps a
    missing or conflicting fact from becoming an exception, a substituted
    number, or an investment verdict.
    """
    spec: Mapping[str, Any] = lens_spec if isinstance(lens_spec, Mapping) else {}
    snapshot: Mapping[str, Any] = fact_snapshot if isinstance(fact_snapshot, Mapping) else {}
    values, input_facts, fact_refs, issues, validity = _resolve_inputs(spec, snapshot)
    if validity != "valid":
        return _result(spec, snapshot, validity=validity, input_facts=input_facts, fact_refs=fact_refs, expression=None, values=values, issues=issues, value=None)
    expression, formula_issues = _formula(spec, values)
    if formula_issues:
        issues.extend(formula_issues)
        if validity == "valid":
            validity = "invalid"
    if validity != "valid" or expression is None:
        return _result(spec, snapshot, validity=validity, input_facts=input_facts, fact_refs=fact_refs, expression=expression, values=values, issues=issues, value=None)

    parsed = _safe_expression(expression, set(values))
    if parsed is None:
        issues.append(_issue("unsafe_expression", message="only numeric arithmetic is allowed"))
        return _result(spec, snapshot, validity="invalid", input_facts=input_facts, fact_refs=fact_refs, expression=expression, values=values, issues=issues, value=None)
    try:
        calculated = _evaluate(parsed, values)
    except (ArithmeticError, KeyError, ValueError, OverflowError):
        issues.append(_issue("calculation_invalid", message="expression did not produce a finite numeric result"))
        return _result(spec, snapshot, validity="invalid", input_facts=input_facts, fact_refs=fact_refs, expression=expression, values=values, issues=issues, value=None)
    if not _numeric(calculated):
        issues.append(_issue("calculation_invalid", message="expression did not produce a finite numeric result"))
        return _result(spec, snapshot, validity="invalid", input_facts=input_facts, fact_refs=fact_refs, expression=expression, values=values, issues=issues, value=None)
    return _result(spec, snapshot, validity="valid", input_facts=input_facts, fact_refs=fact_refs, expression=expression, values=values, issues=issues, value=float(calculated))
