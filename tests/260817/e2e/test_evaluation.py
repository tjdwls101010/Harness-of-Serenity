from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import serenity_core.evaluation as evaluation_module
from serenity_core.cleanroom import CleanroomError, CleanroomLaunch
from serenity_core.evaluation import EvaluationError, evaluate
from serenity_core.providers.base import ProviderEnvelope
from serenity_core.raw_cache import RawPayloadStore
from serenity_core.runtime import canonical_hash


ROOT = Path(__file__).resolve().parents[3]
FAMILIES = (
    "discovery",
    "single-ticker",
    "physical-ai",
    "near-miss",
    "degraded-data",
    "displacement-fear",
)


def reviewer_wilson(passed: int, total: int) -> dict[str, float]:
    z = 1.959963984540054
    proportion = passed / total
    denominator = 1 + z * z / total
    centre = (proportion + z * z / (2 * total)) / denominator
    spread = z * ((proportion * (1 - proportion) / total + z * z / (4 * total * total)) ** 0.5) / denominator
    return {"lower": round(max(0.0, centre - spread), 6), "upper": round(min(1.0, centre + spread), 6)}


def qa_case(case_id: str, family: str, *, network_mode: str = "offline") -> dict:
    return {
        "schema_id": "urn:serenity:schema:qa-case:1",
        "case_id": case_id,
        "family": family,
        "prompt": f"Evaluate {case_id} using only this packet.",
        "cutoff": "2026-08-17T00:00:00Z",
        "expected_invariants": ["identity is pinned", "bear case remains separate"],
        "isolation_policy": {
            "exclude_prior_verdicts": True,
            "exclude_corpus_answers": True,
            "network_mode": network_mode,
        },
    }


def typed_evidence(evidence_id: str = "fixture-evidence") -> dict:
    artifact = {
        "schema_id": "urn:serenity:schema:evidence-result:1",
        "result_id": evidence_id,
        "run_id": "run-evaluation-fixture",
        "request_id": "request-evaluation-fixture",
        "hypothesis_ids": ["hyp-evaluation-fixture"],
        "capability_id": "sec.filings",
        "availability": "available",
        "provider": "sec",
        "source": {"uri": "https://example.test/evaluation/fixture", "parameters": {}, "canonical_id": "fixture-evidence"},
        "temporal": {"effective_at": "2026-08-16", "period_start": "2026-08-01", "period_end": "2026-08-16", "observed_at": "2026-08-16", "available_at": "2026-08-16T00:00:00Z", "source_version": "fixture-1"},
        "fetched_at": "2026-08-16T00:00:00Z",
        "raw_content_sha256": "a" * 64,
        "transform_version": "fixture/1",
        "identity_bindings": {"ticker": "FIXT"},
        "fact_refs": [],
        "value": {
            "observations": [
                {"subject": "Fixture Inc.", "predicate": "reports", "object": "cash balance", "measure": {"amount": 100, "unit": "USD"}},
                {"subject": "Fixture Inc.", "predicate": "discloses", "object": "ATM proceeds", "measure": {"amount": 20, "unit": "USD"}},
            ]
        },
    }
    artifact["content_hash"] = canonical_hash(artifact)
    return {"evidence_id": evidence_id, "artifact": artifact}


def lens_scenario(case_id: str, invariants: list[str]) -> dict:
    snapshot = {
        "schema_id": "urn:serenity:schema:fact-snapshot:2",
        "snapshot_id": "snapshot-evaluation-fixture",
        "run_id": "run-evaluation-fixture",
        "as_of": "2026-08-16",
        "identity": {"ticker": "FIXT", "cik": "0000000001", "name": "Fixture Inc.", "exchange": "NASDAQ"},
        "fetched_at": "2026-08-16T00:00:00Z",
        "facts": [
            {"fact_id": "fact-cash", "name": "cash", "availability": "available", "value": 100, "unit": "USD", "provider": "sec", "request_id": "request-evaluation-fixture", "effective_at": "2026-08-16", "observed_at": "2026-08-16", "available_at": "2026-08-16T00:00:00Z", "fetched_at": "2026-08-16T00:00:00Z", "source_version": "fixture-1"},
            {"fact_id": "fact-atm", "name": "atm_proceeds", "availability": "available", "value": 20, "unit": "USD", "provider": "sec", "request_id": "request-evaluation-fixture", "effective_at": "2026-08-16", "observed_at": "2026-08-16", "available_at": "2026-08-16T00:00:00Z", "fetched_at": "2026-08-16T00:00:00Z", "source_version": "fixture-1"},
            {"fact_id": "fact-debt", "name": "debt", "availability": "available", "value": 25, "unit": "USD", "provider": "sec", "request_id": "request-evaluation-fixture", "effective_at": "2026-08-16", "observed_at": "2026-08-16", "available_at": "2026-08-16T00:00:00Z", "fetched_at": "2026-08-16T00:00:00Z", "source_version": "fixture-1"},
        ],
    }
    return {
        "schema_id": "serenity-evaluation-runtime-scenario/1",
        "actions": [{"action_id": "net-cash", "service": "serenity_core.lens.run_lens", "lens_spec": {"schema_id": "urn:serenity:schema:lens-spec:1", "lens_id": "lens-evaluation-fixture", "run_id": "run-evaluation-fixture", "question": "What net cash remains after the ATM?", "formula": "net-cash-after-atm", "inputs": [{"name": "cash", "fact_ref": "fact-cash", "unit": "USD"}, {"name": "atm_proceeds", "fact_ref": "fact-atm", "unit": "USD"}, {"name": "debt", "fact_ref": "fact-debt", "unit": "USD"}], "output_unit": "USD", "assumptions": [], "validity_constraints": ["Inputs resolve by fact reference."]}, "fact_snapshot": snapshot, "expect": {"validity": "valid"}}],
        "invariant_bindings": [{"invariant": invariant, "action_ids": ["net-cash"]} for invariant in invariants],
    }


def packet(*, prospective: bool = False, after_cutoff: bool = False) -> dict:
    available_at = "2026-08-18T00:00:00Z" if after_cutoff else "2026-08-16T00:00:00Z"
    value = {
        "facts": [{"fact_id": "fixture-fact", "availability": "available", "available_at": available_at}],
        "evidence": [typed_evidence()],
        "deterministic_assertions": [
            {"invariant": "identity is pinned", "passed": True},
            {"invariant": "bear case remains separate", "passed": True},
        ],
        "invariant_evidence": [
            {"invariant": "identity is pinned", "evidence_refs": ["fixture-evidence"]},
            {"invariant": "bear case remains separate", "evidence_refs": ["fixture-evidence"]},
        ],
    }
    if prospective:
        value["prospective"] = {
            "original_decision": {"decision_id": "fixture-decision", "falsifiers": ["fixture falsifier"]},
            "checkpoints": [{"as_of": "2026-09-01", "measurement": "observed"}],
        }
    return value


def live_provider_packet(case_id: str, raw_cache_root: Path, content: object = "fixture SEC response") -> dict:
    raw_content = json.dumps(content, sort_keys=True, separators=(",", ":")).encode("utf-8")
    envelope = ProviderEnvelope.available(
        provider="sec",
        provider_version="fixture/1",
        source_uri="https://example.test/sec/fixture",
        raw_content=raw_content,
        data={"filing": content},
        fetched_at="2026-08-17T01:00:00Z",
        request={"case_id": case_id},
        effective_at="2026-08-16",
        observed_at="2026-08-16",
        available_at="2026-08-17T01:00:00Z",
        source_version="fixture-1",
        identity_bindings={"ticker": "FIXT"},
    )
    serialized = envelope.to_dict()
    content_hash = serialized["source"]["content_sha256"]
    RawPayloadStore(raw_cache_root).cache(envelope)
    return {
        "case_id": case_id,
        "execution_state": "executed",
        "network_policy": {"allow_network": True, "providers": ["sec"]},
        "providers": [{"provider": "sec", "availability": "available", "fetched_at": "2026-08-17T01:00:00Z", "raw_content_sha256": content_hash}],
        "provider_packets": [{"provider": "sec", "envelope": serialized, "raw_cache": {"content_sha256": content_hash, "cache_key": f"sha256/{content_hash}"}}],
    }


def write_case(tmp_path: Path, *, family: str, index: int, track: str = "retrospective", prospective: bool = False) -> dict:
    case_id = f"{family}-{index:02d}"
    case_path = tmp_path / f"{case_id}.case.json"
    packet_path = tmp_path / f"{case_id}.packet.json"
    case_path.write_text(json.dumps(qa_case(case_id, family)), encoding="utf-8")
    value = packet(prospective=prospective)
    if track == "cutoff-frozen":
        value["runtime_scenario"] = lens_scenario(case_id, qa_case(case_id, family)["expected_invariants"])
    packet_path.write_text(json.dumps(value), encoding="utf-8")
    return {"case_id": case_id, "track": track, "mode": "deterministic", "qa_case": case_path.name, "packet": packet_path.name}


def write_config(tmp_path: Path, families: list[dict]) -> Path:
    config_path = tmp_path / "evaluation.json"
    config_path.write_text(json.dumps({
        "format": "serenity-evaluation-config/1",
        "candidate_runner": {
            "model": "gpt-5.6-terra",
            "result_schema": "urn:serenity:schema:candidate-result:1",
            "execution": "required_for_cli",
        },
        "families": families,
    }), encoding="utf-8")
    return config_path


