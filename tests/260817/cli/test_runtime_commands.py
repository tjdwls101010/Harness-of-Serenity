from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

import serenity
from serenity_core.providers.base import ProviderEnvelope
from serenity_core.providers.issuer_ir import VerifiedIssuerOrigin
from serenity_core.research import ResearchArtifactStore
from serenity_core.runtime import RunStore, SerenityError
from serenity_core.snapshot import validate_security_snapshot as public_validate_security_snapshot
from serenity_core.identity import IdentityResolution

def write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def start_run(run_cli) -> str:
    return run_cli(
        "run",
        "start",
        "--mode",
        "single-name",
        "--question",
        "What evidence would change the NVDA thesis?",
        "--subject",
        "NVDA",
        "--as-of",
        "2026-08-17",
        "--offline",
    )["run"]["run_id"]


def frozen_snapshot_packet() -> dict[str, object]:
    return {
        "identity_resolution": {
            "schema_id": "urn:serenity:identity-resolution:1",
            "status": "available",
            "ticker": "NVDA",
            "identity": {
                "ticker": "NVDA",
                "cik": "0001045810",
                "figi": "BBG000BBJQV0",
                "official_name": "NVIDIA Corporation",
                "exchange": "Nasdaq",
                "listing_country": "US",
                "security_type": "Common Stock",
            },
        },
        "market_envelope": {
            "schema_id": "urn:serenity:schema:provider-envelope:1",
            "provider": "yfinance",
            "provider_version": "fixture/1",
            "request_id": "req-market-nvda",
            "status": "available",
            "fetched_at": "2026-08-17T12:00:00Z",
            "source": {"uri": "https://fixture.test/NVDA", "content_sha256": "a" * 64},
            "temporal": {
                "effective_at": "2026-08-17",
                "observed_at": "2026-08-17",
                "available_at": "2026-08-17T12:00:00Z",
                "source_version": "fixture/1",
            },
            "data": {
                "identity": {"ticker": "NVDA"},
                "facts": {
                    "market_cap": {
                        "availability": "available",
                        "value": 4_200_000_000_000,
                        "available_at": "2026-08-17T12:00:00Z",
                    }
                },
            },
        },
    }


def hypotheses() -> list[dict[str, object]]:
    return [
        {
            "hypothesis_id": "hyp-demand-holds",
            "statement": "Demand remains capacity constrained.",
            "predictions": ["Lead times remain elevated."],
            "falsifier": "Supply rises before demand arrives.",
            "status": "open",
            "supporting_fact_refs": [],
            "contradicting_fact_refs": [],
            "requested_evidence_ids": [],
        },
        {
            "hypothesis_id": "hyp-demand-cools",
            "statement": "Demand normalizes before capacity binds.",
            "predictions": ["Inventories normalize first."],
            "falsifier": "Orders rise after inventories normalize.",
            "status": "open",
            "supporting_fact_refs": [],
            "contradicting_fact_refs": [],
            "requested_evidence_ids": [],
        },
    ]


def evidence_request() -> dict[str, object]:
    return {
        "question": "Which recent filing names the constrained input?",
        "evidence_type": "filing-narrative",
        "provider_policy": {"providers": ["sec"], "allow_network": False},
        "acceptance_criteria": ["Name the input and the filing accession."],
        "requested_at": "2026-08-17T00:00:00Z",
        "provider_parameters": {"cik": "0001045810"},
    }


def evidence_result() -> dict[str, object]:
    return {
        "availability": "available",
        "provider": "sec",
        "source": {
            "uri": "https://www.sec.gov/Archives/edgar/data/1045810/example.txt",
            "parameters": {"cik": "0001045810"},
            "canonical_id": "sec:0001045810:example",
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
        "raw_content_sha256": "b" * 64,
        "transform_version": "filing-extract/1",
        "identity_bindings": {"cik": "0001045810", "ticker": "NVDA"},
        "fact_refs": ["fact:filing"],
        "value": {"named_input": "example input"},
    }


def live_evidence_run(tmp_path: Path, *, allow_network: bool = True, cutoff: str | None = "2026-08-17T00:00:00Z") -> tuple[dict[str, object], str]:
    source_policy: dict[str, object] = {"policy_id": "live-free-v1", "allow_network": allow_network}
    if cutoff is not None:
        source_policy["historical_cutoff"] = cutoff
    run = RunStore(tmp_path).start(
        mode="single-name",
        question="What primary evidence resolves the hypothesis?",
        subjects=["NVDA"],
        as_of="2026-08-17",
        source_policy=source_policy,
    )
    artifacts = ResearchArtifactStore(tmp_path / ".serenity" / "runs" / run["run_id"])
    prepared_ledger = artifacts.prepare_hypotheses(hypotheses())
    run = RunStore(tmp_path).publish_or_refresh_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        expected_attachment=None,
        path=prepared_ledger.ledger_path,
        content=prepared_ledger.ledger_content,
        schema_id=prepared_ledger.ledger["schema_id"],
        phase="hypotheses_updated",
    )
    prepared_request = artifacts.prepare_evidence_request(
        hypothesis_ids=["hyp-demand-holds"],
        capability_id="bls.labor-data",
        request={
            "question": "What did the labor series print?",
            "evidence_type": "macro-series",
            "provider_policy": {"providers": ["bls"], "allow_network": True},
            "acceptance_criteria": ["Return the published series observation."],
            "requested_at": "2026-08-17T00:00:00Z",
            "provider_parameters": {"series": ["CES0000000001"]},
        },
    )
    run = RunStore(tmp_path).publish_or_refresh_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        expected_attachment=run["artifacts"]["hypothesis-ledger"],
        path=prepared_request.ledger_path,
        content=prepared_request.ledger_content,
        schema_id=prepared_request.ledger["schema_id"],
        phase="hypotheses_updated",
    )
    assert prepared_request.request is not None
    assert prepared_request.request_path is not None
    assert prepared_request.request_content is not None
    run = RunStore(tmp_path).publish_artifact(
        run["run_id"],
        name=prepared_request.request["request_id"],
        path=prepared_request.request_path,
        content=prepared_request.request_content,
        schema_id=prepared_request.request["schema_id"],
        phase="evidence_requested",
    )
    return run, prepared_request.request["request_id"]


def live_envelope(source_version: str, available_at: str) -> ProviderEnvelope:
    return ProviderEnvelope.available(
        provider="bls",
        provider_version="fixture/1",
        source_uri="https://fixture.test/bls",
        raw_content=source_version.encode(),
        data={"observation": source_version},
        fetched_at="2026-08-17T12:00:00Z",
        request={"series": "CES0000000001"},
        available_at=available_at,
        source_version=source_version,
        source_parameters={"api_key": "never-serialize"},
        parse={"status": "parsed", "transform_version": "fixture/1"},
    )


def lens_spec(run_id: str, fact_ref: str) -> dict[str, object]:
    return {
        "schema_id": "urn:serenity:schema:lens-spec:1",
        "lens_id": "lens-market-cap-ratio",
        "run_id": run_id,
        "question": "What is the market-cap ratio?",
        "formula": "market_cap / market_cap",
        "inputs": [{"name": "market_cap", "fact_ref": fact_ref, "unit": "USD"}],
        "output_unit": "fraction",
        "assumptions": ["The frozen market-cap fact is usable."],
        "validity_constraints": ["market_cap must be available"],
    }


def decision_draft(run_id: str, evidence_id: str, lens_result: dict[str, object]) -> dict[str, object]:
    return {
        "schema_id": "urn:serenity:schema:research-decision:1",
        "decision_id": "decision-nvda-001",
        "run_id": run_id,
        "lineage_id": "lineage-nvda",
        "version": 1,
        "as_of": "2026-08-17",
        "created_at": "2026-08-17T00:00:00Z",
        "scope": {"kind": "single-name", "subjects": ["NVDA"]},
        "action": "ENTER_ON_TRIGGER",
        "thesis": "Demand remains durable, but entry needs revision stabilization.",
        "materiality": "material",
        "priced_in": {"included": ["current demand"], "not_included": ["networking mix"]},
        "strongest_bear_case": "Customer digestion could create a revenue air pocket.",
        "falsifiers": ["Two quarters of estimate cuts."],
        "hypothesis_ids": ["hyp-demand-holds"],
        "evidence_result_ids": [evidence_id],
        "required_evidence": [{"evidence_result_id": evidence_id, "purpose": "identity and filing support", "action_critical": True}],
        "lens_results": [{"lens_result_id": lens_result["lens_result_id"], "validity": "valid", "fact_refs": lens_result["fact_refs"]}],
        "conditions": [
            {
                "condition_id": "condition-revisions-stabilize",
                "condition": "Forward revisions stabilize.",
                "primary": True,
                "observable": {"field": "forward_revision_30d", "operator": "gte", "value": 0, "unit": "fraction"},
                "evidence_ref": {
                    "evidence_result_id": evidence_id,
                    "source_uri": "https://www.sec.gov/Archives/edgar/data/1045810/example.txt",
                    "canonical_id": "sec:0001045810:example",
                },
                "expires_at": "2026-12-31T00:00:00Z",
                "on_met_state": "REASSESS_REQUIRED",
                "status": "unmet",
            }
        ],
        "vehicle": {"kind": "common-stock", "ticker": "NVDA"},
        "conviction": "medium",
        "uncertainty": "Forward revisions can lag a customer digestion cycle.",
    }


def finalized_outcome_decision() -> dict[str, object]:
    return {
        "decision_id": "decision-nvda-001",
        "lineage_id": "lineage-nvda",
        "action": "ENTER_ON_TRIGGER",
        "as_of": "2026-08-17",
        "conditions": [{"condition": "Forward revisions stabilize.", "status": "unmet"}],
        "falsifiers": ["Two quarters of estimate cuts."],
        "finalized_at": "2026-08-17T12:00:00Z",
    }


def outcome_observation() -> dict[str, object]:
    provenance = {"provider": "fixture", "source_version": "2026-09-17"}
    return {
        "observation_id": "nvda-2026-09-17-close",
        "as_of": "2026-09-17",
        "subject_price": {"availability": "available", "value": 184.23, "currency": "USD", "provenance": provenance},
        "benchmark_return": {"availability": "available", "value": 0.041, "unit": "fraction", "provenance": provenance},
        "mechanism_evidence": {"availability": "available", "value": "Mechanism unchanged.", "summary": "Mechanism unchanged.", "provenance": provenance},
        "falsifier_state": {"availability": "available", "value": "not_triggered", "state": "not_triggered", "provenance": provenance},
        "condition_hits": [{"condition": "Forward revisions stabilize.", "hit": True}],
    }


