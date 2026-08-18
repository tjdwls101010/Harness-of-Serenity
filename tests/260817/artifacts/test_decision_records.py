from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from serenity_core.decision import finalize_decision, validate_decision
from serenity_core.runtime import SerenityError, canonical_hash
from serenity_core.schema import validate_document


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def document_with_hash(value: dict) -> dict:
    value["content_hash"] = canonical_hash({key: item for key, item in value.items() if key != "content_hash"})
    return value


def snapshot(run_id: str) -> dict:
    value = {
        "schema_id": "urn:serenity:schema:fact-snapshot:2",
        "run_id": run_id,
        "as_of": "2026-08-17",
        "identity": {"ticker": "NVDA", "name": "NVIDIA CORP", "exchange": "Nasdaq", "listing_type": "common"},
        "fetched_at": "2026-08-17T00:00:00Z",
        "facts": [
            {
                "fact_id": "fact-market-cap",
                "name": "market_cap",
                "availability": "available",
                "value": 4_000_000_000_000,
                "unit": "USD",
                "provider": "yfinance",
                "request_id": "request-market-cap",
                "effective_at": "2026-08-17",
                "observed_at": "2026-08-17",
                "available_at": "2026-08-17T00:00:00Z",
                "fetched_at": "2026-08-17T00:00:00Z",
                "source_version": "fixture-v1",
                "source_uri": "https://fixture.example/market-cap",
                "raw_content_sha256": "a" * 64,
                "identity_bindings": {"ticker": "NVDA"},
            },
            {
                "fact_id": "fact-forward-revenue",
                "name": "forward_revenue",
                "availability": "available",
                "value": 250_000_000_000,
                "unit": "USD",
                "provider": "yfinance",
                "request_id": "request-forward-revenue",
                "effective_at": "2026-08-17",
                "observed_at": "2026-08-17",
                "available_at": "2026-08-17T00:00:00Z",
                "fetched_at": "2026-08-17T00:00:00Z",
                "source_version": "fixture-v1",
                "source_uri": "https://fixture.example/forward-revenue",
                "raw_content_sha256": "b" * 64,
                "identity_bindings": {"ticker": "NVDA"},
            },
        ],
    }
    value["snapshot_id"] = f"snapshot-{canonical_hash(value)[:20]}"
    return document_with_hash(value)


def attached_artifact(manifest: dict, root: Path, run_dir: Path, *, name: str, filename: str, schema_id: str, value: dict) -> None:
    path = run_dir / filename
    write_json(path, value)
    manifest["artifacts"][name] = {
        "path": str(path.relative_to(root)),
        "content_hash": hashlib.sha256(path.read_bytes()).hexdigest(),
        "schema_id": schema_id,
    }