def review_result(case_id: str, reviewer: str, outcome: str, invariants: tuple[str, ...] = ("identity is pinned", "bear case remains separate"), invariant_evidence: dict[str, tuple[str, ...]] | None = None) -> dict:
    passed = len(invariants) if outcome == "pass" else 0
    failed = len(invariants) if outcome == "fail" else 0
    invariant_evidence = invariant_evidence or {invariant: ("fixture-evidence",) for invariant in invariants}
    root_evidence = sorted({reference for references in invariant_evidence.values() for reference in references})
    return {
        "schema_id": "urn:serenity:schema:qa-result:1",
        "result_id": f"{case_id}-{reviewer}",
        "case_id": case_id,
        "mode": "historical",
        "executed_at": "2026-08-17T00:00:00Z",
        "counts": {"passed": passed, "failed": failed, "total": len(invariants), "denominator": "expected_invariants", "wilson_interval": reviewer_wilson(passed, len(invariants))},
        "failure_taxonomy": ([] if passed else [{"category": "review_failure", "count": max(1, failed)}]),
        "evidence_refs": root_evidence,
        "reviewer_outcome": outcome,
        "reviewer": reviewer,
        "invariant_results": [{"invariant": invariant, "outcome": outcome, "evidence_refs": list(invariant_evidence[invariant]), "rationale": "Fixture Inc. reports cash in the cited source."} for invariant in invariants],
    }


def candidate_result(request: object) -> dict:
    frozen_packet = getattr(request, "frozen_packet")
    evidence_id = frozen_packet["evidence"][0]["evidence_id"]
    result = {
        "schema_id": "urn:serenity:schema:candidate-result:1",
        "result_id": f"candidate-{getattr(request, 'case_id')}",
        "case_id": getattr(request, "case_id"),
        "run_id": "candidate-run-01",
        "model": "gpt-5.6-terra",
        "capability": "shared-harness-instruction-integration",
        "harness_hashes": [{"path": "AGENTS.md", "sha256": "a" * 64}],
        "loaded_instruction_paths": ["CLAUDE.md", ".claude/skills/serenity-single-name/SKILL.md"],
        "packet_sha256": getattr(request, "packet_sha256"),
        "decision": {"stance": "insufficient_evidence", "statement": "The available record supports further monitoring.", "evidence_refs": [evidence_id]},
        "action": {"kind": "MONITOR", "statement": "MONITOR while the record is incomplete.", "evidence_refs": [evidence_id]},
        "facts": [{"fact_id": "candidate-fact-01", "claim": "The record contains dated issuer observations.", "evidence_refs": [evidence_id]}],
        "inferences": [{"inference_id": "candidate-inference-01", "claim": "The supplied observations leave a material uncertainty to monitor.", "evidence_refs": [evidence_id]}],
        "trigger": {"statement": "A later disclosure could change the assessment.", "evidence_refs": [evidence_id]},
        "bear_case": {"statement": "The disclosed funding path can remain adverse.", "evidence_refs": [evidence_id]},
        "falsifiers": [{"statement": "A new filing could invalidate this monitoring view.", "evidence_refs": [evidence_id]}],
        "evidence_refs": [evidence_id],
        "user_artifact": {"locale": "ko", "markdown": "현재 기록만으로는 계속 확인이 필요합니다."},
    }
    result["canonical_sha256"] = canonical_hash(result)
    return result


def candidate_body_from_package(case_dir: Path) -> dict:
    packet_value = json.loads((case_dir / "frozen-packet.json").read_text(encoding="utf-8"))
    evidence_id = packet_value["evidence"][0]["evidence_id"]
    return {
        "decision": {"stance": "insufficient_evidence", "statement": "The available record supports further monitoring.", "evidence_refs": [evidence_id]},
        "action": {"kind": "MONITOR", "statement": "MONITOR while the record is incomplete.", "evidence_refs": [evidence_id]},
        "facts": [{"fact_id": "candidate-fact-01", "claim": "The record contains dated issuer observations.", "evidence_refs": [evidence_id]}],
        "inferences": [{"inference_id": "candidate-inference-01", "claim": "The supplied observations leave a material uncertainty to monitor.", "evidence_refs": [evidence_id]}],
        "trigger": {"statement": "A later disclosure could change the assessment.", "evidence_refs": [evidence_id]},
        "bear_case": {"statement": "The disclosed funding path can remain adverse.", "evidence_refs": [evidence_id]},
        "falsifiers": [{"statement": "A new filing could invalidate this monitoring view.", "evidence_refs": [evidence_id]}],
        "evidence_refs": [evidence_id],
        "user_artifact": {"locale": "ko", "markdown": "현재 기록만으로는 계속 확인이 필요합니다."},
    }


def test_evaluation_keeps_the_three_tracks_and_family_rates_separate(tmp_path: Path) -> None:
    families = []
    for position, family in enumerate(FAMILIES):
        track = ("retrospective", "cutoff-frozen", "prospective")[position % 3]
        families.append({"family": family, "cases": [write_case(tmp_path, family=family, index=1, track=track, prospective=track == "prospective")]})
    config_path = write_config(tmp_path, families)
    calls: list[tuple[str, str]] = []

    def injected_runner(request):
        calls.append((request.case_id, request.reviewer))
        return review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(config_path, repo_root=ROOT, review_runner=injected_runner)

    assert set(report["tracks"]) == {"retrospective_independent_first", "cutoff_frozen_current", "prospective_tracking"}
    assert report["aggregate_quality_score"] is None
    assert len(report["families"]) == 6
    assert all(family["counts"] == {"passed": 1, "failed": 0, "needs_review": 0, "total": 1, "denominator": "all cases"} for family in report["families"])
    assert all("wilson_interval" in family for family in report["families"])
    assert report["families"][0]["cases"][0]["cleanroom"]["allowlist"] == ["qa-case.json", "frozen-packet.json", "qa-result.schema.json", "package-manifest.json"]
    assert len(calls) == 12
    assert {reviewer for _, reviewer in calls} == {"terra-1", "terra-2"}


def test_deterministic_cutoff_failure_blocks_reviews_before_any_model_call(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="cutoff-frozen")
    packet_path = tmp_path / descriptor["packet"]
    packet_path.write_text(json.dumps(packet(after_cutoff=True)), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])
    called = False

    def injected_runner(request):
        nonlocal called
        called = True
        return review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(config_path, repo_root=ROOT, review_runner=injected_runner)

    case = report["families"][0]["cases"][0]
    assert called is False
    assert case["deterministic"]["outcome"] == "fail"
    assert case["reviewers"] == []
    assert case["failure_taxonomy"] == [{"category": "cutoff_leakage", "count": 1}, {"category": "runtime_scenario_invalid", "count": 2}]


def test_material_reviewer_disagreement_uses_one_sol_adjudication_and_preserves_the_disagreement(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="physical-ai", index=1)
    config_path = write_config(tmp_path, [{"family": "physical-ai", "cases": [descriptor]}])
    adjudications: list[tuple[str, str]] = []

    def injected_runner(request):
        outcome = "pass" if request.reviewer == "terra-1" else "fail"
        return review_result(request.case_id, request.reviewer, outcome, invariant_evidence=dict(request.invariant_evidence))

    def injected_adjudicator(request):
        adjudications.append((request.case_id, request.model))
        return review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(config_path, repo_root=ROOT, review_runner=injected_runner, adjudicator=injected_adjudicator)

    case = report["families"][0]["cases"][0]
    assert adjudications == [("physical-ai-01", "gpt-5.6-sol")]
    assert case["reviewer_disagreement"]["material"] is True
    assert [review["reviewer_outcome"] for review in case["reviewers"]] == ["pass", "fail"]
    assert case["adjudication"]["model"] == "gpt-5.6-sol"
    assert case["adjudication"]["outcome"] == "pass"
    assert "rationale" not in case["adjudication"]
    validated = case["adjudication"]["result"]
    assert validated["reviewer"] == "sol-adjudicator"
    assert validated["evidence_refs"] == ["fixture-evidence"]
    assert all(row["rationale"] == "Fixture Inc. reports cash in the cited source." for row in validated["invariant_results"])


