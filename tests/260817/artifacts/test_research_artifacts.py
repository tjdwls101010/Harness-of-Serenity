from __future__ import annotations

import hashlib
import json
import multiprocessing
from pathlib import Path

import pytest

from serenity_v2.research import (
    ResearchArtifactConflictError,
    ResearchArtifactValidationError,
    ResearchArtifactStore,
    load_evidence_catalog,
)
from serenity_v2.runtime import RunStore, SerenityError
from serenity_v2.schema import validate_document


def create_run_dir(tmp_path: Path) -> Path:
    manifest = RunStore(tmp_path).start(
        mode="single-name",
        question="What evidence would change this thesis?",
        subjects=["NVDA"],
        as_of="2026-08-17",
    )
    run_dir = tmp_path / ".serenity" / "runs" / manifest["run_id"]
    assert (run_dir / "run-manifest.json").is_file()
    assert not (run_dir / "run.json").exists()
    return run_dir


def competing_hypotheses() -> list[dict[str, object]]:
    return [
        {
            "hypothesis_id": "hyp-demand-constrained",
            "statement": "Demand is constrained by a scarce input.",
            "predictions": ["Lead times remain elevated while orders grow."],
            "falsifier": "Supplier capacity rises before demand reaches the constraint.",
            "status": "open",
            "supporting_fact_refs": ["fact:orders"],
            "contradicting_fact_refs": [],
            "requested_evidence_ids": [],
        },
        {
            "hypothesis_id": "hyp-demand-normalizes",
            "statement": "Demand normalizes before the scarce input matters.",
            "predictions": ["Customer inventories normalize before lead times widen."],
            "falsifier": "Orders continue rising after customer inventory normalizes.",
            "status": "open",
            "supporting_fact_refs": [],
            "contradicting_fact_refs": ["fact:orders"],
            "requested_evidence_ids": [],
        },
    ]


def request_details() -> dict[str, object]:
    return {
        "question": "Which recent filing names the constrained input?",
        "evidence_type": "filing-narrative",
        "provider_policy": {"providers": ["sec"], "allow_network": True},
        "acceptance_criteria": ["Name the input and the filing accession."],
        "requested_at": "2026-08-17T00:00:00Z",
        "provider_parameters": {"cik": "0000320193"},
    }


def available_result() -> dict[str, object]:
    return {
        "availability": "available",
        "provider": "sec",
        "source": {
            "uri": "https://www.sec.gov/Archives/edgar/data/320193/example.txt",
            "parameters": {"cik": "0000320193"},
            "canonical_id": "sec:0000320193:example",
        },
        "temporal": {
            "effective_at": "2026-07-31",
            "period_start": "2026-04-01",
            "period_end": "2026-06-30",
            "observed_at": "2026-07-31",
            "available_at": "2026-08-01T00:00:00Z",
            "source_version": "2026-Q2",
        },
        "fetched_at": "2026-08-17T00:00:00Z",
        "raw_content_sha256": "a" * 64,
        "transform_version": "filing-extract/1",
        "identity_bindings": {"cik": "0000320193", "ticker": "AAPL"},
        "fact_refs": ["fact:10-k"],
        "value": {"named_input": "example input"},
    }


def changed_hypotheses(index: int) -> list[dict[str, object]]:
    hypotheses = competing_hypotheses()
    hypotheses[index]["status"] = "supported"
    hypotheses[index]["supporting_fact_refs"] = ["fact:orders", f"fact:concurrent-{index}"]
    return hypotheses


def commit_prepared_ledger(store: RunStore, run_id: str, prior: dict[str, object] | None, prepared: object) -> dict[str, object]:
    return store.publish_or_refresh_artifact(
        run_id,
        name="hypothesis-ledger",
        expected_attachment=prior,
        path=prepared.ledger_path,
        content=prepared.ledger_content,
        schema_id="urn:serenity:schema:hypothesis-ledger:1",
        phase="hypotheses_updated",
    )


def publish_prepared_request(store: RunStore, run_id: str, prepared: object) -> dict[str, object]:
    assert prepared.request is not None
    assert prepared.request_path is not None
    assert prepared.request_content is not None
    return store.publish_artifact(
        run_id,
        name=prepared.request["request_id"],
        path=prepared.request_path,
        content=prepared.request_content,
        schema_id=prepared.request["schema_id"],
        phase="evidence_requested",
    )