def sector_graph(run_id: str) -> dict[str, object]:
    evidence = ["result-demand", "result-input"]
    return {
        "schema_id": "urn:serenity:schema:sector-graph:1",
        "graph_id": "graph-nvda-input",
        "run_id": run_id,
        "as_of": "2026-08-17",
        "evidence_refs": evidence,
        "nodes": [
            {"node_id": "compute", "node_type": "industry", "label": "Compute", "relationship_to_bottleneck": "enables", "claims": [{"statement": "Compute needs accelerators.", "evidence_refs": ["result-demand"]}]},
            {"node_id": "accelerator", "node_type": "layer", "label": "Accelerator", "relationship_to_bottleneck": "owns", "claims": [{"statement": "Accelerators gate compute throughput.", "evidence_refs": ["result-demand"]}]},
            {"node_id": "substrate", "node_type": "input", "label": "Substrate", "relationship_to_bottleneck": "supplies", "claims": [{"statement": "Qualified substrates constrain production.", "evidence_refs": ["result-input"]}]},
        ],
        "edges": [
            {"from_node_id": "compute", "to_node_id": "accelerator", "edge_type": "depends_on", "claims": [{"statement": "Compute depends on accelerators.", "evidence_refs": ["result-demand"]}]},
            {"from_node_id": "accelerator", "to_node_id": "substrate", "edge_type": "depends_on", "claims": [{"statement": "Accelerators depend on substrates.", "evidence_refs": ["result-input"]}]},
        ],
        "headline_node_id": "accelerator",
        "bottleneck_node_ids": ["accelerator"],
        "recursive_bottom_hop": {"node_id": "substrate", "path": ["accelerator", "substrate"], "stop_rationale": {"reason": "No lower qualified input is evidenced.", "evidence_refs": ["result-input"]}},
        "sibling_comparison": {"node_ids": ["accelerator", "substrate"], "statement": "The layers capture different economics.", "evidence_refs": ["result-demand", "result-input"]},
        "second_order_effect": {"status": "unresolved", "rationale": "No allocation actor is evidenced.", "evidence_refs": ["result-demand"]},
        "ownership_concentration": [{"node_id": "accelerator", "kind": "concentration", "statement": "Capacity is concentrated.", "vector": "stable", "rationale": "The evidence establishes concentration but no current breadth change.", "evidence_refs": ["result-demand"]}],
        "us_expression": {"resolution": "no_clean_vehicle", "rationale": "No US listing is evidenced.", "evidence_refs": ["result-demand"]},
    }


def test_snapshot_security_persists_a_deterministic_frozen_packet(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    packet = write_json(tmp_path / "frozen-snapshot.json", frozen_snapshot_packet())

    result = run_cli("snapshot", "security", run_id, "--frozen-packet", str(packet))

    assert result["command"] == "snapshot.security"
    assert result["ok"] is True
    snapshot = result["snapshot"]
    assert snapshot["run_id"] == run_id
    assert snapshot["identity"]["ticker"] == "NVDA"
    assert snapshot["identity"]["listing_type"] == "common"
    assert (tmp_path / ".serenity" / "runs" / run_id / "fact-snapshot.json").is_file()


def test_snapshot_security_refuses_live_providers_for_an_offline_run(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)

    result = run_cli("snapshot", "security", run_id, expected_exit=4)

    assert result["error"]["code"] == "provider_failure"
    assert not (tmp_path / ".serenity" / "runs" / run_id / "fact-snapshot.json").exists()


def test_snapshot_help_keeps_frozen_packet_optional_because_live_is_the_default(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(serenity.__file__)), "snapshot", "security", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert "--frozen-packet" in completed.stdout
    assert "--live" not in completed.stdout


@pytest.mark.parametrize(
    ("arguments", "required_text"),
    [
        (("run", "start", "--help"), "--as-of derives a 23:59:59Z historical cutoff"),
        (("run", "start", "--help"), "--provider allowlists named provider IDs"),
        (("snapshot", "security", "--help"), "Live execution requires allowed sec, openfigi, and yfinance providers"),
    ],
)
def test_live_snapshot_help_explains_as_of_cutoff_and_provider_policy(tmp_path: Path, arguments: tuple[str, ...], required_text: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(serenity.__file__)), *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert required_text in completed.stdout


@pytest.mark.parametrize(
    "arguments",
    [
        ("--help",),
        ("run", "--help"),
        ("run", "start", "--help"),
        ("run", "status", "--help"),
        ("run", "abandon", "--help"),
        ("run", "close", "--help"),
        ("snapshot", "--help"),
        ("snapshot", "security", "--help"),
        ("hypothesis", "--help"),
        ("hypothesis", "put", "--help"),
        ("evidence", "--help"),
        ("evidence", "catalog", "--help"),
        ("evidence", "request", "--help"),
        ("evidence", "collect", "--help"),
        ("evidence", "read", "--help"),
        ("lens", "--help"),
        ("lens", "run", "--help"),
        ("decision", "--help"),
        ("decision", "validate", "--help"),
        ("decision", "finalize", "--help"),
        ("outcomes", "--help"),
        ("outcomes", "register", "--help"),
        ("outcomes", "refresh", "--help"),
        ("graph", "--help"),
        ("graph", "put", "--help"),
    ],
)
def test_each_cli_help_path_explains_purpose_state_artifact_and_example(tmp_path: Path, arguments: tuple[str, ...]) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(serenity.__file__)), *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert "Purpose:" in completed.stdout
    assert "State:" in completed.stdout
    assert "Artifact:" in completed.stdout
    assert "Example:" in completed.stdout