def test_displacement_fear_det_02_runs_the_actual_capacity_arithmetic_and_binds_forward_economics_separately() -> None:
    requests = []

    def reviewer(request):
        if request.case_id == "displacement-fear-det-02":
            requests.append(request)
        return review_result(request.case_id, request.reviewer, "pass", invariants=request.expected_invariants, invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(ROOT / "config" / "evaluation.json", repo_root=ROOT, review_runner=reviewer)

    case = next(
        item
        for family in report["families"]
        if family["family"] == "displacement-fear"
        for item in family["cases"]
        if item["case_id"] == "displacement-fear-det-02"
    )
    runtime_by_id = {item["evidence_id"]: item["artifact"] for item in case["deterministic"]["runtime_evidence"]}
    annualized_ref = "runtime-displacement-fear-det-02-qualified-capacity-annualized"
    coverage_ref = "runtime-displacement-fear-det-02-qualified-capacity-coverage"
    assert runtime_by_id[annualized_ref]["output"]["expression"] == "qualified_capacity_per_month * months_per_year"
    assert runtime_by_id[annualized_ref]["output"]["value"] == 144000.0
    assert runtime_by_id[coverage_ref]["output"]["expression"] == "qualified_capacity_per_month * months_per_year / platform_annual_volume"
    assert runtime_by_id[coverage_ref]["output"]["value"] == pytest.approx(144000 / 420000)
    assert all(annualized_ref in request.invariant_evidence["mechanical claim tested before sentiment"] for request in requests)
    assert all(coverage_ref in request.invariant_evidence["forward economics and falsifier remain separate"] for request in requests)
    assert all(coverage_ref not in request.invariant_evidence["mechanical claim tested before sentiment"] for request in requests)


def test_cutoff_frozen_sol_keeps_runtime_citations_and_excludes_transport_only_live_provider(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="cutoff-frozen")
    descriptor.update({"mode": "live", "execution_state": "descriptor_not_run", "provider_requirements": [{"provider": "sec", "availability_required": "available"}]})
    (tmp_path / descriptor["qa_case"]).write_text(json.dumps(qa_case("single-ticker-01", "single-ticker", network_mode="live")), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])
    terra_contracts: list[dict[str, tuple[str, ...]]] = []
    sol_requests = []

    def injected_runner(request):
        terra_contracts.append(dict(request.invariant_evidence))
        result = review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))
        result["reviewer_outcome"] = "needs_review"
        result["counts"] = {"passed": 1, "failed": 0, "total": 2, "denominator": "expected_invariants", "wilson_interval": reviewer_wilson(1, 2)}
        result["invariant_results"][0 if request.reviewer == "terra-1" else 1]["outcome"] = "needs_review"
        return result

    def injected_adjudicator(request):
        sol_requests.append(request)
        return review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))

    raw_cache = tmp_path / "raw-cache"
    report = evaluate(
        config_path,
        repo_root=ROOT,
        review_runner=injected_runner,
        adjudicator=injected_adjudicator,
        live_provider_packets={"single-ticker-01": live_provider_packet("single-ticker-01", raw_cache, {"filing": "executed live provider content"})},
        live_raw_cache_root=raw_cache,
    )

    case = report["families"][0]["cases"][0]
    assert len(sol_requests) == 1
    assert sol_requests[0].invariant_evidence == terra_contracts[0] == terra_contracts[1]
    assert all(any(reference.startswith("runtime-single-ticker-01-") for reference in refs) for refs in sol_requests[0].invariant_evidence.values())
    assert all("live-single-ticker-01-sec" not in refs for refs in sol_requests[0].invariant_evidence.values())
    assert case["live_evidence"] == {"role": "transport_only", "semantic_invariant_bindings": []}
    assert case["reviewer_disagreement"] == {"material": True, "reason": "terra invariant outcomes differ"}


def test_consensus_failure_is_final_without_a_sol_adjudication(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="physical-ai", index=1)
    config_path = write_config(tmp_path, [{"family": "physical-ai", "cases": [descriptor]}])

    report = evaluate(
        config_path,
        repo_root=ROOT,
        review_runner=lambda request: review_result(request.case_id, request.reviewer, "fail", invariant_evidence=dict(request.invariant_evidence)),
        adjudicator=lambda request: pytest.fail("consensus must not invoke sol"),
    )

    case = report["families"][0]["cases"][0]
    assert case["outcome"] == "fail"
    assert case["reviewer_disagreement"] == {"material": False, "reason": None}
    assert case["adjudication"] is None


def test_consensus_needs_review_is_final_when_both_invariant_sets_match(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="physical-ai", index=1)
    config_path = write_config(tmp_path, [{"family": "physical-ai", "cases": [descriptor]}])

    def needs_review(request):
        result = review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))
        result["reviewer_outcome"] = "needs_review"
        result["counts"] = {"passed": 1, "failed": 0, "total": 2, "denominator": "expected_invariants", "wilson_interval": reviewer_wilson(1, 2)}
        result["invariant_results"][0]["outcome"] = "needs_review"
        return result

    report = evaluate(
        config_path,
        repo_root=ROOT,
        review_runner=needs_review,
        adjudicator=lambda request: pytest.fail("matching invariant outcomes must not invoke sol"),
    )

    case = report["families"][0]["cases"][0]
    assert case["outcome"] == "needs_review"
    assert case["reviewer_disagreement"] == {"material": False, "reason": None}
    assert case["adjudication"] is None


def test_cutoff_frozen_track_runs_the_runtime_scenario_instead_of_packet_assertions(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="cutoff-frozen")
    packet_path = tmp_path / descriptor["packet"]
    frozen = json.loads(packet_path.read_text(encoding="utf-8"))
    frozen["deterministic_assertions"] = [{"invariant": "identity is pinned", "passed": False}]
    packet_path.write_text(json.dumps(frozen), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    report = evaluate(config_path, repo_root=ROOT)

    assert report["families"][0]["cases"][0]["deterministic"]["outcome"] == "pass"


def test_reviewer_requires_exact_invariant_coverage_and_evidence_refs(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1)
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    def missing_evidence(request):
        result = review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))
        result["invariant_results"][0]["evidence_refs"] = []
        return result

    with pytest.raises(EvaluationError, match="invariant evidence refs"):
        evaluate(config_path, repo_root=ROOT, review_runner=missing_evidence)


def test_cleanroom_packet_excludes_assertion_markers_and_contains_runtime_evidence(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="cutoff-frozen")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])
    captured: list[dict] = []
    requests = []

    def injected_runner(request):
        requests.append(request)
        captured.append(json.loads((request.package.case_dir / "frozen-packet.json").read_text(encoding="utf-8")))
        return review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))

    evaluate(config_path, repo_root=ROOT, review_runner=injected_runner)

    assert len(captured) == 2
    reviewer_packet = captured[0]
    assert "deterministic_assertions" not in reviewer_packet
    assert "runtime_scenario" not in reviewer_packet
    assert reviewer_packet["runtime_evidence"]
    assert all("artifact" in item and item["artifact"].get("schema_id") for item in reviewer_packet["evidence"])
    assert reviewer_packet["citation_contract"]["invariant_evidence"][0]["evidence_refs"]
    assert "passed" not in json.dumps(reviewer_packet["citation_contract"])
    assert all(any(reference.startswith("runtime-single-ticker-01-") for reference in refs) for refs in requests[0].invariant_evidence.values())


def test_sector_graph_runtime_evidence_projects_observed_relations_not_graph_conclusions(tmp_path: Path) -> None:
    captured: list[dict] = []

    def injected_runner(request):
        captured.append(json.loads((request.package.case_dir / "frozen-packet.json").read_text(encoding="utf-8")))
        return review_result(request.case_id, request.reviewer, "pass", invariants=request.expected_invariants, invariant_evidence=dict(request.invariant_evidence))

    evaluate(ROOT / "config" / "evaluation.json", repo_root=ROOT, review_runner=injected_runner)

    reviewer_packet = next(packet for packet in captured if packet["evidence"][0]["evidence_id"] == "physical-ai-det-02-evidence")
    runtime = reviewer_packet["runtime_evidence"][0]["artifact"]
    assert runtime["schema_id"] == "urn:serenity:evaluation:sector-graph-runtime-observations:1"
    assert runtime["service_output_sha256"]
    assert runtime["observations"]
    serialized = json.dumps(runtime)
    assert "recursive_bottom_hop" not in serialized
    assert "sibling_comparison" not in serialized
    assert '"statement"' not in serialized


def test_discovery_runtime_projection_does_not_invent_a_robo_us_listing_from_an_unresolved_vehicle(tmp_path: Path) -> None:
    captured: list[dict] = []

    def injected_runner(request):
        captured.append(json.loads((request.package.case_dir / "frozen-packet.json").read_text(encoding="utf-8")))
        return review_result(request.case_id, request.reviewer, "pass", invariants=request.expected_invariants, invariant_evidence=dict(request.invariant_evidence))

    evaluate(ROOT / "config" / "evaluation.json", repo_root=ROOT, review_runner=injected_runner)

    reviewer_packet = next(packet for packet in captured if packet["evidence"][0]["evidence_id"] == "discovery-det-02-evidence")
    runtime = reviewer_packet["runtime_evidence"][0]["artifact"]
    assert "ROBO" not in json.dumps(runtime)
    assert "trades_on" not in json.dumps(runtime)
    assert reviewer_packet["evidence"][0]["artifact"]["value"]["observations"][-1]["subject"] == "ROBO ETF"


def test_embedded_runtime_manifests_are_schema_valid_and_content_addressed() -> None:
    manifests: list[tuple[Path, dict]] = []
    for packet_path in sorted((ROOT / "tests" / "260817" / "fixtures" / "eval").rglob("*.packet.json")):
        packet_value = json.loads(packet_path.read_text(encoding="utf-8"))
        scenario = packet_value.get("runtime_scenario")
        if not isinstance(scenario, dict):
            continue
        for action in scenario.get("actions", []):
            if isinstance(action, dict) and isinstance(action.get("run_manifest"), dict):
                manifests.append((packet_path, action["run_manifest"]))

    assert manifests
    for packet_path, manifest in manifests:
        assert manifest["content_hash"] == canonical_hash({key: value for key, value in manifest.items() if key != "content_hash"}), packet_path


def test_build_snapshot_runtime_rejects_corrupt_manifest_before_identity_block(tmp_path: Path) -> None:
    source_case = ROOT / "tests" / "260817" / "fixtures" / "eval" / "discovery" / "det-02.case.json"
    source_packet = ROOT / "tests" / "260817" / "fixtures" / "eval" / "discovery" / "det-02.packet.json"
    case_path = tmp_path / source_case.name
    packet_path = tmp_path / source_packet.name
    case_path.write_text(source_case.read_text(encoding="utf-8"), encoding="utf-8")
    packet_value = json.loads(source_packet.read_text(encoding="utf-8"))
    packet_value["runtime_scenario"]["actions"][0]["run_manifest"]["content_hash"] = "0" * 64
    packet_path.write_text(json.dumps(packet_value), encoding="utf-8")
    descriptor = {
        "case_id": "discovery-det-02",
        "track": "cutoff-frozen",
        "mode": "deterministic",
        "qa_case": case_path.name,
        "packet": packet_path.name,
    }
    config_path = write_config(tmp_path, [{"family": "discovery", "cases": [descriptor]}])

    report = evaluate(
        config_path,
        repo_root=ROOT,
        review_runner=lambda request: review_result(request.case_id, request.reviewer, "pass", invariants=request.expected_invariants, invariant_evidence=dict(request.invariant_evidence)),
    )

    case = report["families"][0]["cases"][0]
    runtime = case["deterministic"]["runtime_evidence"][0]["artifact"]
    assert case["outcome"] == "fail"
    assert case["reviewers"] == []
    assert runtime["schema_id"] == "urn:serenity:evaluation:runtime-error:1"
    assert runtime["service"] == "serenity_core.snapshot.build_security_snapshot"
    assert runtime["error"] == "runtime run_manifest content_hash is invalid"
    assert "blocked_reason" not in runtime