def initialize_attached_ledger(tmp_path: Path) -> tuple[RunStore, ResearchArtifactStore, dict[str, object]]:
    runtime = RunStore(tmp_path)
    run_dir = create_run_dir(tmp_path)
    artifacts = ResearchArtifactStore(run_dir)
    prepared = artifacts.prepare_hypotheses(competing_hypotheses())
    commit_prepared_ledger(runtime, run_dir.name, None, prepared)
    return runtime, artifacts, prepared.ledger


def _concurrent_hypothesis_prepare_and_publish(root: str, run_id: str, index: int, barrier, results) -> None:
    prepared = None
    try:
        store = RunStore(Path(root))
        run_dir = Path(root) / ".serenity" / "runs" / run_id
        artifacts = ResearchArtifactStore(run_dir)
        prior = store.read(run_id)["artifacts"]["hypothesis-ledger"]
        prepared = artifacts.prepare_hypotheses(changed_hypotheses(index), expected_revision=1)
        barrier.wait(timeout=10)
        run = commit_prepared_ledger(store, run_id, prior, prepared)
        results.put({"ok": True, "ledger": prepared.ledger, "path": str(prepared.ledger_path), "run": run})
    except (ResearchArtifactConflictError, SerenityError) as exc:
        payload = exc.payload if isinstance(exc, SerenityError) else {"ok": False, "error": {"code": "persistence_conflict", "message": str(exc)}}
        if prepared is not None:
            payload["candidate_path"] = str(prepared.ledger_path)
        results.put(payload)


def _concurrent_request_prepare_and_publish(root: str, run_id: str, hypothesis_id: str, barrier, results) -> None:
    prepared = None
    try:
        store = RunStore(Path(root))
        run_dir = Path(root) / ".serenity" / "runs" / run_id
        artifacts = ResearchArtifactStore(run_dir)
        prior = store.read(run_id)["artifacts"]["hypothesis-ledger"]
        prepared = artifacts.prepare_evidence_request(
            hypothesis_ids=[hypothesis_id], capability_id="sec.submissions", request=request_details()
        )
        barrier.wait(timeout=10)
        run = commit_prepared_ledger(store, run_id, prior, prepared)
        run = publish_prepared_request(store, run_id, prepared)
        results.put({"ok": True, "ledger": prepared.ledger, "request": prepared.request, "path": str(prepared.ledger_path), "run": run})
    except (ResearchArtifactConflictError, SerenityError) as exc:
        payload = exc.payload if isinstance(exc, SerenityError) else {"ok": False, "error": {"code": "persistence_conflict", "message": str(exc)}}
        if prepared is not None:
            payload["candidate_path"] = str(prepared.ledger_path)
        results.put(payload)


def test_catalog_and_every_created_artifact_validate_against_canonical_schemas(tmp_path: Path) -> None:
    catalog = load_evidence_catalog()
    validate_document(catalog, "urn:serenity:schema:evidence-catalog:1")
    providers = {provider["provider_id"]: provider for provider in catalog["providers"]}
    assert catalog["catalog_id"].startswith("evidence-catalog-")
    assert providers["ibd-rs-rating"]["version"] == "0.3.0"
    assert providers["sec"]["tier"] == "baseline"
    assert "sec.submissions" in providers["sec"]["capabilities"]
    assert providers["usaspending"]["tier"] == "adaptive"
    assert providers["sam"]["tier"] == "optional"

    runtime, store, created = initialize_attached_ledger(tmp_path)
    validate_document(created, "urn:serenity:schema:hypothesis-ledger:1")

    prepared_request = store.prepare_evidence_request(
        hypothesis_ids=[created["hypotheses"][0]["hypothesis_id"]],
        capability_id="sec.submissions",
        request=request_details(),
    )
    request = prepared_request.request
    validate_document(request, "urn:serenity:schema:evidence-request:1")
    commit_prepared_ledger(runtime, store.run_id, runtime.read(store.run_id)["artifacts"]["hypothesis-ledger"], prepared_request)
    publish_prepared_request(runtime, store.run_id, prepared_request)

    result = store.record_evidence_result(request_id=request["request_id"], evidence=available_result())
    validate_document(result, "urn:serenity:schema:evidence-result:1")


