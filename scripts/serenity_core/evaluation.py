"""Independent evaluation orchestration.

This module deliberately reports three separate measurements instead of trying to turn
them into a single quality number: retrospective method fidelity, cutoff-frozen packet
quality, and append-only prospective tracking.  Models are an injected boundary in tests;
the Codex cleanroom CLI is available only when explicitly requested by the caller.
"""

from __future__ import annotations

import json
import math
import re
import hashlib
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from serenity_core.candidate_cleanroom import CandidateCleanroomError, CandidateLaunch, CandidatePackage, build_candidate_cleanroom, launch_candidate_cleanroom
from serenity_core.cleanroom import CleanroomError, CleanroomLaunch, CleanroomPackage, build_cleanroom, launch_cleanroom
from serenity_core.lens import run_lens
from serenity_core.runtime import canonical_hash
from serenity_core.schema import SchemaViolation, validate_document
from serenity_core.sector_graph import SectorGraphValidationError, validate_sector_graph
from serenity_core.snapshot import SnapshotBlockedError, SnapshotIntegrityError, build_security_snapshot, validate_security_snapshot
from serenity_core.storage import atomic_write_json


FAMILIES = frozenset({"discovery", "single-ticker", "physical-ai", "near-miss", "degraded-data", "displacement-fear"})
TRACKS = {
    "retrospective": "retrospective_independent_first",
    "cutoff-frozen": "cutoff_frozen_current",
    "prospective": "prospective_tracking",
}
TERRA_MODEL = "gpt-5.6-terra"
SOL_MODEL = "gpt-5.6-sol"


class EvaluationError(RuntimeError):
    """An evaluation config or its isolated evidence packet is unsafe or invalid."""


@dataclass(frozen=True)
class ReviewRequest:
    case_id: str
    reviewer: str
    model: str
    track: str
    package: CleanroomPackage
    expected_invariants: tuple[str, ...]
    invariant_evidence: Mapping[str, tuple[str, ...]]


ReviewRunner = Callable[[ReviewRequest], Mapping[str, Any]]
Adjudicator = Callable[[ReviewRequest], Mapping[str, Any]]


@dataclass(frozen=True)
class CandidateRequest:
    case_id: str
    family: str
    cutoff: str
    question: str
    frozen_packet: Mapping[str, Any]
    packet_sha256: str


CandidateRunner = Callable[[CandidateRequest], Mapping[str, Any]]


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"{label} must be readable JSON: {path}") from exc
    if not isinstance(value, dict):
        raise EvaluationError(f"{label} must be a JSON object: {path}")
    return value


def _parse_time(value: Any, *, label: str) -> datetime:
    if not isinstance(value, str):
        raise EvaluationError(f"{label} must be an ISO timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EvaluationError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None:
        raise EvaluationError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _contains_answer_key(value: Any) -> bool:
    if isinstance(value, dict):
        excluded = {"answer_key", "answer_keys", "old_verdict", "old_verdicts", "prior_verdict", "prior_verdicts", "corpus_answer", "corpus_answers"}
        return any(str(key).casefold() in excluded or _contains_answer_key(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_answer_key(item) for item in value)
    return False


def _contains_evaluator_only_expectation(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            str(key).casefold() in {"expected_case_behavior", "expected_case_behaviors"}
            or _contains_evaluator_only_expectation(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_evaluator_only_expectation(item) for item in value)
    return False


_PROMPT_INTERNAL_MARKER = re.compile(
    r"\b(?:answer[-_ ]?key|old[-_ ]?verdict|prior[-_ ]?verdict|corpus[-_ ]?answer|deterministic_assertions?|assertion[-_ ]?only|expected[_ ]?(?:outcome|invariant)|reviewer_outcome)\b",
    re.IGNORECASE,
)
_PROMPT_EXPECTED_OUTCOME = re.compile(
    r"\b(?:must|should|expected|return|report|correct|answer|outcome|decision)\b[^.]{0,48}\b(?:pass|fail|needs[_ ]?review|blocked|monitor)\b",
    re.IGNORECASE,
)


def _prompt_words(value: str) -> set[str]:
    words: set[str] = set()
    for raw in re.findall(r"[a-zA-Z]{4,}", value.casefold()):
        stem = re.sub(r"(?:ing|ed|ly|es|s)$", "", raw)
        words.add(stem)
    return words


def _validate_qa_prompt(qa_case: Mapping[str, Any], expected_invariants: list[str]) -> None:
    prompt = qa_case.get("prompt")
    if not isinstance(prompt, str):
        raise EvaluationError("qa case prompt leaks internal answer material")
    if _PROMPT_INTERNAL_MARKER.search(prompt) or _PROMPT_EXPECTED_OUTCOME.search(prompt):
        raise EvaluationError("qa case prompt leaks internal answer material")
    prompt_words = _prompt_words(prompt)
    for invariant in expected_invariants:
        invariant_words = _prompt_words(invariant)
        if invariant_words and invariant_words.issubset(prompt_words):
            raise EvaluationError("qa case prompt leaks internal answer material")


def _availability_records(value: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if "availability" in value:
            temporal = value.get("temporal")
            if "available_at" not in value and isinstance(temporal, dict) and "available_at" in temporal:
                records.append({**value, "available_at": temporal["available_at"]})
            else:
                records.append(value)
        for item in value.values():
            records.extend(_availability_records(item))
    elif isinstance(value, list):
        for item in value:
            records.extend(_availability_records(item))
    return records


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_OUTCOME_BEARING_EVIDENCE = re.compile(
    r"\b(?:pass(?:ed)?|fail(?:ed)?|blocked|monitor|recommend(?:ation)?|action|outcome|verdict|sufficient|insufficient|require(?:s|d)?|identified|is pinned|remains (?:explicit|separate)|bottom hop (?:is )?named)\b",
    re.IGNORECASE,
)


def _validate_raw_observations(value: Any) -> None:
    """Require source observations rather than a fixture's already-decided conclusion."""
    if not isinstance(value, dict) or "statement" in value:
        raise EvaluationError("packet evidence is outcome-bearing or invariant-paraphrasing, not raw observations")
    observations = value.get("observations")
    if not isinstance(observations, list) or not observations:
        raise EvaluationError("packet evidence is outcome-bearing or invariant-paraphrasing, not raw observations")
    for observation in observations:
        if not isinstance(observation, dict):
            raise EvaluationError("packet evidence observations must be typed records")
        if not isinstance(observation.get("subject"), str) or not isinstance(observation.get("predicate"), str):
            raise EvaluationError("packet evidence observations require subject and predicate")
        if not any(key in observation for key in ("object", "value", "measure", "related_entity")):
            raise EvaluationError("packet evidence observations require an observed object, value, measure, or related entity")
    if _OUTCOME_BEARING_EVIDENCE.search(json.dumps(value, ensure_ascii=False)):
        raise EvaluationError("packet evidence is outcome-bearing or invariant-paraphrasing, not raw observations")


def _validate_substantive_evidence(packet: Mapping[str, Any]) -> None:
    evidence = packet.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        raise EvaluationError("packet requires substantive typed evidence")
    ids: set[str] = set()
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str) or item["evidence_id"] in ids:
            raise EvaluationError("packet evidence ids must be unique")
        artifact = item.get("artifact")
        if not isinstance(artifact, dict) or not isinstance(artifact.get("schema_id"), str):
            raise EvaluationError("packet evidence must resolve to a substantive typed artifact")
        if artifact["schema_id"] == "urn:serenity:schema:evidence-result:1":
            try:
                validate_document(artifact, artifact["schema_id"])
            except SchemaViolation as exc:
                raise EvaluationError(f"packet evidence artifact schema validation failed: {exc}") from exc
            if artifact.get("result_id") != item["evidence_id"] or not isinstance(artifact.get("value"), (dict, list, str, int, float)):
                raise EvaluationError("packet evidence result must contain substantive value content")
            _validate_raw_observations(artifact["value"])
            unsigned = {key: value for key, value in artifact.items() if key != "content_hash"}
            if artifact.get("content_hash") != canonical_hash(unsigned):
                raise EvaluationError("packet evidence result content_hash is invalid")
        elif artifact["schema_id"] not in {
            "urn:serenity:schema:lens-result:1",
            "urn:serenity:schema:fact-snapshot:2",
            "urn:serenity:schema:sector-graph:1",
        }:
            raise EvaluationError("packet evidence artifact schema is not an allowed typed result")
        ids.add(item["evidence_id"])


def _invariant_evidence(packet: Mapping[str, Any], expected_invariants: list[str]) -> dict[str, tuple[str, ...]]:
    evidence_ids = {item.get("evidence_id") for item in packet.get("evidence", []) if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)}
    raw = packet.get("invariant_evidence")
    if not isinstance(raw, list):
        raise EvaluationError("packet requires invariant_evidence")
    mapping: dict[str, tuple[str, ...]] = {}
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("invariant"), str) or not isinstance(item.get("evidence_refs"), list):
            raise EvaluationError("packet invariant_evidence is invalid")
        refs = tuple(item["evidence_refs"])
        if not refs or not all(isinstance(ref, str) and ref in evidence_ids for ref in refs) or item["invariant"] in mapping:
            raise EvaluationError("packet invariant_evidence must contain non-empty known evidence refs exactly once")
        mapping[item["invariant"]] = refs
    if set(mapping) != set(expected_invariants):
        raise EvaluationError("packet invariant_evidence must match qa-case expected_invariants exactly")
    return mapping


def _failure_counts(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"category": category, "count": count} for category, count in sorted(Counter(check["category"] for check in checks if not check["passed"]).items())]