def open_run(
    tmp_path: Path,
    *,
    identity_status: str = "available",
    evidence_availability: str = "available",
) -> tuple[dict, Path]:
    run_id = "run-abc12345"
    run_dir = tmp_path / ".serenity" / "runs" / run_id
    manifest = {
        "schema_id": "urn:serenity:schema:run-manifest:2",
        "run_id": run_id,
        "status": "OPEN",
        "mode": "single-name",
        "subjects": ["NVDA"],
        "as_of": "2026-08-17",
        "question": "Could an unresolved filing fact change the timing?",
        "started_at": "2026-08-17T00:00:00Z",
        "updated_at": "2026-08-17T00:00:00Z",
        "actor": {"kind": "system", "id": "fixture"},
        "source_policy": {"policy_id": "fixture", "allow_network": False},
        "current_phase": "evidence_ready",
        "events": [{"at": "2026-08-17T00:00:00Z", "type": "run_started"}],
        "artifacts": {},
    }
    ledger = document_with_hash(
        {
            "schema_id": "urn:serenity:schema:hypothesis-ledger:1",
            "ledger_id": "ledger-abc12345",
            "run_id": run_id,
            "revision": 1,
            "created_at": "2026-08-17T00:00:00Z",
            "updated_at": "2026-08-17T00:00:00Z",
            "hypotheses": [
                {"hypothesis_id": "hyp-abc12345", "statement": "Demand stays durable.", "predictions": ["Revenue grows."], "falsifier": "Revenue falls.", "status": "open", "supporting_fact_refs": [], "contradicting_fact_refs": [], "requested_evidence_ids": []},
                {"hypothesis_id": "hyp-bear12345", "statement": "Demand digests.", "predictions": ["Revenue slows."], "falsifier": "Revenue grows.", "status": "open", "supporting_fact_refs": [], "contradicting_fact_refs": [], "requested_evidence_ids": []},
            ],
            "history": [],
        }
    )
    attached_artifact(manifest, tmp_path, run_dir, name="hypothesis-ledger", filename="hypothesis-ledger.json", schema_id="urn:serenity:schema:hypothesis-ledger:1", value=ledger)
    evidence = document_with_hash(
        {
            "schema_id": "urn:serenity:schema:evidence-result:1",
            "result_id": "result-abc12345",
            "run_id": run_id,
            "request_id": "request-evidence123",
            "hypothesis_ids": ["hyp-abc12345"],
            "capability_id": "fixture-evidence",
            "availability": evidence_availability,
            "provider": "fixture",
            "source": {"uri": "https://evidence.example/result-abc12345", "parameters": {}, "canonical_id": "fixture-result-abc12345"},
            "temporal": {"effective_at": "2026-08-17", "period_start": None, "period_end": None, "observed_at": "2026-08-17", "available_at": "2026-08-17T00:00:00Z", "source_version": "fixture-v1"},
            "fetched_at": "2026-08-17T00:00:00Z",
            "raw_content_sha256": "c" * 64 if evidence_availability == "available" else None,
            "transform_version": "fixture-v1",
            "identity_bindings": {"ticker": "NVDA"},
            "fact_refs": [],
            "value": {"revision": 0} if evidence_availability == "available" else None,
        }
    )
    attached_artifact(manifest, tmp_path, run_dir, name="evidence-result", filename="evidence-result-abc12345.json", schema_id="urn:serenity:schema:evidence-result:1", value=evidence)
    attached_artifact(manifest, tmp_path, run_dir, name="fact-snapshot", filename="fact-snapshot.json", schema_id="urn:serenity:schema:fact-snapshot:2", value=snapshot(run_id))
    lens = {
        "schema_id": "urn:serenity:schema:lens-result:1",
        "lens_result_id": "lens-result-abc12345",
        "lens_id": "lens-fixture123",
        "run_id": run_id,
        "validity": "valid",
        "input_facts": [
            {"fact_ref": "fact-market-cap", "availability": "available", "value": 4_000_000_000_000, "unit": "USD"},
            {"fact_ref": "fact-forward-revenue", "availability": "available", "value": 250_000_000_000, "unit": "USD"},
        ],
        "fact_refs": ["fact-market-cap", "fact-forward-revenue"],
        "output": {"value": 16},
        "output_unit": "multiple",
        "reproducibility_hash": "d" * 64,
        "executed_at": "2026-08-17T00:00:00Z",
    }
    attached_artifact(manifest, tmp_path, run_dir, name="lens-result", filename="lens-result.json", schema_id="urn:serenity:schema:lens-result:1", value=lens)
    if identity_status != "available":
        attached_artifact(
            manifest,
            tmp_path,
            run_dir,
            name="identity-resolution",
            filename="identity-resolution.json",
            schema_id="urn:serenity:identity-resolution:1",
            value=document_with_hash({"schema_id": "urn:serenity:identity-resolution:1", "run_id": run_id, "status": identity_status}),
        )
    manifest["content_hash"] = canonical_hash(manifest)
    write_json(run_dir / "run-manifest.json", manifest)
    return manifest, run_dir