def test_hypothesis_ledger_preserves_competing_hypotheses_and_update_history(tmp_path: Path) -> None:
    runtime, store, created = initialize_attached_ledger(tmp_path)
    updated_hypotheses = competing_hypotheses()
    updated_hypotheses[0]["status"] = "supported"
    updated_hypotheses[0]["supporting_fact_refs"] = ["fact:orders", "fact:capacity"]
    prepared = store.prepare_hypotheses(updated_hypotheses, expected_revision=created["revision"])
    commit_prepared_ledger(runtime, store.run_id, runtime.read(store.run_id)["artifacts"]["hypothesis-ledger"], prepared)
    updated = prepared.ledger

    assert created["run_id"] == store.run_id
    assert updated["revision"] == 2
    assert updated["hypotheses"][0]["status"] == "supported"
    assert updated["created_at"] == created["created_at"]
    assert updated["history"] == [
        {"content_hash": created["content_hash"], "revision": 1, "updated_at": created["updated_at"]}
    ]
    validate_document(updated, "urn:serenity:schema:hypothesis-ledger:1")


def test_hypothesis_update_rejects_a_stale_revision(tmp_path: Path) -> None:
    runtime, store, created = initialize_attached_ledger(tmp_path)
    revised_hypotheses = competing_hypotheses()
    revised_hypotheses[0]["status"] = "supported"
    prepared = store.prepare_hypotheses(revised_hypotheses, expected_revision=created["revision"])
    commit_prepared_ledger(runtime, store.run_id, runtime.read(store.run_id)["artifacts"]["hypothesis-ledger"], prepared)

    with pytest.raises(ResearchArtifactConflictError, match="revision conflict"):
        store.prepare_hypotheses(competing_hypotheses(), expected_revision=created["revision"])


def test_evidence_request_links_hypothesis_and_requires_typed_request_fields(tmp_path: Path) -> None:
    runtime, store, ledger = initialize_attached_ledger(tmp_path)

    prepared = store.prepare_evidence_request(
        hypothesis_ids=[ledger["hypotheses"][0]["hypothesis_id"]],
        capability_id="sec.submissions",
        request=request_details(),
    )
    request = prepared.request
    commit_prepared_ledger(runtime, store.run_id, runtime.read(store.run_id)["artifacts"]["hypothesis-ledger"], prepared)
    publish_prepared_request(runtime, store.run_id, prepared)

    linked_ledger = store.read_current_hypothesis_ledger()
    assert linked_ledger["hypotheses"][0]["requested_evidence_ids"] == [request["request_id"]]
    assert request["content_hash"]
    with pytest.raises(ResearchArtifactValidationError, match="acceptance_criteria"):
        store.prepare_evidence_request(
            hypothesis_ids=[ledger["hypotheses"][0]["hypothesis_id"]],
            capability_id="sec.submissions",
            request={"question": "Incomplete request"},
        )


def test_evidence_result_rejects_request_and_run_mismatches(tmp_path: Path) -> None:
    runtime, store, ledger = initialize_attached_ledger(tmp_path)
    prepared = store.prepare_evidence_request(
        hypothesis_ids=[ledger["hypotheses"][0]["hypothesis_id"]],
        capability_id="alfred-fred.macro-series",
        request={
            **request_details(),
            "question": "What did the policy rate print?",
            "evidence_type": "macro-series",
            "provider_policy": {"providers": ["alfred-fred"]},
            "provider_parameters": {"series_id": "DFF"},
        },
    )
    request = prepared.request
    commit_prepared_ledger(runtime, store.run_id, runtime.read(store.run_id)["artifacts"]["hypothesis-ledger"], prepared)
    publish_prepared_request(runtime, store.run_id, prepared)

    with pytest.raises(ResearchArtifactValidationError, match="run_id does not match"):
        store.record_evidence_result(
            request_id=request["request_id"], evidence={**available_result(), "run_id": "run-other"}
        )
    with pytest.raises(ResearchArtifactValidationError, match="request_id does not match"):
        store.record_evidence_result(
            request_id=request["request_id"], evidence={**available_result(), "request_id": "evidence-request-other"}
        )


def test_provider_envelope_converts_to_a_schema_valid_result_without_losing_provenance(tmp_path: Path) -> None:
    runtime, store, ledger = initialize_attached_ledger(tmp_path)
    prepared = store.prepare_evidence_request(
        hypothesis_ids=[ledger["hypotheses"][0]["hypothesis_id"]],
        capability_id="sec.filings",
        request={**request_details(), "evidence_type": "filing-fact"},
    )
    request = prepared.request
    commit_prepared_ledger(runtime, store.run_id, runtime.read(store.run_id)["artifacts"]["hypothesis-ledger"], prepared)
    publish_prepared_request(runtime, store.run_id, prepared)
    envelope = {
        "schema_id": "urn:serenity:schema:provider-envelope:1",
        "provider": "sec",
        "provider_version": "submissions-api/1",
        "request_id": request["request_id"],
        "status": "available",
        "fetched_at": "2026-08-17T00:00:00Z",
        "source": {
            "uri": "https://www.sec.gov/Archives/edgar/data/320193/example.txt",
            "content_sha256": "b" * 64,
            "parameters": {"cik": "0000320193"},
        },
        "temporal": available_result()["temporal"],
        "data": {"fact": "example"},
        "identity_bindings": {"cik": "0000320193"},
        "parse": {"status": "parsed", "transform_version": "sec-envelope/1"},
    }
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")

    result = store.record_evidence_result(
        request_id=request["request_id"],
        evidence={"provider_envelope": envelope, "canonical_id": "sec:0000320193:example", "fact_refs": ["fact:10-q"]},
    )

    assert result["raw_content_sha256"] == envelope["source"]["content_sha256"]
    assert result["transform_version"] == envelope["parse"]["transform_version"]
    assert result["source"]["parameters"] == envelope["source"]["parameters"]
    validate_document(result, "urn:serenity:schema:evidence-result:1")


