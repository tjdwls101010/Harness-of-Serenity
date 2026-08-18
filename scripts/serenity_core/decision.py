from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

from serenity_core.runtime import RunStore, SerenityError, canonical_hash, parse_instant, utc_now
from serenity_core.schema import SchemaViolation, validate_document
from serenity_core.snapshot import SnapshotIntegrityError, validate_security_snapshot
from serenity_core.storage import atomic_write_json, canonical_json, immutable_directory


DECISION_SCHEMA_ID = "urn:serenity:schema:research-decision:1"
ACTIONS = {"RECOMMEND_NOW", "ENTER_ON_TRIGGER", "MONITOR", "PASS", "BLOCKED"}
IDENTITY_BLOCKING_STATES = {"conflict", "unresolved", "invalid"}
UNUSABLE_EVIDENCE_AVAILABILITY = {"unavailable", "invalid", "not_requested", "stale", "conflict", "not_applicable"}
EVIDENCE_AVAILABILITY = {"available", "not_disclosed", *UNUSABLE_EVIDENCE_AVAILABILITY}
RUN_MODE_TO_SCOPE_KIND = {
    "macro-event": "macro",
    "discovery": "sector",
    "single-name": "single-name",
    "cohort": "cohort",
}
IDENTITY_RESOLUTION_SCHEMA_ID = "urn:serenity:identity-resolution:1"
FACT_SNAPSHOT_SCHEMA_ID = "urn:serenity:schema:fact-snapshot:2"
HYPOTHESIS_LEDGER_SCHEMA_ID = "urn:serenity:schema:hypothesis-ledger:1"
EVIDENCE_RESULT_SCHEMA_ID = "urn:serenity:schema:evidence-result:1"
LENS_RESULT_SCHEMA_ID = "urn:serenity:schema:lens-result:1"
SECURITY_SCOPE_KINDS = frozenset({"single-name", "cohort"})


def _schema_path() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas" / "research-decision-1.schema.json"


def _schema() -> dict[str, Any]:
    path = _schema_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SerenityError("usage_or_schema", f"research decision schema unavailable: {path}", 2, path=str(path)) from exc
    if value.get("$id") != DECISION_SCHEMA_ID:
        raise SerenityError("usage_or_schema", f"research decision schema identity mismatch: {path}", 2, path=str(path))
    return value


def _invalid(message: str, **details: Any) -> None:
    raise SerenityError("usage_or_schema", message, 2, **details)


def _as_strings(value: Any) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        return []
    return value


def _content_hash_is_valid(document: Mapping[str, Any]) -> bool:
    content_hash = document.get("content_hash")
    unsigned = {key: value for key, value in document.items() if key != "content_hash"}
    return isinstance(content_hash, str) and content_hash == canonical_hash(unsigned)


def _load_trusted_manifest(project_root: Path, run_manifest: Mapping[str, Any], run_dir: Path) -> dict[str, Any]:
    run_id = run_manifest.get("run_id")
    if not isinstance(run_id, str):
        _invalid("decision run manifest requires run_id")
    stored = RunStore(project_root).read(run_id)
    expected_run_dir = project_root / ".serenity" / "runs" / run_id
    try:
        supplied_dir = run_dir.resolve(strict=True)
    except OSError as exc:
        raise SerenityError("invalid_lifecycle", f"run directory does not exist: {run_dir}", 3, run_dir=str(run_dir)) from exc
    if supplied_dir != expected_run_dir.resolve():
        raise SerenityError("persistence_conflict", "run directory is not the stored run directory", 5, run_dir=str(run_dir))
    if dict(run_manifest) != stored:
        raise SerenityError("persistence_conflict", "provided run manifest does not match stored manifest", 5, run_id=run_id)
    return stored