@pytest.mark.parametrize(
    ("arguments", "expected_example"),
    [
        (("--help",), "serenity.py run start --mode single-name --question"),
        (("run", "--help"), "Workflow: serenity.py run start --mode single-name"),
        (("run", "start", "--help"), "--as-of 2026-08-17 --offline"),
        (("run", "status", "--help"), "serenity.py run status RUN_ID"),
        (("run", "abandon", "--help"), "serenity.py run abandon RUN_ID --reason"),
        (("run", "close", "--help"), "serenity.py run close RUN_ID --reason"),
        (("snapshot", "--help"), "Workflow: serenity.py snapshot security RUN_ID --frozen-packet fixtures/frozen-snapshot.json"),
        (("snapshot", "security", "--help"), "serenity.py snapshot security RUN_ID --frozen-packet fixtures/frozen-snapshot.json"),
        (("hypothesis", "--help"), "Workflow: serenity.py hypothesis put RUN_ID --document fixtures/hypotheses.json"),
        (("hypothesis", "put", "--help"), "serenity.py hypothesis put RUN_ID --document fixtures/hypotheses.json"),
        (("evidence", "--help"), "Workflow: serenity.py evidence request RUN_ID"),
        (("evidence", "catalog", "--help"), "serenity.py evidence catalog"),
        (("evidence", "request", "--help"), "--document fixtures/evidence-request.json"),
        (("evidence", "collect", "--help"), "serenity.py evidence collect RUN_ID evidence-request-001"),
        (("evidence", "read", "--help"), "serenity.py evidence read RUN_ID evidence-result-001"),
        (("lens", "--help"), "Workflow: serenity.py lens run RUN_ID --spec fixtures/lens-spec.json"),
        (("lens", "run", "--help"), "serenity.py lens run RUN_ID --spec fixtures/lens-spec.json"),
        (("decision", "--help"), "Workflow: serenity.py decision validate RUN_ID"),
        (("decision", "validate", "--help"), "--decision fixtures/decision.json --evidence-manifest fixtures/evidence-manifest.json"),
        (("decision", "finalize", "--help"), "--analysis fixtures/analysis.json"),
        (("outcomes", "--help"), "Workflow: serenity.py outcomes register --decision records/decisions/LINEAGE/v001/decision.json"),
        (("outcomes", "register", "--help"), "--benchmark-json fixtures/benchmark.json --checkpoint-schedule-json fixtures/outcome-schedule.json"),
        (("outcomes", "refresh", "--help"), "serenity.py outcomes refresh outcome-001 --observation fixtures/observation.json"),
        (("graph", "--help"), "Workflow: serenity.py graph put RUN_ID --file fixtures/sector-graph.json"),
        (("graph", "put", "--help"), "serenity.py graph put RUN_ID --file fixtures/sector-graph.json"),
    ],
)
def test_each_cli_help_path_shows_an_executable_example_without_io(tmp_path: Path, arguments: tuple[str, ...], expected_example: str) -> None:
    completed = subprocess.run(
        [sys.executable, str(Path(serenity.__file__)), *arguments],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert expected_example in completed.stdout
    if len(arguments) == 3 and arguments[:2] != ("snapshot", "security"):
        assert "--frozen-packet" not in completed.stdout


def test_evidence_help_explains_official_issuer_narrative_capture_without_io(tmp_path: Path) -> None:
    request_help = subprocess.run(
        [sys.executable, str(Path(serenity.__file__)), "evidence", "request", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    collect_help = subprocess.run(
        [sys.executable, str(Path(serenity.__file__)), "evidence", "collect", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    read_help = subprocess.run(
        [sys.executable, str(Path(serenity.__file__)), "evidence", "read", "--help"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert (request_help.returncode, request_help.stderr) == (0, "")
    assert (collect_help.returncode, collect_help.stderr) == (0, "")
    assert (read_help.returncode, read_help.stderr) == (0, "")
    for output in (request_help.stdout, collect_help.stdout):
        assert "issuer-ir.document" in output
        assert "official issuer-owned URL" in output
        assert "identity/domain/time/raw-byte" in output
        assert "Web search only locates the source" in output
        assert "live SEC-provenance fact snapshot" in output
        assert "frozen snapshot cannot authorize" in output
    assert "issuer-ir.document must use evidence collect" in read_help.stdout


def test_snapshot_security_uses_live_provider_seam_and_never_serializes_dotenv_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = RunStore(tmp_path).start(
        mode="single-name",
        question="What evidence would change the NVDA thesis?",
        subjects=["NVDA"],
        as_of="2026-08-17",
        source_policy={"policy_id": "live-free-v1", "allow_network": True},
    )
    (tmp_path / ".env").write_text("SERENITY_SEC_USER_AGENT=Fixture User fixture@example.test\n", encoding="utf-8")
    monkeypatch.delenv("SERENITY_SEC_USER_AGENT", raising=False)
    observed: dict[str, str] = {}

    def live_inputs(
        *, ticker: str, as_of: str, historical_cutoff: str, allowed_providers: frozenset[str]
    ) -> tuple[dict[str, object], dict[str, object], None]:
        observed["ticker"] = ticker
        observed["as_of"] = as_of
        observed["secret"] = os.environ["SERENITY_SEC_USER_AGENT"]
        packet = frozen_snapshot_packet()
        return packet["identity_resolution"], packet["market_envelope"], None

    monkeypatch.setattr(serenity, "build_live_snapshot_inputs", live_inputs)

    result = serenity.dispatch(
        argparse.Namespace(command="snapshot", snapshot_command="security", run_id=run["run_id"], frozen_packet=None), tmp_path
    )

    assert observed == {"ticker": "NVDA", "as_of": "2026-08-17", "secret": "Fixture User fixture@example.test"}
    serialized = json.dumps(result)
    assert "Fixture User fixture@example.test" not in serialized
    assert result["snapshot"]["identity"]["ticker"] == "NVDA"


def test_live_snapshot_caches_private_provider_raw_bytes_before_writing_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = RunStore(tmp_path).start(
        mode="single-name",
        question="What evidence would change the NVDA thesis?",
        subjects=["NVDA"],
        as_of="2026-08-17",
        source_policy={"policy_id": "live-free-v1", "allow_network": True, "historical_cutoff": "2026-08-17T23:59:59Z"},
    )
    raw = b"exact private market provider bytes"
    packet = frozen_snapshot_packet()
    market = ProviderEnvelope.available(
        provider="yfinance",
        provider_version="fixture/1",
        source_uri="https://fixture.test/NVDA",
        raw_content=raw,
        data=packet["market_envelope"]["data"],
        fetched_at="2026-08-17T12:00:00Z",
        request={"ticker": "NVDA"},
        available_at="2026-08-17T12:00:00Z",
        source_version="fixture/1",
        parse={"status": "parsed", "transform_version": "fixture/1"},
    )
    identity_envelopes = tuple(
        ProviderEnvelope.available(
            provider=provider,
            provider_version="fixture/1",
            source_uri=f"https://fixture.test/{provider}",
            raw_content=raw_content,
            data={},
            fetched_at="2026-08-17T12:00:00Z",
            request={"ticker": "NVDA"},
            available_at="2026-08-17T12:00:00Z",
            source_version="fixture/1",
            parse={"status": "parsed", "transform_version": "fixture/1"},
        )
        for provider, raw_content in (
            ("sec.company_tickers", b"exact private SEC directory bytes"),
            ("sec.submissions", b"exact private SEC submissions bytes"),
            ("openfigi.mapping", b"exact private OpenFIGI bytes"),
        )
    )
    identity = IdentityResolution(packet["identity_resolution"], identity_envelopes)

    def live_inputs(*, ticker: str, as_of: str, historical_cutoff: str, allowed_providers: frozenset[str]) -> tuple[IdentityResolution, ProviderEnvelope, None]:
        return identity, market, None

    monkeypatch.setattr(serenity, "build_live_snapshot_inputs", live_inputs)

    result = serenity.dispatch(
        argparse.Namespace(command="snapshot", snapshot_command="security", run_id=run["run_id"], frozen_packet=None), tmp_path
    )

    payloads = [*identity_envelopes, market]
    cache_paths = [
        tmp_path / ".serenity" / "cache" / "provider-raw" / "sha256" / hashlib.sha256(payload).hexdigest()
        for payload in (b"exact private SEC directory bytes", b"exact private SEC submissions bytes", b"exact private OpenFIGI bytes", raw)
    ]
    assert [path.read_bytes() for path in cache_paths] == [
        b"exact private SEC directory bytes",
        b"exact private SEC submissions bytes",
        b"exact private OpenFIGI bytes",
        raw,
    ]
    assert [entry["content_sha256"] for entry in result["raw_payload_cache"]] == [item.to_dict()["source"]["content_sha256"] for item in payloads]
    assert [Path(entry["cache_path"]) for entry in result["raw_payload_cache"]] == cache_paths
    assert all(path.is_file() for path in cache_paths)
    assert [entry["provider"] for entry in result["snapshot"]["identity"]["provenance"]] == ["sec.company_tickers", "sec.submissions", "openfigi.mapping"]
    assert raw.decode() not in json.dumps(result)
    assert raw.decode() not in (tmp_path / ".serenity" / "runs" / run["run_id"] / "fact-snapshot.json").read_text(encoding="utf-8")


def test_backdated_live_snapshot_receives_the_as_of_cutoff_and_marks_newer_facts_stale(run_cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = run_cli(
        "run",
        "start",
        "--mode",
        "single-name",
        "--question",
        "What was knowable before the 2020 event?",
        "--subject",
        "NVDA",
        "--as-of",
        "2020-01-02",
    )["run"]["run_id"]
    observed: dict[str, object] = {}

    def live_inputs(*, ticker: str, as_of: str, historical_cutoff: str, allowed_providers: frozenset[str]) -> tuple[dict[str, object], dict[str, object], None]:
        observed.update({"ticker": ticker, "as_of": as_of, "historical_cutoff": historical_cutoff, "allowed_providers": allowed_providers})
        packet = frozen_snapshot_packet()
        return packet["identity_resolution"], packet["market_envelope"], None

    monkeypatch.setattr(serenity, "build_live_snapshot_inputs", live_inputs)

    result = serenity.dispatch(
        argparse.Namespace(command="snapshot", snapshot_command="security", run_id=run_id, frozen_packet=None), tmp_path
    )

    assert observed == {
        "ticker": "NVDA",
        "as_of": "2020-01-02",
        "historical_cutoff": "2020-01-02T23:59:59Z",
        "allowed_providers": frozenset({"sec", "openfigi", "yfinance", "ibd-rs-rating"}),
    }
    market_cap = next(fact for fact in result["snapshot"]["facts"] if fact["name"] == "market_cap")
    assert market_cap["availability"] == "stale"


@pytest.mark.parametrize(
    ("allowed_providers", "expected_exit", "expected_code"),
    [
        (["yfinance", "ibd-rs-rating"], 3, "identity_blocked"),
        (["sec", "yfinance", "ibd-rs-rating"], 3, "identity_blocked"),
        (["sec", "openfigi", "ibd-rs-rating"], 4, "provider_failure"),
    ],
)
def test_live_snapshot_rejects_missing_mandatory_allowed_providers_before_any_factory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, allowed_providers: list[str], expected_exit: int, expected_code: str
) -> None:
    run = RunStore(tmp_path).start(
        mode="single-name",
        question="What evidence would change the NVDA thesis?",
        subjects=["NVDA"],
        as_of="2026-08-17",
        source_policy={
            "policy_id": "live-free-v1",
            "allow_network": True,
            "historical_cutoff": "2026-08-17T23:59:59Z",
            "allowed_providers": allowed_providers,
        },
    )
    constructed: list[str] = []

    def forbidden(name: str):
        def factory(*_args: object, **_kwargs: object) -> object:
            constructed.append(name)
            raise AssertionError(f"{name} must not be constructed")

        return factory

    monkeypatch.setattr(serenity, "SecIdentityProvider", forbidden("sec"))
    monkeypatch.setattr(serenity, "OpenFigiProvider", forbidden("openfigi"))
    monkeypatch.setattr(serenity, "YFinanceProvider", forbidden("yfinance"))
    monkeypatch.setattr(serenity, "RsRatingProvider", forbidden("ibd-rs-rating"))

    with pytest.raises(SerenityError) as raised:
        serenity.dispatch(
            argparse.Namespace(command="snapshot", snapshot_command="security", run_id=run["run_id"], frozen_packet=None), tmp_path
        )

    assert raised.value.exit_code == expected_exit
    assert raised.value.payload["error"]["code"] == expected_code
    assert constructed == []


def test_live_snapshot_never_constructs_disallowed_optional_rs_provider(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run = RunStore(tmp_path).start(
        mode="single-name",
        question="What evidence would change the NVDA thesis?",
        subjects=["NVDA"],
        as_of="2026-08-17",
        source_policy={
            "policy_id": "live-free-v1",
            "allow_network": True,
            "historical_cutoff": "2026-08-17T23:59:59Z",
            "allowed_providers": ["sec", "openfigi", "yfinance"],
        },
    )
    packet = frozen_snapshot_packet()
    constructed: list[str] = []

    class FakeIdentityResolver:
        def __init__(self, *, sec: object, openfigi: object) -> None:
            constructed.extend(["sec", "openfigi"])

        def resolve(self, ticker: str):
            class Resolution:
                def to_dict(self) -> dict[str, object]:
                    return packet["identity_resolution"]

            return Resolution()

    class FakeYFinanceProvider:
        def fetch(self, ticker: str) -> object:
            constructed.append("yfinance")
            return packet["market_envelope"]

    def forbidden_rs(*_args: object, **_kwargs: object) -> object:
        constructed.append("ibd-rs-rating")
        raise AssertionError("disallowed RS provider must not be constructed")

    monkeypatch.setattr(serenity, "SecIdentityProvider", object)
    monkeypatch.setattr(serenity, "OpenFigiProvider", object)
    monkeypatch.setattr(serenity, "IdentityResolver", FakeIdentityResolver)
    monkeypatch.setattr(serenity, "YFinanceProvider", FakeYFinanceProvider)
    monkeypatch.setattr(serenity, "RsRatingProvider", forbidden_rs)

    result = serenity.dispatch(
        argparse.Namespace(command="snapshot", snapshot_command="security", run_id=run["run_id"], frozen_packet=None), tmp_path
    )

    assert result["ok"] is True
    assert constructed == ["sec", "openfigi", "yfinance"]


def test_snapshot_security_hard_blocks_a_conflicting_frozen_identity(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    packet = frozen_snapshot_packet()
    packet["market_envelope"]["data"]["identity"]["ticker"] = "AMD"

    result = run_cli("snapshot", "security", run_id, "--frozen-packet", str(write_json(tmp_path / "conflict.json", packet)), expected_exit=3)

    assert result["error"]["code"] == "identity_blocked"
    assert not (tmp_path / ".serenity" / "runs" / run_id / "fact-snapshot.json").exists()


def test_hypothesis_and_evidence_commands_persist_typed_research_artifacts(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    catalog = run_cli("evidence", "catalog")
    assert catalog["catalog"]["schema_id"] == "urn:serenity:schema:evidence-catalog:1"

    ledger = run_cli(
        "hypothesis", "put", run_id, "--document", str(write_json(tmp_path / "hypotheses.json", hypotheses()))
    )["ledger"]
    assert ledger["revision"] == 1
    request = run_cli(
        "evidence",
        "request",
        run_id,
        "--hypothesis-id",
        "hyp-demand-holds",
        "--capability-id",
        "sec.submissions",
        "--document",
        str(write_json(tmp_path / "request.json", evidence_request())),
    )["request"]
    result = run_cli(
        "evidence",
        "read",
        run_id,
        request["request_id"],
        "--document",
        str(write_json(tmp_path / "result.json", evidence_result())),
    )["result"]
    reread = run_cli("evidence", "read", run_id, result["result_id"])

    assert reread["result"] == result
    run_dir = tmp_path / ".serenity" / "runs" / run_id
    attachment = run_cli("run", "status", run_id)["run"]["artifacts"]["hypothesis-ledger"]
    assert (tmp_path / attachment["path"]).is_file()
    assert attachment["path"].startswith(f".serenity/runs/{run_id}/evidence/ledger-revisions/")
    assert (run_dir / "evidence" / "requests" / f"{request['request_id']}.json").is_file()
    assert (run_dir / "evidence" / "results" / f"{result['result_id']}.json").is_file()


def test_evidence_collect_persists_registry_envelopes_in_deterministic_order_without_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run, request_id = live_evidence_run(tmp_path)
    received: list[dict[str, object]] = []

    class RegistryFixture:
        def collect(self, request_doc: dict[str, object]) -> list[ProviderEnvelope]:
            received.append(request_doc)
            return [
                live_envelope("2026-08-15", "2026-08-15T00:00:00Z"),
                live_envelope("2026-08-01", "2026-08-01T00:00:00Z"),
            ]

    monkeypatch.setattr(serenity, "build_evidence_provider_registry", lambda _root: RegistryFixture())

    result = serenity.dispatch(
        argparse.Namespace(command="evidence", evidence_command="collect", run_id=run["run_id"], request_id=request_id), tmp_path
    )

    assert received[0]["provider_policy"] == {"providers": ["bls"], "allow_network": True, "historical_cutoff": "2026-08-17T00:00:00Z"}
    assert [item["temporal"]["source_version"] for item in result["results"]] == ["2026-08-01", "2026-08-15"]
    assert "never-serialize" not in json.dumps(result)
    read_back = serenity.dispatch(
        argparse.Namespace(command="evidence", evidence_command="read", run_id=run["run_id"], artifact_id=result["results"][0]["result_id"], document=None), tmp_path
    )
    assert read_back["result"] == result["results"][0]


def test_issuer_ir_collect_resolves_the_origin_against_the_attached_snapshot_before_registry_io(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = RunStore(tmp_path)
    run = runtime.start(
        mode="single-name",
        question="What did management disclose about the operating constraint?",
        subjects=["NVDA"],
        as_of="2026-08-17",
        source_policy={
            "policy_id": "live-issuer-ir-v1",
            "allow_network": True,
            "historical_cutoff": "2026-08-17T23:59:59Z",
            "allowed_providers": ["issuer-ir", "openfigi", "sec", "yfinance"],
        },
    )
    packet = frozen_snapshot_packet()
    packet["identity_resolution"]["identity"]["issuer_domains"] = ["investor.nvidia.com", "www.nvidia.com"]
    submissions_raw = json.dumps(
        {
            "cik": "0001045810",
            "name": "NVIDIA Corporation",
            "tickers": ["NVDA"],
            "exchanges": ["Nasdaq"],
            "website": "https://www.nvidia.com/",
            "investorWebsite": "https://investor.nvidia.com/",
        }
    ).encode()
    identity_envelopes = tuple(
        ProviderEnvelope.available(
            provider=provider,
            provider_version="fixture/1",
            source_uri=source_uri,
            raw_content=raw_content,
            data={},
            fetched_at="2026-08-17T12:00:00Z",
            request={"ticker": "NVDA"},
            available_at="2026-08-17T12:00:00Z",
            source_version="fixture/1",
            parse={"status": "parsed", "transform_version": "fixture/1"},
        )
        for provider, source_uri, raw_content in (
            ("sec.company_tickers", "https://www.sec.gov/files/company_tickers.json", b"exact SEC directory bytes"),
            ("sec.submissions", "https://data.sec.gov/submissions/CIK0001045810.json", submissions_raw),
            ("openfigi.mapping", "https://api.openfigi.com/v3/mapping", b"exact OpenFIGI bytes"),
        )
    )
    identity_resolution = IdentityResolution(packet["identity_resolution"], identity_envelopes)
    market = ProviderEnvelope.available(
        provider="yfinance",
        provider_version="fixture/1",
        source_uri="https://fixture.test/NVDA",
        raw_content=b"exact market bytes",
        data=packet["market_envelope"]["data"],
        fetched_at="2026-08-17T12:00:00Z",
        request={"ticker": "NVDA"},
        available_at="2026-08-17T12:00:00Z",
        source_version="fixture/1",
        parse={"status": "parsed", "transform_version": "fixture/1"},
    )
    monkeypatch.setattr(serenity, "build_live_snapshot_inputs", lambda **_kwargs: (identity_resolution, market, None))
    snapshot_result = serenity.dispatch(
        argparse.Namespace(
            command="snapshot",
            snapshot_command="security",
            run_id=run["run_id"],
            frozen_packet=None,
        ),
        tmp_path,
    )
    snapshot = snapshot_result["snapshot"]
    artifacts = ResearchArtifactStore(tmp_path / ".serenity" / "runs" / run["run_id"])
    prepared_ledger = artifacts.prepare_hypotheses(hypotheses())
    run = runtime.publish_or_refresh_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        expected_attachment=None,
        path=prepared_ledger.ledger_path,
        content=prepared_ledger.ledger_content,
        schema_id=prepared_ledger.ledger["schema_id"],
        phase="hypotheses_updated",
    )

    def publish_request(*, issuer_domain: str) -> str:
        nonlocal run
        prior = run["artifacts"]["hypothesis-ledger"]
        prepared = artifacts.prepare_evidence_request(
            hypothesis_ids=["hyp-demand-holds"],
            capability_id="issuer-ir.document",
            request={
                "question": "What operating constraint did management disclose?",
                "evidence_type": "issuer-narrative",
                "provider_policy": {
                    "providers": ["issuer-ir"],
                    "allow_network": True,
                    "historical_cutoff": "2026-08-17T23:59:59Z",
                },
                "acceptance_criteria": ["Preserve official source provenance."],
                "requested_at": "2026-08-17T00:00:00Z",
                "provider_parameters": {
                    "identity": {"ticker": "NVDA", "cik": "0001045810", "issuer": "NVIDIA Corporation"},
                    "document": {
                        "url": f"https://{issuer_domain}/prepared-remarks",
                        "kind": "prepared_remarks",
                    },
                    "origin_binding": {
                        "issuer_domain": issuer_domain,
                        "binding_source_ref": snapshot["snapshot_id"],
                    },
                },
            },
        )
        run = runtime.publish_or_refresh_artifact(
            run["run_id"],
            name="hypothesis-ledger",
            expected_attachment=prior,
            path=prepared.ledger_path,
            content=prepared.ledger_content,
            schema_id=prepared.ledger["schema_id"],
            phase="hypotheses_updated",
        )
        assert prepared.request is not None and prepared.request_path is not None and prepared.request_content is not None
        run = runtime.publish_artifact(
            run["run_id"],
            name=prepared.request["request_id"],
            path=prepared.request_path,
            content=prepared.request_content,
            schema_id=prepared.request["schema_id"],
            phase="evidence_requested",
        )
        return prepared.request["request_id"]

    request_id = publish_request(issuer_domain="investor.nvidia.com")
    received: list[VerifiedIssuerOrigin] = []

    class RegistryFixture:
        def collect(
            self,
            _request_doc: dict[str, object],
            *,
            issuer_origin_binding: VerifiedIssuerOrigin | None = None,
        ) -> list[ProviderEnvelope]:
            assert issuer_origin_binding is not None
            received.append(issuer_origin_binding)
            return [
                ProviderEnvelope.unavailable(
                    provider="issuer-ir",
                    provider_version="fixture/1",
                    source_uri="https://investor.nvidia.com/prepared-remarks",
                    fetched_at="2026-08-17T12:00:00Z",
                    request={},
                    status="not_disclosed",
                    reason="fixture",
                    parse={"status": "not_parsed", "transform_version": "fixture/1"},
                )
            ]

    monkeypatch.setattr(serenity, "build_evidence_provider_registry", lambda _root: RegistryFixture())
    serenity.dispatch(
        argparse.Namespace(command="evidence", evidence_command="collect", run_id=run["run_id"], request_id=request_id),
        tmp_path,
    )

    assert received == [
        VerifiedIssuerOrigin(
            ticker="NVDA",
            cik="0001045810",
            issuer="NVIDIA Corporation",
            issuer_domain="investor.nvidia.com",
            binding_source_ref=snapshot["snapshot_id"],
            binding_content_hash=snapshot["content_hash"],
        )
    ]

    conflicting_request_id = publish_request(issuer_domain="evil.example.test")
    with pytest.raises(SerenityError) as raised:
        serenity.dispatch(
            argparse.Namespace(
                command="evidence",
                evidence_command="collect",
                run_id=run["run_id"],
                request_id=conflicting_request_id,
            ),
            tmp_path,
        )

    assert raised.value.exit_code == 3
    assert raised.value.payload["error"]["code"] == "identity_blocked"
    assert len(received) == 1

    forged = evidence_result()
    forged["provider"] = "issuer-ir"
    forged["source"] = {
        "uri": "https://evil.example.test/forged-remarks",
        "parameters": {"issuer_domain": "evil.example.test"},
        "canonical_id": "issuer-ir:forged",
    }
    results_dir = tmp_path / ".serenity" / "runs" / run["run_id"] / "evidence" / "results"
    before = sorted(results_dir.glob("*.json"))
    with pytest.raises(SerenityError) as injected:
        serenity.dispatch(
            argparse.Namespace(
                command="evidence",
                evidence_command="read",
                run_id=run["run_id"],
                artifact_id=conflicting_request_id,
                document=str(write_json(tmp_path / "forged-issuer-evidence.json", forged)),
            ),
            tmp_path,
        )

    assert injected.value.exit_code == 2
    assert injected.value.payload["error"]["code"] == "usage_or_schema"
    assert sorted(results_dir.glob("*.json")) == before


def test_frozen_snapshot_cannot_authorize_a_live_issuer_origin(tmp_path: Path) -> None:
    runtime = RunStore(tmp_path)
    run = runtime.start(
        mode="single-name",
        question="What did management disclose?",
        subjects=["NVDA"],
        as_of="2026-08-17",
        source_policy={"policy_id": "live-issuer-ir-v1", "allow_network": True, "allowed_providers": ["issuer-ir"]},
    )
    packet = frozen_snapshot_packet()
    packet["identity_resolution"]["identity"]["issuer_domains"] = ["evil.example.test"]
    snapshot = serenity.dispatch(
        argparse.Namespace(
            command="snapshot",
            snapshot_command="security",
            run_id=run["run_id"],
            frozen_packet=str(write_json(tmp_path / "forged-issuer-snapshot.json", packet)),
        ),
        tmp_path,
    )["snapshot"]
    request = {
        "capability_id": "issuer-ir.document",
        "provider_policy": {"providers": ["issuer-ir"], "allow_network": True},
        "provider_parameters": {
            "identity": {"ticker": "NVDA", "cik": "0001045810", "issuer": "NVIDIA Corporation"},
            "origin_binding": {
                "issuer_domain": "evil.example.test",
                "binding_source_ref": snapshot["snapshot_id"],
            },
        },
    }

    with pytest.raises(SerenityError) as raised:
        serenity.resolve_issuer_origin_binding(
            request=request,
            manifest=runtime.read(run["run_id"]),
            root=tmp_path,
            run_id=run["run_id"],
        )

    assert raised.value.exit_code == 3
    assert raised.value.payload["error"]["code"] == "identity_blocked"


def test_manual_evidence_provider_must_own_the_saved_request_capability(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    run_cli("hypothesis", "put", run_id, "--document", str(write_json(tmp_path / "hypotheses.json", hypotheses())))
    request = run_cli(
        "evidence",
        "request",
        run_id,
        "--hypothesis-id",
        "hyp-demand-holds",
        "--capability-id",
        "sec.submissions",
        "--document",
        str(write_json(tmp_path / "request.json", evidence_request())),
    )["request"]
    forged = evidence_result()
    forged["provider"] = "issuer-ir"
    forged["source"] = {
        "uri": "https://investor.example.test/forged-remarks",
        "parameters": {"issuer_domain": "investor.example.test"},
        "canonical_id": "issuer-ir:forged",
    }

    result = run_cli(
        "evidence",
        "read",
        run_id,
        request["request_id"],
        "--document",
        str(write_json(tmp_path / "forged-provider.json", forged)),
        expected_exit=2,
    )

    assert result["error"]["code"] == "usage_or_schema"
    assert not (tmp_path / ".serenity" / "runs" / run_id / "evidence" / "results").exists()


def test_evidence_collect_turns_off_network_before_registry_io_and_persists_typed_not_requested(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run, request_id = live_evidence_run(tmp_path, allow_network=False)
    received: list[dict[str, object]] = []

    class RegistryFixture:
        def collect(self, request_doc: dict[str, object]) -> list[ProviderEnvelope]:
            received.append(request_doc)
            return [ProviderEnvelope.unavailable(provider="bls", provider_version="fixture/1", source_uri="https://fixture.test/bls", fetched_at="2026-08-17T12:00:00Z", request={}, status="not_requested", reason="network disabled", parse={"status": "not_parsed", "transform_version": "fixture/1"})]

    monkeypatch.setattr(serenity, "build_evidence_provider_registry", lambda _root: RegistryFixture())

    result = serenity.dispatch(
        argparse.Namespace(command="evidence", evidence_command="collect", run_id=run["run_id"], request_id=request_id), tmp_path
    )

    assert received[0]["provider_policy"]["allow_network"] is False
    assert result["results"][0]["availability"] == "not_requested"


def test_evidence_collect_provider_failure_does_not_persist_a_partial_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run, request_id = live_evidence_run(tmp_path)

    class RegistryFixture:
        def collect(self, _request_doc: dict[str, object]) -> list[ProviderEnvelope]:
            raise RuntimeError("fixture transport failure")

    monkeypatch.setattr(serenity, "build_evidence_provider_registry", lambda _root: RegistryFixture())

    with pytest.raises(SerenityError) as raised:
        serenity.dispatch(
            argparse.Namespace(command="evidence", evidence_command="collect", run_id=run["run_id"], request_id=request_id), tmp_path
        )

    assert raised.value.exit_code == 4
    assert not (tmp_path / ".serenity" / "runs" / run["run_id"] / "evidence" / "results").exists()


def test_evidence_collect_derives_a_run_cutoff_and_rejects_later_available_envelopes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run, request_id = live_evidence_run(tmp_path, cutoff=None)
    received: list[dict[str, object]] = []

    class RegistryFixture:
        def collect(self, request_doc: dict[str, object]) -> list[ProviderEnvelope]:
            received.append(request_doc)
            return [live_envelope("2026-08-18", "2026-08-18T00:00:00Z")]

    monkeypatch.setattr(serenity, "build_evidence_provider_registry", lambda _root: RegistryFixture())

    with pytest.raises(SerenityError) as raised:
        serenity.dispatch(
            argparse.Namespace(command="evidence", evidence_command="collect", run_id=run["run_id"], request_id=request_id), tmp_path
        )

    assert raised.value.exit_code == 2
    assert received[0]["provider_policy"]["historical_cutoff"] == "2026-08-17T23:59:59Z"
    assert not (tmp_path / ".serenity" / "runs" / run["run_id"] / "evidence" / "results").exists()


def test_evidence_collect_caches_private_raw_bytes_without_serializing_them(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run, request_id = live_evidence_run(tmp_path)
    raw = b"exact private evidence provider bytes"

    class RegistryFixture:
        def collect(self, _request_doc: dict[str, object]) -> list[ProviderEnvelope]:
            return [
                ProviderEnvelope.available(
                    provider="bls",
                    provider_version="fixture/1",
                    source_uri="https://fixture.test/bls",
                    raw_content=raw,
                    data={"observation": 1},
                    fetched_at="2026-08-17T12:00:00Z",
                    request={"series": "CES0000000001"},
                    available_at="2026-08-15T00:00:00Z",
                    source_version="2026-08-15",
                    parse={"status": "parsed", "transform_version": "fixture/1"},
                )
            ]

    monkeypatch.setattr(serenity, "build_evidence_provider_registry", lambda _root: RegistryFixture())

    result = serenity.dispatch(
        argparse.Namespace(command="evidence", evidence_command="collect", run_id=run["run_id"], request_id=request_id), tmp_path
    )

    digest = hashlib.sha256(raw).hexdigest()
    cache_path = tmp_path / ".serenity" / "cache" / "provider-raw" / "sha256" / digest
    result_path = tmp_path / ".serenity" / "runs" / run["run_id"] / "evidence" / "results" / f"{result['results'][0]['result_id']}.json"
    assert cache_path.read_bytes() == raw
    assert result["raw_payload_cache"] == [{"status": "stored", "content_sha256": digest, "cache_path": str(cache_path)}]
    assert raw.decode() not in json.dumps(result)
    assert raw.decode() not in result_path.read_text(encoding="utf-8")


def test_evidence_collect_cache_failure_prevents_result_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run, request_id = live_evidence_run(tmp_path)

    class RegistryFixture:
        def collect(self, _request_doc: dict[str, object]) -> list[ProviderEnvelope]:
            return [live_envelope("2026-08-15", "2026-08-15T00:00:00Z")]

    def fail_cache(*_args: object, **_kwargs: object) -> list[object]:
        raise OSError("fixture cache is unavailable")

    monkeypatch.setattr(serenity, "build_evidence_provider_registry", lambda _root: RegistryFixture())
    monkeypatch.setattr(serenity, "cache_provider_raw_payloads", fail_cache)

    with pytest.raises(SerenityError) as raised:
        serenity.dispatch(
            argparse.Namespace(command="evidence", evidence_command="collect", run_id=run["run_id"], request_id=request_id), tmp_path
        )

    assert raised.value.exit_code == 5
    assert not (tmp_path / ".serenity" / "runs" / run["run_id"] / "evidence" / "results").exists()


def test_evidence_read_document_refuses_available_result_after_the_run_cutoff(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    run_cli("hypothesis", "put", run_id, "--document", str(write_json(tmp_path / "hypotheses.json", hypotheses())))
    request = run_cli(
        "evidence",
        "request",
        run_id,
        "--hypothesis-id",
        "hyp-demand-holds",
        "--capability-id",
        "sec.submissions",
        "--document",
        str(write_json(tmp_path / "request.json", evidence_request())),
    )["request"]
    late = evidence_result()
    late["temporal"]["available_at"] = "2026-08-18T00:00:00Z"

    result = run_cli(
        "evidence", "read", run_id, request["request_id"], "--document", str(write_json(tmp_path / "late-result.json", late)), expected_exit=2
    )

    assert result["error"]["code"] == "usage_or_schema"
    assert not (tmp_path / ".serenity" / "runs" / run_id / "evidence" / "results").exists()


def test_lens_run_uses_only_saved_snapshot_facts_and_rejects_a_conflicting_rerun(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    snapshot = run_cli(
        "snapshot", "security", run_id, "--frozen-packet", str(write_json(tmp_path / "packet.json", frozen_snapshot_packet()))
    )["snapshot"]
    market_cap = next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")
    spec_path = write_json(tmp_path / "lens.json", lens_spec(run_id, market_cap["fact_id"]))

    result = run_cli("lens", "run", run_id, "--spec", str(spec_path))

    assert result["result"]["validity"] == "valid"
    assert result["result"]["output"]["value"] == 1.0
    assert (tmp_path / ".serenity" / "runs" / run_id / "lens-result.json").is_file()
    conflicting = lens_spec(run_id, market_cap["fact_id"])
    conflicting["formula"] = "market_cap / market_cap + 1"
    rerun = run_cli("lens", "run", run_id, "--spec", str(write_json(tmp_path / "other-lens.json", conflicting)), expected_exit=5)
    assert rerun["error"]["code"] == "persistence_conflict"


def test_concurrent_lens_commands_publish_one_attached_artifact_without_a_stale_file(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    snapshot = run_cli(
        "snapshot", "security", run_id, "--frozen-packet", str(write_json(tmp_path / "packet.json", frozen_snapshot_packet()))
    )["snapshot"]
    market_cap = next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")
    first_spec = write_json(tmp_path / "first-lens.json", lens_spec(run_id, market_cap["fact_id"]))
    second = lens_spec(run_id, market_cap["fact_id"])
    second["formula"] = "market_cap / market_cap + 1"
    second_spec = write_json(tmp_path / "second-lens.json", second)
    commands = [
        [sys.executable, str(Path(serenity.__file__)), "lens", "run", run_id, "--spec", str(first_spec)],
        [sys.executable, str(Path(serenity.__file__)), "lens", "run", run_id, "--spec", str(second_spec)],
    ]
    processes = [subprocess.Popen(command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for command in commands]
    completed = [process.communicate() for process in processes]

    assert sorted(process.returncode for process in processes) == [0, 5]
    for stdout, stderr in completed:
        assert stderr == ""
        assert len(stdout.splitlines()) == 1
    manifest = run_cli("run", "status", run_id)["run"]
    attachment = manifest["artifacts"]["lens-result"]
    result_path = tmp_path / attachment["path"]
    assert attachment["content_hash"] == hashlib.sha256(result_path.read_bytes()).hexdigest()


def test_lens_run_validates_the_attached_snapshot_before_arithmetic(run_cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = start_run(run_cli)
    snapshot = run_cli(
        "snapshot", "security", run_id, "--frozen-packet", str(write_json(tmp_path / "packet.json", frozen_snapshot_packet()))
    )["snapshot"]
    market_cap = next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")
    observed: list[str] = []

    def validate(document: dict[str, object]) -> None:
        observed.append(str(document["snapshot_id"]))
        public_validate_security_snapshot(document)

    monkeypatch.setattr(serenity, "validate_security_snapshot", validate)

    result = serenity.dispatch(
        argparse.Namespace(command="lens", lens_command="run", run_id=run_id, spec=str(write_json(tmp_path / "lens.json", lens_spec(run_id, market_cap["fact_id"])))),
        tmp_path,
    )

    assert result["result"]["validity"] == "valid"
    assert observed == [snapshot["snapshot_id"]]


def test_lens_run_refuses_an_unattached_or_hash_tampered_snapshot(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    snapshot = run_cli(
        "snapshot", "security", run_id, "--frozen-packet", str(write_json(tmp_path / "packet.json", frozen_snapshot_packet()))
    )["snapshot"]
    market_cap = next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")
    snapshot_path = tmp_path / ".serenity" / "runs" / run_id / "fact-snapshot.json"
    tampered = json.loads(snapshot_path.read_text(encoding="utf-8"))
    tampered["facts"][0]["value"] = 7
    write_json(snapshot_path, tampered)

    result = run_cli("lens", "run", run_id, "--spec", str(write_json(tmp_path / "lens.json", lens_spec(run_id, market_cap["fact_id"]))), expected_exit=5)

    assert result["error"]["code"] == "persistence_conflict"
    assert not (tmp_path / ".serenity" / "runs" / run_id / "lens-result.json").exists()


def test_schema_invalid_artifact_is_rejected_before_any_run_file_is_written(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    invalid = {"schema_id": "urn:serenity:schema:lens-spec:1", "run_id": run_id}

    result = run_cli("lens", "run", run_id, "--spec", str(write_json(tmp_path / "invalid-lens.json", invalid)), expected_exit=2)

    assert result["error"]["code"] == "usage_or_schema"
    assert not (tmp_path / ".serenity" / "runs" / run_id / "lens-result.json").exists()


def test_decision_validation_does_not_write_and_finalization_seals_then_closes_the_run(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    snapshot = run_cli(
        "snapshot", "security", run_id, "--frozen-packet", str(write_json(tmp_path / "packet.json", frozen_snapshot_packet()))
    )["snapshot"]
    market_cap = next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")
    run_cli("hypothesis", "put", run_id, "--document", str(write_json(tmp_path / "hypotheses.json", hypotheses())))
    request = run_cli(
        "evidence", "request", run_id, "--hypothesis-id", "hyp-demand-holds", "--capability-id", "sec.submissions", "--document", str(write_json(tmp_path / "request.json", evidence_request()))
    )["request"]
    manifest = run_cli("run", "status", run_id)["run"]
    ledger_path = tmp_path / manifest["artifacts"]["hypothesis-ledger"]["path"]
    assert manifest["artifacts"]["hypothesis-ledger"]["content_hash"] == hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    evidence = run_cli(
        "evidence", "read", run_id, request["request_id"], "--document", str(write_json(tmp_path / "evidence.json", evidence_result()))
    )["result"]
    lens = run_cli("lens", "run", run_id, "--spec", str(write_json(tmp_path / "lens.json", lens_spec(run_id, market_cap["fact_id"]))))["result"]
    draft_path = write_json(tmp_path / "decision.json", decision_draft(run_id, evidence["result_id"], lens))
    evidence_manifest = write_json(tmp_path / "evidence-manifest.json", {"evidence_result_ids": [evidence["result_id"]]})

    validated = run_cli("decision", "validate", run_id, "--decision", str(draft_path), "--evidence-manifest", str(evidence_manifest))
    assert validated["validation"]["valid"] is True
    assert not (tmp_path / "records").exists()

    finalized = run_cli(
        "decision", "finalize", run_id, "--decision", str(draft_path), "--analysis", str(write_json(tmp_path / "analysis.json", {"markdown": "# NVDA\n\nConditional entry only."})), "--evidence-manifest", str(evidence_manifest)
    )
    assert finalized["run"]["status"] == "FINALIZED"
    assert finalized["run"]["artifacts"]["research-decision"]["path"] == "records/decisions/lineage-nvda/v001/decision.json"
    assert (tmp_path / "records" / "decisions" / "lineage-nvda" / "v001" / "decision.json").is_file()

    closed = run_cli("run", "close", run_id, "--reason", "decision persisted")
    assert closed["run"]["status"] == "CLOSED"


def test_concurrent_decision_finalize_and_abandon_leave_one_terminal_state_without_an_orphan_pointer(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    snapshot = run_cli(
        "snapshot", "security", run_id, "--frozen-packet", str(write_json(tmp_path / "packet.json", frozen_snapshot_packet()))
    )["snapshot"]
    market_cap = next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")
    run_cli("hypothesis", "put", run_id, "--document", str(write_json(tmp_path / "hypotheses.json", hypotheses())))
    request = run_cli(
        "evidence", "request", run_id, "--hypothesis-id", "hyp-demand-holds", "--capability-id", "sec.submissions", "--document", str(write_json(tmp_path / "request.json", evidence_request()))
    )["request"]
    evidence = run_cli(
        "evidence", "read", run_id, request["request_id"], "--document", str(write_json(tmp_path / "evidence.json", evidence_result()))
    )["result"]
    lens = run_cli("lens", "run", run_id, "--spec", str(write_json(tmp_path / "lens.json", lens_spec(run_id, market_cap["fact_id"]))))["result"]
    decision_path = write_json(tmp_path / "decision.json", decision_draft(run_id, evidence["result_id"], lens))
    evidence_manifest = write_json(tmp_path / "evidence-manifest.json", {"evidence_result_ids": [evidence["result_id"]]})
    commands = [
        [sys.executable, str(Path(serenity.__file__)), "decision", "finalize", run_id, "--decision", str(decision_path), "--analysis", str(write_json(tmp_path / "analysis.json", {"markdown": "# NVDA\n\nConditional entry only."})), "--evidence-manifest", str(evidence_manifest)],
        [sys.executable, str(Path(serenity.__file__)), "run", "abandon", run_id, "--reason", "concurrent fixture"],
    ]
    processes = [subprocess.Popen(command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for command in commands]
    completed = [process.communicate() for process in processes]

    assert sorted(process.returncode for process in processes) == [0, 3]
    for stdout, stderr in completed:
        assert stderr == ""
        assert len(stdout.splitlines()) == 1
    run = run_cli("run", "status", run_id)["run"]
    current = tmp_path / "records" / "decisions" / "lineage-nvda" / "current.json"
    assert run["status"] in {"FINALIZED", "ABANDONED"}
    if run["status"] == "FINALIZED":
        assert current.is_file()
        assert run["artifacts"]["research-decision"]["path"] == "records/decisions/lineage-nvda/v001/decision.json"
    else:
        assert not current.exists()


def test_repeating_an_evidence_request_repairs_a_crash_after_immutable_ledger_publication(run_cli, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = start_run(run_cli)
    run_cli("hypothesis", "put", run_id, "--document", str(write_json(tmp_path / "hypotheses.json", hypotheses())))
    request_path = write_json(tmp_path / "request.json", evidence_request())
    original = RunStore.publish_artifact

    def crash_before_request_publication(self: RunStore, run_id: str, **kwargs: object) -> dict[str, object]:
        if kwargs["name"].startswith("evidence-request-"):
            raise SerenityError("persistence_conflict", "fixture crash after immutable ledger publication", 5)
        return original(self, run_id, **kwargs)

    monkeypatch.setattr(RunStore, "publish_artifact", crash_before_request_publication)
    with pytest.raises(SerenityError) as raised:
        serenity.dispatch(
            argparse.Namespace(
                command="evidence",
                evidence_command="request",
                run_id=run_id,
                hypothesis_id=["hyp-demand-holds"],
                capability_id="sec.submissions",
                document=str(request_path),
            ),
            tmp_path,
    )
    assert raised.value.exit_code == 5
    published = RunStore(tmp_path).read(run_id)
    ledger_attachment = published["artifacts"]["hypothesis-ledger"]
    ledger_path = tmp_path / ledger_attachment["path"]
    assert ledger_path.is_file()
    assert not (tmp_path / ".serenity" / "runs" / run_id / "evidence" / "requests").exists()

    monkeypatch.setattr(RunStore, "publish_artifact", original)
    repaired = serenity.dispatch(
        argparse.Namespace(
            command="evidence",
            evidence_command="request",
            run_id=run_id,
            hypothesis_id=["hyp-demand-holds"],
            capability_id="sec.submissions",
            document=str(request_path),
        ),
        tmp_path,
    )

    ledger_path = tmp_path / repaired["run"]["artifacts"]["hypothesis-ledger"]["path"]
    assert repaired["run"]["artifacts"]["hypothesis-ledger"]["content_hash"] == hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    assert repaired["run"]["artifacts"][repaired["request"]["request_id"]]["schema_id"] == "urn:serenity:schema:evidence-request:1"


def test_concurrent_evidence_requests_cas_the_immutable_ledger_then_retry_without_losing_the_winner(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    run_cli("hypothesis", "put", run_id, "--document", str(write_json(tmp_path / "hypotheses.json", hypotheses())))
    request_path = write_json(tmp_path / "request.json", evidence_request())
    hypothesis_ids = ["hyp-demand-holds", "hyp-demand-cools"]
    commands = [
        [sys.executable, str(Path(serenity.__file__)), "evidence", "request", run_id, "--hypothesis-id", hypothesis_id, "--capability-id", "sec.submissions", "--document", str(request_path)]
        for hypothesis_id in hypothesis_ids
    ]
    processes = [subprocess.Popen(command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) for command in commands]
    completed = [process.communicate() for process in processes]

    assert all(process.returncode in {0, 5} for process in processes)
    payloads = [json.loads(stdout) for stdout, stderr in completed]
    assert all(stderr == "" for _stdout, stderr in completed)
    successful_requests = {payload["request"]["request_id"] for payload, process in zip(payloads, processes) if process.returncode == 0}
    for hypothesis_id, payload, process in zip(hypothesis_ids, payloads, processes):
        if process.returncode == 5:
            assert payload["error"]["code"] == "persistence_conflict"
            successful_requests.add(
                run_cli(
                    "evidence", "request", run_id, "--hypothesis-id", hypothesis_id, "--capability-id", "sec.submissions", "--document", str(request_path)
                )["request"]["request_id"]
            )
    manifest = run_cli("run", "status", run_id)["run"]
    attachment = manifest["artifacts"]["hypothesis-ledger"]
    ledger_path = tmp_path / attachment["path"]
    assert attachment["content_hash"] == hashlib.sha256(ledger_path.read_bytes()).hexdigest()
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    requested_ids = {request_id for hypothesis in ledger["hypotheses"] for request_id in hypothesis["requested_evidence_ids"]}
    assert requested_ids == successful_requests
    assert requested_ids <= set(manifest["artifacts"])
    attached_bytes = ledger_path.read_bytes()
    stale = hypotheses()
    stale[0]["status"] = "supported"
    run_cli(
        "hypothesis", "put", run_id, "--expected-revision", "1", "--document", str(write_json(tmp_path / "stale-hypotheses.json", stale)), expected_exit=5
    )
    assert ledger_path.read_bytes() == attached_bytes


def test_outcomes_registration_is_explicit_and_refresh_only_appends_measurements(run_cli, tmp_path: Path) -> None:
    rejected = run_cli(
        "outcomes",
        "register",
        "--decision",
        str(write_json(tmp_path / "arbitrary-decision.json", finalized_outcome_decision())),
        "--benchmark-json",
        str(write_json(tmp_path / "benchmark.json", {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust"})),
        "--checkpoint-schedule-json",
        str(write_json(tmp_path / "schedule.json", [{"kind": "earnings", "due_on": "2026-11-18"}])),
        expected_exit=2,
    )
    assert rejected["error"]["code"] == "usage_or_schema"

    run_id = start_run(run_cli)
    snapshot = run_cli(
        "snapshot", "security", run_id, "--frozen-packet", str(write_json(tmp_path / "packet.json", frozen_snapshot_packet()))
    )["snapshot"]
    market_cap = next(fact for fact in snapshot["facts"] if fact["name"] == "market_cap")
    run_cli("hypothesis", "put", run_id, "--document", str(write_json(tmp_path / "hypotheses.json", hypotheses())))
    request = run_cli(
        "evidence", "request", run_id, "--hypothesis-id", "hyp-demand-holds", "--capability-id", "sec.submissions", "--document", str(write_json(tmp_path / "request.json", evidence_request()))
    )["request"]
    evidence = run_cli(
        "evidence", "read", run_id, request["request_id"], "--document", str(write_json(tmp_path / "evidence.json", evidence_result()))
    )["result"]
    lens = run_cli("lens", "run", run_id, "--spec", str(write_json(tmp_path / "lens.json", lens_spec(run_id, market_cap["fact_id"]))))["result"]
    decision_path = write_json(tmp_path / "decision.json", decision_draft(run_id, evidence["result_id"], lens))
    evidence_manifest = write_json(tmp_path / "evidence-manifest.json", {"evidence_result_ids": [evidence["result_id"]]})
    finalized = run_cli(
        "decision", "finalize", run_id, "--decision", str(decision_path), "--analysis", str(write_json(tmp_path / "analysis.json", {"markdown": "# NVDA\n\nConditional entry only."})), "--evidence-manifest", str(evidence_manifest)
    )

    registered = run_cli(
        "outcomes",
        "register",
        "--decision",
        finalized["finalization"]["decision_path"],
        "--benchmark-json",
        str(write_json(tmp_path / "benchmark.json", {"ticker": "SPY", "name": "SPDR S&P 500 ETF Trust"})),
        "--checkpoint-schedule-json",
        str(write_json(tmp_path / "schedule.json", [{"kind": "earnings", "due_on": "2026-11-18"}])),
    )["record"]
    assert registered["observations"] == []

    refreshed = run_cli(
        "outcomes", "refresh", registered["record_id"], "--observation", str(write_json(tmp_path / "observation.json", outcome_observation()))
    )["record"]
    assert len(refreshed["observations"]) == 1
    assert refreshed["observations"][0]["condition_hit_is_trade"] is False

    record_path = tmp_path / "records" / "prospective" / registered["record_id"] / "record.json"
    corrupted = json.loads(record_path.read_text(encoding="utf-8"))
    corrupted["content_hash"] = "0" * 64
    write_json(record_path, corrupted)
    conflict = run_cli(
        "outcomes",
        "refresh",
        registered["record_id"],
        "--observation",
        str(write_json(tmp_path / "second-observation.json", {**outcome_observation(), "observation_id": "nvda-2026-12-17-close", "as_of": "2026-12-17"})),
        expected_exit=5,
    )
    assert conflict["error"]["code"] == "persistence_conflict"


def test_outcomes_refresh_preserves_the_typed_missing_record_exit(run_cli, tmp_path: Path) -> None:
    result = run_cli(
        "outcomes",
        "refresh",
        "prospective-missing",
        "--observation",
        str(write_json(tmp_path / "observation.json", outcome_observation())),
        expected_exit=3,
    )

    assert result["error"]["code"] == "record_not_found"
    assert result["error"]["exit_code"] == 3


def test_graph_put_validates_and_attaches_a_typed_sector_graph(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    run_cli("hypothesis", "put", run_id, "--document", str(write_json(tmp_path / "hypotheses.json", hypotheses())))
    request = run_cli(
        "evidence",
        "request",
        run_id,
        "--hypothesis-id",
        "hyp-demand-holds",
        "--capability-id",
        "sec.submissions",
        "--document",
        str(write_json(tmp_path / "request.json", evidence_request())),
    )["request"]
    evidence = run_cli(
        "evidence",
        "read",
        run_id,
        request["request_id"],
        "--document",
        str(write_json(tmp_path / "evidence.json", evidence_result())),
    )["result"]
    second_evidence = evidence_result()
    second_evidence["source"]["uri"] = "https://www.sec.gov/Archives/edgar/data/1045810/example-second.txt"
    second_evidence["source"]["canonical_id"] = "sec:0001045810:second"
    second_evidence["raw_content_sha256"] = "c" * 64
    second_evidence["value"] = {"named_input": "second input"}
    second = run_cli(
        "evidence",
        "read",
        run_id,
        request["request_id"],
        "--document",
        str(write_json(tmp_path / "second-evidence.json", second_evidence)),
    )["result"]
    graph = sector_graph(run_id)

    def replace_evidence_refs(value: object) -> object:
        if isinstance(value, list):
            return [replace_evidence_refs(item) for item in value]
        if isinstance(value, dict):
            return {key: replace_evidence_refs(item) for key, item in value.items()}
        if value == "result-demand":
            return evidence["result_id"]
        if value == "result-input":
            return second["result_id"]
        return value

    graph = replace_evidence_refs(graph)

    result = run_cli("graph", "put", run_id, "--file", str(write_json(tmp_path / "graph.json", graph)))

    assert result["graph"]["graph_id"] == "graph-nvda-input"
    assert result["run"]["artifacts"]["sector-graph"]["path"].endswith("sector-graph.json")
    assert (tmp_path / ".serenity" / "runs" / run_id / "sector-graph.json").is_file()


def test_active_run_pointer_blocks_a_second_open_run_and_clears_on_abandon(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    pointer_path = tmp_path / ".serenity" / "active-run.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    assert pointer["run_id"] == run_id
    assert pointer["status"] == "OPEN"
    assert len(pointer["content_hash"]) == 64

    blocked = run_cli(
        "run",
        "start",
        "--mode",
        "macro-event",
        "--question",
        "What changed?",
        "--as-of",
        "2026-08-17",
        expected_exit=3,
    )
    assert blocked["error"]["code"] == "invalid_lifecycle"

    run_cli("run", "abandon", run_id, "--reason", "fixture complete")
    assert not pointer_path.exists()
    restarted = start_run(run_cli)
    assert restarted != run_id


def test_corrupt_active_run_pointer_is_a_persistence_conflict(run_cli, tmp_path: Path) -> None:
    start_run(run_cli)
    pointer_path = tmp_path / ".serenity" / "active-run.json"
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["run_id"] = "run-outside-root"
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")

    result = run_cli("run", "status", expected_exit=5)

    assert result["error"]["code"] == "persistence_conflict"


def test_missing_active_pointer_with_an_open_manifest_requires_repair(run_cli, tmp_path: Path) -> None:
    start_run(run_cli)
    (tmp_path / ".serenity" / "active-run.json").unlink()

    result = run_cli("run", "status", expected_exit=5)

    assert result["error"]["code"] == "persistence_conflict"
    assert "repair" in result["error"]["message"]


def test_live_snapshot_reports_why_sec_identity_was_unavailable_instead_of_only_its_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = RunStore(tmp_path).start(
        mode="single-name",
        question="What evidence would change the NVDA thesis?",
        subjects=["NVDA"],
        as_of="2026-08-17",
        source_policy={"policy_id": "live-free-v1", "allow_network": True, "historical_cutoff": "2026-08-17T23:59:59Z"},
    )

    def blocked_identity(
        *, ticker: str, as_of: str, historical_cutoff: str, allowed_providers: frozenset[str]
    ) -> tuple[dict[str, object], None, None]:
        return (
            {
                "schema_id": "urn:serenity:identity-resolution:1",
                "status": "invalid",
                "identity": None,
                "rejection": {
                    "code": "sec_directory_unavailable",
                    "reason": "SEC company_tickers could not be loaded",
                    "category": "availability",
                    "retryable": True,
                    "detail": "SEC company_tickers unavailable: HTTP Error 403: Forbidden",
                    "http_status": 403,
                },
                "provider_envelopes": [],
            },
            None,
            None,
        )

    monkeypatch.setattr(serenity, "build_live_snapshot_inputs", blocked_identity)

    with pytest.raises(SerenityError) as raised:
        serenity.dispatch(
            argparse.Namespace(command="snapshot", snapshot_command="security", run_id=run["run_id"], frozen_packet=None), tmp_path
        )

    error = raised.value.payload["error"]
    assert (raised.value.exit_code, error["code"], error["message"]) == (3, "identity_blocked", "sec_directory_unavailable")
    assert error["category"] == "availability"
    assert error["retryable"] is True
    assert error["http_status"] == 403
    assert error["detail"] == "SEC company_tickers unavailable: HTTP Error 403: Forbidden"
    assert error["reason"] == "SEC company_tickers could not be loaded"


def test_frozen_snapshot_carries_the_identity_rejection_diagnosis_into_the_cli_error(run_cli, tmp_path: Path) -> None:
    run_id = start_run(run_cli)
    packet = frozen_snapshot_packet()
    packet["identity_resolution"] = {
        "schema_id": "urn:serenity:identity-resolution:1",
        "status": "invalid",
        "identity": None,
        "rejection": {
            "code": "sec_submission_unavailable",
            "reason": "SEC submissions could not be loaded",
            "category": "availability",
            "retryable": True,
            "detail": "SEC submissions unavailable: HTTP Error 503: Service Unavailable",
            "http_status": 503,
        },
        "provider_envelopes": [],
    }

    result = run_cli("snapshot", "security", run_id, "--frozen-packet", str(write_json(tmp_path / "blocked.json", packet)), expected_exit=3)

    error = result["error"]
    assert (error["code"], error["message"]) == ("identity_blocked", "sec_submission_unavailable")
    assert error["category"] == "availability"
    assert error["retryable"] is True
    assert error["http_status"] == 503


def test_issuer_without_a_declared_website_records_the_absence_instead_of_erroring_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = RunStore(tmp_path)
    run = runtime.start(
        mode="single-name",
        question="What did management disclose about the operating constraint?",
        subjects=["NVDA"],
        as_of="2026-08-17",
        source_policy={
            "policy_id": "live-issuer-ir-v1",
            "allow_network": True,
            "historical_cutoff": "2026-08-17T23:59:59Z",
            "allowed_providers": ["issuer-ir", "openfigi", "sec", "yfinance"],
        },
    )
    packet = frozen_snapshot_packet()
    submissions_raw = json.dumps(
        {"cik": "0001045810", "name": "NVIDIA Corporation", "tickers": ["NVDA"], "exchanges": ["Nasdaq"]}
    ).encode()
    identity_envelopes = tuple(
        ProviderEnvelope.available(
            provider=provider,
            provider_version="fixture/1",
            source_uri=source_uri,
            raw_content=raw_content,
            data={},
            fetched_at="2026-08-17T12:00:00Z",
            request={"ticker": "NVDA"},
            available_at="2026-08-17T12:00:00Z",
            source_version="fixture/1",
            parse={"status": "parsed", "transform_version": "fixture/1"},
        )
        for provider, source_uri, raw_content in (
            ("sec.company_tickers", "https://www.sec.gov/files/company_tickers.json", b"exact SEC directory bytes"),
            ("sec.submissions", "https://data.sec.gov/submissions/CIK0001045810.json", submissions_raw),
            ("openfigi.mapping", "https://api.openfigi.com/v3/mapping", b"exact OpenFIGI bytes"),
        )
    )
    market = ProviderEnvelope.available(
        provider="yfinance",
        provider_version="fixture/1",
        source_uri="https://fixture.test/NVDA",
        raw_content=b"exact market bytes",
        data=packet["market_envelope"]["data"],
        fetched_at="2026-08-17T12:00:00Z",
        request={"ticker": "NVDA"},
        available_at="2026-08-17T12:00:00Z",
        source_version="fixture/1",
        parse={"status": "parsed", "transform_version": "fixture/1"},
    )
    monkeypatch.setattr(
        serenity,
        "build_live_snapshot_inputs",
        lambda **_kwargs: (IdentityResolution(packet["identity_resolution"], identity_envelopes), market, None),
    )
    snapshot = serenity.dispatch(
        argparse.Namespace(command="snapshot", snapshot_command="security", run_id=run["run_id"], frozen_packet=None), tmp_path
    )["snapshot"]
    artifacts = ResearchArtifactStore(tmp_path / ".serenity" / "runs" / run["run_id"])
    prepared_ledger = artifacts.prepare_hypotheses(hypotheses())
    run = runtime.publish_or_refresh_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        expected_attachment=None,
        path=prepared_ledger.ledger_path,
        content=prepared_ledger.ledger_content,
        schema_id=prepared_ledger.ledger["schema_id"],
        phase="hypotheses_updated",
    )
    prepared = artifacts.prepare_evidence_request(
        hypothesis_ids=["hyp-demand-holds"],
        capability_id="issuer-ir.document",
        request={
            "question": "What operating constraint did management disclose?",
            "evidence_type": "issuer-narrative",
            "provider_policy": {"providers": ["issuer-ir"], "allow_network": True, "historical_cutoff": "2026-08-17T23:59:59Z"},
            "acceptance_criteria": ["Preserve official source provenance."],
            "requested_at": "2026-08-17T00:00:00Z",
            "provider_parameters": {
                "identity": {"ticker": "NVDA", "cik": "0001045810", "issuer": "NVIDIA Corporation"},
                "document": {"url": "https://investor.nvidia.com/prepared-remarks", "kind": "prepared_remarks"},
                "origin_binding": {"issuer_domain": "investor.nvidia.com", "binding_source_ref": snapshot["snapshot_id"]},
            },
        },
    )
    run = runtime.publish_or_refresh_artifact(
        run["run_id"],
        name="hypothesis-ledger",
        expected_attachment=run["artifacts"]["hypothesis-ledger"],
        path=prepared.ledger_path,
        content=prepared.ledger_content,
        schema_id=prepared.ledger["schema_id"],
        phase="hypotheses_updated",
    )
    run = runtime.publish_artifact(
        run["run_id"],
        name=prepared.request["request_id"],
        path=prepared.request_path,
        content=prepared.request_content,
        schema_id=prepared.request["schema_id"],
        phase="evidence_requested",
    )

    collected = serenity.dispatch(
        argparse.Namespace(
            command="evidence", evidence_command="collect", run_id=run["run_id"], request_id=prepared.request["request_id"]
        ),
        tmp_path,
    )

    assert [result["availability"] for result in collected["results"]] == ["not_disclosed"]
    assert [result["provider"] for result in collected["results"]] == ["issuer-ir"]
    assert "issuer declares no website" in collected["results"][0]["error"]["reason"]


def _recorded_evidence_request(tmp_path: Path, run_cli) -> tuple[str, str]:
    run_id = start_run(run_cli)
    run_cli("hypothesis", "put", run_id, "--document", str(write_json(tmp_path / "hyp.json", hypotheses())))
    request = run_cli(
        "evidence", "request", run_id,
        "--hypothesis-id", "hyp-demand-holds",
        "--capability-id", "sec.submissions",
        "--document", str(write_json(tmp_path / "req.json", evidence_request())),
    )["request"]
    return run_id, request["request_id"]


def _large_evidence_result() -> dict[str, object]:
    body = "Item 1A. Risk Factors\n\n" + ("Supply concentration remains material. " * 4000) + "A single foundry supplies the leading node.\n"
    return {**evidence_result(), "value": {"result": {"section": "risk_factors", "text": body}}}


def test_evidence_read_answers_with_the_value_shape_rather_than_the_value(tmp_path: Path, run_cli) -> None:
    """A single risk-factors section measured 91k-144k characters. Printing it by
    default spends the caller's context on text it has not yet decided to read."""

    run_id, request_id = _recorded_evidence_request(tmp_path, run_cli)
    result = run_cli("evidence", "read", run_id, request_id, "--document", str(write_json(tmp_path / "big.json", _large_evidence_result())))["result"]

    summary = run_cli("evidence", "read", run_id, result["result_id"])["result"]

    assert summary["result_id"] == result["result_id"]
    assert summary["availability"] == "available"
    assert summary["raw_content_sha256"] == result["raw_content_sha256"]
    assert summary["source"]["uri"] == result["source"]["uri"]
    assert summary["value"]["characters"] > 100_000
    assert summary["value"]["text_paths"][0]["path"] == "value.result.text"
    assert "Supply concentration" not in json.dumps(summary)


def test_evidence_read_value_opts_into_the_whole_document(tmp_path: Path, run_cli) -> None:
    """Persisting a document answers with its shape too: the caller that just
    supplied the value gains nothing from having it read back at it."""

    run_id, request_id = _recorded_evidence_request(tmp_path, run_cli)
    stored = run_cli("evidence", "read", run_id, request_id, "--document", str(write_json(tmp_path / "big.json", _large_evidence_result())))["result"]

    full = run_cli("evidence", "read", run_id, stored["result_id"], "--value")["result"]

    assert "Supply concentration" not in json.dumps(stored)
    assert full["value"] == _large_evidence_result()["value"]
    assert full["content_hash"] == stored["content_hash"]


def test_evidence_read_match_returns_spans_that_verify_against_the_saved_artifact(tmp_path: Path, run_cli) -> None:
    """An excerpt without offsets is an assertion; with them it is a citation the
    next reader can check against the stored bytes."""

    run_id, request_id = _recorded_evidence_request(tmp_path, run_cli)
    stored = run_cli("evidence", "read", run_id, request_id, "--document", str(write_json(tmp_path / "big.json", _large_evidence_result())))["result"]

    matched = run_cli("evidence", "read", run_id, stored["result_id"], "--match", "single foundry", "--context", "20")

    saved = json.loads((tmp_path / ".serenity" / "runs" / run_id / "evidence" / "results" / f"{stored['result_id']}.json").read_text())
    span = matched["matches"][0]
    assert span["path"] == "value.result.text"
    assert saved["value"]["result"]["text"][span["start"] : span["end"]] == "single foundry"
    assert "single foundry" in span["excerpt"]
    assert matched["match_count"] == 1


def test_evidence_read_match_bounds_how_many_spans_it_returns(tmp_path: Path, run_cli) -> None:
    run_id, request_id = _recorded_evidence_request(tmp_path, run_cli)
    stored = run_cli("evidence", "read", run_id, request_id, "--document", str(write_json(tmp_path / "big.json", _large_evidence_result())))["result"]

    matched = run_cli("evidence", "read", run_id, stored["result_id"], "--match", "Supply concentration", "--max-spans", "3")

    assert len(matched["matches"]) == 3
    assert matched["match_count"] == 4000
    assert matched["truncated"] is True


def test_an_unparsable_match_pattern_is_refused_by_name(tmp_path: Path, run_cli) -> None:
    run_id, request_id = _recorded_evidence_request(tmp_path, run_cli)
    stored = run_cli("evidence", "read", run_id, request_id, "--document", str(write_json(tmp_path / "big.json", _large_evidence_result())))["result"]

    failure = run_cli("evidence", "read", run_id, stored["result_id"], "--match", "unbalanced(", expected_exit=2)

    assert "--match" in failure["error"]["message"]