def decision(*, version: int = 1, action: str = "ENTER_ON_TRIGGER", numeric_target: bool = False) -> dict:
    value = {
        "schema_id": "urn:serenity:schema:research-decision:1",
        "decision_id": f"decision-abc1234{version}",
        "run_id": "run-abc12345",
        "lineage_id": "lineage-nvda",
        "version": version,
        "as_of": "2026-08-17",
        "created_at": "2026-08-17T00:00:00Z",
        "scope": {"kind": "single-name", "subjects": ["NVDA"]},
        "action": action,
        "thesis": "Demand remains durable, but entry needs revision stabilization.",
        "materiality": "material",
        "priced_in": {"included": ["current AI demand"], "not_included": ["networking mix"]},
        "strongest_bear_case": "Customer digestion could create a revenue air pocket.",
        "falsifiers": ["Two quarters of estimate cuts."],
        "hypothesis_ids": ["hyp-abc12345"],
        "evidence_result_ids": ["result-abc12345"],
        "lens_results": [
            {
                "lens_result_id": "lens-result-abc12345",
                "validity": "valid",
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
        "uncertainty": "Forward revisions may not capture a delayed customer digestion cycle.",
        "required_evidence": [
            {
                "evidence_result_id": "result-abc12345",
                "purpose": "Verify the observable forward-revision trigger.",
                "action_critical": True,
            }
        ],
    }
    if version > 1:
        value["supersedes"] = "decision-abc12341"
        value["changed_because"] = "A new evidence result changed the timing condition."
    if numeric_target:
        value["numeric_target"] = {
            "value": 210.0,
            "currency": "USD",
            "timeframe": "12m",
            "lens_result_id": "lens-result-abc12345",
            "lens_validity": "valid",
            "fact_refs": ["fact-market-cap", "fact-forward-revenue"],
        }
    return value


def evidence_manifest() -> dict:
    return {"evidence_result_ids": ["result-abc12345"], "generated_at": "2026-08-17T00:00:00Z"}


def validate(tmp_path: Path, value: dict, *, manifest: dict | None = None, run_dir: Path | None = None) -> dict:
    if manifest is None or run_dir is None:
        manifest, run_dir = open_run(tmp_path)
    return validate_decision(
        project_root=tmp_path,
        run_manifest=manifest,
        run_dir=run_dir,
        decision_draft=value,
        evidence_manifest=evidence_manifest(),
    )


def test_finalize_writes_an_immutable_first_decision_version(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path)

    result = finalize_decision(
        project_root=tmp_path,
        run_manifest=manifest,
        run_dir=run_dir,
        decision_draft=decision(),
        analysis_markdown="# NVDA\n\nConditional entry only.",
        evidence_manifest=evidence_manifest(),
    )

    version_dir = tmp_path / "records" / "decisions" / "lineage-nvda" / "v001"
    stored = json.loads((version_dir / "decision.json").read_text(encoding="utf-8"))
    pointer = json.loads((version_dir.parent / "current.json").read_text(encoding="utf-8"))
    assert result["record_dir"] == str(version_dir)
    assert result["run_update"] == {"status": "FINALIZED", "current_phase": "decision_finalized"}
    assert stored["content_hash"]
    assert stored["content_hash"] == canonical_hash({key: value for key, value in stored.items() if key != "content_hash"})
    assert stored["finalized_at"].endswith("Z")
    validate_document(stored)
    assert (version_dir / "analysis.md").read_text(encoding="utf-8") == "# NVDA\n\nConditional entry only."
    assert pointer["version"] == 1
    assert pointer["decision_id"] == "decision-abc12341"


def test_second_version_requires_lineage_and_moves_only_the_current_pointer(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path)
    first = finalize_decision(
        project_root=tmp_path,
        run_manifest=manifest,
        run_dir=run_dir,
        decision_draft=decision(),
        analysis_markdown="first",
        evidence_manifest=evidence_manifest(),
    )
    second = finalize_decision(
        project_root=tmp_path,
        run_manifest=manifest,
        run_dir=run_dir,
        decision_draft=decision(version=2),
        analysis_markdown="second",
        evidence_manifest=evidence_manifest(),
    )

    lineage_dir = tmp_path / "records" / "decisions" / "lineage-nvda"
    assert (lineage_dir / "v001" / "analysis.md").read_text(encoding="utf-8") == "first"
    assert (lineage_dir / "v002" / "analysis.md").read_text(encoding="utf-8") == "second"
    assert first["record_dir"].endswith("/v001")
    assert second["record_dir"].endswith("/v002")
    assert json.loads((lineage_dir / "current.json").read_text(encoding="utf-8"))["version"] == 2


def test_numeric_target_must_resolve_a_valid_lens_and_all_fact_references(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path)
    invalid = decision(numeric_target=True)
    invalid["numeric_target"]["fact_refs"] = ["fact-market-cap"]

    with pytest.raises(SerenityError) as failure:
        validate_decision(
            project_root=tmp_path,
            run_manifest=manifest,
            run_dir=run_dir,
            decision_draft=invalid,
            evidence_manifest=evidence_manifest(),
        )

    assert failure.value.exit_code == 2
    assert failure.value.payload["error"]["code"] == "usage_or_schema"


def test_uncertainty_and_structured_required_evidence_are_mandatory(tmp_path: Path) -> None:
    missing_uncertainty = decision()
    del missing_uncertainty["uncertainty"]

    with pytest.raises(SerenityError, match="schema validation"):
        validate(tmp_path, missing_uncertainty)

    missing_criticality = decision()
    del missing_criticality["required_evidence"][0]["action_critical"]

    with pytest.raises(SerenityError, match="schema validation"):
        validate(tmp_path, missing_criticality)


def test_unusable_action_critical_evidence_requires_blocked_action(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path, evidence_availability="unavailable")

    with pytest.raises(SerenityError, match="action-critical evidence") as failure:
        validate(tmp_path, decision(action="MONITOR"), manifest=manifest, run_dir=run_dir)

    assert failure.value.exit_code == 2
    assert validate(tmp_path, decision(action="BLOCKED"), manifest=manifest, run_dir=run_dir)["valid"] is True


def test_not_disclosed_evidence_blocks_only_when_declared_action_critical(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path, evidence_availability="not_disclosed")
    noncritical = decision(action="MONITOR")
    noncritical["required_evidence"][0]["action_critical"] = False

    assert validate(tmp_path, noncritical, manifest=manifest, run_dir=run_dir)["valid"] is True

    with pytest.raises(SerenityError, match="action-critical evidence"):
        validate(tmp_path, decision(action="MONITOR"), manifest=manifest, run_dir=run_dir)


def test_enter_on_trigger_requires_one_structured_primary_observable(tmp_path: Path) -> None:
    vague = decision()
    vague["conditions"] = [{"condition": "Wait for confirmation", "status": "unmet"}]

    with pytest.raises(SerenityError, match="schema validation"):
        validate(tmp_path, vague)

    multiple_primary = decision()
    multiple_primary["conditions"].append({**multiple_primary["conditions"][0], "condition_id": "condition-second"})

    with pytest.raises(SerenityError, match="schema validation"):
        validate(tmp_path, multiple_primary)

    missing_expiry = decision()
    del missing_expiry["conditions"][0]["expires_at"]

    with pytest.raises(SerenityError, match="schema validation"):
        validate(tmp_path, missing_expiry)

    invalid_expiry = decision()
    invalid_expiry["conditions"][0]["expires_at"] = "when revisions stabilize"

    with pytest.raises(SerenityError, match="ISO datetime"):
        validate(tmp_path, invalid_expiry)

    trade_on_hit = decision()
    trade_on_hit["conditions"][0]["on_met_state"] = "EXECUTE_TRADE"

    with pytest.raises(SerenityError, match="schema validation"):
        validate(tmp_path, trade_on_hit)


def test_trigger_source_reference_must_match_saved_evidence(tmp_path: Path) -> None:
    invalid = decision()
    invalid["conditions"][0]["evidence_ref"]["canonical_id"] = "wrong-source"

    with pytest.raises(SerenityError, match="source reference"):
        validate(tmp_path, invalid)


def test_decision_rejects_unattached_json_even_when_it_claims_referenced_ids(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path)
    write_json(
        run_dir / "planted-evidence.json",
        {
            "schema_id": "urn:serenity:schema:evidence-result:1",
            "result_id": "result-planted123",
            "availability": "available",
            "source": {"uri": "https://attacker.example/evidence", "canonical_id": "attacker"},
        },
    )

    invalid = decision()
    invalid["evidence_result_ids"] = ["result-planted123"]
    invalid["required_evidence"][0]["evidence_result_id"] = "result-planted123"
    invalid["conditions"][0]["evidence_ref"]["evidence_result_id"] = "result-planted123"
    invalid["conditions"][0]["evidence_ref"]["source_uri"] = "https://attacker.example/evidence"
    invalid["conditions"][0]["evidence_ref"]["canonical_id"] = "attacker"

    with pytest.raises(SerenityError, match="absent from run artifacts"):
        validate(tmp_path, invalid, manifest=manifest, run_dir=run_dir)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("as_of", "2026-08-18"),
        ("scope", {"kind": "single-name", "subjects": ["AMD"]}),
        ("scope", {"kind": "cohort", "subjects": ["NVDA"]}),
        ("run_id", "run-other123"),
    ],
)
def test_decision_must_match_run_manifest_intent(tmp_path: Path, field: str, value: object) -> None:
    invalid = decision()
    invalid[field] = value

    with pytest.raises(SerenityError, match="run manifest"):
        validate(tmp_path, invalid)