def test_discovery_runtime_uses_a_fail_closed_identity_snapshot_without_projecting_graph_claims(tmp_path: Path) -> None:
    captured: list[dict] = []

    def blocked_candidate(request):
        result = candidate_result(request)
        result["action"] = {"kind": "BLOCKED", "statement": "MORIY venue evidence does not bind it to Mori Precision, and ROBO's holding does not establish a US listing.", "evidence_refs": list(result["evidence_refs"])}
        result["user_artifact"] = {"locale": "ko", "markdown": "식별과 상장 상태가 확인되지 않아 보류합니다."}
        result["canonical_sha256"] = canonical_hash({key: value for key, value in result.items() if key != "canonical_sha256"})
        return result

    def injected_runner(request):
        captured.append(json.loads((request.package.case_dir / "frozen-packet.json").read_text(encoding="utf-8")))
        return review_result(request.case_id, request.reviewer, "pass", invariants=request.expected_invariants, invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(ROOT / "config" / "evaluation.json", repo_root=ROOT, candidate_runner=blocked_candidate, review_runner=injected_runner)

    reviewer_packet = next(packet for packet in captured if packet["evidence"][0]["evidence_id"] == "discovery-det-02-evidence")
    runtime = reviewer_packet["runtime_evidence"][0]["artifact"]
    assert runtime["schema_id"] == "urn:serenity:evaluation:runtime-blocked:1"
    assert runtime["service"] == "serenity_core.snapshot.build_security_snapshot"
    assert runtime["blocked_reason"] == "issuer_identity_unresolved"
    assert "edges" not in json.dumps(runtime)
    assert "concentration" not in json.dumps(runtime)
    assert "content_hash" not in json.dumps(runtime)
    discovery_case = next(case for family in report["families"] if family["family"] == "discovery" for case in family["cases"] if case["case_id"] == "discovery-det-02")
    assert discovery_case["candidate"]["action"] == "BLOCKED"
    assert discovery_case["outcome"] == "pass"


def test_reviewer_rationale_cannot_cite_an_excluded_assertion_marker(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1)
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    def assertion_rationale(request):
        result = review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))
        result["invariant_results"][0]["rationale"] = "deterministic_assertions says passed"
        return result

    with pytest.raises(EvaluationError, match="excluded assertion marker"):
        evaluate(config_path, repo_root=ROOT, review_runner=assertion_rationale)


def test_reviewer_rationale_cannot_treat_a_runtime_schema_field_as_the_evidence(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="cutoff-frozen")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    def assertion_rationale(request):
        result = review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))
        result["invariant_results"][0]["rationale"] = "The runtime validator explicitly identifies the invariant."
        return result

    with pytest.raises(EvaluationError, match="merely cites a runtime assertion"):
        evaluate(config_path, repo_root=ROOT, review_runner=assertion_rationale)


def test_bare_id_evidence_is_rejected_at_the_public_evaluate_seam(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1)
    packet_path = tmp_path / descriptor["packet"]
    unsafe_packet = json.loads(packet_path.read_text(encoding="utf-8"))
    unsafe_packet["evidence"] = [{"evidence_id": "fixture-evidence", "availability": "available"}]
    packet_path.write_text(json.dumps(unsafe_packet), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    with pytest.raises(EvaluationError, match="substantive typed artifact"):
        evaluate(config_path, repo_root=ROOT)


def test_outcome_bearing_or_expected_invariant_paraphrase_is_not_substantive_evidence(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1)
    packet_path = tmp_path / descriptor["packet"]
    unsafe_packet = json.loads(packet_path.read_text(encoding="utf-8"))
    artifact = unsafe_packet["evidence"][0]["artifact"]
    artifact["value"] = {"statement": "Identity is pinned, so the action requires a PASS recommendation."}
    artifact["content_hash"] = canonical_hash({key: value for key, value in artifact.items() if key != "content_hash"})
    packet_path.write_text(json.dumps(unsafe_packet), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    with pytest.raises(EvaluationError, match="outcome-bearing or invariant-paraphrasing"):
        evaluate(config_path, repo_root=ROOT)


def test_opt_in_cli_runs_two_terra_reviews_then_one_sol_adjudication(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="physical-ai", index=1)
    config_path = write_config(tmp_path, [{"family": "physical-ai", "cases": [descriptor]}])
    models: list[str] = []

    def fake_subprocess(argv: list[str], **kwargs: object) -> object:
        case_dir = Path(str(argv[argv.index("--cd") + 1]))
        model = str(argv[argv.index("--model") + 1])
        output = Path(str(argv[argv.index("--output-last-message") + 1]))
        if (case_dir / "candidate-case.json").is_file():
            models.append("candidate")
            output.write_text(json.dumps(candidate_body_from_package(case_dir)), encoding="utf-8")
            return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        models.append(model)
        reviewer_models = [item for item in models if item != "candidate"]
        outcome = "pass" if model == "gpt-5.6-sol" or len(reviewer_models) == 1 else "fail"
        reviewer = ("terra-1", "terra-2", "sol-adjudicator")[len(reviewer_models) - 1]
        output.write_text(json.dumps(review_result("physical-ai-01", reviewer, outcome)), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    report = evaluate(
        config_path,
        repo_root=ROOT,
        execute_cli=True,
        cleanroom_root=tmp_path / "cleanrooms",
        results_root=tmp_path / "results",
        subprocess_runner=fake_subprocess,
    )

    assert models == ["candidate", "gpt-5.6-terra", "gpt-5.6-terra", "gpt-5.6-sol"]
    case = report["families"][0]["cases"][0]
    assert case["candidate_required"] is True
    assert case["candidate"]["required"] is True
    assert case["candidate"]["status"] == "executed"
    assert case["adjudication"]["outcome"] == "pass"
    records = list((tmp_path / "results" / "physical-ai-01").glob("*/execution.json"))
    assert len(records) == 3
    assert all(json.loads(path.read_text(encoding="utf-8"))["transcript_audit"]["command_count"] == 0 for path in records)


def test_cli_preserves_model_reviewer_identity_but_binds_it_to_the_assigned_terra_slot(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="cutoff-frozen")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    def fake_subprocess(argv: list[str], **kwargs: object) -> object:
        case_dir = Path(str(argv[argv.index("--cd") + 1]))
        output = Path(str(argv[argv.index("--output-last-message") + 1]))
        if (case_dir / "candidate-case.json").is_file():
            output.write_text(json.dumps(candidate_body_from_package(case_dir)), encoding="utf-8")
            return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        refs = ("runtime-single-ticker-01-net-cash", "fixture-evidence")
        result = review_result(
            "single-ticker-01",
            "independent_qa_reviewer",
            "pass",
            invariant_evidence={
                "identity is pinned": refs,
                "bear case remains separate": refs,
            },
        )
        output.write_text(json.dumps(result), encoding="utf-8")
        return type("Completed", (), {"returncode": 0, "stdout": "", "stderr": ""})()

    report = evaluate(
        config_path,
        repo_root=ROOT,
        execute_cli=True,
        cleanroom_root=tmp_path / "cleanrooms",
        results_root=tmp_path / "results",
        subprocess_runner=fake_subprocess,
    )

    reviewers = report["families"][0]["cases"][0]["reviewers"]
    assert [item["reviewer"] for item in reviewers] == ["independent_qa_reviewer", "independent_qa_reviewer"]
    assert [item["assigned_reviewer"] for item in reviewers] == ["terra-1", "terra-2"]


@pytest.mark.parametrize(
    ("error", "expected_category"),
    (
        (CleanroomError("os-enforced runner unavailable", code="invalid_reviewer_output"), "invalid_reviewer_output"),
        (CleanroomError("reviewer output semantic aggregate is invalid", code="isolation_unavailable"), "isolation_unavailable"),
    ),
)
def test_cli_cleanroom_error_taxonomy_uses_typed_code_not_error_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: CleanroomError, expected_category: str) -> None:
    descriptor = write_case(tmp_path, family="degraded-data", index=1)
    config_path = write_config(tmp_path, [{"family": "degraded-data", "cases": [descriptor]}])

    def raise_cleanroom_error(*args: object, **kwargs: object) -> object:
        raise error

    monkeypatch.setattr(evaluation_module, "_launch_reviewer", raise_cleanroom_error)

    report = evaluate(
        config_path,
        repo_root=ROOT,
        execute_cli=True,
        cleanroom_root=tmp_path / "cleanrooms",
        results_root=tmp_path / "results",
        subprocess_runner=lambda *args, **kwargs: pytest.fail("typed launch error must short-circuit runner"),
        candidate_runner=candidate_result,
    )

    case = report["families"][0]["cases"][0]
    assert case["outcome"] == "needs_review"
    assert case["failure_taxonomy"] == [{"category": expected_category, "count": 1}]
    assert case["execution_linkage"] == {"status": "not_executed", "reason": str(error), "error_code": error.code}


def test_cli_adjudication_cleanroom_error_uses_typed_taxonomy_and_preserves_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    descriptor = write_case(tmp_path, family="physical-ai", index=1)
    config_path = write_config(tmp_path, [{"family": "physical-ai", "cases": [descriptor]}])
    error = CleanroomError("semantic output defect", code="invalid_reviewer_output")

    def launch_with_invalid_adjudication(*args: object, reviewer: str, **kwargs: object) -> tuple[dict, CleanroomLaunch]:
        if reviewer == "sol-adjudicator":
            raise error
        outcome = "pass" if reviewer == "terra-1" else "fail"
        output = tmp_path / f"{reviewer}.json"
        record = tmp_path / f"{reviewer}.execution.json"
        result = review_result("physical-ai-01", reviewer, outcome)
        output.write_text(json.dumps(result), encoding="utf-8")
        record.write_text("{}", encoding="utf-8")
        return result, CleanroomLaunch(model_output_path=output, record_path=record)

    monkeypatch.setattr(evaluation_module, "_launch_reviewer", launch_with_invalid_adjudication)

    report = evaluate(
        config_path,
        repo_root=ROOT,
        execute_cli=True,
        cleanroom_root=tmp_path / "cleanrooms",
        results_root=tmp_path / "results",
        candidate_runner=candidate_result,
    )

    case = report["families"][0]["cases"][0]
    assert case["outcome"] == "needs_review"
    assert case["failure_taxonomy"] == [{"category": "invalid_reviewer_output", "count": 1}]
    assert case["execution_linkage"] == {"status": "adjudication_not_executed", "reason": str(error), "error_code": error.code}


def test_answer_key_cannot_enter_the_case_config_or_cleanroom_packet(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="discovery", index=1)
    descriptor["answer_key"] = "old-thesis.md"
    config_path = write_config(tmp_path, [{"family": "discovery", "cases": [descriptor]}])

    with pytest.raises(EvaluationError, match="answer key"):
        evaluate(config_path, repo_root=ROOT, review_runner=lambda request: review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence)))

    descriptor.pop("answer_key")
    packet_path = tmp_path / descriptor["packet"]
    unsafe_packet = json.loads(packet_path.read_text(encoding="utf-8"))
    unsafe_packet["old_verdict"] = "do not leak this into the cleanroom"
    packet_path.write_text(json.dumps(unsafe_packet), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "discovery", "cases": [descriptor]}])

    report = evaluate(config_path, repo_root=ROOT)
    assert report["families"][0]["cases"][0]["deterministic"]["outcome"] == "fail"