def _load_attached_artifact_documents(
    project_root: Path, run_manifest: Mapping[str, Any], run_dir: Path
) -> list[tuple[Path, dict[str, Any]]]:
    artifacts = run_manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise SerenityError("persistence_conflict", "stored run manifest has no artifact registry", 5)
    root = project_root.resolve()
    documents: list[tuple[Path, dict[str, Any]]] = []
    known_schemas = {
        HYPOTHESIS_LEDGER_SCHEMA_ID,
        EVIDENCE_RESULT_SCHEMA_ID,
        LENS_RESULT_SCHEMA_ID,
        FACT_SNAPSHOT_SCHEMA_ID,
        IDENTITY_RESOLUTION_SCHEMA_ID,
    }
    for name, attachment in sorted(artifacts.items()):
        if not isinstance(name, str) or not isinstance(attachment, Mapping):
            raise SerenityError("persistence_conflict", "stored artifact registry is malformed", 5)
        relative_path = attachment.get("path")
        expected_hash = attachment.get("content_hash")
        schema_id = attachment.get("schema_id")
        if not isinstance(relative_path, str) or not isinstance(expected_hash, str) or not isinstance(schema_id, str):
            raise SerenityError("persistence_conflict", f"artifact attachment is incomplete: {name}", 5, artifact=name)
        candidate = project_root / relative_path
        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise SerenityError("persistence_conflict", f"attached artifact is missing: {name}", 5, artifact=name) from exc
        if candidate.is_symlink() or resolved == root or root not in resolved.parents or not resolved.is_file():
            raise SerenityError("persistence_conflict", f"attached artifact escapes project root: {name}", 5, artifact=name)
        actual_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise SerenityError("persistence_conflict", f"attached artifact hash mismatch: {name}", 5, artifact=name)
        if schema_id not in known_schemas:
            continue
        try:
            document = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SerenityError("persistence_conflict", f"attached artifact cannot be parsed: {name}", 5, artifact=name) from exc
        if not isinstance(document, dict) or document.get("schema_id") != schema_id:
            raise SerenityError("persistence_conflict", f"attached artifact schema mismatch: {name}", 5, artifact=name)
        if document.get("run_id") != run_manifest["run_id"]:
            raise SerenityError("persistence_conflict", f"attached artifact run_id mismatch: {name}", 5, artifact=name)
        if schema_id != IDENTITY_RESOLUTION_SCHEMA_ID:
            try:
                validate_document(document, schema_id)
            except SchemaViolation as exc:
                raise SerenityError("persistence_conflict", f"attached artifact fails schema validation: {name}: {exc}", 5, artifact=name) from exc
        if schema_id in {HYPOTHESIS_LEDGER_SCHEMA_ID, EVIDENCE_RESULT_SCHEMA_ID, IDENTITY_RESOLUTION_SCHEMA_ID} and not _content_hash_is_valid(document):
            raise SerenityError("persistence_conflict", f"attached artifact content hash mismatch: {name}", 5, artifact=name)
        if schema_id == FACT_SNAPSHOT_SCHEMA_ID:
            try:
                validate_security_snapshot(document)
            except SnapshotIntegrityError as exc:
                raise SerenityError("persistence_conflict", f"attached fact snapshot integrity failure: {name}: {exc}", 5, artifact=name) from exc
        documents.append((resolved, document))
    return documents