def test_unrelated_manifest_or_artifact_text_does_not_trigger_identity_block(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path)
    write_json(run_dir / "research-notes.json", {"summary": "Analyst conflict is a normal disagreement."})

    assert validate(tmp_path, decision(), manifest=manifest, run_dir=run_dir)["valid"] is True


def test_explicit_identity_resolution_artifact_blocks_nonblocked_action(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path, identity_status="conflict")

    with pytest.raises(SerenityError, match="unresolved identity") as failure:
        validate(tmp_path, decision(), manifest=manifest, run_dir=run_dir)

    assert failure.value.exit_code == 3
    assert validate(tmp_path, decision(action="BLOCKED"), manifest=manifest, run_dir=run_dir)["valid"] is True


def test_unresolved_identity_can_only_finalize_as_blocked(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path, identity_status="conflict")

    with pytest.raises(SerenityError) as failure:
        validate_decision(
            project_root=tmp_path,
            run_manifest=manifest,
            run_dir=run_dir,
            decision_draft=decision(),
            evidence_manifest=evidence_manifest(),
        )

    assert failure.value.exit_code == 3
    blocked = decision(action="BLOCKED")
    assert validate_decision(
        project_root=tmp_path,
        run_manifest=manifest,
        run_dir=run_dir,
        decision_draft=blocked,
        evidence_manifest=evidence_manifest(),
    )["valid"] is True