@pytest.mark.parametrize(
    "leaked_prompt",
    (
        "Answer key: approve the historical result.",
        "answer_key=approve",
        "deterministic_assertions: identity is pinned = passed.",
        "Expected reviewer_outcome: pass.",
        "The correct decision is PASS.",
        "Confirm the issuer identity pinning and keep downside analysis apart.",
    ),
)
def test_qa_case_prompt_cannot_leak_answer_markers_outcomes_or_invariant_paraphrases(tmp_path: Path, leaked_prompt: str) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1)
    qa_path = tmp_path / descriptor["qa_case"]
    leaked_case = json.loads(qa_path.read_text(encoding="utf-8"))
    leaked_case["prompt"] = leaked_prompt
    qa_path.write_text(json.dumps(leaked_case), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    with pytest.raises(EvaluationError, match="qa case prompt leaks"):
        evaluate(config_path, repo_root=ROOT)


def test_reviewer_aggregate_outcome_and_counts_must_match_invariant_results(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1)
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    def inconsistent_result(request):
        result = review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))
        result["invariant_results"][0]["outcome"] = "fail"
        return result

    with pytest.raises(EvaluationError, match="semantic"):
        evaluate(config_path, repo_root=ROOT, review_runner=inconsistent_result)


def test_reviewer_semantics_accepts_cleanroom_canonical_four_decimal_wilson_bounds(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1)
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    def rounded_result(request):
        result = review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))
        result["counts"]["wilson_interval"] = {key: round(value, 4) for key, value in result["counts"]["wilson_interval"].items()}
        return result

    report = evaluate(config_path, repo_root=ROOT, review_runner=rounded_result)

    assert report["families"][0]["cases"][0]["outcome"] == "pass"


@pytest.mark.parametrize(
    ("invariant_outcomes", "reviewer_outcome", "wilson_interval"),
    (
        (("pass", "pass"), "pass", {"lower": 0.342372, "upper": 1.0}),
        (("pass", "needs_review"), "needs_review", {"lower": 0.094529, "upper": 0.905471}),
        (("fail", "fail"), "fail", {"lower": 0.0, "upper": 0.657628}),
    ),
)
def test_reviewer_semantics_accepts_cleanroom_z_196_wilson_bounds(tmp_path: Path, invariant_outcomes: tuple[str, str], reviewer_outcome: str, wilson_interval: dict[str, float]) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1)
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    def z_196_result(request):
        result = review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))
        for row, outcome in zip(result["invariant_results"], invariant_outcomes, strict=True):
            row["outcome"] = outcome
        passed = invariant_outcomes.count("pass")
        failed = invariant_outcomes.count("fail")
        result["reviewer_outcome"] = reviewer_outcome
        result["counts"] = {"passed": passed, "failed": failed, "total": 2, "denominator": "expected_invariants", "wilson_interval": wilson_interval}
        return result

    report = evaluate(config_path, repo_root=ROOT, review_runner=z_196_result)

    assert report["families"][0]["cases"][0]["outcome"] == reviewer_outcome


def test_reviewer_semantics_rejects_impossible_wilson_interval_even_with_z_196_tolerance(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="degraded-data", index=1)
    config_path = write_config(tmp_path, [{"family": "degraded-data", "cases": [descriptor]}])

    def impossible_interval(request):
        result = review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))
        result["invariant_results"][1]["outcome"] = "needs_review"
        result["reviewer_outcome"] = "needs_review"
        result["counts"] = {"passed": 1, "failed": 0, "total": 2, "denominator": "expected_invariants", "wilson_interval": {"lower": 0.0, "upper": 1.0}}
        return result

    with pytest.raises(EvaluationError, match="semantic aggregate"):
        evaluate(config_path, repo_root=ROOT, review_runner=impossible_interval)


def test_committed_config_has_two_deterministic_cases_and_one_opt_in_live_descriptor_per_family() -> None:
    config_path = ROOT / "config" / "evaluation.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert {family["family"] for family in config["families"]} == set(FAMILIES)
    for family in config["families"]:
        modes = [case["mode"] for case in family["cases"]]
        assert modes.count("deterministic") == 2
        assert modes.count("live") == 1
        assert all(case["execution_state"] == "descriptor_not_run" for case in family["cases"] if case["mode"] == "live")
        assert {case["provider_requirements"][0]["provider"] for case in family["cases"] if case["mode"] == "live"} == {"yfinance"}
        assert all(case["live_evidence"] == {"role": "transport_only"} for case in family["cases"] if case["mode"] == "live")
        assert all("answer_key" not in case for case in family["cases"])


def test_cli_emits_one_json_report_without_opted_in_model_execution() -> None:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "serenity_eval.py")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    lines = completed.stdout.splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["ok"] is True
    assert payload["report"]["aggregate_quality_score"] is None


def test_cli_help_explains_the_evaluation_contract_without_running_or_writing(tmp_path: Path) -> None:
    out = tmp_path / "must-not-exist.json"
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "serenity_eval.py"), "--out", str(out), "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert out.exists() is False
    for phrase in (
        "A — retrospective independent-first",
        "B — cutoff-frozen current packets",
        "C — prospective tracking",
        "deterministic fixture cases and opt-in live descriptors",
        "shared-Harness candidate",
        "family-routed Harness root/skill snapshot",
        "typed candidate result and user-facing artifact",
        "two independent Codex terra reviews",
        "One Codex sol adjudication only for material disagreement",
        "No configured hook lifecycle is executed",
        "transport_only",
        "provider_transport_only",
        "Semantic live evidence requires exact subject identity and availability at or before the cutoff",
        "cleanroom",
        "--out",
        "--live-packet-dir",
        "needs_review",
        "all cases",
        "exit 0",
        "exit 2",
        "Examples:",
        "serenity_eval.py --out reports/evaluation.json",
        "serenity_eval.py --live-packet-dir /secure/provider-packets --live-raw-cache-dir /secure/provider-raw",
        "serenity_eval.py --execute-cli",
    ):
        assert phrase in completed.stdout


def test_qa_case_and_injected_reviewer_outputs_are_validated_against_their_actual_schemas(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1)
    qa_path = tmp_path / descriptor["qa_case"]
    invalid_qa = json.loads(qa_path.read_text(encoding="utf-8"))
    invalid_qa["unexpected"] = True
    qa_path.write_text(json.dumps(invalid_qa), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    with pytest.raises(EvaluationError, match="qa case schema"):
        evaluate(config_path, repo_root=ROOT, review_runner=lambda request: review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence)))

    qa_path.write_text(json.dumps(qa_case("single-ticker-01", "single-ticker")), encoding="utf-8")

    def invalid_reviewer(request):
        result = review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))
        result["unexpected"] = True
        return result

    with pytest.raises(EvaluationError, match="reviewer terra-1 schema"):
        evaluate(config_path, repo_root=ROOT, review_runner=invalid_reviewer)

    def split_reviewers(request):
        return review_result(request.case_id, request.reviewer, "pass" if request.reviewer == "terra-1" else "fail", invariant_evidence=dict(request.invariant_evidence))

    with pytest.raises(EvaluationError, match="reviewer sol-adjudicator schema"):
        evaluate(
            config_path,
            repo_root=ROOT,
            review_runner=split_reviewers,
            adjudicator=lambda request: {**review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence)), "unexpected": True},
        )