def test_unavailable_provider_envelope_preserves_the_raw_hash_but_nulls_the_value(tmp_path: Path) -> None:
    runtime, store, ledger = initialize_attached_ledger(tmp_path)
    prepared = store.prepare_evidence_request(
        hypothesis_ids=[ledger["hypotheses"][0]["hypothesis_id"]],
        capability_id="sec.filings",
        request=request_details(),
    )
    request = prepared.request
    commit_prepared_ledger(runtime, store.run_id, runtime.read(store.run_id)["artifacts"]["hypothesis-ledger"], prepared)
    publish_prepared_request(runtime, store.run_id, prepared)
    envelope = {
        "schema_id": "urn:serenity:schema:provider-envelope:1",
        "provider": "sec",
        "provider_version": "submissions-api/1",
        "request_id": request["request_id"],
        "status": "unavailable",
        "fetched_at": "2026-08-17T00:00:00Z",
        "source": {
            "uri": "https://www.sec.gov/Archives/edgar/data/320193/example.txt",
            "content_sha256": "c" * 64,
        },
        "temporal": available_result()["temporal"],
        "data": None,
        "parse": {"status": "not_parsed", "transform_version": "sec-envelope/1"},
    }
    validate_document(envelope, "urn:serenity:schema:provider-envelope:1")

    result = store.record_evidence_result(
        request_id=request["request_id"],
        evidence={"provider_envelope": envelope, "canonical_id": "sec:0000320193:example"},
    )

    assert result["availability"] == "unavailable"
    assert result["value"] is None
    assert result["raw_content_sha256"] == envelope["source"]["content_sha256"]
    validate_document(result, "urn:serenity:schema:evidence-result:1")


def test_evidence_request_rejects_a_capability_absent_from_the_catalog(tmp_path: Path) -> None:
    _, store, ledger = initialize_attached_ledger(tmp_path)

    with pytest.raises(ResearchArtifactValidationError, match="not declared by the evidence catalog"):
        store.prepare_evidence_request(
            hypothesis_ids=[ledger["hypotheses"][0]["hypothesis_id"]],
            capability_id="made-up.provider",
            request=request_details(),
        )


def test_retired_mutable_methods_name_the_prepare_seam_and_never_write(tmp_path: Path) -> None:
    run_dir = create_run_dir(tmp_path)
    artifacts = ResearchArtifactStore(run_dir)

    with pytest.raises(ResearchArtifactValidationError, match="prepare_hypotheses"):
        artifacts.put_hypotheses(competing_hypotheses())
    with pytest.raises(ResearchArtifactValidationError, match="prepare_evidence_request"):
        artifacts.create_evidence_request(
            hypothesis_ids=["hyp-demand-constrained"], capability_id="sec.submissions", request=request_details()
        )

    assert not (run_dir / "hypothesis-ledger.json").exists()
    assert not (run_dir / "evidence").exists()