def test_collision_never_mutates_an_older_version_or_current_pointer(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path)
    finalize_decision(
        project_root=tmp_path,
        run_manifest=manifest,
        run_dir=run_dir,
        decision_draft=decision(),
        analysis_markdown="first",
        evidence_manifest=evidence_manifest(),
    )
    current_path = tmp_path / "records" / "decisions" / "lineage-nvda" / "current.json"
    pointer_before = current_path.read_text(encoding="utf-8")

    with pytest.raises(SerenityError) as failure:
        finalize_decision(
            project_root=tmp_path,
            run_manifest=manifest,
            run_dir=run_dir,
            decision_draft=decision(),
            analysis_markdown="attempted overwrite",
            evidence_manifest=evidence_manifest(),
        )

    assert failure.value.exit_code == 5
    assert (tmp_path / "records" / "decisions" / "lineage-nvda" / "v001" / "analysis.md").read_text(encoding="utf-8") == "first"
    assert current_path.read_text(encoding="utf-8") == pointer_before


def test_retry_recovers_a_published_version_when_pointer_write_is_interrupted(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path)

    with pytest.raises(RuntimeError, match="simulated pointer interruption"):
        finalize_decision(
            project_root=tmp_path,
            run_manifest=manifest,
            run_dir=run_dir,
            decision_draft=decision(),
            analysis_markdown="first",
            evidence_manifest=evidence_manifest(),
            fault_injector=lambda stage: (_ for _ in ()).throw(RuntimeError("simulated pointer interruption")) if stage == "after_version_published" else None,
        )

    lineage_dir = tmp_path / "records" / "decisions" / "lineage-nvda"
    assert (lineage_dir / "v001" / "finalization-receipt.json").is_file()
    assert not (lineage_dir / "current.json").exists()

    recovered = finalize_decision(
        project_root=tmp_path,
        run_manifest=manifest,
        run_dir=run_dir,
        decision_draft=decision(),
        analysis_markdown="first",
        evidence_manifest=evidence_manifest(),
    )

    assert recovered["finalization_receipt"]["state"] == "recovered"
    assert recovered["record_dir"].endswith("/v001")
    assert json.loads((lineage_dir / "current.json").read_text(encoding="utf-8"))["version"] == 1


def test_tampered_attached_snapshot_is_revalidated_before_its_fact_ids_are_trusted(tmp_path: Path) -> None:
    manifest, run_dir = open_run(tmp_path)
    snapshot_path = run_dir / "fact-snapshot.json"
    tampered = json.loads(snapshot_path.read_text(encoding="utf-8"))
    tampered["facts"][0]["value"] = 1
    write_json(snapshot_path, tampered)
    manifest["artifacts"]["fact-snapshot"]["content_hash"] = hashlib.sha256(snapshot_path.read_bytes()).hexdigest()
    manifest["content_hash"] = canonical_hash({key: value for key, value in manifest.items() if key != "content_hash"})
    write_json(run_dir / "run-manifest.json", manifest)

    with pytest.raises(SerenityError, match="fact snapshot integrity") as failure:
        validate(tmp_path, decision(), manifest=manifest, run_dir=run_dir)

    assert failure.value.exit_code == 5