def _reviewable_runtime_artifact(service: str, result: dict[str, Any]) -> dict[str, Any]:
    """Bind a production graph result without handing its conclusion fields to a reviewer."""
    if service != "serenity_core.sector_graph.validate_sector_graph" or result.get("schema_id") != "urn:serenity:schema:sector-graph:1":
        return result
    observations: list[dict[str, Any]] = []
    for edge in result.get("edges", []):
        if isinstance(edge, dict) and all(isinstance(edge.get(key), str) for key in ("from_node_id", "edge_type", "to_node_id")):
            observations.append({"subject": edge["from_node_id"], "predicate": edge["edge_type"], "object": edge["to_node_id"]})
    us_expression = result.get("us_expression")
    if isinstance(us_expression, dict):
        for expression in us_expression.get("listed_expressions", []):
            if isinstance(expression, dict) and isinstance(expression.get("ticker"), str) and isinstance(expression.get("market"), str):
                observations.append({"subject": expression["ticker"], "predicate": "trades_on", "object": expression["market"]})
    return {
        "schema_id": "urn:serenity:evaluation:sector-graph-runtime-observations:1",
        "service": service,
        "service_output_sha256": canonical_hash(result),
        "graph_id": result.get("graph_id"),
        "as_of": result.get("as_of"),
        "observations": observations,
    }


def _runtime_lens_expectation_matches(result: Mapping[str, Any], expected: Any) -> bool:
    if not isinstance(expected, dict):
        return False
    for key, value in expected.items():
        if key == "output_value":
            output = result.get("output")
            if not isinstance(output, dict) or output.get("value") != value:
                return False
        elif result.get(key) != value:
            return False
    return True


def _run_runtime_scenario(*, qa_case: dict[str, Any], packet: dict[str, Any], expected_invariants: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, tuple[str, ...]]]:
    scenario = packet.get("runtime_scenario")
    if not isinstance(scenario, dict) or scenario.get("schema_id") != "serenity-evaluation-runtime-scenario/1":
        raise EvaluationError("cutoff-frozen packet requires a runtime_scenario")
    actions = scenario.get("actions")
    bindings = scenario.get("invariant_bindings")
    if not isinstance(actions, list) or not isinstance(bindings, list):
        raise EvaluationError("runtime_scenario requires actions and invariant_bindings")
    outcomes: dict[str, bool] = {}
    artifacts: dict[str, dict[str, Any]] = {}
    for action in actions:
        if not isinstance(action, dict) or not isinstance(action.get("action_id"), str):
            raise EvaluationError("runtime_scenario action is invalid")
        action_id = action["action_id"]
        if action_id in outcomes:
            raise EvaluationError("runtime_scenario action ids must be unique")
        service = action.get("service")
        if service == "serenity_core.lens.run_lens":
            try:
                result = run_lens(action.get("lens_spec"), action.get("fact_snapshot"))
            except Exception as exc:  # the frozen packet records a service error as evidence, never hides it
                result = {"schema_id": "urn:serenity:evaluation:runtime-error:1", "service": service, "error": str(exc)}
            outcomes[action_id] = _runtime_lens_expectation_matches(result, action.get("expect"))
            artifacts[action_id] = result
        elif service == "serenity_core.snapshot.validate_security_snapshot":
            snapshot = action.get("snapshot")
            try:
                validate_security_snapshot(snapshot)
                result = dict(snapshot) if isinstance(snapshot, dict) else {"schema_id": "urn:serenity:evaluation:runtime-error:1", "service": service, "error": "snapshot is not an object"}
                outcomes[action_id] = action.get("expect") == "valid"
            except (SchemaViolation, SnapshotIntegrityError, TypeError, ValueError) as exc:
                result = {"schema_id": "urn:serenity:evaluation:runtime-error:1", "service": service, "error": str(exc)}
                outcomes[action_id] = action.get("expect") == "invalid"
            artifacts[action_id] = result
        elif service == "serenity_core.snapshot.build_security_snapshot":
            try:
                run_manifest = action.get("run_manifest")
                if not isinstance(run_manifest, dict):
                    raise ValueError("runtime run_manifest must be an object")
                validate_document(run_manifest, "urn:serenity:schema:run-manifest:2")
                if run_manifest.get("content_hash") != canonical_hash({key: value for key, value in run_manifest.items() if key != "content_hash"}):
                    raise ValueError("runtime run_manifest content_hash is invalid")
                result = build_security_snapshot(
                    run_manifest,
                    action.get("identity_resolution"),
                    action.get("market_envelope"),
                    action.get("rs_envelope"),
                )
                outcomes[action_id] = action.get("expect") == "valid"
            except SnapshotBlockedError as exc:
                result = {"schema_id": "urn:serenity:evaluation:runtime-blocked:1", "service": service, "blocked_reason": exc.reason}
                expected = action.get("expect")
                outcomes[action_id] = isinstance(expected, dict) and expected.get("blocked_reason") == exc.reason
            except (SchemaViolation, SnapshotIntegrityError, TypeError, ValueError) as exc:
                result = {"schema_id": "urn:serenity:evaluation:runtime-error:1", "service": service, "error": str(exc)}
                outcomes[action_id] = False
            artifacts[action_id] = result
        elif service == "serenity_core.sector_graph.validate_sector_graph":
            try:
                result = validate_sector_graph(
                    action.get("graph"),
                    run_manifest=action.get("run_manifest"),
                    evidence_results=action.get("evidence_results"),
                )
                outcomes[action_id] = action.get("expect") == "valid"
            except (SectorGraphValidationError, SchemaViolation, TypeError, ValueError) as exc:
                result = {"schema_id": "urn:serenity:evaluation:runtime-error:1", "service": service, "error": str(exc)}
                outcomes[action_id] = action.get("expect") == "invalid"
            artifacts[action_id] = result
        else:
            raise EvaluationError("runtime_scenario action must call an allowed current production service")
    bound: dict[str, tuple[str, ...]] = {}
    for binding in bindings:
        if not isinstance(binding, dict) or not isinstance(binding.get("invariant"), str) or not isinstance(binding.get("action_ids"), list):
            raise EvaluationError("runtime_scenario invariant binding is invalid")
        action_ids = tuple(binding["action_ids"])
        if not action_ids or not all(isinstance(item, str) and item in outcomes for item in action_ids) or binding["invariant"] in bound:
            raise EvaluationError("runtime_scenario invariant binding references unknown actions")
        bound[binding["invariant"]] = action_ids
    if set(bound) != set(expected_invariants):
        raise EvaluationError("runtime_scenario invariant bindings must match qa-case expected_invariants exactly")
    runtime_evidence = [
        {
            "evidence_id": f"runtime-{qa_case['case_id']}-{action_id}",
            "service": actions[index]["service"],
            "artifact": _reviewable_runtime_artifact(actions[index]["service"], artifacts[action_id]),
            "input_sha256": canonical_hash({key: value for key, value in actions[index].items() if key != "expect"}),
        }
        for index, action_id in enumerate(artifacts)
    ]
    runtime_refs_by_action = {item["evidence_id"].removeprefix(f"runtime-{qa_case['case_id']}-"): item["evidence_id"] for item in runtime_evidence}
    return (
        [{"category": "runtime_invariant", "invariant": invariant, "passed": all(outcomes[action_id] for action_id in bound[invariant])} for invariant in expected_invariants],
        runtime_evidence,
        {invariant: tuple(runtime_refs_by_action[action_id] for action_id in bound[invariant]) for invariant in expected_invariants},
    )