def test_family_denominator_includes_unresolved_cases_and_wilson_names_that_denominator(tmp_path: Path) -> None:
    first = write_case(tmp_path, family="discovery", index=1)
    second = write_case(tmp_path, family="discovery", index=2)
    config_path = write_config(tmp_path, [{"family": "discovery", "cases": [first, second]}])

    report = evaluate(config_path, repo_root=ROOT)

    family = report["families"][0]
    assert family["counts"] == {"passed": 0, "failed": 0, "needs_review": 2, "total": 2, "denominator": "all cases"}
    assert family["wilson_interval"]["denominator"] == "all cases; needs_review is not a success"
    assert family["wilson_interval"]["numerator"] == 0


def test_default_live_descriptors_are_not_run_or_presented_as_provider_evidence() -> None:
    report = evaluate(ROOT / "config" / "evaluation.json", repo_root=ROOT)

    live_cases = [case for family in report["families"] for case in family["cases"] if case["mode"] == "live"]
    assert len(live_cases) == 6
    assert all(case["execution_state"] == "descriptor_not_run" for case in live_cases)
    assert all(case["outcome"] == "needs_review" and case["reviewers"] == [] for case in live_cases)
    assert all(case["provider_requirements"][0]["provider"] != "fixture" for case in live_cases)


def test_post_cutoff_transport_only_live_capture_is_executed_but_never_citable(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="prospective", prospective=True)
    descriptor.update({"mode": "live", "execution_state": "descriptor_not_run", "provider_requirements": [{"provider": "sec", "availability_required": "available"}]})
    qa_path = tmp_path / descriptor["qa_case"]
    qa_path.write_text(json.dumps(qa_case("single-ticker-01", "single-ticker", network_mode="live")), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])
    calls: list[str] = []
    citation_contracts: list[dict[str, tuple[str, ...]]] = []

    def injected_runner(request):
        calls.append(request.reviewer)
        citation_contracts.append(dict(request.invariant_evidence))
        return review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(
        config_path,
        repo_root=ROOT,
        review_runner=injected_runner,
        live_provider_packets={"single-ticker-01": live_provider_packet("single-ticker-01", tmp_path / "raw-cache")},
        live_raw_cache_root=tmp_path / "raw-cache",
    )

    case = report["families"][0]["cases"][0]
    assert calls == ["terra-1", "terra-2"]
    assert case["execution_state"] == "executed"
    assert case["provider_execution"]["providers"][0]["provider"] == "sec"
    assert case["provider_execution"]["checkpoint_role"] == "provider_transport_only"
    assert case["provider_execution"]["eligible_for_case_evidence"] is False
    assert case["live_evidence"] == {"role": "transport_only", "semantic_invariant_bindings": []}
    assert case["provider_execution"]["providers"][0]["fetched_at"] > "2026-08-17T00:00:00Z"
    assert all("live-single-ticker-01-sec" not in refs for contract in citation_contracts for refs in contract.values())
    assert case["source_packet"]["executed_live_packet_hash"]
    envelope = live_provider_packet("single-ticker-01", tmp_path / "another-raw-cache")["provider_packets"][0]["envelope"]
    assert envelope["source"]["content_sha256"] != canonical_hash(envelope)


def test_live_provider_is_semantic_evidence_only_for_an_explicit_subject_bound_invariant_mapping(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="prospective", prospective=True)
    descriptor.update(
        {
            "mode": "live",
            "execution_state": "descriptor_not_run",
            "provider_requirements": [{"provider": "sec", "availability_required": "available"}],
            "live_evidence": {
                "role": "semantic",
                "provider_subject": {"ticker": "FIXT"},
                "invariant_bindings": [{"invariant": "identity is pinned", "provider": "sec"}],
            },
        }
    )
    qa_path = tmp_path / descriptor["qa_case"]
    case = qa_case("single-ticker-01", "single-ticker", network_mode="live")
    case["cutoff"] = "2026-08-17T02:00:00Z"
    qa_path.write_text(json.dumps(case), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])
    contracts: list[dict[str, tuple[str, ...]]] = []

    def injected_runner(request):
        contracts.append(dict(request.invariant_evidence))
        return review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(
        config_path,
        repo_root=ROOT,
        review_runner=injected_runner,
        live_provider_packets={"single-ticker-01": live_provider_packet("single-ticker-01", tmp_path / "raw-cache")},
        live_raw_cache_root=tmp_path / "raw-cache",
    )

    case = report["families"][0]["cases"][0]
    assert all("live-single-ticker-01-sec" in contract["identity is pinned"] for contract in contracts)
    assert all("live-single-ticker-01-sec" not in contract["bear case remains separate"] for contract in contracts)
    assert case["live_evidence"] == {
        "role": "semantic",
        "provider_subject": {"ticker": "FIXT"},
        "semantic_invariant_bindings": [{"invariant": "identity is pinned", "provider": "sec"}],
    }


def test_semantic_live_provider_mapping_rejects_a_subject_identity_mismatch(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="prospective", prospective=True)
    descriptor.update(
        {
            "mode": "live",
            "execution_state": "descriptor_not_run",
            "provider_requirements": [{"provider": "sec", "availability_required": "available"}],
            "live_evidence": {
                "role": "semantic",
                "provider_subject": {"ticker": "NVDA"},
                "invariant_bindings": [{"invariant": "identity is pinned", "provider": "sec"}],
            },
        }
    )
    qa_path = tmp_path / descriptor["qa_case"]
    case = qa_case("single-ticker-01", "single-ticker", network_mode="live")
    case["cutoff"] = "2026-08-17T02:00:00Z"
    qa_path.write_text(json.dumps(case), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    with pytest.raises(EvaluationError, match="provider_subject"):
        evaluate(
            config_path,
            repo_root=ROOT,
            live_provider_packets={"single-ticker-01": live_provider_packet("single-ticker-01", tmp_path / "raw-cache")},
            live_raw_cache_root=tmp_path / "raw-cache",
        )


def test_semantic_live_provider_mapping_rejects_evidence_available_after_the_case_cutoff(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="prospective", prospective=True)
    descriptor.update(
        {
            "mode": "live",
            "execution_state": "descriptor_not_run",
            "provider_requirements": [{"provider": "sec", "availability_required": "available"}],
            "live_evidence": {
                "role": "semantic",
                "provider_subject": {"ticker": "FIXT"},
                "invariant_bindings": [{"invariant": "identity is pinned", "provider": "sec"}],
            },
        }
    )
    qa_path = tmp_path / descriptor["qa_case"]
    qa_path.write_text(json.dumps(qa_case("single-ticker-01", "single-ticker", network_mode="live")), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    with pytest.raises(EvaluationError, match="available at or before the case cutoff"):
        evaluate(
            config_path,
            repo_root=ROOT,
            live_provider_packets={"single-ticker-01": live_provider_packet("single-ticker-01", tmp_path / "raw-cache")},
            live_raw_cache_root=tmp_path / "raw-cache",
        )


def test_live_packet_requires_case_bound_provider_content_not_only_metadata(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="prospective", prospective=True)
    descriptor.update({"mode": "live", "execution_state": "descriptor_not_run", "provider_requirements": [{"provider": "sec", "availability_required": "available"}]})
    qa_path = tmp_path / descriptor["qa_case"]
    qa_path.write_text(json.dumps(qa_case("single-ticker-01", "single-ticker", network_mode="live")), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])
    metadata_only = {
        "case_id": "single-ticker-01",
        "execution_state": "executed",
        "network_policy": {"allow_network": True, "providers": ["sec"]},
        "providers": [{"provider": "sec", "availability": "available", "fetched_at": "2026-08-17T01:00:00Z", "raw_content_sha256": "a" * 64}],
    }

    with pytest.raises(EvaluationError, match="provider packet content"):
        evaluate(config_path, repo_root=ROOT, live_provider_packets={"single-ticker-01": metadata_only})


def test_live_provider_envelope_requires_the_private_raw_cache_bytes_for_its_source_digest(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="prospective", prospective=True)
    descriptor.update({"mode": "live", "execution_state": "descriptor_not_run", "provider_requirements": [{"provider": "sec", "availability_required": "available"}]})
    qa_path = tmp_path / descriptor["qa_case"]
    qa_path.write_text(json.dumps(qa_case("single-ticker-01", "single-ticker", network_mode="live")), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])
    raw_cache = tmp_path / "raw-cache"
    live_packet = live_provider_packet("single-ticker-01", raw_cache, {"filing": "actual provider envelope"})
    raw_hash = live_packet["provider_packets"][0]["envelope"]["source"]["content_sha256"]
    (raw_cache / "sha256" / raw_hash).write_bytes(b"tampered raw bytes")

    with pytest.raises(EvaluationError, match="raw-cache bytes"):
        evaluate(
            config_path,
            repo_root=ROOT,
            live_provider_packets={"single-ticker-01": live_packet},
            live_raw_cache_root=raw_cache,
        )