def _cohort_run(tmp_path: Path, *, pinned: tuple[str, ...]) -> tuple[dict, Path]:
    manifest, run_dir = open_run(tmp_path)
    manifest["mode"] = "cohort"
    manifest["subjects"] = ["NVDA", "AMD"]
    for ticker in pinned:
        if ticker == "NVDA":
            continue
        peer = snapshot(manifest["run_id"])
        for derived in ("snapshot_id", "content_hash"):
            peer.pop(derived, None)
        peer["identity"] = {**peer["identity"], "ticker": ticker, "name": f"{ticker} INC"}
        peer["facts"] = [{**fact, "fact_id": f"{fact['fact_id']}-{ticker.lower()}", "identity_bindings": {"ticker": ticker}} for fact in peer["facts"]]
        peer["snapshot_id"] = f"snapshot-{canonical_hash(peer)[:20]}"
        attached_artifact(manifest, tmp_path, run_dir, name=f"fact-snapshot-{ticker}", filename=f"fact-snapshot-{ticker}.json", schema_id="urn:serenity:schema:fact-snapshot:2", value=document_with_hash(peer))
    manifest.pop("content_hash", None)
    manifest["content_hash"] = canonical_hash(manifest)
    write_json(run_dir / "run-manifest.json", manifest)
    return manifest, run_dir


def test_a_cohort_decision_is_refused_while_a_subject_has_no_pinned_identity(tmp_path: Path) -> None:
    """A comparison whose peers were never identity-bound compares whatever the
    tickers happened to resolve to. Only single-name was gated before, so the
    cohort, discovery, and macro decisions on disk have no snapshot at all."""

    manifest, run_dir = _cohort_run(tmp_path, pinned=("NVDA",))
    unpinned = decision()
    unpinned["scope"] = {"kind": "cohort", "subjects": ["NVDA", "AMD"]}

    with pytest.raises(SerenityError, match="AMD"):
        validate(tmp_path, unpinned, manifest=manifest, run_dir=run_dir)


def test_a_cohort_decision_validates_once_every_subject_is_pinned(tmp_path: Path) -> None:
    manifest, run_dir = _cohort_run(tmp_path, pinned=("NVDA", "AMD"))
    pinned = decision()
    pinned["scope"] = {"kind": "cohort", "subjects": ["NVDA", "AMD"]}

    assert validate(tmp_path, pinned, manifest=manifest, run_dir=run_dir)["valid"] is True


def test_an_unpinned_cohort_subject_can_still_reach_a_blocked_decision(tmp_path: Path) -> None:
    """Unresolved identity has to stay recordable, or a run with a peer it cannot
    bind has no way to finish and the lifecycle is unfinishable rather than honest."""

    manifest, run_dir = _cohort_run(tmp_path, pinned=("NVDA",))
    blocked = decision(action="BLOCKED")
    blocked["scope"] = {"kind": "cohort", "subjects": ["NVDA", "AMD"]}

    assert validate(tmp_path, blocked, manifest=manifest, run_dir=run_dir)["valid"] is True


def test_macro_subjects_are_series_identifiers_and_need_no_security_snapshot(tmp_path: Path) -> None:
    """DGS10 is a FRED series, not a security. Requiring `snapshot security` for it
    would demand an identity resolution that has no meaning for the subject."""

    manifest, run_dir = open_run(tmp_path)
    manifest["mode"] = "macro-event"
    manifest["subjects"] = ["DGS10"]
    del manifest["artifacts"]["fact-snapshot"]
    manifest.pop("content_hash", None)
    manifest["content_hash"] = canonical_hash(manifest)
    write_json(run_dir / "run-manifest.json", manifest)
    macro = decision()
    macro["scope"] = {"kind": "macro", "subjects": ["DGS10"]}

    assert validate(tmp_path, macro, manifest=manifest, run_dir=run_dir)["valid"] is True