def test_concurrent_hypothesis_preparations_allow_one_cas_winner_without_overwriting_current_ledger(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run_dir = create_run_dir(tmp_path)
    run_id = run_dir.name
    artifacts = ResearchArtifactStore(run_dir)
    initial = artifacts.prepare_hypotheses(competing_hypotheses())
    first_manifest = commit_prepared_ledger(store, run_id, None, initial)
    first_attachment = first_manifest["artifacts"]["hypothesis-ledger"]

    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()
    processes = [
        context.Process(target=_concurrent_hypothesis_prepare_and_publish, args=(str(tmp_path), run_id, index, barrier, results))
        for index in (0, 1)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
    assert all(process.exitcode == 0 for process in processes)

    payloads = [results.get(timeout=5) for _ in processes]
    successes = [payload for payload in payloads if payload["ok"] is True]
    failures = [payload for payload in payloads if payload["ok"] is False]
    assert len(successes) == 1
    assert [payload["error"]["code"] for payload in failures] == ["persistence_conflict"]
    assert not Path(failures[0]["candidate_path"]).exists()

    current = store.read(run_id)
    attachment = current["artifacts"]["hypothesis-ledger"]
    assert attachment != first_attachment
    current_path = tmp_path / attachment["path"]
    assert attachment["content_hash"] == hashlib.sha256(current_path.read_bytes()).hexdigest()
    assert json.loads(current_path.read_text(encoding="utf-8")) == successes[0]["ledger"]


def test_concurrent_evidence_requests_retry_against_the_latest_immutable_ledger(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run_dir = create_run_dir(tmp_path)
    run_id = run_dir.name
    artifacts = ResearchArtifactStore(run_dir)
    initial = artifacts.prepare_hypotheses(competing_hypotheses())
    commit_prepared_ledger(store, run_id, None, initial)

    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()
    hypothesis_ids = ["hyp-demand-constrained", "hyp-demand-normalizes"]
    processes = [
        context.Process(target=_concurrent_request_prepare_and_publish, args=(str(tmp_path), run_id, hypothesis_id, barrier, results))
        for hypothesis_id in hypothesis_ids
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=20)
    assert all(process.exitcode == 0 for process in processes)

    payloads = [results.get(timeout=5) for _ in processes]
    successes = [payload for payload in payloads if payload["ok"] is True]
    failures = [payload for payload in payloads if payload["ok"] is False]
    assert len(successes) == 1
    assert [payload["error"]["code"] for payload in failures] == ["persistence_conflict"]
    assert not Path(failures[0]["candidate_path"]).exists()

    winner = successes[0]
    losing_hypothesis = next(hypothesis_id for hypothesis_id in hypothesis_ids if hypothesis_id not in winner["request"]["hypothesis_ids"])
    prior = store.read(run_id)["artifacts"]["hypothesis-ledger"]
    retry = ResearchArtifactStore(run_dir).prepare_evidence_request(
        hypothesis_ids=[losing_hypothesis], capability_id="sec.submissions", request=request_details()
    )
    repaired = commit_prepared_ledger(store, run_id, prior, retry)
    repaired = publish_prepared_request(store, run_id, retry)

    final_path = tmp_path / repaired["artifacts"]["hypothesis-ledger"]["path"]
    final_ledger = json.loads(final_path.read_text(encoding="utf-8"))
    assert final_ledger["revision"] == 3
    requested_ids = {request_id for hypothesis in final_ledger["hypotheses"] for request_id in hypothesis["requested_evidence_ids"]}
    assert requested_ids == {winner["request"]["request_id"], retry.request["request_id"]}
    assert {winner["request"]["request_id"], retry.request["request_id"]} <= set(repaired["artifacts"])


def test_repeating_a_request_after_ledger_publication_crash_returns_the_current_ledger_without_a_second_mutation(tmp_path: Path) -> None:
    store = RunStore(tmp_path)
    run_dir = create_run_dir(tmp_path)
    run_id = run_dir.name
    artifacts = ResearchArtifactStore(run_dir)
    initial = artifacts.prepare_hypotheses(competing_hypotheses())
    commit_prepared_ledger(store, run_id, None, initial)

    first = artifacts.prepare_evidence_request(
        hypothesis_ids=["hyp-demand-constrained"], capability_id="sec.submissions", request=request_details()
    )
    published = commit_prepared_ledger(
        store, run_id, store.read(run_id)["artifacts"]["hypothesis-ledger"], first
    )
    assert not first.request_path.exists()

    retried = ResearchArtifactStore(run_dir).prepare_evidence_request(
        hypothesis_ids=["hyp-demand-constrained"], capability_id="sec.submissions", request=request_details()
    )
    assert retried.request == first.request
    assert retried.ledger == first.ledger
    assert retried.ledger_content == first.ledger_content
    assert retried.ledger["revision"] == 2
    idempotent = commit_prepared_ledger(
        store, run_id, published["artifacts"]["hypothesis-ledger"], retried
    )
    repaired = publish_prepared_request(store, run_id, retried)

    assert idempotent == published
    assert repaired["artifacts"][retried.request["request_id"]]["content_hash"] == hashlib.sha256(
        retried.request_path.read_bytes()
    ).hexdigest()
    current = ResearchArtifactStore(run_dir).read_current_hypothesis_ledger()
    assert current == first.ledger
