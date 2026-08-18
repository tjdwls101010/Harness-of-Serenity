"""One real provider envelope, through the real registry, into a saved result.

Every layer here was covered on its own and the whole path was still broken:
the registry tests asserted a hand-built envelope's provider name as correct,
and the research tests hand-authored the owner name and took the non-envelope
path. Nothing joined the two, so the name a provider stamps was never compared
against the name the artifact store accepts.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

import serenity
from serenity_core.providers.filings import FilingsProvider
from serenity_core.providers.registry import EvidenceProviderRegistry
from serenity_core.research import ResearchArtifactStore
from serenity_core.runtime import RunStore


FROZEN_NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)
IDENTITY = {"ticker": "AAOI", "cik": "0001158114", "issuer": "APPLIED OPTOELECTRONICS, INC."}


class RiskFactorsBackend:
    """Stands in for EDGAR only; the provider above it is the real one."""

    def __init__(self) -> None:
        self.requests: list[dict[str, object]] = []

    def execute(self, request: dict[str, object]) -> dict[str, object]:
        self.requests.append(dict(request))
        return {
            "filing": {
                "form": "10-K",
                "filing_date": "2026-03-05",
                "report_date": "2025-12-31",
                "accession": "0001158114-26-000012",
                "primary_document": "aaoi-20251231.htm",
                "acceptance_datetime": "2026-03-05T16:31:00Z",
            },
            "data": {"section": "risk_factors", "text": "Our transceiver supply depends on a narrow set of laser vendors."},
            "raw_content": b"<html>exact 10-K bytes</html>",
        }


def collect_through_the_cli(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, run_id: str, request_id: str, backend: object, value: bool = False
) -> list[dict[str, object]]:
    """Drive the one production call site that builds real providers."""

    monkeypatch.setattr(
        serenity,
        "build_evidence_provider_registry",
        lambda _root: EvidenceProviderRegistry(
            provider_factories={"sec": lambda **_kwargs: FilingsProvider(backend=backend, clock=lambda: FROZEN_NOW)},
            clock=lambda: FROZEN_NOW,
        ),
    )
    return serenity.dispatch(
        argparse.Namespace(command="evidence", evidence_command="collect", run_id=run_id, request_id=request_id, value=value), tmp_path
    )["results"]


@pytest.fixture
def prepared_run(tmp_path: Path) -> tuple[ResearchArtifactStore, dict[str, object]]:
    runtime = RunStore(tmp_path)
    manifest = runtime.start(
        mode="single-name",
        question="Which disclosed dependency could break the AAOI thesis?",
        subjects=["AAOI"],
        as_of="2026-08-17",
        source_policy={"policy_id": "live-sec-v1", "allow_network": True, "historical_cutoff": "2026-08-17T23:59:59Z", "allowed_providers": ["sec"]},
    )
    store = ResearchArtifactStore(tmp_path / ".serenity" / "runs" / manifest["run_id"])
    prepared_ledger = store.prepare_hypotheses(
        [
            {
                "hypothesis_id": "hyp-supply-concentrated",
                "statement": "A narrow laser-vendor set concentrates AAOI's supply risk.",
                "predictions": ["The 10-K names vendor concentration as a risk factor."],
                "falsifier": "The 10-K names a diversified vendor base.",
                "status": "open",
                "supporting_fact_refs": [],
                "contradicting_fact_refs": [],
                "requested_evidence_ids": [],
            },
            {
                "hypothesis_id": "hyp-supply-diversified",
                "statement": "AAOI's laser sourcing is diversified enough to absorb a vendor loss.",
                "predictions": ["The 10-K names alternate qualified vendors."],
                "falsifier": "The 10-K names a single-source dependency.",
                "status": "open",
                "supporting_fact_refs": [],
                "contradicting_fact_refs": [],
                "requested_evidence_ids": [],
            },
        ]
    )
    run = runtime.publish_or_refresh_artifact(
        manifest["run_id"],
        name="hypothesis-ledger",
        expected_attachment=None,
        path=prepared_ledger.ledger_path,
        content=prepared_ledger.ledger_content,
        schema_id=prepared_ledger.ledger["schema_id"],
        phase="hypotheses_updated",
    )
    prepared = store.prepare_evidence_request(
        hypothesis_ids=["hyp-supply-concentrated"],
        capability_id="sec.filing-section",
        request={
            "question": "Which risk factors does the latest 10-K disclose?",
            "evidence_type": "filing-narrative",
            "provider_policy": {"providers": ["sec"], "allow_network": True, "historical_cutoff": "2026-08-17T23:59:59Z"},
            "acceptance_criteria": ["Preserve the accession and the disclosed text."],
            "requested_at": "2026-08-17T00:00:00Z",
            "provider_parameters": {"identity": dict(IDENTITY), "form": "10-K", "named": "risk_factors"},
        },
    )
    runtime.publish_or_refresh_artifact(
        manifest["run_id"],
        name="hypothesis-ledger",
        expected_attachment=run["artifacts"]["hypothesis-ledger"],
        path=prepared.ledger_path,
        content=prepared.ledger_content,
        schema_id=prepared.ledger["schema_id"],
        phase="hypotheses_updated",
    )
    runtime.publish_artifact(
        manifest["run_id"],
        name=prepared.request["request_id"],
        path=prepared.request_path,
        content=prepared.request_content,
        schema_id=prepared.request["schema_id"],
        phase="evidence_requested",
    )
    return store, prepared.request


def test_a_real_sec_envelope_survives_the_registry_and_becomes_a_saved_evidence_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prepared_run: tuple[ResearchArtifactStore, dict[str, object]]
) -> None:
    store, request = prepared_run
    backend = RiskFactorsBackend()

    results = collect_through_the_cli(
        tmp_path, monkeypatch, run_id=store.run_id, request_id=request["request_id"], backend=backend, value=True
    )

    assert [entry["capability"] for entry in backend.requests] == ["section"]
    assert [result["provider"] for result in results] == ["sec.filings"]
    assert [result["availability"] for result in results] == ["available"]
    assert results[0]["value"]["result"]["text"].startswith("Our transceiver supply")
    assert store.read_evidence_result(results[0]["result_id"]) == results[0]


def test_collect_withholds_a_narrative_value_it_has_nonetheless_stored_in_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prepared_run: tuple[ResearchArtifactStore, dict[str, object]]
) -> None:
    """The stored artifact stays complete and hash-anchored; only the read view is
    bounded. Otherwise collecting a section spends the caller's context before it
    has decided the section is worth reading."""

    store, request = prepared_run

    results = collect_through_the_cli(
        tmp_path, monkeypatch, run_id=store.run_id, request_id=request["request_id"], backend=RiskFactorsBackend()
    )

    assert "Our transceiver supply" not in json.dumps(results)
    assert results[0]["value"]["text_paths"][0]["path"] == "value.result.text"
    assert store.read_evidence_result(results[0]["result_id"])["value"]["result"]["text"].startswith("Our transceiver supply")


def test_an_unavailable_real_envelope_is_saved_with_the_reason_that_forces_a_blocked_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, prepared_run: tuple[ResearchArtifactStore, dict[str, object]]
) -> None:
    store, request = prepared_run

    class RefusingBackend:
        def execute(self, _request: dict[str, object]) -> object:
            raise OSError("EDGAR refused the request")

    results = collect_through_the_cli(
        tmp_path, monkeypatch, run_id=store.run_id, request_id=request["request_id"], backend=RefusingBackend()
    )

    assert [result["availability"] for result in results] == ["unavailable"]
    assert results[0]["value"] is None
    assert "EDGAR refused the request" in results[0]["error"]["reason"]