def test_transport_only_live_packet_stays_in_provider_execution_and_out_of_cleanroom_input(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1, track="prospective", prospective=True)
    descriptor.update({"mode": "live", "execution_state": "descriptor_not_run", "provider_requirements": [{"provider": "sec", "availability_required": "available"}]})
    qa_path = tmp_path / descriptor["qa_case"]
    qa_path.write_text(json.dumps(qa_case("single-ticker-01", "single-ticker", network_mode="live")), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])
    raw_cache = tmp_path / "raw-cache"
    live_packet = live_provider_packet("single-ticker-01", raw_cache, {"filing": "actual SEC provider response"})
    captured: list[dict] = []

    def injected_runner(request):
        captured.append(json.loads((request.package.case_dir / "frozen-packet.json").read_text(encoding="utf-8")))
        return review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(config_path, repo_root=ROOT, review_runner=injected_runner, live_provider_packets={"single-ticker-01": live_packet}, live_raw_cache_root=raw_cache)

    assert len(captured) == 2
    assert "live_provider_evidence" not in captured[0]
    assert "actual SEC provider response" not in json.dumps(captured[0])
    case = report["families"][0]["cases"][0]
    assert case["live_evidence"] == {"role": "transport_only", "semantic_invariant_bindings": []}
    assert case["source_packet"]["executed_live_packet_hash"] == canonical_hash(live_packet)


def test_candidate_artifact_is_grounded_and_enters_the_independent_reviewer_packet_without_private_expectations(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1)
    descriptor["expected_case_behavior"] = {"allowed_actions": ["MONITOR", "BLOCKED"]}
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])
    candidate_requests = []
    reviewer_packets: list[dict] = []

    def candidate_runner(request):
        candidate_requests.append(request)
        evidence_id = request.frozen_packet["evidence"][0]["evidence_id"]
        result = {
            "schema_id": "urn:serenity:schema:candidate-result:1",
            "result_id": "candidate-single-ticker-01",
            "case_id": request.case_id,
            "run_id": "candidate-run-01",
                "model": "gpt-5.6-terra",
                "capability": "shared-harness-instruction-integration",
                "harness_hashes": [{"path": "AGENTS.md", "sha256": "a" * 64}],
                "loaded_instruction_paths": ["CLAUDE.md", ".claude/skills/serenity-single-name/SKILL.md"],
                "packet_sha256": request.packet_sha256,
            "decision": {"stance": "insufficient_evidence", "statement": "The issuer identity and funding facts require monitoring.", "evidence_refs": [evidence_id]},
            "action": {"kind": "MONITOR", "statement": "MONITOR until a filing resolves the funding path.", "evidence_refs": [evidence_id]},
            "facts": [{"fact_id": "candidate-fact-01", "claim": "Fixture Inc. reports cash and ATM proceeds.", "evidence_refs": [evidence_id]}],
            "inferences": [{"inference_id": "candidate-inference-01", "claim": "Funding terms need monitoring before action.", "evidence_refs": [evidence_id]}],
            "trigger": {"statement": "A future filing can resolve the funding path.", "evidence_refs": [evidence_id]},
            "bear_case": {"statement": "The financing path could dilute holders.", "evidence_refs": [evidence_id]},
            "falsifiers": [{"statement": "A disclosed funding change can invalidate the monitoring thesis.", "evidence_refs": [evidence_id]}],
            "evidence_refs": [evidence_id],
            "user_artifact": {"locale": "ko", "markdown": "현재는 추가 공시를 확인할 때까지 모니터링합니다. NFA."},
        }
        result["canonical_sha256"] = canonical_hash(result)
        return result

    def reviewer(request):
        reviewer_packets.append(json.loads((request.package.case_dir / "frozen-packet.json").read_text(encoding="utf-8")))
        return review_result(request.case_id, request.reviewer, "pass", invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(config_path, repo_root=ROOT, candidate_runner=candidate_runner, review_runner=reviewer)

    assert len(candidate_requests) == 1
    assert "deterministic_assertions" not in candidate_requests[0].frozen_packet
    assert "expected_case_behavior" not in candidate_requests[0].frozen_packet
    assert all(packet["candidate_artifact"]["case_id"] == "single-ticker-01" for packet in reviewer_packets)
    assert all(packet["evidence"][0]["evidence_id"] == "fixture-evidence" for packet in reviewer_packets)
    assert all("expected_case_behavior" not in packet for packet in reviewer_packets)
    candidate = report["families"][0]["cases"][0]["candidate"]
    assert candidate["status"] == "executed"
    assert candidate["packet_sha256"] == candidate_requests[0].packet_sha256
    assert candidate["artifact_sha256"] == canonical_hash(candidate_runner(candidate_requests[0]))


def test_frozen_packet_cannot_carry_evaluator_only_expected_case_behavior(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="single-ticker", index=1)
    packet_path = tmp_path / descriptor["packet"]
    packet_value = json.loads(packet_path.read_text(encoding="utf-8"))
    packet_value["expected_case_behavior"] = {"allowed_actions": ["MONITOR", "BLOCKED"]}
    packet_path.write_text(json.dumps(packet_value), encoding="utf-8")
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    with pytest.raises(EvaluationError, match="evaluator-only expected case behavior"):
        evaluate(config_path, repo_root=ROOT)


def test_report_can_be_atomically_persisted_with_its_canonical_hash(tmp_path: Path) -> None:
    descriptor = write_case(tmp_path, family="near-miss", index=1)
    config_path = write_config(tmp_path, [{"family": "near-miss", "cases": [descriptor]}])
    out = tmp_path / "reports" / "evaluation.json"

    report = evaluate(config_path, repo_root=ROOT, out_path=out)

    persisted = json.loads(out.read_text(encoding="utf-8"))
    assert persisted == report
    assert len(report["content_hash"]) == 64
    assert report["content_hash"] != "0" * 64
    assert report["content_hash"] == canonical_hash({key: value for key, value in report.items() if key != "content_hash"})

    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "serenity_eval.py"), "--out", str(tmp_path / "cli-report.json")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0
    assert len(completed.stdout.splitlines()) == 1
    assert json.loads((tmp_path / "cli-report.json").read_text(encoding="utf-8"))["content_hash"] == json.loads(completed.stdout)["report"]["content_hash"]


def test_committed_family_invariants_are_specific_to_their_failure_semantics() -> None:
    expected = {
        "discovery": "US-listed resolution",
        "single-ticker": "conditional entry",
        "physical-ai": "recursive bottom hop",
        "near-miss": "no clean vehicle",
        "degraded-data": "BLOCKED",
        "displacement-fear": "mechanical claim",
    }
    for family, required_invariant in expected.items():
        cases = list((ROOT / "tests" / "260817" / "fixtures" / "eval" / family).glob("*.case.json"))
        invariant_sets = [set(json.loads(path.read_text(encoding="utf-8"))["expected_invariants"]) for path in cases]
        assert all(any(required_invariant in invariant for invariant in invariants) for invariants in invariant_sets)


def test_committed_single_ticker_conflict_cases_require_a_blocked_action_not_a_pinned_identity() -> None:
    fixture_root = ROOT / "tests" / "260817" / "fixtures" / "eval" / "single-ticker"
    expected = {"identity conflict blocks action", "conditional entry and bear case are separate"}
    for stem in ("det-01", "det-02", "live-01"):
        qa_case_value = json.loads((fixture_root / f"{stem}.case.json").read_text(encoding="utf-8"))
        packet_value = json.loads((fixture_root / f"{stem}.packet.json").read_text(encoding="utf-8"))
        assert set(qa_case_value["expected_invariants"]) == expected
        assert {item["invariant"] for item in packet_value["invariant_evidence"]} == expected
    bindings = (json.loads((fixture_root / "det-02.packet.json").read_text(encoding="utf-8"))["runtime_scenario"]["invariant_bindings"])
    assert {item["invariant"] for item in bindings} == expected


def test_committed_discovery_cases_require_an_explicit_unresolved_status_without_an_invented_identity_linkage() -> None:
    fixture_root = ROOT / "tests" / "260817" / "fixtures" / "eval" / "discovery"
    expected = {"US-listed resolution status is explicit without invented identity linkage", "candidate distinctions are evidence-backed"}
    for stem in ("det-01", "det-02", "live-01"):
        qa_case_value = json.loads((fixture_root / f"{stem}.case.json").read_text(encoding="utf-8"))
        packet_value = json.loads((fixture_root / f"{stem}.packet.json").read_text(encoding="utf-8"))
        assert set(qa_case_value["expected_invariants"]) == expected
        assert {item["invariant"] for item in packet_value["invariant_evidence"]} == expected
    bindings = json.loads((fixture_root / "det-02.packet.json").read_text(encoding="utf-8"))["runtime_scenario"]["invariant_bindings"]
    assert {item["invariant"] for item in bindings} == expected


def test_committed_near_miss_cases_forbid_unsupported_actions_without_forcing_a_single_honest_state() -> None:
    fixture_root = ROOT / "tests" / "260817" / "fixtures" / "eval" / "near-miss"
    expected = {"no clean vehicle is preserved", "no unsupported US-listed action is taken"}
    for stem in ("det-01", "det-02", "live-01"):
        qa_case_value = json.loads((fixture_root / f"{stem}.case.json").read_text(encoding="utf-8"))
        packet_value = json.loads((fixture_root / f"{stem}.packet.json").read_text(encoding="utf-8"))
        assert set(qa_case_value["expected_invariants"]) == expected
        assert {item["invariant"] for item in packet_value["invariant_evidence"]} == expected
    bindings = json.loads((fixture_root / "det-02.packet.json").read_text(encoding="utf-8"))["runtime_scenario"]["invariant_bindings"]
    assert {item["invariant"] for item in bindings} == expected