def _deterministic_validate(*, qa_case: dict[str, Any], packet: dict[str, Any], track: str) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    runtime_evidence: list[dict[str, Any]] = []
    runtime_invariant_evidence: dict[str, tuple[str, ...]] = {}
    cutoff = _parse_time(qa_case.get("cutoff"), label="qa case cutoff")
    policy = qa_case.get("isolation_policy")
    independent = isinstance(policy, dict) and policy.get("exclude_prior_verdicts") is True and policy.get("exclude_corpus_answers") is True
    checks.append({"category": "answer_key_exposure", "passed": independent and not _contains_answer_key(packet)})

    for record in _availability_records(packet):
        if record.get("availability") != "available":
            continue
        available_at = record.get("available_at")
        if not isinstance(available_at, str):
            checks.append({"category": "missing_availability", "passed": False})
        else:
            checks.append({"category": "cutoff_leakage", "passed": _parse_time(available_at, label="packet available_at") <= cutoff})

    expected = qa_case.get("expected_invariants")
    if not isinstance(expected, list) or not expected or not all(isinstance(item, str) for item in expected):
        checks.append({"category": "missing_invariant_contract", "passed": False})
    elif track == "cutoff-frozen":
        try:
            runtime_checks, runtime_evidence, runtime_invariant_evidence = _run_runtime_scenario(qa_case=qa_case, packet=packet, expected_invariants=expected)
            checks.extend(runtime_checks)
        except EvaluationError:
            checks.extend({"category": "runtime_scenario_invalid", "invariant": invariant, "passed": False} for invariant in expected)

    if track == "prospective":
        prospective = packet.get("prospective")
        original = prospective.get("original_decision") if isinstance(prospective, dict) else None
        checkpoints = prospective.get("checkpoints") if isinstance(prospective, dict) else None
        preserves = isinstance(original, dict) and bool(original.get("decision_id")) and isinstance(checkpoints, list) and all(
            isinstance(checkpoint, dict) and "decision" not in checkpoint for checkpoint in checkpoints
        )
        checks.append({"category": "prospective_rewrite", "passed": preserves})

    passed = sum(check["passed"] for check in checks)
    return {
        "outcome": "pass" if passed == len(checks) else "fail",
        "checks": checks,
        "counts": {"passed": passed, "failed": len(checks) - passed, "total": len(checks), "denominator": "deterministic checks"},
        "failure_taxonomy": _failure_counts(checks),
        "runtime_evidence": runtime_evidence,
        "runtime_invariant_evidence": runtime_invariant_evidence,
    }


_RUNTIME_ASSERTION_RATIONALE = re.compile(
    r"\b(?:sector graph|runtime (?:validator|artifact)|schema|recursive_bottom_hop|sibling_comparison|second_order_effect)\b.*\b(?:explicitly|identif(?:y|ies)|provid(?:e|es)|valid|resolved)\b",
    re.IGNORECASE,
)


def _validate_result(result: Mapping[str, Any], *, case_id: str, reviewer: str, expected_invariants: tuple[str, ...], invariant_evidence: Mapping[str, tuple[str, ...]], rationale_predicates: Mapping[str, frozenset[str]] | None = None, allow_model_reported_identity: bool = False) -> dict[str, Any]:
    value = dict(result)
    try:
        validate_document(value, "urn:serenity:schema:qa-result:1")
    except SchemaViolation as exc:
        raise EvaluationError(f"reviewer {reviewer} schema validation failed: {exc}") from exc
    if value.get("case_id") != case_id or (value.get("reviewer") != reviewer and not allow_model_reported_identity):
        raise EvaluationError(f"reviewer {reviewer} returned a result for the wrong case")
    if value.get("reviewer_outcome") not in {"pass", "fail", "needs_review"}:
        raise EvaluationError(f"reviewer {reviewer} returned an invalid reviewer_outcome")
    rows = value.get("invariant_results")
    if not isinstance(rows, list):
        raise EvaluationError(f"reviewer {reviewer} omitted invariant_results")
    observed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("invariant"), str) or row["invariant"] in observed:
            raise EvaluationError(f"reviewer {reviewer} invariant results are invalid")
        rationale = row.get("rationale")
        if not isinstance(rationale, str) or re.search(r"\b(deterministic_assertions?|assertion[- ]?only|passed\s*[:=])\b", rationale, re.IGNORECASE):
            raise EvaluationError(f"reviewer {reviewer} rationale cites an excluded assertion marker")
        predicates = (rationale_predicates or {}).get(row["invariant"], frozenset())
        rationale_words = frozenset(re.findall(r"[a-z]{4,}", rationale.casefold()))
        if _RUNTIME_ASSERTION_RATIONALE.search(rationale) and predicates.isdisjoint(rationale_words):
            raise EvaluationError(f"reviewer {reviewer} rationale merely cites a runtime assertion instead of an observed relation")
        refs = row.get("evidence_refs")
        expected_refs = invariant_evidence.get(row["invariant"])
        if not isinstance(refs, list) or not refs or len(refs) != len(set(refs)) or expected_refs is None or set(refs) != set(expected_refs):
            raise EvaluationError(f"reviewer {reviewer} invariant evidence refs must match the packet contract")
        observed[row["invariant"]] = row
    if set(observed) != set(expected_invariants):
        raise EvaluationError(f"reviewer {reviewer} invariant set must match the qa case exactly")
    invariant_counts = Counter(row["outcome"] for row in observed.values())
    expected_outcome = "fail" if invariant_counts["fail"] else ("pass" if invariant_counts["pass"] == len(expected_invariants) else "needs_review")
    counts = value.get("counts")
    expected_interval = _wilson(invariant_counts["pass"], len(expected_invariants))
    interval = counts.get("wilson_interval") if isinstance(counts, dict) else None
    if (
        not isinstance(counts, dict)
        or counts.get("passed") != invariant_counts["pass"]
        or counts.get("failed") != invariant_counts["fail"]
        or counts.get("total") != len(expected_invariants)
        or counts.get("denominator") != "expected_invariants"
        or not isinstance(interval, dict)
        or expected_interval is None
        or not _matches_wilson_bound(interval.get("lower"), expected_interval["lower"])
        or not _matches_wilson_bound(interval.get("upper"), expected_interval["upper"])
        or value["reviewer_outcome"] != expected_outcome
    ):
        raise EvaluationError(f"reviewer {reviewer} semantic aggregate does not match invariant results")
    union = {ref for refs in invariant_evidence.values() for ref in refs}
    root_refs = value.get("evidence_refs", [])
    if not isinstance(root_refs, list) or len(root_refs) != len(set(root_refs)) or set(root_refs) != union:
        raise EvaluationError(f"reviewer {reviewer} root evidence_refs must equal invariant evidence refs")
    if allow_model_reported_identity:
        value["assigned_reviewer"] = reviewer
    return value


