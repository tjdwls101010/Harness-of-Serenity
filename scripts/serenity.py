#!/usr/bin/env python3
"""The single public runtime interface for Harness of Serenity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, NoReturn
from urllib.parse import urlparse

from serenity_core.research import (
    ResearchArtifactConflictError,
    ResearchArtifactStore,
    ResearchArtifactValidationError,
    load_evidence_catalog,
)
from serenity_core.runtime import RUN_MODES, RunStore, SerenityError, parse_as_of, parse_instant
from serenity_core.lens import run_lens
from serenity_core.schema import SchemaViolation, validate_document
from serenity_core.decision import finalize_decision, validate_decision
from serenity_core.outcomes import OutcomesError, OutcomesStore
from serenity_core.sector_graph import SectorGraphValidationError, build_sector_graph
from serenity_core.snapshot import SnapshotBlockedError, SnapshotIntegrityError, build_security_snapshot, validate_security_snapshot
from serenity_core.identity import IdentityResolver
from serenity_core.providers.openfigi import OpenFigiProvider
from serenity_core.providers.rs_rating import RsRatingProvider
from serenity_core.providers.sec import SecIdentityProvider
from serenity_core.providers.yfinance import YFinanceProvider
from serenity_core.providers.base import ProviderEnvelope
from serenity_core.providers.issuer_ir import VerifiedIssuerOrigin
from serenity_core.providers.registry import EvidenceProviderRegistry, ProviderRegistryValidationError
from serenity_core.raw_cache import RawPayloadConflictError, cache_provider_raw_payloads


class JsonArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("formatter_class", argparse.RawDescriptionHelpFormatter)
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> NoReturn:
        raise SerenityError("usage_or_schema", message, 2)


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def load_json_value(path: str, *, label: str) -> Any:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SerenityError("usage_or_schema", f"{label} must be readable JSON: {path}", 2) from exc
    return value


def load_json_document(path: str, *, label: str) -> dict[str, Any]:
    value = load_json_value(path, label=label)
    if not isinstance(value, dict):
        raise SerenityError("usage_or_schema", f"{label} must be a JSON object: {path}", 2)
    return value


def research_store(store: RunStore, root: Path, run_id: str) -> ResearchArtifactStore:
    manifest = store.read(run_id)
    if manifest.get("status") != "OPEN":
        raise SerenityError("invalid_lifecycle", f"research artifacts require an OPEN run: {run_id}", 3, run_id=run_id)
    try:
        return ResearchArtifactStore(root / ".serenity" / "runs" / run_id)
    except ResearchArtifactValidationError as exc:
        raise SerenityError("usage_or_schema", str(exc), 2, run_id=run_id) from exc


def publish_run_document(
    store: RunStore,
    *,
    run_id: str,
    name: str,
    filename: str,
    document: dict[str, Any],
    phase: str,
) -> dict[str, Any]:
    path = store.runs_dir / run_id / filename
    schema_id = document.get("schema_id")
    if not isinstance(schema_id, str):
        raise SerenityError("usage_or_schema", f"artifact requires schema_id: {filename}", 2)
    try:
        validate_document(document, schema_id)
    except SchemaViolation as exc:
        raise SerenityError("usage_or_schema", f"artifact is not schema-valid: {filename}: {exc}", 2) from exc
    content = (json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return store.publish_artifact(run_id, name=name, path=path, content=content, schema_id=schema_id, phase=phase)


def load_project_env(root: Path) -> None:
    env_path = root / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)
    except Exception as exc:
        raise SerenityError("provider_failure", "project .env could not be loaded for live providers", 4) from exc


_SNAPSHOT_IDENTITY_PROVIDERS = frozenset({"sec", "openfigi"})
_SNAPSHOT_REQUIRED_PROVIDERS = frozenset({*_SNAPSHOT_IDENTITY_PROVIDERS, "yfinance"})
_SNAPSHOT_DEFAULT_PROVIDERS = frozenset({*_SNAPSHOT_REQUIRED_PROVIDERS, "ibd-rs-rating"})


def run_historical_cutoff(manifest: dict[str, Any]) -> str:
    source_policy = manifest.get("source_policy")
    if not isinstance(source_policy, dict):
        raise SerenityError("usage_or_schema", "run source_policy must be an object", 2, run_id=manifest.get("run_id"))
    cutoff = source_policy.get("historical_cutoff") or f"{manifest['as_of']}T23:59:59Z"
    cutoff = parse_instant(str(cutoff))
    as_of_cutoff = f"{manifest['as_of']}T23:59:59Z"
    if cutoff > as_of_cutoff:
        raise SerenityError("usage_or_schema", "run historical_cutoff cannot be after the run as_of day", 2, run_id=manifest.get("run_id"))
    return cutoff


def live_snapshot_policy(manifest: dict[str, Any]) -> tuple[str, frozenset[str]]:
    source_policy = manifest.get("source_policy")
    if not isinstance(source_policy, dict):
        raise SerenityError("usage_or_schema", "run source_policy must be an object", 2, run_id=manifest.get("run_id"))
    cutoff = run_historical_cutoff(manifest)
    configured = source_policy.get("allowed_providers")
    if configured is None:
        allowed = _SNAPSHOT_DEFAULT_PROVIDERS
    elif isinstance(configured, list) and all(isinstance(provider, str) and provider for provider in configured):
        allowed = frozenset(configured)
    else:
        raise SerenityError("usage_or_schema", "run source_policy.allowed_providers must be a string array", 2, run_id=manifest.get("run_id"))
    missing_identity = sorted(_SNAPSHOT_IDENTITY_PROVIDERS - allowed)
    if missing_identity:
        raise SerenityError("identity_blocked", f"live snapshot identity providers are not allowed: {', '.join(missing_identity)}", 3, run_id=manifest.get("run_id"))
    if "yfinance" not in allowed:
        raise SerenityError("provider_failure", "live snapshot market provider is not allowed: yfinance", 4, run_id=manifest.get("run_id"))
    return cutoff, allowed


def require_evidence_available_by_cutoff(evidence: dict[str, Any], *, cutoff: str, label: str) -> None:
    availability = evidence.get("status", evidence.get("availability"))
    if availability != "available":
        return
    temporal = evidence.get("temporal")
    available_at = temporal.get("available_at") if isinstance(temporal, dict) else None
    if not isinstance(available_at, str):
        raise SerenityError("usage_or_schema", f"available {label} requires temporal.available_at", 2)
    if parse_instant(available_at) > cutoff:
        raise SerenityError("usage_or_schema", f"available {label} was not available by the run historical cutoff", 2)


def load_attached_security_snapshot(*, manifest: dict[str, Any], root: Path, run_id: str) -> dict[str, Any]:
    snapshot_path = root / ".serenity" / "runs" / run_id / "fact-snapshot.json"
    artifact = manifest.get("artifacts", {}).get("fact-snapshot") if isinstance(manifest.get("artifacts"), dict) else None
    expected_path = str(snapshot_path.relative_to(root))
    if not isinstance(artifact, dict) or artifact.get("path") != expected_path or artifact.get("schema_id") != "urn:serenity:schema:fact-snapshot:2":
        raise SerenityError("persistence_conflict", "fact snapshot is not attached to the run manifest", 5, run_id=run_id)
    try:
        raw = snapshot_path.read_bytes()
    except OSError as exc:
        raise SerenityError("persistence_conflict", "attached fact snapshot cannot be read", 5, run_id=run_id) from exc
    if artifact.get("content_hash") != hashlib.sha256(raw).hexdigest():
        raise SerenityError("persistence_conflict", "attached fact snapshot content hash mismatch", 5, run_id=run_id)
    try:
        snapshot = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SerenityError("persistence_conflict", "attached fact snapshot is not valid JSON", 5, run_id=run_id) from exc
    if not isinstance(snapshot, dict):
        raise SerenityError("persistence_conflict", "attached fact snapshot is not an object", 5, run_id=run_id)
    try:
        validate_security_snapshot(snapshot)
    except (SchemaViolation, SnapshotIntegrityError) as exc:
        raise SerenityError("persistence_conflict", f"attached fact snapshot is invalid: {exc}", 5, run_id=run_id) from exc
    return snapshot


def resolve_issuer_origin_binding(
    *, request: dict[str, Any], manifest: dict[str, Any], root: Path, run_id: str
) -> VerifiedIssuerOrigin | None:
    if request.get("capability_id") != "issuer-ir.document":
        return None
    policy = request.get("provider_policy")
    if isinstance(policy, dict) and policy.get("allow_network") is False:
        return None
    parameters = request.get("provider_parameters")
    identity = parameters.get("identity") if isinstance(parameters, dict) else None
    origin = parameters.get("origin_binding") if isinstance(parameters, dict) else None
    if not isinstance(identity, dict) or not isinstance(origin, dict):
        raise SerenityError("usage_or_schema", "issuer-ir.document requires identity and origin_binding objects", 2, run_id=run_id)
    ticker = identity.get("ticker")
    cik = identity.get("cik")
    issuer = identity.get("issuer")
    issuer_domain = origin.get("issuer_domain")
    binding_source_ref = origin.get("binding_source_ref")
    if not all(isinstance(value, str) and value.strip() for value in (ticker, cik, issuer, issuer_domain, binding_source_ref)):
        raise SerenityError("usage_or_schema", "issuer-ir.document origin identity fields must be non-empty strings", 2, run_id=run_id)
    normalized_cik = cik.strip()
    if not normalized_cik.isdigit():
        raise SerenityError("usage_or_schema", "issuer-ir.document identity.cik must be numeric", 2, run_id=run_id)
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or "fact-snapshot" not in artifacts:
        raise SerenityError("identity_blocked", "issuer-ir.document requires an attached fact snapshot", 3, run_id=run_id)
    snapshot = load_attached_security_snapshot(manifest=manifest, root=root, run_id=run_id)
    snapshot_identity = snapshot.get("identity")
    if not isinstance(snapshot_identity, dict):
        raise SerenityError("persistence_conflict", "attached fact snapshot has no identity", 5, run_id=run_id)
    provenance = snapshot_identity.get("provenance")
    submissions = [entry for entry in provenance if isinstance(entry, dict) and entry.get("provider") == "sec.submissions"] if isinstance(provenance, list) else []
    if len(submissions) != 1:
        raise SerenityError("identity_blocked", "issuer origin requires raw SEC submissions provenance", 3, run_id=run_id)
    submission = submissions[0]
    submission_uri = submission.get("source_uri")
    submission_hash = submission.get("raw_content_sha256")
    parsed_submission_uri = urlparse(submission_uri) if isinstance(submission_uri, str) else None
    if (
        parsed_submission_uri is None
        or parsed_submission_uri.scheme != "https"
        or parsed_submission_uri.hostname != "data.sec.gov"
        or not isinstance(submission_hash, str)
        or len(submission_hash) != 64
    ):
        raise SerenityError("identity_blocked", "issuer origin has invalid SEC submissions provenance", 3, run_id=run_id)
    submission_path = root / ".serenity" / "cache" / "provider-raw" / "sha256" / submission_hash
    try:
        if submission_path.is_symlink() or not submission_path.is_file():
            raise OSError("raw SEC submissions payload is missing")
        submission_raw = submission_path.read_bytes()
        if hashlib.sha256(submission_raw).hexdigest() != submission_hash:
            raise OSError("raw SEC submissions payload hash mismatch")
        submission_document = json.loads(submission_raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise SerenityError("persistence_conflict", f"raw SEC submissions provenance cannot be verified: {exc}", 5, run_id=run_id) from exc
    if not isinstance(submission_document, dict):
        raise SerenityError("persistence_conflict", "raw SEC submissions payload is not an object", 5, run_id=run_id)
    domains = snapshot_identity.get("issuer_domains")
    normalized_domain = issuer_domain.casefold().strip().strip(".")
    normalized_domains = {
        domain.casefold().strip().strip(".")
        for domain in domains
        if isinstance(domain, str) and domain.strip()
    } if isinstance(domains, list) else set()
    expected = (
        str(snapshot_identity.get("ticker") or "").upper(),
        str(snapshot_identity.get("cik") or ""),
        str(snapshot_identity.get("name") or ""),
        str(snapshot.get("snapshot_id") or ""),
    )
    supplied = (
        ticker.strip().upper(),
        f"{int(normalized_cik):010d}",
        issuer.strip(),
        binding_source_ref.strip(),
    )
    raw_domains: set[str] = set()
    for field in ("website", "investorWebsite"):
        candidate = submission_document.get(field)
        parsed = urlparse(candidate) if isinstance(candidate, str) else None
        if parsed is not None and parsed.scheme == "https" and isinstance(parsed.hostname, str):
            raw_domains.add(parsed.hostname.casefold().strip("."))
    submission_cik = str(submission_document.get("cik") or "")
    normalized_submission_cik = f"{int(submission_cik):010d}" if submission_cik.isdigit() else ""
    submission_name = str(submission_document.get("name") or "")
    expected_submission_path = f"/submissions/CIK{expected[1]}.json"
    if (
        supplied != expected
        or normalized_domain not in normalized_domains
        or normalized_domain not in raw_domains
        or normalized_submission_cik != expected[1]
        or submission_name != expected[2]
        or parsed_submission_uri.path != expected_submission_path
    ):
        raise SerenityError("identity_blocked", "issuer-ir.document origin does not match the attached fact snapshot", 3, run_id=run_id)
    return VerifiedIssuerOrigin(
        ticker=expected[0],
        cik=expected[1],
        issuer=expected[2],
        issuer_domain=normalized_domain,
        binding_source_ref=expected[3],
        binding_content_hash=str(snapshot["content_hash"]),
    )


def cache_live_provider_payloads(envelopes: list[ProviderEnvelope], *, root: Path) -> list[dict[str, str | None]]:
    try:
        return [result.to_dict() for result in cache_provider_raw_payloads(envelopes, root=root / ".serenity" / "cache" / "provider-raw")]
    except (OSError, ValueError, RawPayloadConflictError) as exc:
        raise SerenityError("persistence_conflict", f"provider raw payload cache failed: {exc}", 5) from exc


def build_live_snapshot_inputs(
    *, ticker: str, as_of: str, historical_cutoff: str, allowed_providers: frozenset[str]
) -> tuple[Any, Any | None, Any | None]:
    if not historical_cutoff:
        raise SerenityError("usage_or_schema", "live snapshot requires a historical cutoff", 2)
    identity = IdentityResolver(sec=SecIdentityProvider(), openfigi=OpenFigiProvider()).resolve(ticker)
    if identity.to_dict().get("status") != "available":
        return identity, None, None
    market = YFinanceProvider().fetch(ticker)
    rs = RsRatingProvider().fetch(ticker, as_of=as_of) if "ibd-rs-rating" in allowed_providers else None
    return identity, market, rs


def build_evidence_provider_registry(root: Path) -> EvidenceProviderRegistry:
    load_project_env(root)
    config: dict[str, dict[str, str]] = {}
    for provider_id, (variable, parameter) in {
        "alfred-fred": ("FRED_API_KEY", "api_key"),
        "eia": ("EIA_API_KEY", "api_key"),
        "bea": ("BEA_API_KEY", "api_key"),
        "bls": ("BLS_REGISTRATION_KEY", "bls_registration_key"),
        "sam": ("SAM_API_KEY", "api_key"),
        "uspto": ("USPTO_API_KEY", "api_key"),
    }.items():
        value = os.environ.get(variable)
        if value:
            config[provider_id] = {parameter: value}
    return EvidenceProviderRegistry(config=config)


def evidence_execution_request(request: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    source_policy = manifest.get("source_policy")
    request_policy = request.get("provider_policy")
    if not isinstance(source_policy, dict) or not isinstance(request_policy, dict):
        raise SerenityError("usage_or_schema", "run and evidence request require source policies", 2)
    allow_network = source_policy.get("allow_network")
    if not isinstance(allow_network, bool):
        raise SerenityError("usage_or_schema", "run source_policy.allow_network must be boolean", 2)
    request_allow_network = request_policy.get("allow_network", True)
    if not isinstance(request_allow_network, bool):
        raise SerenityError("usage_or_schema", "evidence request provider_policy.allow_network must be boolean", 2)
    run_cutoff = run_historical_cutoff(manifest)
    request_cutoff = request_policy.get("historical_cutoff")
    if request_cutoff is not None:
        request_cutoff = parse_instant(str(request_cutoff))
    if run_cutoff is not None and request_cutoff is not None and run_cutoff != request_cutoff:
        raise SerenityError("usage_or_schema", "run and evidence request historical_cutoff values must match", 2)
    providers = request_policy.get("providers")
    if not isinstance(providers, list) or not all(isinstance(provider, str) and provider for provider in providers):
        raise SerenityError("usage_or_schema", "evidence request provider_policy.providers must be a string array", 2)
    allowed = source_policy.get("allowed_providers")
    if allowed is not None:
        if not isinstance(allowed, list) or not all(isinstance(provider, str) and provider for provider in allowed):
            raise SerenityError("usage_or_schema", "run source_policy.allowed_providers must be a string array", 2)
        if not set(providers).issubset(allowed):
            raise SerenityError("usage_or_schema", "evidence request providers are not allowed by the run source policy", 2)
    execution = json.loads(json.dumps(request, ensure_ascii=False))
    execution_policy = dict(execution["provider_policy"])
    execution_policy["allow_network"] = allow_network and request_allow_network
    cutoff = run_cutoff or request_cutoff
    if cutoff is not None:
        execution_policy["historical_cutoff"] = cutoff
    execution["provider_policy"] = execution_policy
    return execution


def redact_evidence_envelope(envelope: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    def redact(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: "[REDACTED]" if key.lower().replace("-", "_") in {"api_key", "apikey", "authorization", "password", "secret", "token", "userid", "registrationkey", "bls_registration_key"} or key.lower().endswith("_api_key") else redact(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    bound = redact(envelope)
    if not isinstance(bound, dict):
        raise SerenityError("provider_failure", "registry produced a non-object provider envelope", 4)
    bound["request_id"] = request_id
    try:
        validate_document(bound, "urn:serenity:schema:provider-envelope:1")
    except SchemaViolation as exc:
        raise SerenityError("provider_failure", f"registry produced an invalid provider envelope: {exc}", 4) from exc
    return bound


def document_cli_help(parser: JsonArgumentParser) -> None:
    entries = {
        "serenity.py": ("Operate the typed research runtime without producing an investment verdict.", "Commands enforce their own lifecycle state.", "JSON stdout only; artifacts live under .serenity/ or records/.", "Workflow: serenity.py run start --mode single-name --question 'What evidence changes the NVDA thesis?' --subject NVDA --as-of 2026-08-17 --offline\n  -> serenity.py snapshot security RUN_ID --frozen-packet fixtures/frozen-snapshot.json\n  -> serenity.py hypothesis put RUN_ID --document fixtures/hypotheses.json"),
        "serenity.py run": ("Manage immutable research-run lifecycle state.", "OPEN starts work; FINALIZED can close; CLOSED and ABANDONED are terminal.", ".serenity/runs/<run_id>/run-manifest.json and .serenity/active-run.json.", "Workflow: serenity.py run start --mode single-name --question 'What evidence changes the NVDA thesis?' --subject NVDA --as-of 2026-08-17 --offline\n  -> serenity.py run status RUN_ID\n  -> serenity.py run abandon RUN_ID --reason 'research stopped'"),
        "serenity.py run start": ("Create one OPEN run with intent and source policy.", "Requires no active OPEN or FINALIZED run; --as-of derives a 23:59:59Z historical cutoff, --cutoff cannot be later, and --provider allowlists named provider IDs.", "A new run-manifest.json and active-run.json pointer.", "serenity.py run start --mode single-name --question 'What evidence changes the NVDA thesis?' --subject NVDA --as-of 2026-08-17 --offline\nOr live: serenity.py run start --mode single-name --question 'What evidence changes the NVDA thesis?' --subject NVDA --as-of 2026-08-17 --cutoff 2026-08-17T23:59:59Z --provider sec --provider openfigi --provider yfinance"),
        "serenity.py run status": ("Read a run or active-run inventory without mutation.", "Any lifecycle state may be read if its hash is valid.", "No artifact is written.", "serenity.py run status RUN_ID"),
        "serenity.py run abandon": ("Terminally abandon an unfinished run with a reason.", "Requires OPEN.", "Updated run-manifest.json; matching active pointer is cleared.", "serenity.py run abandon RUN_ID --reason 'research stopped'"),
        "serenity.py run close": ("Close a finalized run after decision persistence.", "Requires FINALIZED.", "Updated run-manifest.json; matching active pointer is cleared.", "serenity.py run close RUN_ID --reason 'validated decision persisted'"),
        "serenity.py snapshot": ("Create deterministic security fact snapshots.", "Snapshot writes require OPEN.", "fact-snapshot.json.", "Workflow: serenity.py snapshot security RUN_ID --frozen-packet fixtures/frozen-snapshot.json"),
        "serenity.py snapshot security": ("Resolve identity and persist a small security fact snapshot.", "Requires OPEN and one subject for live collection. Live execution requires allowed sec, openfigi, and yfinance providers; ibd-rs-rating is optional.", "fact-snapshot.json attached to the run.", "serenity.py snapshot security RUN_ID --frozen-packet fixtures/frozen-snapshot.json"),
        "serenity.py hypothesis": ("Maintain competing research hypotheses.", "Hypothesis mutations require OPEN.", "hypothesis-ledger.json.", "Workflow: serenity.py hypothesis put RUN_ID --document fixtures/hypotheses.json"),
        "serenity.py hypothesis put": ("Store a versioned competing-hypothesis ledger.", "Requires OPEN.", "hypothesis-ledger.json.", "serenity.py hypothesis put RUN_ID --document fixtures/hypotheses.json"),
        "serenity.py evidence": ("Catalog, request, collect, and read typed evidence.", "Request, collect, and manual record operations require OPEN.", "evidence requests and results under the run.", "Workflow: serenity.py evidence request RUN_ID --hypothesis-id hyp-demand-holds --capability-id sec.filings --document fixtures/evidence-request.json\n  -> serenity.py evidence collect RUN_ID evidence-request-001\n  -> serenity.py evidence read RUN_ID evidence-result-001"),
        "serenity.py evidence catalog": ("List known provider capabilities without prioritizing them.", "No run state is required.", "Checked-in evidence-catalog.json is read only.", "serenity.py evidence catalog"),
        "serenity.py evidence request": ("Persist an adaptive evidence request linked to hypotheses. For issuer-ir.document, supply an official issuer-owned URL; Web search only locates the source, while identity/domain/time/raw-byte binding happens at collection. A live SEC-provenance fact snapshot must authorize the issuer domain; a frozen snapshot cannot authorize a live issuer fetch.", "Requires OPEN and an existing ledger.", "evidence/requests/evidence-request-<id>.json.", "serenity.py evidence request RUN_ID --hypothesis-id hyp-demand-holds --capability-id sec.filings --document fixtures/evidence-request.json"),
        "serenity.py evidence collect": ("Explicitly execute a saved request through the provider registry. For issuer-ir.document, supply an official issuer-owned URL; Web search only locates the source, while identity/domain/time/raw-byte binding happens at collection. A live SEC-provenance fact snapshot must authorize the issuer domain; a frozen snapshot cannot authorize a live issuer fetch.", "Requires OPEN; run/request network and cutoff policies must agree.", "One or more evidence/ results, deterministically ordered.", "serenity.py evidence collect RUN_ID evidence-request-001"),
        "serenity.py evidence read": ("Read a saved result, or explicitly persist a supplied typed result document. issuer-ir.document must use evidence collect because a supplied document cannot prove the live SEC origin or raw response bytes.", "Requires OPEN for manual persistence; saved reads validate linkage.", "evidence/results/evidence-result-<id>.json.", "serenity.py evidence read RUN_ID evidence-result-001"),
        "serenity.py lens": ("Execute declared arithmetic only from saved facts.", "Lens writes require OPEN.", "lens-result.json.", "Workflow: serenity.py lens run RUN_ID --spec fixtures/lens-spec.json"),
        "serenity.py lens run": ("Evaluate a schema-valid lens spec against its saved snapshot.", "Requires OPEN and fact-snapshot.json.", "lens-result.json.", "serenity.py lens run RUN_ID --spec fixtures/lens-spec.json"),
        "serenity.py decision": ("Validate and seal analyst-authored decisions.", "Validation/finalization require OPEN.", "Validation JSON or immutable records/decisions lineage.", "Workflow: serenity.py decision validate RUN_ID --decision fixtures/decision.json --evidence-manifest fixtures/evidence-manifest.json\n  -> serenity.py decision finalize RUN_ID --decision fixtures/decision.json --evidence-manifest fixtures/evidence-manifest.json --analysis fixtures/analysis.json"),
        "serenity.py decision validate": ("Validate a draft without writing final decision state.", "Requires OPEN and linked run artifacts.", "No artifact is written.", "serenity.py decision validate RUN_ID --decision fixtures/decision.json --evidence-manifest fixtures/evidence-manifest.json"),
        "serenity.py decision finalize": ("Persist an immutable valid decision and finalize its run.", "Requires OPEN and a valid decision draft.", "records/decisions/<lineage>/vNNN plus run attachment.", "serenity.py decision finalize RUN_ID --decision fixtures/decision.json --evidence-manifest fixtures/evidence-manifest.json --analysis fixtures/analysis.json"),
        "serenity.py outcomes": ("Explicitly register and measure prospective outcome records.", "Registration needs a finalized decision; refresh needs an existing record.", "records/prospective/.", "Workflow: serenity.py outcomes register --decision records/decisions/LINEAGE/v001/decision.json --benchmark-json fixtures/benchmark.json --checkpoint-schedule-json fixtures/outcome-schedule.json\n  -> serenity.py outcomes refresh outcome-001 --observation fixtures/observation.json"),
        "serenity.py outcomes register": ("Register a finalized decision for future measurement.", "Requires the stored current immutable decision document, not an arbitrary JSON fixture.", "records/prospective/<record_id>/record.json.", "serenity.py outcomes register --decision records/decisions/LINEAGE/v001/decision.json --benchmark-json fixtures/benchmark.json --checkpoint-schedule-json fixtures/outcome-schedule.json"),
        "serenity.py outcomes refresh": ("Append one dated measurement without placing a trade.", "Requires an existing prospective record.", "Updated prospective observation stream.", "serenity.py outcomes refresh outcome-001 --observation fixtures/observation.json"),
        "serenity.py graph": ("Persist structural sector-graph evidence without an investment verdict.", "Graph writes require OPEN.", "sector-graph.json.", "Workflow: serenity.py graph put RUN_ID --file fixtures/sector-graph.json"),
        "serenity.py graph put": ("Validate and attach a typed supply-chain sector graph.", "Requires OPEN and a matching run_id.", "sector-graph.json.", "serenity.py graph put RUN_ID --file fixtures/sector-graph.json"),
    }
    shared = "\n\nExecution: live providers run only when the run/request policy allows network; --offline prevents live I/O.\nExit codes: 0 success; 2 usage/schema; 3 identity/lifecycle; 4 provider; 5 persistence/hash conflict; 70 internal error."

    def apply(current: argparse.ArgumentParser) -> None:
        purpose, state, artifact, example = entries[current.prog]
        current.description = f"Purpose: {purpose}\nState: {state}\nArtifact: {artifact}"
        frozen = "\nFrozen input: --frozen-packet fixtures/frozen-snapshot.json supplies deterministic snapshot data." if current.prog.startswith("serenity.py snapshot") else ""
        current.epilog = f"Example: {example}{frozen}{shared}"
        for action in current._actions:
            if isinstance(action, argparse._SubParsersAction):
                for child in action.choices.values():
                    apply(child)

    apply(parser)


def build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(prog="serenity.py")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)

    run = commands.add_parser("run")
    run_commands = run.add_subparsers(dest="run_command", required=True, parser_class=JsonArgumentParser)

    start = run_commands.add_parser("start")
    start.add_argument("--mode", required=True, choices=RUN_MODES)
    start.add_argument("--question", required=True)
    start.add_argument("--subject", action="append", default=[])
    start.add_argument("--as-of", required=True, type=parse_as_of, help="Research date; derives an end-of-day historical cutoff unless --cutoff is supplied.")
    start.add_argument("--actor-kind", choices=("human", "model", "system"), default="model")
    start.add_argument("--actor-id", default="harness-agent")
    start.add_argument("--offline", action="store_true")
    start.add_argument("--cutoff", type=parse_instant, help="ISO instant at or before the --as-of day; narrows historical availability.")
    start.add_argument("--provider", action="append", default=[], help="Repeatable provider-ID allowlist for live calls, for example sec, openfigi, yfinance, or ibd-rs-rating.")

    status = run_commands.add_parser("status")
    status.add_argument("run_id", nargs="?")

    abandon = run_commands.add_parser("abandon")
    abandon.add_argument("run_id")
    abandon.add_argument("--reason", required=True)

    close = run_commands.add_parser("close")
    close.add_argument("run_id")
    close.add_argument("--reason", default="validated decision persisted")

    snapshot = commands.add_parser("snapshot")
    snapshot_commands = snapshot.add_subparsers(dest="snapshot_command", required=True, parser_class=JsonArgumentParser)
    security = snapshot_commands.add_parser("security")
    security.add_argument("run_id")
    security.add_argument("--frozen-packet")

    hypothesis = commands.add_parser("hypothesis")
    hypothesis_commands = hypothesis.add_subparsers(dest="hypothesis_command", required=True, parser_class=JsonArgumentParser)
    put = hypothesis_commands.add_parser("put")
    put.add_argument("run_id")
    put.add_argument("--document", required=True)
    put.add_argument("--expected-revision", type=int)

    evidence = commands.add_parser("evidence")
    evidence_commands = evidence.add_subparsers(dest="evidence_command", required=True, parser_class=JsonArgumentParser)
    evidence_commands.add_parser("catalog")
    request = evidence_commands.add_parser("request")
    request.add_argument("run_id")
    request.add_argument("--hypothesis-id", action="append", required=True)
    request.add_argument("--capability-id", required=True)
    request.add_argument("--document", required=True)
    collect = evidence_commands.add_parser("collect")
    collect.add_argument("run_id")
    collect.add_argument("request_id")
    read = evidence_commands.add_parser("read")
    read.add_argument("run_id")
    read.add_argument("artifact_id")
    read.add_argument("--document")

    lens = commands.add_parser("lens")
    lens_commands = lens.add_subparsers(dest="lens_command", required=True, parser_class=JsonArgumentParser)
    lens_run = lens_commands.add_parser("run")
    lens_run.add_argument("run_id")
    lens_run.add_argument("--spec", required=True)

    decision = commands.add_parser("decision")
    decision_commands = decision.add_subparsers(dest="decision_command", required=True, parser_class=JsonArgumentParser)
    for name in ("validate", "finalize"):
        decision_command = decision_commands.add_parser(name)
        decision_command.add_argument("run_id")
        decision_command.add_argument("--decision", required=True)
        decision_command.add_argument("--evidence-manifest", required=True)
        if name == "finalize":
            decision_command.add_argument("--analysis", required=True)

    outcomes = commands.add_parser("outcomes")
    outcomes_commands = outcomes.add_subparsers(dest="outcomes_command", required=True, parser_class=JsonArgumentParser)
    register = outcomes_commands.add_parser("register")
    register.add_argument("--decision", required=True)
    register.add_argument("--benchmark", "--benchmark-json", dest="benchmark", required=True)
    register.add_argument("--schedule", "--checkpoint-schedule-json", dest="schedule", required=True)
    refresh = outcomes_commands.add_parser("refresh")
    refresh.add_argument("record_id")
    refresh.add_argument("--observation", required=True)

    graph = commands.add_parser("graph")
    graph_commands = graph.add_subparsers(dest="graph_command", required=True, parser_class=JsonArgumentParser)
    graph_put = graph_commands.add_parser("put")
    graph_put.add_argument("run_id")
    graph_put.add_argument("--file", required=True)
    document_cli_help(parser)
    return parser


def dispatch(args: argparse.Namespace, root: Path) -> dict[str, Any]:
    store = RunStore(root)
    if args.command == "run" and args.run_command == "start":
        subjects = [subject.strip().upper() for subject in args.subject if subject.strip()]
        question = args.question.strip()
        if not question:
            raise SerenityError("usage_or_schema", "--question cannot be empty", 2)
        if args.mode == "single-name" and len(subjects) != 1:
            raise SerenityError("usage_or_schema", "single-name mode requires exactly one --subject", 2)
        if args.mode == "cohort" and len(subjects) < 2:
            raise SerenityError("usage_or_schema", "cohort mode requires at least two --subject values", 2)
        as_of_cutoff = f"{args.as_of}T23:59:59Z"
        if args.cutoff and args.cutoff > as_of_cutoff:
            raise SerenityError("usage_or_schema", "--cutoff cannot be after the --as-of day", 2)
        source_policy: dict[str, Any] = {
            "policy_id": "live-free-v1",
            "allow_network": not args.offline,
            "historical_cutoff": args.cutoff or as_of_cutoff,
        }
        if args.provider:
            source_policy["allowed_providers"] = sorted(set(args.provider))
        run = store.start(
            mode=args.mode,
            question=question,
            subjects=subjects,
            as_of=args.as_of,
            actor={"kind": args.actor_kind, "id": args.actor_id},
            source_policy=source_policy,
        )
        return {"command": "run.start", "ok": True, "run": run}
    if args.command == "run" and args.run_command == "status":
        if args.run_id:
            return {"command": "run.status", "ok": True, "run": store.read(args.run_id)}
        return {"command": "run.status", "ok": True, "active_run": store.read_active(), "open_runs": store.list_open()}
    if args.command == "run" and args.run_command == "abandon":
        run = store.abandon(args.run_id, args.reason.strip())
        return {"command": "run.abandon", "ok": True, "run": run}
    if args.command == "run" and args.run_command == "close":
        return {"command": "run.close", "ok": True, "run": store.close(args.run_id, args.reason.strip())}
    if args.command == "snapshot" and args.snapshot_command == "security":
        manifest = store.read(args.run_id)
        raw_payload_cache: list[dict[str, str | None]] | None = None
        if manifest.get("status") != "OPEN":
            raise SerenityError("invalid_lifecycle", f"only an OPEN run can create a snapshot: {args.run_id}", 3, run_id=args.run_id)
        if args.frozen_packet:
            packet = load_json_document(args.frozen_packet, label="frozen snapshot packet")
            identity = packet.get("identity_resolution")
            market = packet.get("market_envelope")
            if not isinstance(identity, dict) or not isinstance(market, dict):
                raise SerenityError("usage_or_schema", "frozen snapshot packet requires identity_resolution and market_envelope objects", 2)
            rs_envelope = packet.get("rs_envelope")
            if rs_envelope is not None and not isinstance(rs_envelope, dict):
                raise SerenityError("usage_or_schema", "frozen snapshot packet rs_envelope must be an object when present", 2)
            provider_error_code = 2
        else:
            source_policy = manifest.get("source_policy")
            if isinstance(source_policy, dict) and source_policy.get("allow_network") is False:
                raise SerenityError("provider_failure", "live snapshot providers are disabled by the run source policy", 4, run_id=args.run_id)
            subjects = manifest.get("subjects")
            if not isinstance(subjects, list) or len(subjects) != 1 or not isinstance(subjects[0], str):
                raise SerenityError("usage_or_schema", "live security snapshot requires exactly one run subject", 2, run_id=args.run_id)
            historical_cutoff, allowed_providers = live_snapshot_policy(manifest)
            load_project_env(root)
            try:
                identity, market, rs_envelope = build_live_snapshot_inputs(
                    ticker=subjects[0],
                    as_of=manifest["as_of"],
                    historical_cutoff=historical_cutoff,
                    allowed_providers=allowed_providers,
                )
            except SerenityError:
                raise
            except Exception as exc:
                raise SerenityError("provider_failure", f"live snapshot providers could not produce typed envelopes: {exc}", 4, run_id=args.run_id) from exc
            identity_document = identity.to_dict() if hasattr(identity, "to_dict") else identity
            if not isinstance(identity_document, dict):
                raise SerenityError("provider_failure", "live identity provider returned no typed resolution", 4, run_id=args.run_id)
            if identity_document.get("status") != "available":
                rejection = identity_document.get("rejection") if isinstance(identity_document.get("rejection"), dict) else {}
                reason = rejection.get("code", "identity_unresolved")
                diagnosis = {key: value for key, value in rejection.items() if key != "code"}
                raise SerenityError("identity_blocked", str(reason), 3, run_id=args.run_id, **diagnosis)
            identity_envelopes = getattr(identity, "provider_envelopes", ())
            if not isinstance(identity_envelopes, tuple) or not all(isinstance(item, ProviderEnvelope) for item in identity_envelopes):
                raise SerenityError("provider_failure", "live identity provider returned invalid source envelopes", 4, run_id=args.run_id)
            live_envelopes = [*identity_envelopes, *(item for item in (market, rs_envelope) if isinstance(item, ProviderEnvelope))]
            raw_payload_cache = cache_live_provider_payloads(live_envelopes, root=root)
            market = market.to_dict() if isinstance(market, ProviderEnvelope) else market
            rs_envelope = rs_envelope.to_dict() if isinstance(rs_envelope, ProviderEnvelope) else rs_envelope
            if not isinstance(market, dict) or (rs_envelope is not None and not isinstance(rs_envelope, dict)):
                raise SerenityError("provider_failure", "live providers returned no typed envelopes", 4, run_id=args.run_id)
            provider_error_code = 4
        try:
            validate_document(market, "urn:serenity:schema:provider-envelope:1")
            if rs_envelope is not None:
                validate_document(rs_envelope, "urn:serenity:schema:provider-envelope:1")
            snapshot = build_security_snapshot(manifest, identity, market, rs_envelope)
        except SchemaViolation as exc:
            raise SerenityError(
                "usage_or_schema" if provider_error_code == 2 else "provider_failure",
                f"snapshot provider envelope is invalid: {exc}",
                provider_error_code,
            ) from exc
        except SnapshotBlockedError as exc:
            raise SerenityError("identity_blocked", exc.reason, 3, run_id=args.run_id, **exc.diagnosis) from exc
        except Exception as exc:
            raise SerenityError("provider_failure", f"snapshot providers could not build a typed fact snapshot: {exc}", 4, run_id=args.run_id) from exc
        run = publish_run_document(
            store,
            run_id=args.run_id,
            name="fact-snapshot",
            filename="fact-snapshot.json",
            document=snapshot,
            phase="snapshot_created",
        )
        response: dict[str, Any] = {"command": "snapshot.security", "ok": True, "snapshot": snapshot, "run": run}
        if raw_payload_cache is not None:
            response["raw_payload_cache"] = raw_payload_cache
        return response
    if args.command == "hypothesis" and args.hypothesis_command == "put":
        prior = store.read(args.run_id).get("artifacts", {}).get("hypothesis-ledger")
        artifacts = research_store(store, root, args.run_id)
        hypotheses = load_json_value(args.document, label="hypotheses")
        if not isinstance(hypotheses, list):
            raise SerenityError("usage_or_schema", "hypotheses must be a JSON array", 2)
        try:
            prepared = artifacts.prepare_hypotheses(hypotheses, expected_revision=args.expected_revision)
        except ResearchArtifactConflictError as exc:
            raise SerenityError("persistence_conflict", str(exc), 5, run_id=args.run_id) from exc
        except ResearchArtifactValidationError as exc:
            raise SerenityError("usage_or_schema", str(exc), 2, run_id=args.run_id) from exc
        run = store.publish_or_refresh_artifact(
            args.run_id,
            name="hypothesis-ledger",
            expected_attachment=prior if isinstance(prior, dict) else None,
            path=prepared.ledger_path,
            content=prepared.ledger_content,
            schema_id=prepared.ledger["schema_id"],
            phase="hypotheses_updated",
        )
        return {"command": "hypothesis.put", "ok": True, "ledger": prepared.ledger, "run": run}
    if args.command == "evidence" and args.evidence_command == "catalog":
        try:
            return {"command": "evidence.catalog", "ok": True, "catalog": load_evidence_catalog()}
        except ResearchArtifactValidationError as exc:
            raise SerenityError("persistence_conflict", str(exc), 5) from exc
    if args.command == "evidence" and args.evidence_command == "request":
        prior = store.read(args.run_id).get("artifacts", {}).get("hypothesis-ledger")
        artifacts = research_store(store, root, args.run_id)
        request_document = load_json_document(args.document, label="evidence request")
        try:
            prepared = artifacts.prepare_evidence_request(
                hypothesis_ids=args.hypothesis_id,
                capability_id=args.capability_id,
                request=request_document,
            )
        except ResearchArtifactConflictError as exc:
            raise SerenityError("persistence_conflict", str(exc), 5, run_id=args.run_id) from exc
        except ResearchArtifactValidationError as exc:
            raise SerenityError("usage_or_schema", str(exc), 2, run_id=args.run_id) from exc
        run = store.publish_or_refresh_artifact(
            args.run_id,
            name="hypothesis-ledger",
            expected_attachment=prior if isinstance(prior, dict) else None,
            path=prepared.ledger_path,
            content=prepared.ledger_content,
            schema_id="urn:serenity:schema:hypothesis-ledger:1",
            phase="hypotheses_updated",
        )
        if prepared.request is None or prepared.request_path is None or prepared.request_content is None:
            raise SerenityError("internal_error", "prepared evidence request is incomplete", 70, run_id=args.run_id)
        run = store.publish_artifact(
            args.run_id,
            name=prepared.request["request_id"],
            path=prepared.request_path,
            content=prepared.request_content,
            schema_id=prepared.request["schema_id"],
            phase="evidence_requested",
        )
        return {"command": "evidence.request", "ok": True, "request": prepared.request, "run": run}
    if args.command == "evidence" and args.evidence_command == "collect":
        manifest = store.read(args.run_id)
        artifacts = research_store(store, root, args.run_id)
        try:
            request = artifacts.read_evidence_request(args.request_id)
            execution_request = evidence_execution_request(request, manifest)
            issuer_origin_binding = resolve_issuer_origin_binding(
                request=execution_request,
                manifest=manifest,
                root=root,
                run_id=args.run_id,
            )
            registry = build_evidence_provider_registry(root)
            if issuer_origin_binding is None:
                envelopes = registry.collect(execution_request)
            else:
                envelopes = registry.collect(execution_request, issuer_origin_binding=issuer_origin_binding)
            raw_payload_cache = cache_live_provider_payloads([envelope for envelope in envelopes if isinstance(envelope, ProviderEnvelope)], root=root)
            documents = [redact_evidence_envelope(envelope.to_dict(), request_id=request["request_id"]) for envelope in envelopes]
            cutoff = run_historical_cutoff(manifest)
            for envelope in documents:
                require_evidence_available_by_cutoff(envelope, cutoff=cutoff, label="provider envelope")
        except SerenityError:
            raise
        except ProviderRegistryValidationError as exc:
            raise SerenityError("usage_or_schema", str(exc), 2, run_id=args.run_id) from exc
        except ResearchArtifactValidationError as exc:
            raise SerenityError("usage_or_schema", str(exc), 2, run_id=args.run_id) from exc
        except Exception as exc:
            raise SerenityError("provider_failure", f"evidence registry could not collect typed provider envelopes: {exc}", 4, run_id=args.run_id) from exc
        documents.sort(
            key=lambda envelope: (
                str(envelope["provider"]),
                str(envelope["temporal"].get("available_at") or ""),
                str(envelope["temporal"].get("effective_at") or ""),
                str(envelope["temporal"].get("source_version") or ""),
                json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            )
        )
        try:
            results = [
                artifacts.record_evidence_result(
                    request_id=request["request_id"],
                    evidence={"provider_envelope": envelope, "fact_refs": [], "transform_version": "registry/1"},
                )
                for envelope in documents
            ]
            run = store.read(args.run_id)
            for result in results:
                path = root / ".serenity" / "runs" / args.run_id / "evidence" / "results" / f"{result['result_id']}.json"
                run = store.attach_artifact(
                    args.run_id,
                    name=result["result_id"],
                    path=path,
                    schema_id=result["schema_id"],
                    phase="evidence_collected",
                )
        except ResearchArtifactConflictError as exc:
            raise SerenityError("persistence_conflict", str(exc), 5, run_id=args.run_id) from exc
        except ResearchArtifactValidationError as exc:
            raise SerenityError("usage_or_schema", str(exc), 2, run_id=args.run_id) from exc
        return {"command": "evidence.collect", "ok": True, "results": results, "run": run, "raw_payload_cache": raw_payload_cache}
    if args.command == "evidence" and args.evidence_command == "read":
        artifacts = research_store(store, root, args.run_id)
        try:
            if args.document:
                if not args.artifact_id.startswith("evidence-request-"):
                    raise SerenityError("usage_or_schema", "--document requires an evidence request id", 2)
                request = artifacts.read_evidence_request(args.artifact_id)
                if request.get("capability_id") == "issuer-ir.document":
                    raise SerenityError(
                        "usage_or_schema",
                        "issuer-ir.document cannot accept a manually supplied result; use evidence collect",
                        2,
                        run_id=args.run_id,
                    )
                evidence = load_json_document(args.document, label="evidence result")
                require_evidence_available_by_cutoff(evidence, cutoff=run_historical_cutoff(store.read(args.run_id)), label="evidence result")
                result = artifacts.record_evidence_result(
                    request_id=args.artifact_id,
                    evidence=evidence,
                )
                path = root / ".serenity" / "runs" / args.run_id / "evidence" / "results" / f"{result['result_id']}.json"
                run = store.attach_artifact(args.run_id, name=result["result_id"], path=path, schema_id=result["schema_id"], phase="evidence_recorded")
                return {"command": "evidence.read", "ok": True, "result": result, "run": run}
            if not args.artifact_id.startswith("evidence-result-"):
                raise SerenityError("usage_or_schema", "evidence read requires an evidence result id", 2)
            return {"command": "evidence.read", "ok": True, "result": artifacts.read_evidence_result(args.artifact_id)}
        except ResearchArtifactConflictError as exc:
            raise SerenityError("persistence_conflict", str(exc), 5, run_id=args.run_id) from exc
        except ResearchArtifactValidationError as exc:
            raise SerenityError("usage_or_schema", str(exc), 2, run_id=args.run_id) from exc
    if args.command == "lens" and args.lens_command == "run":
        manifest = store.read(args.run_id)
        if manifest.get("status") != "OPEN":
            raise SerenityError("invalid_lifecycle", f"only an OPEN run can execute a lens: {args.run_id}", 3, run_id=args.run_id)
        spec = load_json_document(args.spec, label="lens spec")
        if spec.get("run_id") != args.run_id:
            raise SerenityError("usage_or_schema", "lens spec run_id does not match the active run", 2, run_id=args.run_id)
        try:
            validate_document(spec, "urn:serenity:schema:lens-spec:1")
        except SchemaViolation as exc:
            raise SerenityError("usage_or_schema", str(exc), 2, run_id=args.run_id) from exc
        snapshot = load_attached_security_snapshot(manifest=manifest, root=root, run_id=args.run_id)
        result = run_lens(spec, snapshot)
        try:
            validate_document(result, "urn:serenity:schema:lens-result:1")
        except SchemaViolation as exc:
            raise SerenityError("internal_error", f"lens service returned an invalid result: {exc}", 70, run_id=args.run_id) from exc
        run = publish_run_document(
            store,
            run_id=args.run_id,
            name="lens-result",
            filename="lens-result.json",
            document=result,
            phase="lens_executed",
        )
        return {"command": "lens.run", "ok": True, "result": result, "run": run}
    if args.command == "decision" and args.decision_command in {"validate", "finalize"}:
        manifest = store.read(args.run_id)
        run_dir = root / ".serenity" / "runs" / args.run_id
        draft = load_json_document(args.decision, label="decision draft")
        evidence_manifest = load_json_document(args.evidence_manifest, label="evidence manifest")
        if args.decision_command == "validate":
            validation = validate_decision(
                project_root=root,
                run_manifest=manifest,
                run_dir=run_dir,
                decision_draft=draft,
                evidence_manifest=evidence_manifest,
            )
            return {"command": "decision.validate", "ok": True, "validation": validation}
        analysis = load_json_document(args.analysis, label="analysis")
        markdown = analysis.get("markdown")
        if not isinstance(markdown, str) or not markdown.strip():
            raise SerenityError("usage_or_schema", "analysis requires a non-empty markdown field", 2)
        lineage_id = draft.get("lineage_id")
        version = draft.get("version")
        if not isinstance(lineage_id, str) or not isinstance(version, int):
            raise SerenityError("usage_or_schema", "decision draft requires lineage_id and integer version", 2, run_id=args.run_id)
        expected_path = root / "records" / "decisions" / lineage_id / f"v{version:03d}" / "decision.json"
        finalized: dict[str, Any] = {}

        def publish() -> Path:
            nonlocal finalized
            finalized = finalize_decision(
                project_root=root,
                run_manifest=store.read(args.run_id),
                run_dir=run_dir,
                decision_draft=draft,
                analysis_markdown=markdown,
                evidence_manifest=evidence_manifest,
            )
            return Path(finalized["decision_path"])

        run = store.finalize_with_publication(args.run_id, decision_path=expected_path, publish=publish)
        return {"command": "decision.finalize", "ok": True, "finalization": finalized, "run": run}
    if args.command == "outcomes" and args.outcomes_command == "register":
        decision = load_json_document(args.decision, label="finalized decision")
        benchmark = load_json_document(args.benchmark, label="benchmark")
        schedule = load_json_value(args.schedule, label="checkpoint schedule")
        if not isinstance(schedule, list):
            raise SerenityError("usage_or_schema", "checkpoint schedule must be a JSON array", 2)
        try:
            record = OutcomesStore(root).register(decision, benchmark=benchmark, checkpoint_schedule=schedule)
        except OutcomesError as exc:
            raise SerenityError(exc.code, str(exc), exc.exit_code) from exc
        return {"command": "outcomes.register", "ok": True, "record": record}
    if args.command == "outcomes" and args.outcomes_command == "refresh":
        observation = load_json_document(args.observation, label="outcome observation")
        try:
            record = OutcomesStore(root).refresh(args.record_id, observation=observation)
        except OutcomesError as exc:
            raise SerenityError(exc.code, str(exc), exc.exit_code, record_id=args.record_id) from exc
        return {"command": "outcomes.refresh", "ok": True, "record": record}
    if args.command == "graph" and args.graph_command == "put":
        manifest = store.read(args.run_id)
        if manifest.get("status") != "OPEN":
            raise SerenityError("invalid_lifecycle", f"only an OPEN run can store a graph: {args.run_id}", 3, run_id=args.run_id)
        graph = load_json_document(args.file, label="sector graph")
        if graph.get("run_id") != args.run_id:
            raise SerenityError("usage_or_schema", "sector graph run_id does not match the active run", 2, run_id=args.run_id)
        try:
            artifacts = research_store(store, root, args.run_id)
            evidence_results = [artifacts.read_evidence_result(result_id) for result_id in graph.get("evidence_refs", [])]
            graph = build_sector_graph(graph, run_manifest=manifest, evidence_results=evidence_results)
            validate_document(graph, "urn:serenity:schema:sector-graph:1")
        except (ResearchArtifactValidationError, SectorGraphValidationError, SchemaViolation) as exc:
            raise SerenityError("usage_or_schema", str(exc), 2, run_id=args.run_id) from exc
        run = publish_run_document(
            store,
            run_id=args.run_id,
            name="sector-graph",
            filename="sector-graph.json",
            document=graph,
            phase="sector_graph_saved",
        )
        return {"command": "graph.put", "ok": True, "graph": graph, "run": run}
    raise SerenityError("usage_or_schema", "unsupported command", 2)


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        emit(dispatch(args, Path.cwd()))
        return 0
    except SerenityError as exc:
        emit(exc.payload)
        return exc.exit_code
    except Exception as exc:  # pragma: no cover - last-resort stable process contract
        emit({"ok": False, "error": {"code": "internal_error", "message": str(exc), "exit_code": 70}})
        return 70


if __name__ == "__main__":
    sys.exit(main())