def _walk(value: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield key, item
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def _artifact_index(
    documents: list[tuple[Path, dict[str, Any]]],
) -> tuple[dict[str, Path], dict[str, dict[str, Any]], set[str], dict[str, dict[str, Any]], set[str]]:
    locations: dict[str, Path] = {}
    lens_documents: dict[str, dict[str, Any]] = {}
    fact_ids: set[str] = set()
    evidence_documents: dict[str, dict[str, Any]] = {}
    pinned_subjects: set[str] = set()
    for path, document in documents:
        schema_id = document.get("schema_id")
        if schema_id == HYPOTHESIS_LEDGER_SCHEMA_ID:
            for hypothesis in document.get("hypotheses", []):
                if isinstance(hypothesis, Mapping) and isinstance(hypothesis.get("hypothesis_id"), str):
                    locations.setdefault(hypothesis["hypothesis_id"], path)
        elif schema_id == EVIDENCE_RESULT_SCHEMA_ID and isinstance(document.get("result_id"), str):
            result_id = document["result_id"]
            locations.setdefault(result_id, path)
            evidence_documents.setdefault(result_id, document)
        elif schema_id == LENS_RESULT_SCHEMA_ID and isinstance(document.get("lens_result_id"), str):
            lens_id = document["lens_result_id"]
            locations.setdefault(lens_id, path)
            lens_documents.setdefault(lens_id, document)
        elif schema_id == FACT_SNAPSHOT_SCHEMA_ID:
            identity = document.get("identity")
            if isinstance(identity, Mapping) and isinstance(identity.get("ticker"), str):
                pinned_subjects.add(identity["ticker"].strip().upper())
            for fact in document.get("facts", []):
                if isinstance(fact, Mapping) and isinstance(fact.get("fact_id"), str):
                    fact_ids.add(fact["fact_id"])
    return locations, lens_documents, fact_ids, evidence_documents, pinned_subjects


def _has_unresolved_identity(run_manifest: Mapping[str, Any], documents: list[tuple[Path, dict[str, Any]]]) -> bool:
    def status(value: Any) -> str | None:
        if isinstance(value, str):
            return value.lower()
        if isinstance(value, Mapping):
            for key in ("status", "resolution_status", "identity_status"):
                candidate = value.get(key)
                if isinstance(candidate, str):
                    return candidate.lower()
        return None

    manifest_statuses = (status(run_manifest.get("identity_status")), status(run_manifest.get("identity_resolution")))
    if any(candidate in IDENTITY_BLOCKING_STATES for candidate in manifest_statuses):
        return True
    for _, document in documents:
        schema_id = document.get("schema_id")
        if schema_id == IDENTITY_RESOLUTION_SCHEMA_ID:
            candidates = (status(document.get("status")), status(document.get("resolution_status")))
        elif schema_id == FACT_SNAPSHOT_SCHEMA_ID:
            candidates = (status(document.get("identity_status")), status(document.get("identity_resolution")))
        else:
            continue
        if any(candidate in IDENTITY_BLOCKING_STATES for candidate in candidates):
            return True
    return False


def _assert_no_portfolio_fields(value: Any) -> None:
    forbidden = {"weight", "weights", "allocation", "allocations", "portfolio_weight", "position_size", "sizing"}
    for key, _ in _walk(value):
        if key.lower() in forbidden:
            _invalid("portfolio allocation fields are outside the decision contract", field=key)


def _assert_schema(decision: Mapping[str, Any]) -> None:
    errors = sorted(Draft202012Validator(_schema(), format_checker=FormatChecker()).iter_errors(dict(decision)), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        _invalid("research decision fails schema validation", path=list(error.path), reason=error.message)


def _assert_manifest_intent(decision: Mapping[str, Any], run_manifest: Mapping[str, Any]) -> None:
    if decision.get("as_of") != run_manifest.get("as_of"):
        _invalid("decision as_of does not match the run manifest")
    scope = decision.get("scope")
    if not isinstance(scope, Mapping) or scope.get("subjects") != run_manifest.get("subjects"):
        _invalid("decision scope subjects do not match the run manifest")
    expected_kind = RUN_MODE_TO_SCOPE_KIND.get(run_manifest.get("mode"))
    if expected_kind is None or scope.get("kind") != expected_kind:
        _invalid("decision scope kind does not match the run manifest")


def _assert_required_evidence(
    decision: Mapping[str, Any],
    *,
    evidence_ids: list[str],
    evidence_documents: Mapping[str, Mapping[str, Any]],
) -> None:
    action = decision.get("action")
    required_evidence = decision.get("required_evidence")
    if not isinstance(required_evidence, list):
        _invalid("decision required_evidence must be structured")
    for item in required_evidence:
        if not isinstance(item, Mapping):
            _invalid("decision required_evidence must be structured")
        evidence_id = item.get("evidence_result_id")
        if not isinstance(evidence_id, str) or evidence_id not in evidence_ids:
            _invalid("required evidence must be linked by evidence_result_ids", evidence_result_id=evidence_id)
        document = evidence_documents.get(evidence_id)
        if document is None:
            _invalid("required evidence must resolve to a saved evidence result", evidence_result_id=evidence_id)
        availability = document.get("availability")
        if availability not in EVIDENCE_AVAILABILITY:
            _invalid("required evidence has no recognized availability", evidence_result_id=evidence_id)
        action_critical = item.get("action_critical")
        unusable = availability in UNUSABLE_EVIDENCE_AVAILABILITY or (availability == "not_disclosed" and action_critical is True)
        if unusable and action != "BLOCKED":
            _invalid(
                "unusable action-critical evidence requires a BLOCKED action",
                evidence_result_id=evidence_id,
                availability=availability,
            )


def _assert_trigger_conditions(
    decision: Mapping[str, Any], evidence_documents: Mapping[str, Mapping[str, Any]]) -> None:
    if decision.get("action") != "ENTER_ON_TRIGGER":
        return
    conditions = decision.get("conditions")
    if not isinstance(conditions, list):
        _invalid("ENTER_ON_TRIGGER requires structured conditions")
    primary_conditions = [item for item in conditions if isinstance(item, Mapping) and item.get("primary") is True]
    if len(primary_conditions) != 1:
        _invalid("ENTER_ON_TRIGGER requires exactly one primary observable condition")
    primary = primary_conditions[0]
    expiry = primary.get("expires_at")
    if not isinstance(expiry, str):
        _invalid("ENTER_ON_TRIGGER primary condition requires an expiry")
    try:
        parse_instant(expiry)
    except SerenityError:
        _invalid("ENTER_ON_TRIGGER primary condition expiry must be an ISO datetime")
    reference = primary.get("evidence_ref")
    if not isinstance(reference, Mapping):
        _invalid("ENTER_ON_TRIGGER primary condition requires a stable source reference")
    source_uri = reference.get("source_uri")
    parsed_uri = urlparse(source_uri) if isinstance(source_uri, str) else None
    if parsed_uri is None or not parsed_uri.scheme or not (parsed_uri.netloc or parsed_uri.path):
        _invalid("ENTER_ON_TRIGGER primary condition requires a stable source URI")
    evidence_id = reference.get("evidence_result_id")
    document = evidence_documents.get(evidence_id) if isinstance(evidence_id, str) else None
    source = document.get("source") if isinstance(document, Mapping) else None
    if not isinstance(source, Mapping) or source_uri != source.get("uri") or reference.get("canonical_id") != source.get("canonical_id"):
        _invalid("ENTER_ON_TRIGGER source reference does not match saved evidence", evidence_result_id=evidence_id)


def _assert_common_semantics(
    decision: Mapping[str, Any],
    *,
    project_root: Path,
    run_manifest: Mapping[str, Any],
    run_dir: Path,
    evidence_manifest: Mapping[str, Any],
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    if decision.get("schema_id") != DECISION_SCHEMA_ID:
        _invalid("decision schema_id is not research-decision/1")
    _assert_schema(decision)
    _assert_no_portfolio_fields(decision)

    action = decision.get("action")
    if action not in ACTIONS:
        _invalid("decision action is not permitted", action=action)
    trusted_manifest = _load_trusted_manifest(project_root, run_manifest, run_dir)
    if decision.get("run_id") != trusted_manifest.get("run_id"):
        _invalid("decision run_id does not match the run manifest")
    _assert_manifest_intent(decision, trusted_manifest)
    if run_dir.name != trusted_manifest.get("run_id"):
        raise SerenityError("invalid_lifecycle", "run directory and manifest identity differ", 3, run_dir=str(run_dir))
    if trusted_manifest.get("status") != "OPEN":
        raise SerenityError("invalid_lifecycle", "only an OPEN run can finalize a decision", 3, status=trusted_manifest.get("status"))

    if not isinstance(decision.get("strongest_bear_case"), str) or not decision["strongest_bear_case"].strip():
        _invalid("decision requires a strongest bear case")
    if not _as_strings(decision.get("falsifiers")):
        _invalid("decision requires at least one falsifier")
    evidence_ids = _as_strings(decision.get("evidence_result_ids"))
    if not evidence_ids:
        _invalid("decision requires linked evidence")
    documents = _load_attached_artifact_documents(project_root, trusted_manifest, run_dir)
    locations, lens_documents, fact_ids, evidence_documents, pinned_subjects = _artifact_index(documents)
    reference_ids = _as_strings(decision.get("hypothesis_ids")) + evidence_ids
    for lens in decision.get("lens_results", []):
        if isinstance(lens, dict) and isinstance(lens.get("lens_result_id"), str):
            reference_ids.append(lens["lens_result_id"])
    for reference in reference_ids:
        if reference not in locations:
            _invalid("decision reference is absent from run artifacts", reference=reference)
    manifest_ids = _as_strings(evidence_manifest.get("evidence_result_ids"))
    if not set(evidence_ids).issubset(manifest_ids):
        _invalid("evidence manifest does not cover every decision evidence result")
    _assert_required_evidence(decision, evidence_ids=evidence_ids, evidence_documents=evidence_documents)
    _assert_trigger_conditions(decision, evidence_documents)

    unpinned = _unpinned_subjects(decision, pinned_subjects)
    if (_has_unresolved_identity(trusted_manifest, documents) or unpinned) and action != "BLOCKED":
        detail = f": no pinned fact snapshot for {', '.join(unpinned)}" if unpinned else ""
        raise SerenityError("identity_unresolved", f"unresolved identity requires a BLOCKED decision{detail}", 3)
    return lens_documents, fact_ids


def _unpinned_subjects(decision: Mapping[str, Any], pinned_subjects: set[str]) -> list[str]:
    """Subjects that name a security the run never bound to an identity.

    Only ``single-name`` and ``cohort`` subjects are securities. A ``macro``
    subject is a series identifier such as DGS10 and a ``sector`` subject is an
    industry, so demanding ``snapshot security`` for either would ask for an
    identity resolution that has no meaning for the subject. A cohort peer left
    unpinned is the case this exists for: a comparison whose peers were never
    identity-bound compares whatever their tickers happened to resolve to.
    """

    scope = decision.get("scope")
    if not isinstance(scope, Mapping) or scope.get("kind") not in SECURITY_SCOPE_KINDS:
        return []
    subjects = {subject.strip().upper() for subject in _as_strings(scope.get("subjects"))}
    return sorted(subjects - pinned_subjects)


def _assert_numeric_target(decision: Mapping[str, Any], lens_documents: Mapping[str, Mapping[str, Any]], fact_ids: set[str]) -> None:
    target = decision.get("numeric_target")
    if target is None:
        return
    if not isinstance(target, dict):
        _invalid("numeric_target must be an object")
    lens_id = target.get("lens_result_id")
    if not isinstance(lens_id, str) or lens_id not in lens_documents:
        _invalid("numeric target must reference a saved lens result")
    lens = lens_documents[lens_id]
    validity = lens.get("lens_validity", lens.get("validity"))
    if target.get("lens_validity") != "valid" or validity != "valid":
        _invalid("numeric target requires a valid lens result", lens_result_id=lens_id)
    if not isinstance(lens.get("reproducibility_hash"), str) or not re.fullmatch(r"[0-9a-f]{64}", lens["reproducibility_hash"]):
        _invalid("numeric target requires a reproducible saved lens result", lens_result_id=lens_id)
    target_refs = _as_strings(target.get("fact_refs"))
    lens_refs = _as_strings(lens.get("fact_refs"))
    if not target_refs or set(target_refs) != set(lens_refs) or not set(target_refs).issubset(fact_ids):
        _invalid("numeric target must carry every valid lens fact reference", lens_result_id=lens_id)


def validate_decision(
    *,
    project_root: Path,
    run_manifest: Mapping[str, Any],
    run_dir: Path,
    decision_draft: Mapping[str, Any],
    evidence_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a decision through its artifact boundary without mutating state."""
    decision = copy.deepcopy(dict(decision_draft))
    lens_documents, fact_ids = _assert_common_semantics(
        decision,
        project_root=project_root,
        run_manifest=run_manifest,
        run_dir=run_dir,
        evidence_manifest=evidence_manifest,
    )
    _assert_numeric_target(decision, lens_documents, fact_ids)
    return {"valid": True, "decision_id": decision["decision_id"], "lineage_id": decision["lineage_id"], "version": decision["version"]}


def _read_current(lineage_dir: Path) -> dict[str, Any] | None:
    path = lineage_dir / "current.json"
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SerenityError("persistence_conflict", f"current decision pointer cannot be read: {path}", 5, path=str(path)) from exc
    if not isinstance(value, dict):
        raise SerenityError("persistence_conflict", f"current decision pointer is invalid: {path}", 5, path=str(path))
    if not _content_hash_is_valid(value):
        raise SerenityError("persistence_conflict", f"current decision pointer content hash mismatch: {path}", 5, path=str(path))
    return value


def _existing_versions(lineage_dir: Path) -> list[int]:
    versions: list[int] = []
    if not lineage_dir.exists():
        return versions
    for path in lineage_dir.iterdir():
        if path.is_dir() and re.fullmatch(r"v\d{3}", path.name):
            versions.append(int(path.name[1:]))
    return sorted(versions)


def _assert_lineage(decision: Mapping[str, Any], lineage_dir: Path) -> None:
    versions = _existing_versions(lineage_dir)
    expected_version = (versions[-1] if versions else 0) + 1
    if decision.get("version") != expected_version:
        if decision.get("version") in versions:
            raise SerenityError("persistence_conflict", "decision version already exists", 5, version=decision.get("version"))
        _invalid("decision version must be the next immutable lineage version", expected_version=expected_version)
    previous = _read_current(lineage_dir)
    if expected_version == 1:
        if decision.get("supersedes") or decision.get("changed_because"):
            _invalid("first decision version cannot supersede another decision")
        return
    if not isinstance(decision.get("supersedes"), str) or decision.get("supersedes") != (previous or {}).get("decision_id"):
        _invalid("revised decision must supersede the current decision")
    if not isinstance(decision.get("changed_because"), str) or not decision["changed_because"].strip():
        _invalid("revised decision requires changed_because")


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _finalization_intent(decision_draft: Mapping[str, Any], analysis_markdown: str, evidence_manifest: Mapping[str, Any]) -> dict[str, Any]:
    decision = copy.deepcopy(dict(decision_draft))
    decision.pop("finalized_at", None)
    decision.pop("content_hash", None)
    manifest = copy.deepcopy(dict(evidence_manifest))
    manifest.pop("content_hash", None)
    intent_payload = {
        "decision_draft": decision,
        "analysis_sha256": _hash_text(analysis_markdown),
        "evidence_manifest": manifest,
    }
    return {
        "receipt_id": f"finalization-{canonical_hash(intent_payload)[:20]}",
        "intent_hash": canonical_hash(intent_payload),
        "analysis_sha256": intent_payload["analysis_sha256"],
        "evidence_manifest_intent_hash": canonical_hash(manifest),
    }


def _pointer(project_root: Path, lineage_id: str, version_dir: Path, decision: Mapping[str, Any]) -> dict[str, Any]:
    pointer = {
        "lineage_id": lineage_id,
        "version": decision["version"],
        "decision_id": decision["decision_id"],
        "decision_content_hash": decision["content_hash"],
        "record_dir": str(version_dir.relative_to(project_root)),
        "updated_at": utc_now(),
    }
    pointer["content_hash"] = canonical_hash(pointer)
    return pointer


def _read_record_document(path: Path, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SerenityError("persistence_conflict", f"published {label} cannot be read: {path}", 5, path=str(path)) from exc
    if not isinstance(value, dict):
        raise SerenityError("persistence_conflict", f"published {label} is not an object: {path}", 5, path=str(path))
    return value


def _recover_published_version(
    *,
    project_root: Path,
    lineage_dir: Path,
    version_dir: Path,
    intent: Mapping[str, Any],
) -> dict[str, Any]:
    decision = _read_record_document(version_dir / "decision.json", label="decision")
    evidence_manifest = _read_record_document(version_dir / "evidence-manifest.json", label="evidence manifest")
    receipt = _read_record_document(version_dir / "finalization-receipt.json", label="finalization receipt")
    try:
        validate_document(decision, DECISION_SCHEMA_ID)
    except SchemaViolation as exc:
        raise SerenityError("persistence_conflict", f"published decision fails schema validation: {exc}", 5) from exc
    if not _content_hash_is_valid(decision) or not _content_hash_is_valid(evidence_manifest) or not _content_hash_is_valid(receipt):
        raise SerenityError("persistence_conflict", "published finalization record content hash mismatch", 5)
    if receipt.get("intent_hash") != intent["intent_hash"] or receipt.get("receipt_id") != intent["receipt_id"]:
        raise SerenityError("persistence_conflict", "existing decision version belongs to a different finalization intent", 5)
    if receipt.get("decision_content_hash") != decision.get("content_hash"):
        raise SerenityError("persistence_conflict", "finalization receipt does not match published decision", 5)
    if receipt.get("evidence_manifest_content_hash") != evidence_manifest.get("content_hash"):
        raise SerenityError("persistence_conflict", "finalization receipt does not match published evidence manifest", 5)
    if receipt.get("analysis_sha256") != intent["analysis_sha256"] or receipt.get("evidence_manifest_intent_hash") != intent["evidence_manifest_intent_hash"]:
        raise SerenityError("persistence_conflict", "finalization receipt does not match retried inputs", 5)
    try:
        analysis_markdown = (version_dir / "analysis.md").read_text(encoding="utf-8")
    except OSError as exc:
        raise SerenityError("persistence_conflict", "published analysis markdown cannot be read", 5, path=str(version_dir / "analysis.md")) from exc
    if _hash_text(analysis_markdown) != receipt["analysis_sha256"]:
        raise SerenityError("persistence_conflict", "published analysis markdown hash mismatch", 5)
    current = _read_current(lineage_dir)
    if current is not None and (current.get("lineage_id"), current.get("version"), current.get("decision_id")) != (
        decision["lineage_id"],
        decision["version"],
        decision["decision_id"],
    ):
        raise SerenityError("persistence_conflict", "current decision pointer advanced to a different version", 5)
    pointer = _pointer(project_root, decision["lineage_id"], version_dir, decision)
    if current is None:
        atomic_write_json(lineage_dir / "current.json", pointer)
    else:
        pointer = current
    return {"decision": decision, "pointer": pointer, "receipt": receipt}


def finalize_decision(
    *,
    project_root: Path,
    run_manifest: Mapping[str, Any],
    run_dir: Path,
    decision_draft: Mapping[str, Any],
    analysis_markdown: str,
    evidence_manifest: Mapping[str, Any],
    fault_injector: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    """Persist a validated decision as an immutable lineage version and move its pointer."""
    validation = validate_decision(
        project_root=project_root,
        run_manifest=run_manifest,
        run_dir=run_dir,
        decision_draft=decision_draft,
        evidence_manifest=evidence_manifest,
    )
    if not isinstance(analysis_markdown, str) or not analysis_markdown.strip():
        _invalid("finalization requires non-empty analysis markdown")
    decision = copy.deepcopy(dict(decision_draft))
    lineage_id = decision["lineage_id"]
    if not isinstance(lineage_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", lineage_id):
        _invalid("lineage_id is unsafe for immutable storage")
    lineage_dir = project_root / "records" / "decisions" / lineage_id
    version_dir = lineage_dir / f"v{decision['version']:03d}"
    intent = _finalization_intent(decision, analysis_markdown, evidence_manifest)
    if version_dir.exists():
        recovered = _recover_published_version(
            project_root=project_root,
            lineage_dir=lineage_dir,
            version_dir=version_dir,
            intent=intent,
        )
        return {
            "validation": validation,
            "record_dir": str(version_dir),
            "decision_path": str(version_dir / "decision.json"),
            "current": recovered["pointer"],
            "finalization_receipt": {**recovered["receipt"], "state": "recovered"},
            "run_update": {"status": "FINALIZED", "current_phase": "decision_finalized"},
        }
    _assert_lineage(decision, lineage_dir)

    decision["finalized_at"] = utc_now()
    decision["content_hash"] = canonical_hash(decision)
    stored_manifest = copy.deepcopy(dict(evidence_manifest))
    stored_manifest["content_hash"] = canonical_hash(stored_manifest)
    receipt = {
        **intent,
        "lineage_id": lineage_id,
        "version": decision["version"],
        "decision_id": decision["decision_id"],
        "decision_content_hash": decision["content_hash"],
        "evidence_manifest_content_hash": stored_manifest["content_hash"],
    }
    receipt["content_hash"] = canonical_hash(receipt)
    immutable_directory(
        version_dir,
        {
            "decision.json": canonical_json(decision),
            "analysis.md": analysis_markdown,
            "evidence-manifest.json": canonical_json(stored_manifest),
            "finalization-receipt.json": canonical_json(receipt),
        },
    )
    if fault_injector is not None:
        fault_injector("after_version_published")
    pointer = _pointer(project_root, lineage_id, version_dir, decision)
    atomic_write_json(lineage_dir / "current.json", pointer)
    return {
        "validation": validation,
        "record_dir": str(version_dir),
        "decision_path": str(version_dir / "decision.json"),
        "current": pointer,
        "finalization_receipt": {**receipt, "state": "published"},
        "run_update": {"status": "FINALIZED", "current_phase": "decision_finalized"},
    }