def _matches_wilson_bound(value: float, expected_value: float) -> bool:
    """Mirror cleanroom's narrow tolerance for conventional 95% Wilson constants."""
    return math.isclose(value, expected_value, abs_tol=0.0005)


def _candidate_packet(packet: Mapping[str, Any], *, semantic_live_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Give the harness candidate raw typed evidence, never evaluator assertions or oracle fields."""
    hidden = {"deterministic_assertions", "runtime_scenario", "invariant_evidence", "facts", "executed_live_provider_packet", "expected_case_behavior"}
    candidate_packet = {key: value for key, value in packet.items() if key not in hidden}
    candidate_packet["evidence"] = [*packet["evidence"], *semantic_live_evidence]
    return candidate_packet


def _validate_candidate_result(result: Mapping[str, Any], *, request: CandidateRequest) -> dict[str, Any]:
    value = dict(result)
    try:
        validate_document(value, "urn:serenity:schema:candidate-result:1")
    except SchemaViolation as exc:
        raise EvaluationError(f"candidate result schema validation failed: {exc}") from exc
    if value.get("case_id") != request.case_id or value.get("packet_sha256") != request.packet_sha256:
        raise EvaluationError("candidate result must bind its case_id and raw evidence packet hash")
    if value.get("canonical_sha256") != canonical_hash({key: item for key, item in value.items() if key != "canonical_sha256"}):
        raise EvaluationError("candidate result canonical hash is invalid")
    def packet_ids(item: Any) -> set[str]:
        if isinstance(item, dict):
            return {
                value
                for key, value in item.items()
                if key in {"fact_id", "evidence_id", "artifact_id", "result_id", "request_id", "id"} and isinstance(value, str)
            } | set().union(*(packet_ids(value) for value in item.values()))
        if isinstance(item, list):
            return set().union(*(packet_ids(value) for value in item)) if item else set()
        return set()

    evidence_ids = packet_ids(request.frozen_packet)
    referenced = set(value.get("evidence_refs", []))
    for key in ("decision", "action", "trigger", "bear_case"):
        item = value.get(key)
        if isinstance(item, dict):
            referenced.update(item.get("evidence_refs", []))
    for key in ("facts", "inferences", "falsifiers"):
        for item in value.get(key, []):
            if isinstance(item, dict):
                referenced.update(item.get("evidence_refs", []))
    if not referenced or not referenced.issubset(evidence_ids):
        raise EvaluationError("candidate result evidence refs must resolve to its raw typed evidence packet")
    return value


def _review_packet(packet: Mapping[str, Any], *, runtime_evidence: list[dict[str, Any]], semantic_live_evidence: list[dict[str, Any]], invariant_evidence: Mapping[str, tuple[str, ...]], candidate_artifact: Mapping[str, Any] | None = None, candidate_required: bool = False) -> dict[str, Any]:
    """Expose only independent evidence, never evaluator expectations or answer markers."""
    if candidate_required and candidate_artifact is None:
        raise EvaluationError("E2E reviewer packet requires a validated candidate artifact")
    hidden = {"deterministic_assertions", "runtime_scenario", "invariant_evidence", "facts", "executed_live_provider_packet", "expected_case_behavior"}
    reviewer_packet = {key: value for key, value in packet.items() if key not in hidden}
    reviewer_packet["evidence"] = [*packet["evidence"], *runtime_evidence, *semantic_live_evidence]
    reviewer_packet["runtime_evidence"] = runtime_evidence
    reviewer_packet["citation_contract"] = {
        "invariant_evidence": [
            {"invariant": invariant, "evidence_refs": list(refs)}
            for invariant, refs in invariant_evidence.items()
        ],
        "instruction": "For each invariant, cite exactly its listed evidence_refs. Explain a subject-predicate-object or measured relation from the raw observations; a runtime validator, schema field, or named graph conclusion is not proof by itself.",
    }
    if semantic_live_evidence:
        reviewer_packet["live_provider_evidence"] = semantic_live_evidence
    if candidate_artifact is not None:
        reviewer_packet["candidate_artifact"] = dict(candidate_artifact)
    serialized = json.dumps(reviewer_packet, ensure_ascii=False, sort_keys=True)
    if "deterministic_assertions" in serialized or '"passed"' in serialized:
        raise EvaluationError("cleanroom reviewer packet contains an excluded assertion marker")
    return reviewer_packet


def _invariant_observation_predicates(packet: Mapping[str, Any], invariant_evidence: Mapping[str, tuple[str, ...]]) -> dict[str, frozenset[str]]:
    by_id = {item.get("evidence_id"): item for item in packet.get("evidence", []) if isinstance(item, dict)}
    predicates_by_ref: dict[str, frozenset[str]] = {}
    for evidence_id, item in by_id.items():
        artifact = item.get("artifact")
        value = artifact.get("value") if isinstance(artifact, dict) else None
        observations = value.get("observations") if isinstance(value, dict) else None
        if isinstance(evidence_id, str) and isinstance(observations, list):
            predicates_by_ref[evidence_id] = frozenset(
                token
                for observation in observations if isinstance(observation, dict)
                for token in re.findall(r"[a-z]{4,}", str(observation.get("predicate", "")).casefold())
            )
    return {
        invariant: frozenset(token for reference in refs for token in predicates_by_ref.get(reference, frozenset()))
        for invariant, refs in invariant_evidence.items()
    }


def _wilson(passed: int, total: int) -> dict[str, Any] | None:
    if total == 0:
        return None
    z = 1.959963984540054
    proportion = passed / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    spread = z * ((proportion * (1 - proportion) / total + z * z / (4 * total * total)) ** 0.5) / denominator
    return {
        "lower": round(max(0.0, centre - spread), 6),
        "upper": round(min(1.0, centre + spread), 6),
        "numerator": passed,
        "denominator": "all cases; needs_review is not a success",
        "denominator_count": total,
    }


def _validate_live_packet(value: Mapping[str, Any], requirements: list[dict[str, Any]], *, case_id: str, raw_cache_root: Path | None) -> dict[str, Any]:
    if _contains_answer_key(value):
        raise EvaluationError("executed live packet must exclude answer-key and prior-verdict provenance")
    if value.get("case_id") != case_id:
        raise EvaluationError("executed live packet case_id must match its descriptor")
    if value.get("execution_state") != "executed" or not isinstance(value.get("providers"), list) or not isinstance(value.get("provider_packets"), list) or not isinstance(value.get("network_policy"), dict):
        raise EvaluationError("executed live packet requires execution_state, providers, and provider packet content")
    if raw_cache_root is None or not raw_cache_root.is_dir() or raw_cache_root.is_symlink():
        raise EvaluationError("executed live packet requires a real private raw-cache directory")
    providers = value["providers"]
    requirement_by_provider = {item["provider"]: item["availability_required"] for item in requirements}
    observed: dict[str, dict[str, Any]] = {}
    for provider in providers:
        if not isinstance(provider, dict) or not isinstance(provider.get("provider"), str):
            raise EvaluationError("executed live packet has an invalid provider record")
        name = provider["provider"]
        if name not in requirement_by_provider or provider.get("availability") != requirement_by_provider[name]:
            raise EvaluationError("executed live packet does not meet provider availability requirements")
        _parse_time(provider.get("fetched_at"), label="live provider fetched_at")
        if not isinstance(provider.get("raw_content_sha256"), str) or re.fullmatch(r"[a-f0-9]{64}", provider["raw_content_sha256"]) is None:
            raise EvaluationError("executed live packet requires provider raw_content_sha256")
        observed[name] = {"provider": name, "availability": provider["availability"], "fetched_at": provider["fetched_at"], "raw_content_sha256": provider["raw_content_sha256"]}
    if set(observed) != set(requirement_by_provider):
        raise EvaluationError("executed live packet is missing a required provider")
    packet_content: dict[str, dict[str, Any]] = {}
    for provider_packet in value["provider_packets"]:
        if not isinstance(provider_packet, dict) or not isinstance(provider_packet.get("provider"), str) or not isinstance(provider_packet.get("envelope"), dict) or not isinstance(provider_packet.get("raw_cache"), dict):
            raise EvaluationError("executed live packet requires serialized provider envelope and raw-cache binding")
        name = provider_packet["provider"]
        envelope = provider_packet["envelope"]
        try:
            validate_document(envelope, "urn:serenity:schema:provider-envelope:1")
        except SchemaViolation as exc:
            raise EvaluationError(f"executed live provider envelope schema validation failed: {exc}") from exc
        source = envelope.get("source")
        raw_cache = provider_packet["raw_cache"]
        content_hash = source.get("content_sha256") if isinstance(source, dict) else None
        cache_key = raw_cache.get("cache_key")
        if (
            name not in observed
            or name in packet_content
            or envelope.get("provider") != name
            or envelope.get("status") != observed[name]["availability"]
            or envelope.get("fetched_at") != observed[name]["fetched_at"]
            or not isinstance(content_hash, str)
            or content_hash != observed[name]["raw_content_sha256"]
            or raw_cache.get("content_sha256") != content_hash
            or cache_key != f"sha256/{content_hash}"
        ):
            raise EvaluationError("executed live provider envelope/raw-cache linkage is invalid")
        cached_raw = raw_cache_root / cache_key
        if cached_raw.is_symlink() or not cached_raw.is_file() or _sha256_file(cached_raw) != content_hash:
            raise EvaluationError("executed live provider raw-cache bytes do not match envelope source.content_sha256")
        packet_content[name] = {"provider": name, "envelope_sha256": canonical_hash(envelope), "raw_content_sha256": content_hash, "cache_key": cache_key}
    if set(packet_content) != set(observed):
        raise EvaluationError("executed live packet requires content for every provider")
    return {
        "execution_state": "executed",
        "providers": [observed[name] for name in sorted(observed)],
        "provider_packet_hashes": [packet_content[name] for name in sorted(packet_content)],
        "network_policy": dict(value["network_policy"]),
        "packet_hash": canonical_hash(dict(value)),
    }


def load_live_packet_dir(path: Path) -> dict[str, dict[str, Any]]:
    """Load case-id keyed actual provider packets; descriptors never double as live evidence."""
    if not path.is_dir() or path.is_symlink():
        raise EvaluationError(f"live packet dir must be a real directory: {path}")
    packets: dict[str, dict[str, Any]] = {}
    for candidate in sorted(path.glob("*.json")):
        if candidate.is_symlink():
            raise EvaluationError(f"live packet must not be a symlink: {candidate}")
        value = _read_json(candidate, label="live provider packet")
        case_id = value.get("case_id")
        if not isinstance(case_id, str) or case_id in packets:
            raise EvaluationError("live provider packet requires a unique case_id")
        packets[case_id] = value
    return packets


def _live_evidence_policy(descriptor: Mapping[str, Any], *, expected_invariants: list[str], requirements: list[dict[str, Any]]) -> dict[str, Any]:
    raw = descriptor.get("live_evidence", {"role": "transport_only"})
    if not isinstance(raw, dict) or raw.get("role") not in {"transport_only", "semantic"}:
        raise EvaluationError("live evidence requires role=transport_only or semantic")
    role = raw["role"]
    if role == "transport_only":
        if set(raw) != {"role"}:
            raise EvaluationError("transport_only live evidence cannot declare semantic bindings")
        return {"role": role, "semantic_invariant_bindings": []}
    subject = raw.get("provider_subject")
    bindings = raw.get("invariant_bindings")
    if set(raw) != {"role", "provider_subject", "invariant_bindings"} or not isinstance(subject, dict) or not subject or not all(isinstance(key, str) and key and isinstance(value, str) and value for key, value in subject.items()) or not isinstance(bindings, list) or not bindings:
        raise EvaluationError("semantic live evidence requires typed provider_subject and invariant_bindings")
    allowed_providers = {item["provider"] for item in requirements}
    normalized: list[dict[str, str]] = []
    for binding in bindings:
        if not isinstance(binding, dict) or set(binding) != {"invariant", "provider"} or binding.get("invariant") not in expected_invariants or binding.get("provider") not in allowed_providers:
            raise EvaluationError("semantic live evidence invariant binding is invalid")
        normalized.append({"invariant": binding["invariant"], "provider": binding["provider"]})
    if len({(binding["invariant"], binding["provider"]) for binding in normalized}) != len(normalized):
        raise EvaluationError("semantic live evidence invariant bindings must be unique")
    return {"role": role, "provider_subject": dict(subject), "semantic_invariant_bindings": normalized}


def _live_provider_evidence(case_id: str, live_packet: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for provider_packet in live_packet["provider_packets"]:
        provider = provider_packet["provider"]
        evidence.append(
            {
                "evidence_id": f"live-{case_id}-{provider}",
                "artifact": {
                    "schema_id": "urn:serenity:evaluation:live-provider-evidence:1",
                    "provider": provider,
                    "envelope": provider_packet["envelope"],
                    "envelope_sha256": canonical_hash(provider_packet["envelope"]),
                    "raw_content_sha256": provider_packet["envelope"]["source"]["content_sha256"],
                    "raw_cache_key": provider_packet["raw_cache"]["cache_key"],
                },
            }
        )
    return evidence


def _semantic_live_evidence(case_id: str, live_packet: Mapping[str, Any], policy: Mapping[str, Any], *, cutoff: str) -> tuple[list[dict[str, Any]], dict[str, tuple[str, ...]]]:
    if policy["role"] == "transport_only":
        return [], {}
    evidence_by_provider = {
        item["artifact"]["provider"]: item
        for item in _live_provider_evidence(case_id, live_packet)
    }
    envelopes = {
        item["provider"]: item["envelope"]
        for item in live_packet["provider_packets"]
    }
    subject = policy["provider_subject"]
    cutoff_at = _parse_time(cutoff, label="case cutoff")
    selected: dict[str, dict[str, Any]] = {}
    invariant_refs: dict[str, list[str]] = {}
    for binding in policy["semantic_invariant_bindings"]:
        provider = binding["provider"]
        envelope = envelopes[provider]
        identity = envelope.get("identity_bindings")
        if not isinstance(identity, dict) or any(identity.get(key) != value for key, value in subject.items()):
            raise EvaluationError("semantic live evidence provider_subject does not match the provider envelope identity_bindings")
        temporal = envelope.get("temporal")
        available_at = temporal.get("available_at") if isinstance(temporal, dict) else None
        if not isinstance(available_at, str) or _parse_time(available_at, label="semantic live evidence available_at") > cutoff_at:
            raise EvaluationError("semantic live evidence must be available at or before the case cutoff")
        evidence = evidence_by_provider[provider]
        selected[provider] = evidence
        invariant_refs.setdefault(binding["invariant"], []).append(evidence["evidence_id"])
    return list(selected.values()), {invariant: tuple(refs) for invariant, refs in invariant_refs.items()}


def _launch_reviewer(package: CleanroomPackage, *, reviewer: str, model: str, results_root: Path, repo_root: Path, subprocess_runner: Callable[..., Any], prior_result_paths: tuple[Path, ...] = ()) -> tuple[dict[str, Any], CleanroomLaunch]:
    launched = launch_cleanroom(
        package,
        results_root=results_root,
        repo_root=repo_root,
        runner=subprocess_runner,
        model=model,
        reviewer_role="adjudicator" if model == SOL_MODEL else "reviewer",
        isolation_mode="os-enforced",
        prior_result_paths=prior_result_paths,
    )
    return _read_json(launched.model_output_path, label=f"{reviewer} result"), launched


def _launch_candidate(request: CandidateRequest, *, candidate_case_path: Path, frozen_packet_path: Path, candidate_schema_path: Path, candidate_cleanroom_root: Path, candidate_results_root: Path, repo_root: Path, subprocess_runner: Callable[..., Any], model: str) -> tuple[dict[str, Any], CandidatePackage, CandidateLaunch]:
    package = build_candidate_cleanroom(
        candidate_case_path=candidate_case_path,
        frozen_packet_path=frozen_packet_path,
        candidate_result_schema_path=candidate_schema_path,
        harness_root=repo_root,
        cleanroom_root=candidate_cleanroom_root,
        repo_root=repo_root,
    )
    launched = launch_candidate_cleanroom(
        package,
        results_root=candidate_results_root,
        repo_root=repo_root,
        runner=subprocess_runner,
        model=model,
        isolation_mode="os-enforced",
    )
    return _read_json(launched.result_path, label=f"{request.case_id} candidate result"), package, launched


def _cleanroom_error_category(error: CleanroomError) -> str:
    code = getattr(error, "code", "generic")
    if code in {"invalid_reviewer_output", "isolation_violation", "isolation_unavailable"}:
        return code
    return "cleanroom_error"


def _cleanroom_error_linkage(*, status: str, error: CleanroomError) -> dict[str, str]:
    return {"status": status, "reason": str(error), "error_code": getattr(error, "code", "generic")}


def evaluate(
    config_path: Path,
    *,
    repo_root: Path,
    review_runner: ReviewRunner | None = None,
    adjudicator: Adjudicator | None = None,
    candidate_runner: CandidateRunner | None = None,
    execute_cli: bool = False,
    cleanroom_root: Path | None = None,
    results_root: Path | None = None,
    subprocess_runner: Callable[..., Any] = subprocess.run,
    live_provider_packets: Mapping[str, Mapping[str, Any]] | None = None,
    live_raw_cache_root: Path | None = None,
    out_path: Path | None = None,
) -> dict[str, Any]:
    """Run deterministic validation before isolated reviewers and retain every disagreement."""
    config_path = config_path.resolve()
    repo_root = repo_root.resolve()
    config = _read_json(config_path, label="evaluation config")
    if config.get("format") != "serenity-evaluation-config/1" or _contains_answer_key(config):
        raise EvaluationError("evaluation config must exclude every answer key")
    candidate_settings = config.get("candidate_runner")
    if execute_cli and (
        not isinstance(candidate_settings, dict)
        or candidate_settings != {"model": TERRA_MODEL, "result_schema": "urn:serenity:schema:candidate-result:1", "execution": "required_for_cli"}
    ):
        raise EvaluationError("CLI evaluation requires the configured shared-harness candidate runner")
    families = config.get("families")
    if not isinstance(families, list) or not families:
        raise EvaluationError("evaluation config requires families")

    temporary_root: Path | None = None
    if cleanroom_root is None:
        temporary_root = Path(tempfile.mkdtemp(prefix="serenity-evaluation-"))
        cleanroom_root = temporary_root
    if results_root is None:
        results_root = cleanroom_root.parent / f"{cleanroom_root.name}-results"
    qa_schema = repo_root / "schemas" / "qa-result-1.schema.json"
    candidate_schema = repo_root / "schemas" / "candidate-result-1.schema.json"
    candidate_cleanroom_root = cleanroom_root.parent / f"{cleanroom_root.name}-candidates"
    candidate_results_root = results_root.parent / f"{results_root.name}-candidates"
    candidate_input_root: Path | None = Path(tempfile.mkdtemp(prefix="serenity-candidate-inputs-")) if execute_cli and candidate_runner is None else None
    seen_ids: set[str] = set()
    report_families: list[dict[str, Any]] = []
    temporary_packets: list[Path] = []
    tracks = {name: {"case_ids": [], "purpose": purpose} for name, purpose in {
        "retrospective_independent_first": "fresh decision before any answer-key comparison",
        "cutoff_frozen_current": "current code against a documented frozen cutoff packet",
        "prospective_tracking": "append checkpoints without rewriting the original decision",
    }.items()}
    try:
        for family_spec in families:
            if not isinstance(family_spec, dict) or family_spec.get("family") not in FAMILIES:
                raise EvaluationError("evaluation config has an unknown family")
            family_name = family_spec["family"]
            descriptors = family_spec.get("cases")
            if not isinstance(descriptors, list) or not descriptors:
                raise EvaluationError(f"{family_name} requires case descriptors")
            case_reports: list[dict[str, Any]] = []
            for descriptor in descriptors:
                if not isinstance(descriptor, dict) or _contains_answer_key(descriptor):
                    raise EvaluationError("case descriptor must exclude every answer key")
                track = descriptor.get("track")
                if track not in TRACKS or descriptor.get("mode") not in {"deterministic", "live"}:
                    raise EvaluationError("case descriptor requires a valid track and deterministic/live mode")
                qa_path = (config_path.parent / str(descriptor.get("qa_case", ""))).resolve()
                packet_path = (config_path.parent / str(descriptor.get("packet", ""))).resolve()
                qa_case = _read_json(qa_path, label="qa case")
                packet = _read_json(packet_path, label="frozen packet")
                if _contains_evaluator_only_expectation(packet):
                    raise EvaluationError("frozen packet cannot contain evaluator-only expected case behavior")
                try:
                    validate_document(qa_case, "urn:serenity:schema:qa-case:1")
                except SchemaViolation as exc:
                    raise EvaluationError(f"qa case schema validation failed: {exc}") from exc
                case_id = qa_case.get("case_id")
                if not isinstance(case_id, str) or case_id in seen_ids or descriptor.get("case_id") != case_id:
                    raise EvaluationError("case ids must be unique and match their qa case")
                if qa_case.get("family") != family_name:
                    raise EvaluationError(f"case {case_id} does not belong to family {family_name}")
                expected_invariants = qa_case.get("expected_invariants")
                if not isinstance(expected_invariants, list) or not all(isinstance(item, str) for item in expected_invariants):
                    raise EvaluationError("qa case requires string expected_invariants")
                _validate_qa_prompt(qa_case, expected_invariants)
                _validate_substantive_evidence(packet)
                invariant_evidence = _invariant_evidence(packet, expected_invariants)
                live_execution: dict[str, Any] | None = None
                semantic_live_evidence: list[dict[str, Any]] = []
                semantic_live_invariant_evidence: dict[str, tuple[str, ...]] = {}
                requirements: list[dict[str, Any]] = []
                live_evidence_policy: dict[str, Any] = {"role": "not_applicable", "semantic_invariant_bindings": []}
                if descriptor["mode"] == "live":
                    if descriptor.get("execution_state") != "descriptor_not_run":
                        raise EvaluationError("live case descriptors must declare execution_state=descriptor_not_run")
                    raw_requirements = descriptor.get("provider_requirements")
                    if not isinstance(raw_requirements, list) or not raw_requirements:
                        raise EvaluationError("live case descriptors require actual provider identifiers and availability requirements")
                    for requirement in raw_requirements:
                        if not isinstance(requirement, dict) or not isinstance(requirement.get("provider"), str) or requirement["provider"] == "fixture" or requirement.get("availability_required") not in {"available", "unavailable", "stale", "conflict", "not_disclosed"}:
                            raise EvaluationError("live provider requirements are invalid")
                        requirements.append({"provider": requirement["provider"], "availability_required": requirement["availability_required"]})
                    live_evidence_policy = _live_evidence_policy(descriptor, expected_invariants=expected_invariants, requirements=requirements)
                    injected_packet = (live_provider_packets or {}).get(case_id)
                    if injected_packet is not None:
                        live_execution = _validate_live_packet(injected_packet, requirements, case_id=case_id, raw_cache_root=live_raw_cache_root)
                        if live_evidence_policy["role"] == "transport_only":
                            live_execution["checkpoint_role"] = "provider_transport_only"
                            live_execution["eligible_for_case_evidence"] = False
                        else:
                            live_execution["checkpoint_role"] = "provider_semantic_evidence"
                            live_execution["eligible_for_case_evidence"] = True
                        semantic_live_evidence, semantic_live_invariant_evidence = _semantic_live_evidence(case_id, injected_packet, live_evidence_policy, cutoff=qa_case["cutoff"])
                seen_ids.add(case_id)
                tracks[TRACKS[track]]["case_ids"].append(case_id)
                deterministic = _deterministic_validate(qa_case=qa_case, packet=packet, track=track)
                review_invariant_evidence = {
                    invariant: tuple([*refs, *deterministic["runtime_invariant_evidence"].get(invariant, ()), *semantic_live_invariant_evidence.get(invariant, ())])
                    for invariant, refs in invariant_evidence.items()
                }
                case_report: dict[str, Any] = {
                    "case_id": case_id,
                    "mode": descriptor["mode"],
                    "execution_state": live_execution["execution_state"] if live_execution is not None else ("descriptor_not_run" if descriptor["mode"] == "live" else "not_applicable"),
                    "provider_requirements": requirements if descriptor["mode"] == "live" else [],
                    "provider_execution": live_execution,
                    "live_evidence": live_evidence_policy,
                    "source_packet": {
                        "sha256": _sha256_file(packet_path),
                        "network_policy": {"mode": qa_case["isolation_policy"]["network_mode"], "provider_execution_required": descriptor["mode"] == "live"},
                    },
                    "track": TRACKS[track],
                    "deterministic": deterministic,
                    "candidate_required": execute_cli or candidate_runner is not None,
                    "candidate": {"required": execute_cli or candidate_runner is not None, "status": "not_executed"},
                    "reviewers": [],
                    "reviewer_disagreement": {"material": False, "reason": None},
                    "adjudication": None,
                    "failure_taxonomy": list(deterministic["failure_taxonomy"]),
                    "outcome": "fail" if deterministic["outcome"] == "fail" else "needs_review",
                }
                if deterministic["outcome"] == "fail":
                    case_reports.append(case_report)
                    continue
                if descriptor["mode"] == "live" and live_execution is None:
                    case_reports.append(case_report)
                    continue

                candidate_packet = _candidate_packet(packet, semantic_live_evidence=semantic_live_evidence)
                candidate_request = CandidateRequest(
                    case_id=case_id,
                    family=family_name,
                    cutoff=qa_case["cutoff"],
                    question=qa_case["prompt"],
                    frozen_packet=candidate_packet,
                    packet_sha256=canonical_hash(candidate_packet),
                )
                candidate_artifact: dict[str, Any] | None = None
                if candidate_runner is not None:
                    candidate_artifact = _validate_candidate_result(candidate_runner(candidate_request), request=candidate_request)
                    case_report["candidate"] = {
                        "required": True,
                        "status": "executed",
                        "packet_sha256": candidate_request.packet_sha256,
                        "artifact_sha256": canonical_hash(candidate_artifact),
                        "action": candidate_artifact["action"]["kind"],
                    }
                elif execute_cli:
                    assert candidate_input_root is not None
                    candidate_case_path = candidate_input_root / f"{case_id}.candidate-case.json"
                    candidate_packet_path = candidate_input_root / f"{case_id}.packet.json"
                    atomic_write_json(
                        candidate_case_path,
                        {
                            "schema_id": "urn:serenity:schema:candidate-case:1",
                            "case_id": case_id,
                            "family": family_name,
                            "question": qa_case["prompt"],
                            "cutoff": qa_case["cutoff"],
                            "isolation_policy": {"network_mode": "recorded", "exclude_prior_outputs": True},
                        },
                    )
                    atomic_write_json(candidate_packet_path, candidate_packet)
                    candidate_request = CandidateRequest(
                        case_id=case_id,
                        family=family_name,
                        cutoff=qa_case["cutoff"],
                        question=qa_case["prompt"],
                        frozen_packet=candidate_packet,
                        packet_sha256=_sha256_file(candidate_packet_path),
                    )
                    try:
                        candidate_raw, candidate_package, candidate_launch = _launch_candidate(
                            candidate_request,
                            candidate_case_path=candidate_case_path,
                            frozen_packet_path=candidate_packet_path,
                            candidate_schema_path=candidate_schema,
                            candidate_cleanroom_root=candidate_cleanroom_root,
                            candidate_results_root=candidate_results_root,
                            repo_root=repo_root,
                            subprocess_runner=subprocess_runner,
                            model=candidate_settings["model"],
                        )
                        candidate_artifact = _validate_candidate_result(candidate_raw, request=candidate_request)
                    except CandidateCleanroomError as exc:
                        case_report["candidate"] = {"required": True, "status": "failed", "reason": str(exc), "error_code": exc.code}
                        case_report["failure_taxonomy"] = _failure_counts([{"category": f"candidate_{exc.code}", "passed": False}])
                        case_report["outcome"] = "needs_review"
                        case_report["execution_linkage"] = {"status": "candidate_not_executed", "reason": str(exc), "error_code": exc.code}
                        case_reports.append(case_report)
                        continue
                    case_report["candidate"] = {
                        "required": True,
                        "status": "executed",
                        "packet_sha256": candidate_request.packet_sha256,
                        "artifact_sha256": _sha256_file(candidate_launch.result_path),
                        "action": candidate_artifact["action"]["kind"],
                        "cleanroom": {
                            "package_sha256": candidate_package.package_hashes,
                            "harness_sha256": candidate_package.harness_hashes,
                            "execution_sha256": _sha256_file(candidate_launch.record_path),
                        },
                    }

                reviewer_packet = _review_packet(packet, runtime_evidence=deterministic["runtime_evidence"], semantic_live_evidence=semantic_live_evidence, invariant_evidence=review_invariant_evidence, candidate_artifact=candidate_artifact, candidate_required=execute_cli or candidate_runner is not None)
                rationale_predicates = _invariant_observation_predicates(packet, invariant_evidence)
                cleanroom_packet_path = cleanroom_root.parent / f".{case_id}-{canonical_hash(reviewer_packet)[:16]}.packet.json"
                atomic_write_json(cleanroom_packet_path, reviewer_packet)
                temporary_packets.append(cleanroom_packet_path)
                if live_execution is not None:
                    case_report["source_packet"]["executed_live_packet_hash"] = live_execution["packet_hash"]
                package = build_cleanroom(
                    qa_case_path=qa_path,
                    frozen_packet_path=cleanroom_packet_path,
                    qa_result_schema_path=qa_schema,
                    cleanroom_root=cleanroom_root,
                    repo_root=repo_root,
                )
                case_report["cleanroom"] = {
                    "allowlist": ["qa-case.json", "frozen-packet.json", "qa-result.schema.json", "package-manifest.json"],
                    "package_sha256": package.package_hashes,
                    "output_schema": "urn:serenity:schema:qa-result:1",
                }
                requests = [ReviewRequest(case_id, "terra-1", TERRA_MODEL, track, package, tuple(expected_invariants), review_invariant_evidence), ReviewRequest(case_id, "terra-2", TERRA_MODEL, track, package, tuple(expected_invariants), review_invariant_evidence)]
                if execute_cli:
                    try:
                        launched_reviews = [
                            _launch_reviewer(package, reviewer=request.reviewer, model=request.model, results_root=results_root, repo_root=repo_root, subprocess_runner=subprocess_runner)
                            for request in requests
                        ]
                    except CleanroomError as exc:
                        case_report["failure_taxonomy"] = _failure_counts([{"category": _cleanroom_error_category(exc), "passed": False}])
                        case_report["outcome"] = "needs_review"
                        case_report["execution_linkage"] = _cleanroom_error_linkage(status="not_executed", error=exc)
                        case_reports.append(case_report)
                        continue
                    review_results = [
                        _validate_result(result, case_id=case_id, reviewer=request.reviewer, expected_invariants=request.expected_invariants, invariant_evidence=request.invariant_evidence, rationale_predicates=rationale_predicates, allow_model_reported_identity=True)
                        for request, (result, _) in zip(requests, launched_reviews, strict=True)
                    ]
                    case_report["execution_linkage"] = {
                        "status": "executed",
                        "review_records": [{"reviewer": request.reviewer, "record_sha256": _sha256_file(launch.record_path), "output_sha256": _sha256_file(launch.model_output_path)} for request, (_, launch) in zip(requests, launched_reviews, strict=True)],
                    }
                elif review_runner is not None:
                    review_results = [_validate_result(review_runner(request), case_id=case_id, reviewer=request.reviewer, expected_invariants=request.expected_invariants, invariant_evidence=request.invariant_evidence, rationale_predicates=rationale_predicates) for request in requests]
                else:
                    review_results = []
                case_report["reviewers"] = review_results
                reviewer_taxonomy = [
                    {"category": item["category"], "passed": False}
                    for result in review_results
                    for item in result.get("failure_taxonomy", [])
                    if isinstance(item, dict) and isinstance(item.get("category"), str) and isinstance(item.get("count"), int)
                    for _ in range(item["count"])
                ]
                if reviewer_taxonomy:
                    case_report["failure_taxonomy"] = _failure_counts(
                        [{"category": item["category"], "passed": False} for item in deterministic["failure_taxonomy"] for _ in range(item["count"])]
                        + reviewer_taxonomy
                    )
                if len(review_results) != 2:
                    case_reports.append(case_report)
                    continue

                outcomes = {result["reviewer_outcome"] for result in review_results}
                invariant_outcomes = [{row["invariant"]: row["outcome"] for row in result["invariant_results"]} for result in review_results]
                material = len(outcomes) != 1 or invariant_outcomes[0] != invariant_outcomes[1]
                if material:
                    reason = "terra reviewers differ" if len(outcomes) != 1 else "terra invariant outcomes differ"
                    case_report["reviewer_disagreement"] = {"material": True, "reason": reason}
                    request = ReviewRequest(case_id, "sol-adjudicator", SOL_MODEL, track, package, tuple(expected_invariants), review_invariant_evidence)
                    if execute_cli:
                        try:
                            adjudicated_raw, adjudicated_launch = _launch_reviewer(package, reviewer=request.reviewer, model=request.model, results_root=results_root, repo_root=repo_root, subprocess_runner=subprocess_runner, prior_result_paths=tuple(launch.model_output_path for _, launch in launched_reviews))
                        except CleanroomError as exc:
                            case_report["failure_taxonomy"] = _failure_counts([{"category": _cleanroom_error_category(exc), "passed": False}])
                            case_report["outcome"] = "needs_review"
                            case_report["execution_linkage"] = _cleanroom_error_linkage(status="adjudication_not_executed", error=exc)
                            case_reports.append(case_report)
                            continue
                        adjudicated = _validate_result(adjudicated_raw, case_id=case_id, reviewer=request.reviewer, expected_invariants=request.expected_invariants, invariant_evidence=request.invariant_evidence, rationale_predicates=rationale_predicates, allow_model_reported_identity=True)
                        decision = {"outcome": adjudicated["reviewer_outcome"], "result": adjudicated}
                        case_report.setdefault("execution_linkage", {}).setdefault("review_records", []).append({"reviewer": request.reviewer, "record_sha256": _sha256_file(adjudicated_launch.record_path), "output_sha256": _sha256_file(adjudicated_launch.model_output_path)})
                    elif adjudicator is not None:
                        adjudicated = _validate_result(adjudicator(request), case_id=case_id, reviewer=request.reviewer, expected_invariants=request.expected_invariants, invariant_evidence=request.invariant_evidence, rationale_predicates=rationale_predicates)
                        decision = {"outcome": adjudicated["reviewer_outcome"], "result": adjudicated}
                    else:
                        decision = {"outcome": "needs_review", "result": None}
                    if decision.get("outcome") not in {"pass", "fail", "needs_review"} or (decision.get("result") is not None and not isinstance(decision.get("result"), dict)):
                        raise EvaluationError("sol adjudication requires a validated result or an explicit unexecuted state")
                    case_report["adjudication"] = {"model": SOL_MODEL, "outcome": decision["outcome"], "result": decision["result"]}
                    case_report["outcome"] = decision["outcome"]
                else:
                    case_report["outcome"] = review_results[0]["reviewer_outcome"]
                case_reports.append(case_report)

            passed = sum(case["outcome"] == "pass" for case in case_reports)
            failed = sum(case["outcome"] == "fail" for case in case_reports)
            needs_review = sum(case["outcome"] == "needs_review" for case in case_reports)
            total = len(case_reports)
            report_families.append({
                "family": family_name,
                "cases": case_reports,
                "counts": {"passed": passed, "failed": failed, "needs_review": needs_review, "total": total, "denominator": "all cases"},
                "wilson_interval": _wilson(passed, total),
                "split": {
                    "deterministic": sum(case["mode"] == "deterministic" for case in case_reports),
                    "live": sum(case["mode"] == "live" for case in case_reports),
                },
                "failure_taxonomy": _failure_counts([
                    {"category": item["category"], "passed": False}
                    for case in case_reports for item in case["failure_taxonomy"] for _ in range(item["count"])
                ]),
            })
    finally:
        for path in temporary_packets:
            path.unlink(missing_ok=True)
        if temporary_root is not None:
            shutil.rmtree(temporary_root, ignore_errors=True)
        if candidate_input_root is not None:
            shutil.rmtree(candidate_input_root, ignore_errors=True)

    report = {
        "format": "serenity-evaluation-report/2",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "tracks": tracks,
        "families": report_families,
        "aggregate_quality_score": None,
    }
    report["content_hash"] = canonical_hash(report)
    if out_path is not None:
        try:
            atomic_write_json(out_path, report)
        except Exception as exc:  # storage's error object is intentionally not part of this maintenance CLI API
            raise EvaluationError(f"cannot persist evaluation report: {out_path}") from exc
    return report
