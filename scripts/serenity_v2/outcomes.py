"""Local, append-only prospective outcome records.

The store only accepts a finalized decision that is already present in the
immutable decision lineage. It records future observations without deciding
whether a condition should cause a trade.
"""

from __future__ import annotations

import copy
import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from serenity_v2.runtime import canonical_hash
from serenity_v2.schema import SchemaViolation, validate_document


DECISION_SCHEMA_ID = "urn:serenity:schema:research-decision:1"
PROSPECTIVE_RECORD_SCHEMA_ID = "urn:serenity:schema:prospective-record:1"
AVAILABILITY_STATES = frozenset(
    {
        "available",
        "not_disclosed",
        "not_applicable",
        "unavailable",
        "invalid",
        "not_requested",
        "stale",
        "conflict",
    }
)
MEASUREMENT_FIELDS = ("subject_price", "benchmark_return", "mechanism_evidence", "falsifier_state")


class OutcomesError(Exception):
    """Raised when a prospective record cannot preserve its immutable history."""

    def __init__(self, code: str, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def _usage(message: str) -> OutcomesError:
    return OutcomesError("usage_or_schema", message, 2)


def _missing_record(message: str) -> OutcomesError:
    return OutcomesError("record_not_found", message, 3)


def _persistence(message: str) -> OutcomesError:
    return OutcomesError("persistence_conflict", message, 5)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _content_hash(document: Mapping[str, Any]) -> str:
    return canonical_hash({key: value for key, value in document.items() if key != "content_hash"})


class OutcomesStore:
    """Persist finalized research decisions and their future measurements locally."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.records_dir = root / "records" / "prospective"

    def register(
        self,
        decision: Mapping[str, Any],
        *,
        benchmark: Mapping[str, Any],
        checkpoint_schedule: Sequence[Mapping[str, Any]],
    ) -> dict[str, Any]:
        """Create an immutable prospective contract from the current decision version."""
        decision_contract = self._validate_finalized_decision(decision)
        registration = {
            "decision": decision_contract,
            "benchmark": copy.deepcopy(dict(benchmark)),
            "checkpoint_schedule": [copy.deepcopy(dict(checkpoint)) for checkpoint in checkpoint_schedule],
        }
        record_id = f"prospective-{canonical_hash(registration)[:16]}"
        record: dict[str, Any] = {
            "schema_id": PROSPECTIVE_RECORD_SCHEMA_ID,
            "record_id": record_id,
            "content_hash": "",
            "registered_at": _utc_now(),
            **registration,
            "condition_hit_is_trade": False,
            "observations": [],
        }
        record["content_hash"] = _content_hash(record)
        self._validate_record_schema(record, error_factory=_usage)

        path = self._record_path(record_id)
        try:
            self._atomic_create(path, record)
        except FileExistsError:
            existing = self._read_record(record_id)
            existing_registration = {
                "decision": existing["decision"],
                "benchmark": existing["benchmark"],
                "checkpoint_schedule": existing["checkpoint_schedule"],
            }
            if canonical_hash(existing_registration) != canonical_hash(registration):
                raise _persistence(f"content-address conflict for prospective record: {record_id}")
            return self._compose(existing, self._load_observations(record_id, existing))
        return record

    def read(self, record_id: str) -> dict[str, Any]:
        """Read a schema-valid root plus its validated append-only observations."""
        record = self._read_record(record_id)
        return self._compose(record, self._load_observations(record_id, record))

    def refresh(self, record_id: str, *, observation: Mapping[str, Any]) -> dict[str, Any]:
        """Append one explicit measurement; a condition hit never becomes an order."""
        lock_path = self._observations_path(record_id).with_suffix(".lock")
        try:
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            with lock_path.open("a+", encoding="utf-8") as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                record = self._read_record(record_id)
                observations = self._load_observations(record_id, record)
                normalized = self._normalize_observation(record_id, observation)
                for existing in observations:
                    if existing["observation_id"] != normalized["observation_id"]:
                        continue
                    if existing["measurement_hash"] == normalized["measurement_hash"]:
                        return self._compose(record, observations)
                    raise _persistence(f"conflicting duplicate observation: {normalized['observation_id']}")

                event = {
                    **normalized,
                    "previous_event_hash": observations[-1]["event_hash"] if observations else record["content_hash"],
                    "refreshed_at": _utc_now(),
                    "condition_hit_is_trade": False,
                }
                event["event_hash"] = canonical_hash(event)
                updated = [*observations, event]
                self._compose(record, updated, error_factory=_usage)
                self._append_jsonl(self._observations_path(record_id), event)
                return self._compose(record, updated)
        except OSError as exc:
            raise _persistence(f"cannot append prospective observation: {record_id}") from exc

    def _validate_finalized_decision(self, decision: Mapping[str, Any]) -> dict[str, Any]:
        candidate = copy.deepcopy(dict(decision))
        try:
            validate_document(candidate, DECISION_SCHEMA_ID)
        except SchemaViolation as exc:
            raise _usage(f"immutable decision fails schema validation: {exc}") from exc
        if not candidate.get("finalized_at"):
            raise _usage("immutable decision is not finalized")
        if candidate.get("content_hash") != _content_hash(candidate):
            raise _persistence("immutable decision content hash mismatch")

        lineage_id = candidate["lineage_id"]
        version = candidate["version"]
        version_dir = self.root / "records" / "decisions" / lineage_id / f"v{version:03d}"
        decision_path = version_dir / "decision.json"
        stored = self._read_json(decision_path, label="immutable decision")
        try:
            validate_document(stored, DECISION_SCHEMA_ID)
        except SchemaViolation as exc:
            raise _persistence(f"stored immutable decision fails schema validation: {exc}") from exc
        if stored.get("content_hash") != _content_hash(stored):
            raise _persistence("stored immutable decision content hash mismatch")
        if stored != candidate:
            raise _persistence("immutable decision does not exactly match its stored version")

        pointer_path = version_dir.parent / "current.json"
        pointer = self._read_json(pointer_path, label="current decision pointer")
        expected_record_dir = str(version_dir.relative_to(self.root))
        expected_pointer = {
            "lineage_id": lineage_id,
            "version": version,
            "decision_id": candidate["decision_id"],
            "decision_content_hash": candidate["content_hash"],
            "record_dir": expected_record_dir,
        }
        if any(pointer.get(key) != value for key, value in expected_pointer.items()):
            raise _persistence("immutable decision is not the current lineage pointer")
        if pointer.get("content_hash") != _content_hash(pointer):
            raise _persistence("current decision pointer content hash mismatch")

        return {
            "decision_id": candidate["decision_id"],
            "lineage_id": lineage_id,
            "version": version,
            "decision_content_hash": candidate["content_hash"],
            "current_pointer_hash": pointer["content_hash"],
            "action": candidate["action"],
            "as_of": candidate["as_of"],
            "entry_conditions": [
                {"condition": item["condition"], "status": item["status"]} for item in candidate["conditions"]
            ],
            "falsifiers": list(candidate["falsifiers"]),
        }

    def _read_record(self, record_id: str) -> dict[str, Any]:
        path = self._record_path(record_id)
        record = self._read_json(path, label="prospective record", missing_error_factory=_missing_record)
        if record.get("record_id") != record_id:
            raise _persistence(f"prospective record identity mismatch: {record_id}")
        self._validate_record_schema(record, error_factory=_persistence)
        if record.get("content_hash") != _content_hash(record):
            raise _persistence(f"prospective root content hash mismatch: {record_id}")
        if record.get("observations") != []:
            raise _persistence(f"prospective root must not embed observations: {record_id}")
        return record

    def _compose(
        self,
        record: Mapping[str, Any],
        observations: Sequence[Mapping[str, Any]],
        *,
        error_factory: Any = _persistence,
    ) -> dict[str, Any]:
        composite = copy.deepcopy(dict(record))
        composite["observations"] = [copy.deepcopy(dict(event)) for event in observations]
        self._validate_record_schema(composite, error_factory=error_factory)
        self._verify_hash_chain(composite)
        return composite

    def _normalize_observation(self, record_id: str, observation: Mapping[str, Any]) -> dict[str, Any]:
        value = copy.deepcopy(dict(observation))
        observation_id = value.get("observation_id")
        if not isinstance(observation_id, str) or not observation_id:
            raise _usage("prospective observation requires a stable observation_id")
        if not isinstance(value.get("as_of"), str) or not value["as_of"]:
            raise _usage("prospective observation requires as_of")
        for field in MEASUREMENT_FIELDS:
            self._validate_measurement(field, value.get(field))
        condition_hits = value.get("condition_hits", [])
        if not isinstance(condition_hits, list) or any(
            not isinstance(hit, Mapping) or not isinstance(hit.get("condition"), str) or not isinstance(hit.get("hit"), bool)
            for hit in condition_hits
        ):
            raise _usage("condition_hits must contain a condition and boolean hit")
        normalized = {
            "observation_id": observation_id,
            "as_of": value["as_of"],
            **{field: dict(value[field]) for field in MEASUREMENT_FIELDS},
            "condition_hits": [dict(hit) for hit in condition_hits],
        }
        normalized["measurement_hash"] = canonical_hash({"record_id": record_id, **normalized})
        return normalized

    @staticmethod
    def _validate_measurement(field: str, value: Any) -> None:
        if not isinstance(value, Mapping):
            raise _usage(f"{field} must be an availability object")
        availability = value.get("availability")
        if availability not in AVAILABILITY_STATES:
            raise _usage(f"{field} has invalid availability: {availability}")
        if "value" not in value:
            raise _usage(f"{field} requires an explicit value; use null when unavailable")
        if availability == "available" and value["value"] is None:
            raise _usage(f"{field} is available but has no value")
        if availability != "available" and value["value"] is not None:
            raise _usage(f"{field} is {availability} and must use a null value")
        if not isinstance(value.get("provenance"), Mapping):
            raise _usage(f"{field} requires provenance even when unavailable")

    def _load_observations(self, record_id: str, record: Mapping[str, Any]) -> list[dict[str, Any]]:
        path = self._observations_path(record_id)
        if not path.exists():
            return []
        observations: list[dict[str, Any]] = []
        try:
            with path.open(encoding="utf-8") as handle:
                for line in handle:
                    if line.strip():
                        event = json.loads(line)
                        if not isinstance(event, dict):
                            raise _persistence(f"prospective observation is not an object: {record_id}")
                        observations.append(event)
        except (OSError, json.JSONDecodeError) as exc:
            raise _persistence(f"cannot read prospective observations: {record_id}") from exc
        self._compose(record, observations)
        return observations

    @staticmethod
    def _verify_hash_chain(record: Mapping[str, Any]) -> None:
        previous_event_hash = record["content_hash"]
        for event in record["observations"]:
            unsigned_event = {key: value for key, value in event.items() if key != "event_hash"}
            measurement = {
                "observation_id": event.get("observation_id"),
                "as_of": event.get("as_of"),
                **{field: event.get(field) for field in MEASUREMENT_FIELDS},
                "condition_hits": event.get("condition_hits", []),
            }
            expected_measurement_hash = canonical_hash({"record_id": record["record_id"], **measurement})
            if (
                event.get("previous_event_hash") != previous_event_hash
                or event.get("measurement_hash") != expected_measurement_hash
                or event.get("event_hash") != canonical_hash(unsigned_event)
            ):
                raise _persistence(f"prospective observation hash chain is invalid: {record['record_id']}")
            previous_event_hash = event["event_hash"]

    @staticmethod
    def _validate_record_schema(record: Mapping[str, Any], *, error_factory: Any) -> None:
        try:
            validate_document(dict(record), PROSPECTIVE_RECORD_SCHEMA_ID)
        except SchemaViolation as exc:
            raise error_factory(f"prospective record fails schema validation: {exc}") from exc

    def _record_path(self, record_id: str) -> Path:
        if not record_id.startswith("prospective-") or "/" in record_id or "\\" in record_id or ".." in record_id:
            raise _usage(f"invalid prospective record id: {record_id}")
        return self.records_dir / record_id / "record.json"

    def _observations_path(self, record_id: str) -> Path:
        return self._record_path(record_id).with_name("observations.jsonl")

    @staticmethod
    def _read_json(path: Path, *, label: str, missing_error_factory: Any = _persistence) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise missing_error_factory(f"{label} is missing: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise _persistence(f"cannot read {label}: {path}") from exc
        if not isinstance(payload, dict):
            raise _persistence(f"{label} is not an object: {path}")
        return payload

    @staticmethod
    def _append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            written = 0
            while written < len(encoded):
                written += os.write(descriptor, encoded[written:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @staticmethod
    def _atomic_create(path: Path, value: Mapping[str, Any]) -> None:
        encoded = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            raise
        except OSError as exc:
            raise _persistence(f"cannot create prospective record: {path}") from exc
        try:
            written = 0
            while written < len(encoded):
                written += os.write(descriptor, encoded[written:])
            os.fsync(descriptor)
        except OSError as exc:
            path.unlink(missing_ok=True)
            raise _persistence(f"cannot write prospective record: {path}") from exc
        finally:
            os.close(descriptor)
