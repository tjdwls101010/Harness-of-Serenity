"""Canonical, provider-neutral research artifacts for one active v2 run."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from serenity_core.schema import SchemaViolation, validate_document


HYPOTHESIS_LEDGER_SCHEMA_ID = "urn:serenity:schema:hypothesis-ledger:1"
EVIDENCE_CATALOG_SCHEMA_ID = "urn:serenity:schema:evidence-catalog:1"
EVIDENCE_REQUEST_SCHEMA_ID = "urn:serenity:schema:evidence-request:1"
EVIDENCE_RESULT_SCHEMA_ID = "urn:serenity:schema:evidence-result:1"
PROVIDER_ENVELOPE_SCHEMA_ID = "urn:serenity:schema:provider-envelope:1"
RUN_MANIFEST_SCHEMA_ID = "urn:serenity:schema:run-manifest:2"

HYPOTHESIS_STATUSES = frozenset({"open", "supported", "weakened", "rejected", "unresolved"})
AVAILABILITY = frozenset(
    {"available", "not_disclosed", "not_applicable", "unavailable", "invalid", "not_requested", "stale", "conflict"}
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_REQUIRED_PROVIDERS = frozenset(
    {
        "yfinance",
        "sec",
        "openfigi",
        "alfred-fred",
        "ibd-rs-rating",
        "usaspending",
        "usitc",
        "eia",
        "bls",
        "bea",
        "cftc",
        "federal-register",
        "bis",
        "issuer-ir",
    }
)


class ResearchArtifactError(Exception):
    """Base error for caller-visible research artifact failures."""


class ResearchArtifactValidationError(ResearchArtifactError):
    """Raised when a typed artifact is invalid or cannot be linked safely."""


class ResearchArtifactConflictError(ResearchArtifactError):
    """Raised when an existing artifact or revision cannot be safely replaced."""


@dataclass(frozen=True)
class PreparedResearchMutation:
    """Immutable bytes prepared outside the RunStore lifecycle lock for CAS publication."""

    ledger: dict[str, Any]
    ledger_path: Path
    ledger_content: bytes
    request: dict[str, Any] | None = None
    request_path: Path | None = None
    request_content: bytes | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def content_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _document_bytes(document: Mapping[str, Any]) -> bytes:
    return (canonical_json(dict(document)) + "\n").encode("utf-8")


def load_evidence_catalog(path: Path | None = None) -> dict[str, Any]:
    """Load the checked-in provider-capability registry without fetching any data."""

    catalog_path = path or Path(__file__).resolve().parents[2] / "config" / "evidence-catalog.v1.json"
    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResearchArtifactValidationError(f"evidence catalog cannot be read: {catalog_path}") from exc
    if not isinstance(catalog, dict):
        raise ResearchArtifactValidationError("evidence catalog must be an object")
    _validate_schema(catalog, EVIDENCE_CATALOG_SCHEMA_ID)
    _validate_catalog_semantics(catalog)
    return catalog


class ResearchArtifactStore:
    """Persist canonical research artifacts under a caller-provided OPEN run directory."""

    def __init__(self, run_dir: Path) -> None:
        self.run_dir = Path(run_dir)
        try:
            self._project_root = self.run_dir.parents[2]
        except IndexError as exc:
            raise ResearchArtifactValidationError(f"run directory has no project root: {self.run_dir}") from exc
        self.run_id = self._read_run_id()
        self.catalog = load_evidence_catalog()
        self._capability_owners = {
            capability: provider["provider_id"]
            for provider in self.catalog["providers"]
            for capability in provider["capabilities"]
        }
        self._provider_ids = {provider["provider_id"] for provider in self.catalog["providers"]}
        self._ledger_revision_dir = self.run_dir / "evidence" / "ledger-revisions"
        self._request_dir = self.run_dir / "evidence" / "requests"
        self._result_dir = self.run_dir / "evidence" / "results"

    def prepare_hypotheses(
        self, hypotheses: Sequence[Mapping[str, Any]], *, expected_revision: int | None = None
    ) -> PreparedResearchMutation:
        """Prepare, but do not publish, an immutable ledger revision for RunStore CAS."""

        normalized = _normalize_hypotheses(hypotheses)
        existing = self._read_attached_ledger_optional()
        if existing is None:
            if expected_revision is not None:
                raise ResearchArtifactConflictError("revision conflict: ledger does not exist")
            revision = 1
            created_at = utc_now()
            history: list[dict[str, Any]] = []
        else:
            if expected_revision != existing["revision"]:
                raise ResearchArtifactConflictError(
                    f"revision conflict: expected {expected_revision!r}, current {existing['revision']!r}"
                )
            revision = existing["revision"] + 1
            created_at = existing["created_at"]
            history = [
                *existing["history"],
                {"revision": existing["revision"], "content_hash": existing["content_hash"], "updated_at": existing["updated_at"]},
            ]
            prior_requested = {
                hypothesis["hypothesis_id"]: hypothesis["requested_evidence_ids"] for hypothesis in existing["hypotheses"]
            }
            for hypothesis in normalized:
                hypothesis["requested_evidence_ids"] = sorted(
                    set(hypothesis["requested_evidence_ids"]) | set(prior_requested.get(hypothesis["hypothesis_id"], []))
                )
        ledger = self._build_ledger(
            hypotheses=normalized,
            revision=revision,
            created_at=created_at,
            updated_at=utc_now(),
            history=history,
        )
        return self._prepared_mutation(ledger)

    def prepare_evidence_request(
        self, *, hypothesis_ids: Sequence[str], capability_id: str, request: Mapping[str, Any]
    ) -> PreparedResearchMutation:
        """Prepare an idempotent request and its linked immutable ledger revision without writing either."""

        ledger = self._read_attached_ledger_optional()
        if ledger is None:
            raise ResearchArtifactValidationError("hypothesis ledger must be attached before requesting evidence")
        normalized_hypothesis_ids = _normalize_identifiers(hypothesis_ids, "hypothesis_ids", required=True)
        known_hypotheses = {hypothesis["hypothesis_id"] for hypothesis in ledger["hypotheses"]}
        unknown_hypotheses = set(normalized_hypothesis_ids) - known_hypotheses
        if unknown_hypotheses:
            raise ResearchArtifactValidationError(f"unknown hypothesis_ids: {sorted(unknown_hypotheses)}")
        if not isinstance(capability_id, str) or capability_id not in self._capability_owners:
            raise ResearchArtifactValidationError(f"capability_id is not declared by the evidence catalog: {capability_id}")
        request_body = _normalize_request_body(request, provider_ids=self._provider_ids)
        owner = self._capability_owners[capability_id]
        if owner not in request_body["provider_policy"]["providers"]:
            raise ResearchArtifactValidationError(f"provider_policy must include capability owner: {owner}")
        seed = {
            "schema_id": EVIDENCE_REQUEST_SCHEMA_ID,
            "run_id": self.run_id,
            "hypothesis_ids": normalized_hypothesis_ids,
            "capability_id": capability_id,
            **request_body,
        }
        request_id = f"evidence-request-{content_hash(seed)[:20]}"
        request_document = {**seed, "request_id": request_id}
        request_document["content_hash"] = content_hash(request_document)
        _validate_request(request_document, self.run_id)
        request_path = self._request_path(request_id)
        existing_request = self._read_optional(request_path)
        if existing_request is not None:
            _validate_request(existing_request, self.run_id)
            if existing_request != request_document:
                raise ResearchArtifactConflictError(f"request content conflict: {request_id}")
        linked = self._prepare_request_link(ledger, request_document)
        mutation = self._prepared_mutation(linked)
        return PreparedResearchMutation(
            ledger=mutation.ledger,
            ledger_path=mutation.ledger_path,
            ledger_content=mutation.ledger_content,
            request=request_document,
            request_path=request_path,
            request_content=_document_bytes(request_document),
        )

    def put_hypotheses(
        self, hypotheses: Sequence[Mapping[str, Any]], *, expected_revision: int | None = None
    ) -> dict[str, Any]:
        raise ResearchArtifactValidationError(
            "direct mutable ledger writes are retired; use prepare_hypotheses() and RunStore.publish_or_refresh_artifact()"
        )

    def read_hypothesis_ledger(self) -> dict[str, Any]:
        return self.read_current_hypothesis_ledger()

    def read_current_hypothesis_ledger(self) -> dict[str, Any]:
        """Read the manifest-attached immutable ledger revision used by lifecycle consumers."""

        ledger = self._read_attached_ledger_optional()
        if ledger is None:
            raise ResearchArtifactValidationError("hypothesis ledger is not attached to the current run")
        return ledger

    def create_evidence_request(
        self, *, hypothesis_ids: Sequence[str], capability_id: str, request: Mapping[str, Any]
    ) -> dict[str, Any]:
        raise ResearchArtifactValidationError(
            "direct mutable request writes are retired; use prepare_evidence_request() and RunStore publication"
        )

    def read_evidence_request(self, request_id: str) -> dict[str, Any]:
        request = self._read_required(self._request_path(request_id), "evidence request")
        _validate_request(request, self.run_id)
        return request

    def record_evidence_result(self, *, request_id: str, evidence: Mapping[str, Any]) -> dict[str, Any]:
        """Store a result only when its request, run, provenance, and availability agree."""

        request = self.read_evidence_request(request_id)
        if not isinstance(evidence, Mapping):
            raise ResearchArtifactValidationError("evidence must be an object")
        _check_optional_equal(evidence, "run_id", self.run_id, "run_id does not match active run")
        _check_optional_equal(evidence, "request_id", request_id, "request_id does not match request")
        _check_optional_equal(evidence, "capability_id", request["capability_id"], "capability_id does not match request")
        if "hypothesis_ids" in evidence and _normalize_identifiers(evidence["hypothesis_ids"], "hypothesis_ids", required=True) != request[
            "hypothesis_ids"
        ]:
            raise ResearchArtifactValidationError("hypothesis_ids do not match request")
        result_seed = self._result_seed_from_evidence(request, evidence)
        owner = self._capability_owners[request["capability_id"]]
        if result_seed.get("provider") != owner:
            raise ResearchArtifactValidationError("evidence provider does not own the request capability")
        result_id = f"evidence-result-{content_hash(result_seed)[:20]}"
        if "result_id" in evidence and evidence["result_id"] != result_id:
            raise ResearchArtifactValidationError("result_id does not match content-addressed result")
        artifact = {**result_seed, "result_id": result_id}
        artifact["content_hash"] = content_hash(artifact)
        _validate_result(artifact, self.run_id)
        path = self._result_path(result_id)
        existing = self._read_optional(path)
        if existing is not None:
            _validate_result(existing, self.run_id)
            if existing != artifact:
                raise ResearchArtifactConflictError(f"result content conflict: {result_id}")
            return existing
        self._write_atomic(path, artifact, create_only=True)
        return artifact

    def read_evidence_result(self, result_id: str) -> dict[str, Any]:
        result = self._read_required(self._result_path(result_id), "evidence result")
        _validate_result(result, self.run_id)
        request = self.read_evidence_request(result["request_id"])
        if result["hypothesis_ids"] != request["hypothesis_ids"] or result["capability_id"] != request["capability_id"]:
            raise ResearchArtifactValidationError("stored result does not match its request")
        if result["provider"] != self._capability_owners[request["capability_id"]]:
            raise ResearchArtifactValidationError("stored result provider does not own the request capability")
        return result

    def _result_seed_from_evidence(self, request: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
        if "provider_envelope" in evidence:
            return self._result_seed_from_envelope(request, evidence)
        required = {
            "availability",
            "provider",
            "source",
            "temporal",
            "fetched_at",
            "raw_content_sha256",
            "transform_version",
            "identity_bindings",
            "fact_refs",
            "value",
        }
        missing = sorted(required - set(evidence))
        if missing:
            raise ResearchArtifactValidationError(f"evidence is missing required provenance fields: {missing}")
        return {
            "schema_id": EVIDENCE_RESULT_SCHEMA_ID,
            "run_id": self.run_id,
            "request_id": request["request_id"],
            "hypothesis_ids": request["hypothesis_ids"],
            "capability_id": request["capability_id"],
            "availability": evidence["availability"],
            "provider": evidence["provider"],
            "source": dict(evidence["source"]) if isinstance(evidence["source"], Mapping) else evidence["source"],
            "temporal": dict(evidence["temporal"]) if isinstance(evidence["temporal"], Mapping) else evidence["temporal"],
            "fetched_at": evidence["fetched_at"],
            "raw_content_sha256": evidence["raw_content_sha256"],
            "transform_version": evidence["transform_version"],
            "identity_bindings": dict(evidence["identity_bindings"])
            if isinstance(evidence["identity_bindings"], Mapping)
            else evidence["identity_bindings"],
            "fact_refs": _normalize_identifiers(evidence["fact_refs"], "fact_refs", required=False),
            "value": evidence["value"],
            **({"conflicts": list(evidence["conflicts"])} if "conflicts" in evidence else {}),
        }

    def _result_seed_from_envelope(self, request: Mapping[str, Any], evidence: Mapping[str, Any]) -> dict[str, Any]:
        envelope = evidence["provider_envelope"]
        if not isinstance(envelope, Mapping):
            raise ResearchArtifactValidationError("provider_envelope must be an object")
        envelope = dict(envelope)
        _validate_schema(envelope, PROVIDER_ENVELOPE_SCHEMA_ID)
        if envelope["request_id"] != request["request_id"]:
            raise ResearchArtifactValidationError("provider envelope request_id does not match request")
        canonical_id = evidence.get("canonical_id")
        if canonical_id is not None and not isinstance(canonical_id, str):
            raise ResearchArtifactValidationError("canonical_id must be a string or null")
        transform_version = evidence.get("transform_version")
        if transform_version is None:
            parse = envelope.get("parse")
            transform_version = parse.get("transform_version") if isinstance(parse, Mapping) else None
        if not isinstance(transform_version, str) or not transform_version:
            raise ResearchArtifactValidationError("provider envelope requires a transform_version")
        source = envelope["source"]
        return {
            "schema_id": EVIDENCE_RESULT_SCHEMA_ID,
            "run_id": self.run_id,
            "request_id": request["request_id"],
            "hypothesis_ids": request["hypothesis_ids"],
            "capability_id": request["capability_id"],
            "availability": envelope["status"],
            "provider": envelope["provider"],
            "source": {
                "uri": source["uri"],
                "parameters": dict(source.get("parameters", {})),
                "canonical_id": canonical_id,
            },
            "temporal": dict(envelope["temporal"]),
            "fetched_at": envelope["fetched_at"],
            "raw_content_sha256": source["content_sha256"],
            "transform_version": transform_version,
            "identity_bindings": dict(envelope.get("identity_bindings", {})),
            "fact_refs": _normalize_identifiers(evidence.get("fact_refs", []), "fact_refs", required=False),
            "value": envelope["data"],
            **({"conflicts": list(evidence["conflicts"])} if "conflicts" in evidence else {}),
        }

    def _build_ledger(
        self,
        *,
        hypotheses: list[dict[str, Any]],
        revision: int,
        created_at: str,
        updated_at: str,
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        ledger = {
            "schema_id": HYPOTHESIS_LEDGER_SCHEMA_ID,
            "ledger_id": f"hypothesis-ledger-{content_hash(self.run_id)[:20]}",
            "run_id": self.run_id,
            "revision": revision,
            "created_at": created_at,
            "updated_at": updated_at,
            "hypotheses": hypotheses,
            "history": history,
        }
        ledger["content_hash"] = content_hash(ledger)
        _validate_ledger(ledger, self.run_id)
        return ledger

    def _prepared_mutation(self, ledger: dict[str, Any]) -> PreparedResearchMutation:
        content = _document_bytes(ledger)
        return PreparedResearchMutation(
            ledger=ledger,
            ledger_path=self._ledger_revision_dir / f"{ledger['content_hash']}.json",
            ledger_content=content,
        )

    def _prepare_request_link(self, ledger: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
        requested_hypothesis_ids = set(request["hypothesis_ids"])
        changed = False
        hypotheses: list[dict[str, Any]] = []
        for current in ledger["hypotheses"]:
            hypothesis = dict(current)
            if hypothesis["hypothesis_id"] in requested_hypothesis_ids:
                requested_ids = sorted(set(hypothesis["requested_evidence_ids"]) | {request["request_id"]})
                if requested_ids != hypothesis["requested_evidence_ids"]:
                    hypothesis["requested_evidence_ids"] = requested_ids
                    changed = True
            hypotheses.append(hypothesis)
        if not changed:
            return dict(ledger)
        history = [
            *ledger["history"],
            {"revision": ledger["revision"], "content_hash": ledger["content_hash"], "updated_at": ledger["updated_at"]},
        ]
        return self._build_ledger(
            hypotheses=hypotheses,
            revision=ledger["revision"] + 1,
            created_at=ledger["created_at"],
            updated_at=utc_now(),
            history=history,
        )

    def _read_attached_ledger_optional(self) -> dict[str, Any] | None:
        manifest = self._read_run_manifest()
        attachment = manifest.get("artifacts", {}).get("hypothesis-ledger")
        if attachment is None:
            return None
        if not isinstance(attachment, Mapping):
            raise ResearchArtifactValidationError("hypothesis ledger attachment must be an object")
        if attachment.get("schema_id") != HYPOTHESIS_LEDGER_SCHEMA_ID:
            raise ResearchArtifactValidationError("hypothesis ledger attachment has an unexpected schema")
        relative_path = attachment.get("path")
        expected_hash = attachment.get("content_hash")
        if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
            raise ResearchArtifactValidationError("hypothesis ledger attachment is incomplete")
        path = (self._project_root / relative_path).resolve()
        root = self._project_root.resolve()
        if path != root and root not in path.parents:
            raise ResearchArtifactValidationError("hypothesis ledger attachment escapes the project root")
        if not path.is_file() or path.is_symlink():
            raise ResearchArtifactValidationError("hypothesis ledger attachment is not a regular file")
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != expected_hash:
            raise ResearchArtifactConflictError("hypothesis ledger attachment content hash does not match the run manifest")
        try:
            ledger = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ResearchArtifactValidationError("attached hypothesis ledger is not valid JSON") from exc
        if not isinstance(ledger, dict):
            raise ResearchArtifactValidationError("attached hypothesis ledger must be an object")
        _validate_ledger(ledger, self.run_id)
        return ledger

    def _read_run_manifest(self) -> dict[str, Any]:
        manifest = self._read_required(self.run_dir / "run-manifest.json", "run manifest")
        _validate_schema(manifest, RUN_MANIFEST_SCHEMA_ID)
        if manifest.get("run_id") != self.run_id or manifest.get("status") != "OPEN":
            raise ResearchArtifactValidationError(f"research artifacts require the current OPEN run: {self.run_id}")
        return manifest

    def _read_run_id(self) -> str:
        manifest = self._read_required(self.run_dir / "run-manifest.json", "run manifest")
        _validate_schema(manifest, RUN_MANIFEST_SCHEMA_ID)
        run_id = manifest.get("run_id")
        if not isinstance(run_id, str) or not _IDENTIFIER.fullmatch(run_id):
            raise ResearchArtifactValidationError("run manifest has an invalid run_id")
        if manifest.get("status") != "OPEN":
            raise ResearchArtifactValidationError(f"research artifacts require an OPEN run: {run_id}")
        return run_id

    def _request_path(self, request_id: str) -> Path:
        _validate_id(request_id, "evidence-request-", "request_id")
        return self._request_dir / f"{request_id}.json"

    def _result_path(self, result_id: str) -> Path:
        _validate_id(result_id, "evidence-result-", "result_id")
        return self._result_dir / f"{result_id}.json"

    @staticmethod
    def _read_optional(path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise ResearchArtifactConflictError(f"artifact cannot be read: {path}") from exc
        if not isinstance(value, dict):
            raise ResearchArtifactValidationError(f"artifact must be an object: {path}")
        return value

    def _read_required(self, path: Path, label: str) -> dict[str, Any]:
        value = self._read_optional(path)
        if value is None:
            raise ResearchArtifactValidationError(f"{label} not found: {path}")
        return value

    @staticmethod
    def _write_atomic(path: Path, value: Mapping[str, Any], *, create_only: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
        try:
            temporary.write_text(canonical_json(dict(value)) + "\n", encoding="utf-8")
            if create_only:
                try:
                    os.link(temporary, path)
                except FileExistsError as exc:
                    raise ResearchArtifactConflictError(f"artifact already exists: {path}") from exc
            else:
                os.replace(temporary, path)
        except ResearchArtifactConflictError:
            raise
        except OSError as exc:
            raise ResearchArtifactConflictError(f"artifact cannot be written: {path}") from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _normalize_hypotheses(hypotheses: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(hypotheses, (str, bytes)) or not isinstance(hypotheses, Sequence) or len(hypotheses) < 2:
        raise ResearchArtifactValidationError("at least two competing hypotheses are required")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, Mapping):
            raise ResearchArtifactValidationError("each hypothesis must be an object")
        hypothesis_id = hypothesis.get("hypothesis_id")
        _validate_id(hypothesis_id, "hyp-", "hypothesis_id")
        if hypothesis_id in seen:
            raise ResearchArtifactValidationError(f"duplicate hypothesis_id: {hypothesis_id}")
        seen.add(hypothesis_id)
        statement = hypothesis.get("statement")
        falsifier = hypothesis.get("falsifier")
        if not isinstance(statement, str) or not statement.strip() or not isinstance(falsifier, str) or not falsifier.strip():
            raise ResearchArtifactValidationError("hypothesis statement and falsifier must be non-empty strings")
        status = hypothesis.get("status")
        if status not in HYPOTHESIS_STATUSES:
            raise ResearchArtifactValidationError(f"hypothesis status must be one of {sorted(HYPOTHESIS_STATUSES)}")
        predictions = _normalize_strings(hypothesis.get("predictions"), "predictions", required=True)
        normalized.append(
            {
                "hypothesis_id": hypothesis_id,
                "statement": statement.strip(),
                "predictions": predictions,
                "falsifier": falsifier.strip(),
                "status": status,
                "supporting_fact_refs": _normalize_identifiers(
                    hypothesis.get("supporting_fact_refs", []), "supporting_fact_refs", required=False
                ),
                "contradicting_fact_refs": _normalize_identifiers(
                    hypothesis.get("contradicting_fact_refs", []), "contradicting_fact_refs", required=False
                ),
                "requested_evidence_ids": _normalize_identifiers(
                    hypothesis.get("requested_evidence_ids", []), "requested_evidence_ids", required=False
                ),
            }
        )
    return normalized


def _normalize_request_body(request: Mapping[str, Any], *, provider_ids: set[str]) -> dict[str, Any]:
    if not isinstance(request, Mapping):
        raise ResearchArtifactValidationError("request must be an object")
    required = {"question", "evidence_type", "provider_policy", "acceptance_criteria", "requested_at", "provider_parameters"}
    missing = sorted(required - set(request))
    if missing:
        raise ResearchArtifactValidationError(f"request is missing required fields: {missing}")
    allowed = required | {"status"}
    unexpected = sorted(set(request) - allowed)
    if unexpected:
        raise ResearchArtifactValidationError(f"request has unsupported fields: {unexpected}")
    question = request["question"]
    evidence_type = request["evidence_type"]
    if not isinstance(question, str) or not question.strip() or not isinstance(evidence_type, str) or not evidence_type.strip():
        raise ResearchArtifactValidationError("question and evidence_type must be non-empty strings")
    provider_policy = request["provider_policy"]
    if not isinstance(provider_policy, Mapping):
        raise ResearchArtifactValidationError("provider_policy must be an object")
    policy_allowed = {"providers", "historical_cutoff", "allow_network"}
    if set(provider_policy) - policy_allowed:
        raise ResearchArtifactValidationError("provider_policy has unsupported fields")
    providers = _normalize_strings(provider_policy.get("providers"), "provider_policy.providers", required=True)
    if unknown_providers := set(providers) - provider_ids:
        raise ResearchArtifactValidationError(f"provider_policy has unknown providers: {sorted(unknown_providers)}")
    normalized_policy: dict[str, Any] = {"providers": providers}
    for field in ("historical_cutoff", "allow_network"):
        if field in provider_policy:
            normalized_policy[field] = provider_policy[field]
    if not isinstance(request["provider_parameters"], Mapping):
        raise ResearchArtifactValidationError("provider_parameters must be an object")
    body: dict[str, Any] = {
        "question": question.strip(),
        "evidence_type": evidence_type.strip(),
        "provider_policy": normalized_policy,
        "acceptance_criteria": _normalize_strings(request["acceptance_criteria"], "acceptance_criteria", required=True),
        "requested_at": request["requested_at"],
        "provider_parameters": dict(request["provider_parameters"]),
    }
    if "status" in request:
        body["status"] = request["status"]
    return body


def _normalize_identifiers(values: Any, label: str, *, required: bool) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ResearchArtifactValidationError(f"{label} must be a list of identifiers")
    normalized = sorted(set(values))
    if len(normalized) != len(values):
        raise ResearchArtifactValidationError(f"{label} must not contain duplicates")
    if required and not normalized:
        raise ResearchArtifactValidationError(f"{label} must not be empty")
    for value in normalized:
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise ResearchArtifactValidationError(f"{label} contains an invalid identifier")
    return normalized


def _normalize_strings(values: Any, label: str, *, required: bool) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise ResearchArtifactValidationError(f"{label} must be a list of strings")
    normalized = [value.strip() if isinstance(value, str) else value for value in values]
    if required and not normalized:
        raise ResearchArtifactValidationError(f"{label} must not be empty")
    if any(not isinstance(value, str) or not value for value in normalized):
        raise ResearchArtifactValidationError(f"{label} contains an invalid string")
    if len(set(normalized)) != len(normalized):
        raise ResearchArtifactValidationError(f"{label} must not contain duplicates")
    return normalized


def _validate_id(value: Any, prefix: str, label: str) -> None:
    if not isinstance(value, str) or not value.startswith(prefix) or not _IDENTIFIER.fullmatch(value):
        raise ResearchArtifactValidationError(f"{label} must start with {prefix!r} and contain only safe identifier characters")


def _check_optional_equal(evidence: Mapping[str, Any], key: str, expected: Any, message: str) -> None:
    if key in evidence and evidence[key] != expected:
        raise ResearchArtifactValidationError(message)


def _validate_schema(document: Mapping[str, Any], schema_id: str) -> None:
    try:
        validate_document(dict(document), schema_id)
    except SchemaViolation as exc:
        raise ResearchArtifactValidationError(str(exc)) from exc


def _validate_hash(document: Mapping[str, Any], label: str) -> None:
    seed = {key: value for key, value in document.items() if key != "content_hash"}
    if document.get("content_hash") != content_hash(seed):
        raise ResearchArtifactValidationError(f"{label} content hash does not match")


def _validate_ledger(ledger: Mapping[str, Any], run_id: str) -> None:
    if ledger.get("run_id") != run_id:
        raise ResearchArtifactValidationError("hypothesis ledger does not match active run")
    _validate_schema(ledger, HYPOTHESIS_LEDGER_SCHEMA_ID)
    _validate_hash(ledger, "hypothesis ledger")


def _validate_request(request: Mapping[str, Any], run_id: str) -> None:
    if request.get("run_id") != run_id:
        raise ResearchArtifactValidationError("evidence request does not match active run")
    _validate_schema(request, EVIDENCE_REQUEST_SCHEMA_ID)
    _validate_hash(request, "evidence request")


def _validate_result(result: Mapping[str, Any], run_id: str) -> None:
    if result.get("run_id") != run_id:
        raise ResearchArtifactValidationError("evidence result does not match active run")
    _validate_schema(result, EVIDENCE_RESULT_SCHEMA_ID)
    _validate_hash(result, "evidence result")


def _validate_catalog_semantics(catalog: Mapping[str, Any]) -> None:
    providers = catalog["providers"]
    provider_ids = [provider["provider_id"] for provider in providers]
    if len(set(provider_ids)) != len(provider_ids):
        raise ResearchArtifactValidationError("evidence catalog has duplicate provider_id values")
    missing = _REQUIRED_PROVIDERS - set(provider_ids)
    if missing:
        raise ResearchArtifactValidationError(f"evidence catalog is missing required providers: {sorted(missing)}")
    capabilities = [capability for provider in providers for capability in provider["capabilities"]]
    if len(set(capabilities)) != len(capabilities):
        raise ResearchArtifactValidationError("evidence catalog has duplicate capability IDs")
    providers_by_id = {provider["provider_id"]: provider for provider in providers}
    if providers_by_id["ibd-rs-rating"].get("version") != "0.3.0":
        raise ResearchArtifactValidationError("ibd-rs-rating must declare version 0.3.0")
    sec = providers_by_id["sec"]
    if sec["tier"] != "baseline" or not {"sec.identity", "sec.submissions", "sec.filings"} <= set(sec["capabilities"]):
        raise ResearchArtifactValidationError("SEC must provide baseline identity, submissions, and filings capabilities")