@pytest.mark.parametrize(
    ("action_kind", "expected_outcome"),
    (("PASS", "pass"), ("MONITOR", "pass"), ("BLOCKED", "pass"), ("RECOMMEND_NOW", "fail"), ("ENTER_ON_TRIGGER", "fail")),
)
def test_near_miss_qa_allows_honest_no_vehicle_actions_and_rejects_unsupported_us_listed_actions(tmp_path: Path, action_kind: str, expected_outcome: str) -> None:
    fixture_root = ROOT / "tests" / "260817" / "fixtures" / "eval" / "near-miss"
    qa_path = tmp_path / "near-miss.case.json"
    packet_path = tmp_path / "near-miss.packet.json"
    qa_path.write_text((fixture_root / "det-02.case.json").read_text(encoding="utf-8"), encoding="utf-8")
    packet_path.write_text((fixture_root / "det-02.packet.json").read_text(encoding="utf-8"), encoding="utf-8")
    descriptor = {"case_id": "near-miss-det-02", "track": "cutoff-frozen", "mode": "deterministic", "qa_case": qa_path.name, "packet": packet_path.name}
    config_path = write_config(tmp_path, [{"family": "near-miss", "cases": [descriptor]}])

    def candidate(request):
        result = candidate_result(request)
        result["action"] = {
            "kind": action_kind,
            "statement": "The record supports no US-listed action." if action_kind in {"PASS", "MONITOR", "BLOCKED"} else "Take a US-listed action despite the missing vehicle evidence.",
            "evidence_refs": list(result["evidence_refs"]),
        }
        result["user_artifact"] = {"locale": "ko", "markdown": "미국 상장 표현을 확인할 수 없어 행동을 보류합니다." if action_kind in {"PASS", "MONITOR", "BLOCKED"} else "지금 행동합니다. NFA."}
        result["canonical_sha256"] = canonical_hash({key: value for key, value in result.items() if key != "canonical_sha256"})
        return result

    def qa_reviewer(request):
        assert "no unsupported US-listed action is taken" in request.expected_invariants
        candidate_artifact = json.loads((request.package.case_dir / "frozen-packet.json").read_text(encoding="utf-8"))["candidate_artifact"]
        outcome = "pass" if candidate_artifact["action"]["kind"] in {"PASS", "MONITOR", "BLOCKED"} else "fail"
        return review_result(request.case_id, request.reviewer, outcome, invariants=request.expected_invariants, invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(config_path, repo_root=ROOT, candidate_runner=candidate, review_runner=qa_reviewer)
    assert report["families"][0]["cases"][0]["outcome"] == expected_outcome


@pytest.mark.parametrize(("action_kind", "expected_outcome"), (("BLOCKED", "pass"), ("RECOMMEND_NOW", "fail")))
def test_single_ticker_conflict_qa_scores_a_blocked_candidate_not_a_recommendation(tmp_path: Path, action_kind: str, expected_outcome: str) -> None:
    fixture_root = ROOT / "tests" / "260817" / "fixtures" / "eval" / "single-ticker"
    qa_path = tmp_path / "single-ticker-conflict.case.json"
    packet_path = tmp_path / "single-ticker-conflict.packet.json"
    qa_path.write_text((fixture_root / "det-01.case.json").read_text(encoding="utf-8"), encoding="utf-8")
    packet_path.write_text((fixture_root / "det-01.packet.json").read_text(encoding="utf-8"), encoding="utf-8")
    descriptor = {"case_id": "single-ticker-det-01", "track": "retrospective", "mode": "deterministic", "qa_case": qa_path.name, "packet": packet_path.name}
    config_path = write_config(tmp_path, [{"family": "single-ticker", "cases": [descriptor]}])

    def conflict_candidate(request):
        result = candidate_result(request)
        result["action"] = {
            "kind": action_kind,
            "statement": "The issuer identity conflict requires no final trade action." if action_kind == "BLOCKED" else "Recommend an immediate position despite the conflicting identifiers.",
            "evidence_refs": list(result["evidence_refs"]),
        }
        result["user_artifact"] = {"locale": "ko", "markdown": "식별자 충돌이 있어 결론을 보류합니다." if action_kind == "BLOCKED" else "지금 매수합니다. NFA."}
        result["canonical_sha256"] = canonical_hash({key: value for key, value in result.items() if key != "canonical_sha256"})
        return result

    def qa_reviewer(request):
        candidate = json.loads((request.package.case_dir / "frozen-packet.json").read_text(encoding="utf-8"))["candidate_artifact"]
        outcome = "pass" if candidate["action"]["kind"] == "BLOCKED" else "fail"
        return review_result(request.case_id, request.reviewer, outcome, invariants=request.expected_invariants, invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(config_path, repo_root=ROOT, candidate_runner=conflict_candidate, review_runner=qa_reviewer)
    case = report["families"][0]["cases"][0]
    assert case["candidate"]["action"] == action_kind
    assert case["outcome"] == expected_outcome


@pytest.mark.parametrize(
    ("action_kind", "invented_linkage", "expected_outcome"),
    (
        ("PASS", False, "pass"),
        ("MONITOR", False, "pass"),
        ("BLOCKED", False, "pass"),
        ("MONITOR", True, "fail"),
        ("RECOMMEND_NOW", False, "fail"),
        ("ENTER_ON_TRIGGER", False, "fail"),
    ),
)
def test_discovery_qa_requires_an_explicit_unresolved_status_without_an_invented_identity_linkage(
    tmp_path: Path, action_kind: str, invented_linkage: bool, expected_outcome: str
) -> None:
    fixture_root = ROOT / "tests" / "260817" / "fixtures" / "eval" / "discovery"
    qa_path = tmp_path / "discovery.case.json"
    packet_path = tmp_path / "discovery.packet.json"
    qa_path.write_text((fixture_root / "det-01.case.json").read_text(encoding="utf-8"), encoding="utf-8")
    packet_path.write_text((fixture_root / "det-01.packet.json").read_text(encoding="utf-8"), encoding="utf-8")
    descriptor = {"case_id": "discovery-det-01", "track": "retrospective", "mode": "deterministic", "qa_case": qa_path.name, "packet": packet_path.name}
    config_path = write_config(tmp_path, [{"family": "discovery", "cases": [descriptor]}])

    def discovery_candidate(request):
        result = candidate_result(request)
        result["action"] = {
            "kind": action_kind,
            "statement": "Keep the vehicle status unresolved." if action_kind in {"PASS", "MONITOR", "BLOCKED"} else "Take the US-listed action now.",
            "evidence_refs": list(result["evidence_refs"]),
        }
        result["decision"]["statement"] = (
            "MORIY is a direct revenue-linked security expression for Mori Precision." if invented_linkage else "The supplied observations do not establish a security identity linkage from MORIY to Mori Precision."
        )
        result["user_artifact"] = {"locale": "ko", "markdown": "연결 근거가 없어 상태를 보류합니다." if action_kind in {"PASS", "MONITOR", "BLOCKED"} else "지금 행동합니다. NFA."}
        result["canonical_sha256"] = canonical_hash({key: value for key, value in result.items() if key != "canonical_sha256"})
        return result

    def qa_reviewer(request):
        assert "US-listed resolution status is explicit without invented identity linkage" in request.expected_invariants
        reviewer_packet = json.loads((request.package.case_dir / "frozen-packet.json").read_text(encoding="utf-8"))
        observations = reviewer_packet["evidence"][0]["artifact"]["value"]["observations"]
        assert not any(item.get("subject") == "MORIY" and item.get("predicate") in {"maps_to_cik", "revenue_linked_to"} for item in observations)
        candidate = reviewer_packet["candidate_artifact"]
        invented = "direct revenue-linked" in candidate["decision"]["statement"]
        allowed_unresolved_action = candidate["action"]["kind"] in {"PASS", "MONITOR", "BLOCKED"}
        outcome = "pass" if allowed_unresolved_action and not invented else "fail"
        return review_result(request.case_id, request.reviewer, outcome, invariants=request.expected_invariants, invariant_evidence=dict(request.invariant_evidence))

    report = evaluate(config_path, repo_root=ROOT, candidate_runner=discovery_candidate, review_runner=qa_reviewer)
    assert report["families"][0]["cases"][0]["outcome"] == expected_outcome


def test_committed_representative_packets_use_substantive_artifacts_and_family_runtime_services() -> None:
    expected_services = {
        "discovery": "serenity_core.snapshot.build_security_snapshot",
        "single-ticker": "serenity_core.snapshot.validate_security_snapshot",
        "physical-ai": "serenity_core.sector_graph.validate_sector_graph",
        "near-miss": "serenity_core.lens.run_lens",
        "degraded-data": "serenity_core.snapshot.validate_security_snapshot",
        "displacement-fear": "serenity_core.lens.run_lens",
    }
    for family, service in expected_services.items():
        packet_path = ROOT / "tests" / "260817" / "fixtures" / "eval" / family / "det-02.packet.json"
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        assert "deterministic_assertions" not in packet
        assert "facts" not in packet
        refs = {entry["evidence_id"] for entry in packet["evidence"]}
        assert refs
        assert all(entry["artifact"]["schema_id"] == "urn:serenity:schema:evidence-result:1" for entry in packet["evidence"])
        for entry in packet["evidence"]:
            value = entry["artifact"]["value"]
            assert "statement" not in value
            assert value["observations"]
            assert all(
                isinstance(observation["subject"], str)
                and isinstance(observation["predicate"], str)
                and any(key in observation for key in ("object", "value", "measure", "related_entity"))
                for observation in value["observations"]
            )
        assert all(set(binding["evidence_refs"]).issubset(refs) for binding in packet["invariant_evidence"])
        assert packet["runtime_scenario"]["actions"][0]["service"] == service
