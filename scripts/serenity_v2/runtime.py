from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

import fcntl

from serenity_v2.schema import SchemaViolation, validate_document


RUN_SCHEMA_ID = "urn:serenity:schema:run-manifest:2"
RUN_MODES = ("macro-event", "discovery", "single-name", "cohort")
LIFECYCLE_LOCK_TIMEOUT_SECONDS = 5.0
LIFECYCLE_LOCK_POLL_SECONDS = 0.02


class SerenityError(Exception):
    def __init__(self, code: str, message: str, exit_code: int, **details: Any) -> None:
        super().__init__(message)
        self.payload = {
            "ok": False,
            "error": {"code": code, "message": message, "exit_code": exit_code, **details},
        }
        self.exit_code = exit_code


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_as_of(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise SerenityError("usage_or_schema", f"invalid --as-of date: {value}", 2) from exc


def parse_instant(value: str) -> str:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SerenityError("usage_or_schema", f"invalid ISO datetime: {value}", 2) from exc
    if parsed.tzinfo is None:
        raise SerenityError("usage_or_schema", f"datetime requires an explicit timezone: {value}", 2)
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def atomic_write_text(path: Path, text: str, *, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        encoded = text.encode("utf-8")
        written = 0
        while written < len(encoded):
            written += os.write(descriptor, encoded[written:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        os.replace(temporary, path)
    except OSError as exc:
        raise SerenityError("persistence_conflict", f"cannot persist {label}", 5, path=str(path)) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def atomic_create_bytes(path: Path, content: bytes, *, label: str) -> bool:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    descriptor: int | None = None
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        written = 0
        while written < len(content):
            written += os.write(descriptor, content[written:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = None
        try:
            os.link(temporary, path)
        except FileExistsError:
            return False
        return True
    except OSError as exc:
        raise SerenityError("persistence_conflict", f"cannot publish {label}", 5, path=str(path)) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


class RunStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.runs_dir = root / ".serenity" / "runs"
        self.active_path = root / ".serenity" / "active-run.json"
        self.lock_path = root / ".serenity" / "runstore.lock"
        self.pending_finalization_path = root / ".serenity" / "pending-finalization.json"
        self._lock_depth = 0
        self._thread_lock = threading.RLock()

    @contextmanager
    def _lifecycle_lock(self) -> Iterator[None]:
        with self._thread_lock:
            if self._lock_depth:
                self._lock_depth += 1
                try:
                    yield
                finally:
                    self._lock_depth -= 1
                return
            descriptor = self._acquire_lifecycle_lock()
            self._lock_depth = 1
            try:
                yield
            finally:
                self._lock_depth = 0
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                finally:
                    os.close(descriptor)

    def _acquire_lifecycle_lock(self) -> int:
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            descriptor = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o644)
        except OSError as exc:
            raise SerenityError("persistence_conflict", "cannot open run lifecycle lock", 5, path=str(self.lock_path)) from exc
        deadline = time.monotonic() + LIFECYCLE_LOCK_TIMEOUT_SECONDS
        try:
            while True:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return descriptor
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise SerenityError("persistence_conflict", "timed out acquiring run lifecycle lock", 5, path=str(self.lock_path))
                    time.sleep(LIFECYCLE_LOCK_POLL_SECONDS)
                except OSError as exc:
                    raise SerenityError("persistence_conflict", "cannot acquire run lifecycle lock", 5, path=str(self.lock_path)) from exc
        except Exception:
            os.close(descriptor)
            raise

    def start(
        self,
        *,
        mode: str,
        question: str,
        subjects: list[str],
        as_of: str,
        actor: dict[str, Any] | None = None,
        source_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._lifecycle_lock():
            self._reconcile_lifecycle()
            return self._start(
                mode=mode,
                question=question,
                subjects=subjects,
                as_of=as_of,
                actor=actor,
                source_policy=source_policy,
            )

    def _start(
        self,
        *,
        mode: str,
        question: str,
        subjects: list[str],
        as_of: str,
        actor: dict[str, Any] | None = None,
        source_policy: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        active = self.read_active()
        if active is not None:
            raise SerenityError(
                "invalid_lifecycle",
                f"an active {active['status']} run must be resolved first: {active['run_id']}",
                3,
                run_id=active["run_id"],
                status=active["status"],
            )
        orphaned = self.list_open()
        if orphaned:
            raise SerenityError(
                "persistence_conflict",
                "active run pointer is missing while OPEN runs exist; repair .serenity/active-run.json before starting another run",
                5,
                run_ids=[manifest["run_id"] for manifest in orphaned],
            )
        now = utc_now()
        seed = {
            "mode": mode,
            "question": question,
            "subjects": subjects,
            "as_of": as_of,
            "started_at": now,
        }
        run_id = f"run-{canonical_hash(seed)[:16]}"
        manifest: dict[str, Any] = {
            "schema_id": RUN_SCHEMA_ID,
            "run_id": run_id,
            "status": "OPEN",
            "mode": mode,
            "question": question,
            "subjects": subjects,
            "as_of": as_of,
            "started_at": now,
            "updated_at": now,
            "actor": actor or {"kind": "model", "id": "harness-agent"},
            "source_policy": source_policy or {"policy_id": "live-free-v1", "allow_network": True},
            "current_phase": "started",
            "events": [{"at": now, "type": "run_started"}],
            "artifacts": {},
        }
        manifest["content_hash"] = canonical_hash(manifest)
        try:
            validate_document(manifest, RUN_SCHEMA_ID)
        except SchemaViolation as exc:
            raise SerenityError("usage_or_schema", str(exc), 2) from exc
        run_dir = self.runs_dir / run_id
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise SerenityError("persistence_conflict", f"run already exists: {run_id}", 5, run_id=run_id) from exc
        self._write(run_id, manifest)
        self._write_active(manifest)
        return manifest

    def read(self, run_id: str) -> dict[str, Any]:
        path = self._path(run_id)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise SerenityError("run_not_found", f"run not found: {run_id}", 3, run_id=run_id) from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise SerenityError("persistence_conflict", f"run cannot be read: {run_id}", 5, run_id=run_id) from exc
        if not isinstance(value, dict) or value.get("run_id") != run_id:
            raise SerenityError("persistence_conflict", f"run identity mismatch: {run_id}", 5, run_id=run_id)
        expected_hash = canonical_hash({key: item for key, item in value.items() if key != "content_hash"})
        if value.get("content_hash") != expected_hash:
            raise SerenityError("persistence_conflict", f"run content hash mismatch: {run_id}", 5, run_id=run_id)
        try:
            validate_document(value, RUN_SCHEMA_ID)
        except SchemaViolation as exc:
            raise SerenityError("persistence_conflict", f"invalid stored run: {exc}", 5, run_id=run_id) from exc
        return value

    def abandon(self, run_id: str, reason: str) -> dict[str, Any]:
        with self._lifecycle_lock():
            self._reconcile_lifecycle()
            return self._abandon(run_id, reason)

    def _abandon(self, run_id: str, reason: str) -> dict[str, Any]:
        manifest = self.read(run_id)
        if manifest.get("status") != "OPEN":
            raise SerenityError(
                "invalid_lifecycle",
                f"only an OPEN run can be abandoned: {run_id}",
                3,
                run_id=run_id,
                status=manifest.get("status"),
            )
        manifest["status"] = "ABANDONED"
        manifest["abandon_reason"] = reason
        manifest["current_phase"] = "abandoned"
        manifest["updated_at"] = utc_now()
        manifest["events"].append({"at": manifest["updated_at"], "type": "run_abandoned", "detail": reason})
        manifest["content_hash"] = canonical_hash({key: value for key, value in manifest.items() if key != "content_hash"})
        self._write(run_id, manifest)
        self._clear_active(run_id)
        return manifest

    def list_open(self) -> list[dict[str, Any]]:
        with self._lifecycle_lock():
            return self._list_open()

    def _list_open(self) -> list[dict[str, Any]]:
        return [manifest for manifest in self._list_active_manifests() if manifest.get("status") == "OPEN"]

    def _list_active_manifests(self) -> list[dict[str, Any]]:
        if not self.runs_dir.exists():
            return []
        manifests: list[dict[str, Any]] = []
        for path in sorted(self.runs_dir.glob("run-*/run-manifest.json")):
            manifest = self.read(path.parent.name)
            if manifest.get("status") in {"OPEN", "FINALIZED"}:
                manifests.append(manifest)
        return manifests

    def read_active(self) -> dict[str, Any] | None:
        with self._lifecycle_lock():
            return self._read_active()

    def reconcile(self) -> dict[str, Any]:
        with self._lifecycle_lock():
            return self._reconcile_lifecycle()

    def _reconcile_lifecycle(self, *, allow_pending_finalization: bool = False) -> dict[str, Any]:
        pending = self._read_pending_finalization()
        if pending is not None and not allow_pending_finalization:
            raise SerenityError(
                "persistence_conflict",
                "pending finalization requires retrying finalize_with_publication",
                5,
                run_id=pending["run_id"],
            )
        pointer = self._read_active_pointer()
        if pointer is not None:
            try:
                self.read(pointer["run_id"])
            except SerenityError as exc:
                if exc.payload["error"]["code"] == "run_not_found":
                    raise SerenityError(
                        "persistence_conflict",
                        "active run pointer references a missing manifest",
                        5,
                        run_id=pointer["run_id"],
                    ) from exc
                raise
        candidates = self._list_active_manifests()
        if len(candidates) > 1:
            raise SerenityError(
                "persistence_conflict",
                "multiple active run manifests require manual repair",
                5,
                run_ids=[manifest["run_id"] for manifest in candidates],
            )
        target = self._pointer_for(candidates[0]) if candidates else None
        if pointer == target:
            return {"reconciled": False, "active_run": target}
        if target is None:
            if pointer is not None:
                try:
                    self.active_path.unlink()
                except OSError as exc:
                    raise SerenityError("persistence_conflict", "active run pointer cannot be cleared", 5) from exc
        else:
            self._write_active(candidates[0])
        return {"reconciled": True, "active_run": target}

    def _read_active(self) -> dict[str, Any] | None:
        pointer = self._read_active_pointer()
        if pointer is None:
            orphaned = self.list_open()
            if orphaned:
                raise SerenityError(
                    "persistence_conflict",
                    "active run pointer is missing while OPEN runs exist; repair .serenity/active-run.json",
                    5,
                    run_ids=[manifest["run_id"] for manifest in orphaned],
                )
            return None
        run_id = pointer.get("run_id")
        status = pointer.get("status")
        manifest = self.read(run_id)
        if manifest.get("status") != status:
            raise SerenityError("persistence_conflict", "active run pointer does not match run lifecycle", 5, run_id=run_id)
        return pointer

    def _read_active_pointer(self) -> dict[str, Any] | None:
        if not self.active_path.exists():
            return None
        try:
            pointer = json.loads(self.active_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SerenityError("persistence_conflict", "active run pointer cannot be read", 5) from exc
        if not isinstance(pointer, dict):
            raise SerenityError("persistence_conflict", "active run pointer is not an object", 5)
        unsigned = {key: value for key, value in pointer.items() if key != "content_hash"}
        if pointer.get("content_hash") != canonical_hash(unsigned):
            raise SerenityError("persistence_conflict", "active run pointer content hash mismatch", 5)
        run_id = pointer.get("run_id")
        status = pointer.get("status")
        if not isinstance(run_id, str) or not isinstance(status, str) or status not in {"OPEN", "FINALIZED"}:
            raise SerenityError("persistence_conflict", "active run pointer has invalid identity or status", 5)
        return pointer

    def _resolve_project_path(self, path: Path, *, label: str) -> Path:
        resolved_root = self.root.resolve()
        resolved_path = path.resolve()
        if resolved_path == resolved_root or resolved_root not in resolved_path.parents:
            raise SerenityError("persistence_conflict", f"{label} is outside the project root: {path}", 5)
        return resolved_path

    def _read_pending_finalization(self) -> dict[str, Any] | None:
        if not self.pending_finalization_path.exists():
            return None
        try:
            pending = json.loads(self.pending_finalization_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SerenityError("persistence_conflict", "pending finalization cannot be read", 5) from exc
        if not isinstance(pending, dict):
            raise SerenityError("persistence_conflict", "pending finalization is not an object", 5)
        unsigned = {key: value for key, value in pending.items() if key != "content_hash"}
        if pending.get("content_hash") != canonical_hash(unsigned):
            raise SerenityError("persistence_conflict", "pending finalization content hash mismatch", 5)
        if not isinstance(pending.get("run_id"), str) or not isinstance(pending.get("decision_path"), str):
            raise SerenityError("persistence_conflict", "pending finalization has invalid identity", 5)
        return pending

    def _write_pending_finalization(self, run_id: str, decision_path: Path) -> None:
        pending = {"run_id": run_id, "decision_path": str(decision_path.relative_to(self.root.resolve()))}
        pending["content_hash"] = canonical_hash(pending)
        atomic_write_text(
            self.pending_finalization_path,
            json.dumps(pending, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            label="pending finalization",
        )

    def _clear_pending_finalization(self) -> None:
        if not self.pending_finalization_path.exists():
            return
        try:
            self.pending_finalization_path.unlink()
        except OSError as exc:
            raise SerenityError("persistence_conflict", "pending finalization cannot be cleared", 5) from exc

    def attach_artifact(
        self,
        run_id: str,
        *,
        name: str,
        path: Path,
        schema_id: str | None = None,
        phase: str | None = None,
    ) -> dict[str, Any]:
        with self._lifecycle_lock():
            self._reconcile_lifecycle()
            return self._attach_artifact(run_id, name=name, path=path, schema_id=schema_id, phase=phase)

    def _attach_artifact(
        self,
        run_id: str,
        *,
        name: str,
        path: Path,
        schema_id: str | None = None,
        phase: str | None = None,
    ) -> dict[str, Any]:
        manifest = self.read(run_id)
        if manifest.get("status") != "OPEN":
            raise SerenityError("invalid_lifecycle", f"only an OPEN run accepts artifacts: {run_id}", 3, run_id=run_id)
        artifact = self._build_attachment(name=name, path=path, schema_id=schema_id)
        existing = manifest["artifacts"].get(name)
        if existing is not None and existing != artifact:
            raise SerenityError("persistence_conflict", f"artifact name already has different content: {name}", 5)
        if existing == artifact:
            return manifest
        manifest["artifacts"][name] = artifact
        now = utc_now()
        manifest["updated_at"] = now
        if phase:
            manifest["current_phase"] = phase
        manifest["events"].append({"at": now, "type": "artifact_attached", "detail": name})
        self._rehash_and_write(run_id, manifest)
        return manifest

    def publish_artifact(
        self,
        run_id: str,
        *,
        name: str,
        path: Path,
        content: bytes,
        schema_id: str | None = None,
        phase: str | None = None,
    ) -> dict[str, Any]:
        with self._lifecycle_lock():
            self._reconcile_lifecycle()
            return self._publish_artifact(
                run_id,
                name=name,
                path=path,
                content=content,
                schema_id=schema_id,
                phase=phase,
            )

    def _publish_artifact(
        self,
        run_id: str,
        *,
        name: str,
        path: Path,
        content: bytes,
        schema_id: str | None,
        phase: str | None,
    ) -> dict[str, Any]:
        if not isinstance(content, bytes):
            raise SerenityError("usage_or_schema", "published artifact content must be bytes", 2)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,127}", name):
            raise SerenityError("usage_or_schema", f"invalid artifact name: {name}", 2)
        resolved_root = self.root.resolve()
        resolved_path = path.resolve()
        if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
            raise SerenityError("persistence_conflict", f"artifact is outside the project root: {path}", 5)
        planned: dict[str, Any] = {
            "path": str(resolved_path.relative_to(resolved_root)),
            "content_hash": hashlib.sha256(content).hexdigest(),
        }
        if schema_id:
            planned["schema_id"] = schema_id
        manifest = self.read(run_id)
        if manifest.get("status") != "OPEN":
            raise SerenityError("invalid_lifecycle", f"only an OPEN run accepts artifacts: {run_id}", 3, run_id=run_id)
        existing = manifest["artifacts"].get(name)
        if existing is not None:
            if existing != planned:
                raise SerenityError("persistence_conflict", f"artifact name already has different content: {name}", 5)
            if self._build_attachment(name=name, path=path, schema_id=schema_id) != planned:
                raise SerenityError("persistence_conflict", f"published artifact content hash mismatch: {name}", 5)
            return manifest
        atomic_create_bytes(path, content, label=f"artifact {name}")
        if self._build_attachment(name=name, path=path, schema_id=schema_id) != planned:
            raise SerenityError("persistence_conflict", f"published artifact content conflict: {name}", 5)
        manifest["artifacts"][name] = planned
        now = utc_now()
        manifest["updated_at"] = now
        if phase:
            manifest["current_phase"] = phase
        manifest["events"].append({"at": now, "type": "artifact_published", "detail": name})
        self._rehash_and_write(run_id, manifest)
        return manifest

    def publish_or_refresh_artifact(
        self,
        run_id: str,
        *,
        name: str,
        expected_attachment: Mapping[str, Any] | None,
        path: Path,
        content: bytes,
        schema_id: str | None = None,
        phase: str | None = None,
    ) -> dict[str, Any]:
        with self._lifecycle_lock():
            self._reconcile_lifecycle()
            return self._publish_or_refresh_artifact(
                run_id,
                name=name,
                expected_attachment=expected_attachment,
                path=path,
                content=content,
                schema_id=schema_id,
                phase=phase,
            )

    def _publish_or_refresh_artifact(
        self,
        run_id: str,
        *,
        name: str,
        expected_attachment: Mapping[str, Any] | None,
        path: Path,
        content: bytes,
        schema_id: str | None,
        phase: str | None,
    ) -> dict[str, Any]:
        if expected_attachment is not None and not isinstance(expected_attachment, Mapping):
            raise SerenityError("usage_or_schema", "expected attachment must be an object or null", 2)
        if not isinstance(content, bytes):
            raise SerenityError("usage_or_schema", "published artifact content must be bytes", 2)
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,127}", name):
            raise SerenityError("usage_or_schema", f"invalid artifact name: {name}", 2)
        resolved_path = self._resolve_project_path(path, label="artifact")
        planned: dict[str, Any] = {
            "path": str(resolved_path.relative_to(self.root.resolve())),
            "content_hash": hashlib.sha256(content).hexdigest(),
        }
        if schema_id:
            planned["schema_id"] = schema_id
        manifest = self.read(run_id)
        if manifest.get("status") != "OPEN":
            raise SerenityError("invalid_lifecycle", f"only an OPEN run accepts artifacts: {run_id}", 3, run_id=run_id)
        existing = manifest["artifacts"].get(name)
        expected = dict(expected_attachment) if expected_attachment is not None else None
        if existing != expected:
            raise SerenityError("persistence_conflict", f"artifact attachment has changed: {name}", 5)
        if existing is not None and existing.get("schema_id") != schema_id:
            raise SerenityError("persistence_conflict", f"artifact schema cannot change during refresh: {name}", 5)
        if existing == planned:
            if self._build_attachment(name=name, path=path, schema_id=schema_id) != planned:
                raise SerenityError("persistence_conflict", f"published artifact content hash mismatch: {name}", 5)
            return manifest
        if existing is not None and existing.get("path") == planned["path"]:
            raise SerenityError("persistence_conflict", f"artifact refresh requires a new immutable path: {name}", 5)
        atomic_create_bytes(path, content, label=f"artifact {name}")
        if self._build_attachment(name=name, path=path, schema_id=schema_id) != planned:
            raise SerenityError("persistence_conflict", f"published artifact content conflict: {name}", 5)
        manifest["artifacts"][name] = planned
        now = utc_now()
        manifest["updated_at"] = now
        if phase:
            manifest["current_phase"] = phase
        if existing is None:
            manifest["events"].append({"at": now, "type": "artifact_published", "detail": name})
        else:
            audit = {"name": name, "previous": existing, "replacement": planned}
            manifest["events"].append(
                {"at": now, "type": "artifact_superseded", "detail": json.dumps(audit, ensure_ascii=False, sort_keys=True, separators=(",", ":"))}
            )
        self._rehash_and_write(run_id, manifest)
        return manifest

    def refresh_artifact(
        self,
        run_id: str,
        *,
        name: str,
        expected_attachment: Mapping[str, Any],
        path: Path,
        schema_id: str,
        phase: str | None = None,
    ) -> dict[str, Any]:
        with self._lifecycle_lock():
            self._reconcile_lifecycle()
            return self._refresh_artifact(
                run_id,
                name=name,
                expected_attachment=expected_attachment,
                path=path,
                schema_id=schema_id,
                phase=phase,
            )

    def _refresh_artifact(
        self,
        run_id: str,
        *,
        name: str,
        expected_attachment: Mapping[str, Any],
        path: Path,
        schema_id: str,
        phase: str | None,
    ) -> dict[str, Any]:
        manifest = self.read(run_id)
        if manifest.get("status") != "OPEN":
            raise SerenityError("invalid_lifecycle", f"only an OPEN run accepts artifact refreshes: {run_id}", 3, run_id=run_id)
        if not isinstance(expected_attachment, Mapping):
            raise SerenityError("usage_or_schema", "expected attachment must be an object", 2)
        if not isinstance(schema_id, str) or not schema_id:
            raise SerenityError("usage_or_schema", "artifact refresh requires a schema_id", 2)
        previous = manifest["artifacts"].get(name)
        if not isinstance(previous, dict):
            raise SerenityError("persistence_conflict", f"artifact is not attached: {name}", 5)
        expected = dict(expected_attachment)
        if expected != previous:
            raise SerenityError("persistence_conflict", f"artifact attachment has changed: {name}", 5)
        if previous.get("schema_id") != schema_id:
            raise SerenityError("persistence_conflict", f"artifact schema cannot change during refresh: {name}", 5)
        replacement = self._build_attachment(name=name, path=path, schema_id=schema_id)
        manifest["artifacts"][name] = replacement
        now = utc_now()
        manifest["updated_at"] = now
        if phase:
            manifest["current_phase"] = phase
        audit = {"name": name, "previous": previous, "replacement": replacement}
        manifest["events"].append(
            {"at": now, "type": "artifact_superseded", "detail": json.dumps(audit, ensure_ascii=False, sort_keys=True, separators=(",", ":"))}
        )
        self._rehash_and_write(run_id, manifest)
        return manifest

    def _build_attachment(self, *, name: str, path: Path, schema_id: str | None) -> dict[str, Any]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,127}", name):
            raise SerenityError("usage_or_schema", f"invalid artifact name: {name}", 2)
        resolved_root = self.root.resolve()
        resolved_path = path.resolve()
        if resolved_path != resolved_root and resolved_root not in resolved_path.parents:
            raise SerenityError("persistence_conflict", f"artifact is outside the project root: {path}", 5)
        if path.is_symlink() or not resolved_path.is_file():
            raise SerenityError("persistence_conflict", f"artifact is not a regular file: {path}", 5)
        raw_hash = hashlib.sha256(resolved_path.read_bytes()).hexdigest()
        relative_path = str(resolved_path.relative_to(resolved_root))
        artifact: dict[str, Any] = {"path": relative_path, "content_hash": raw_hash}
        if schema_id:
            artifact["schema_id"] = schema_id
        return artifact

    def finalize(self, run_id: str, *, decision_path: Path) -> dict[str, Any]:
        with self._lifecycle_lock():
            self._reconcile_lifecycle()
            return self._finalize_locked(run_id, decision_path=decision_path)

    def finalize_with_publication(
        self,
        run_id: str,
        *,
        decision_path: Path,
        publish: Callable[[], Path],
    ) -> dict[str, Any]:
        with self._lifecycle_lock():
            self._reconcile_lifecycle(allow_pending_finalization=True)
            expected_path = self._resolve_project_path(decision_path, label="decision")
            pending = self._read_pending_finalization()
            if pending is not None:
                expected_relative_path = str(expected_path.relative_to(self.root.resolve()))
                if pending["run_id"] != run_id or pending["decision_path"] != expected_relative_path:
                    raise SerenityError("persistence_conflict", "pending finalization belongs to a different decision", 5, run_id=run_id)
            manifest = self.read(run_id)
            if manifest.get("status") == "FINALIZED":
                attachment = manifest.get("artifacts", {}).get("research-decision")
                if not isinstance(attachment, dict) or attachment.get("path") != str(expected_path.relative_to(self.root.resolve())):
                    raise SerenityError("invalid_lifecycle", f"run is already finalized with a different decision: {run_id}", 3, run_id=run_id)
                published_path = Path(publish()).resolve()
                if published_path != expected_path:
                    raise SerenityError("persistence_conflict", "decision publisher returned an unexpected path", 5, run_id=run_id)
                self._clear_pending_finalization()
                return manifest
            if manifest.get("status") != "OPEN":
                raise SerenityError(
                    "invalid_lifecycle",
                    f"only an OPEN run can publish a finalized decision: {run_id}",
                    3,
                    run_id=run_id,
                    status=manifest.get("status"),
                )
            if pending is None:
                self._write_pending_finalization(run_id, expected_path)
            try:
                published_path = Path(publish()).resolve()
                if published_path != expected_path:
                    raise SerenityError("persistence_conflict", "decision publisher returned an unexpected path", 5, run_id=run_id)
                finalized = self._finalize_locked(run_id, decision_path=expected_path)
            except Exception:
                raise
            self._clear_pending_finalization()
            return finalized

    def _finalize_locked(self, run_id: str, *, decision_path: Path) -> dict[str, Any]:
        manifest = self._attach_artifact(
            run_id,
            name="research-decision",
            path=decision_path,
            schema_id="urn:serenity:schema:research-decision:1",
            phase="decision_finalized",
        )
        manifest["status"] = "FINALIZED"
        now = utc_now()
        manifest["updated_at"] = now
        manifest["events"].append({"at": now, "type": "decision_finalized"})
        self._rehash_and_write(run_id, manifest)
        self._write_active(manifest)
        return manifest

    def close(self, run_id: str, reason: str) -> dict[str, Any]:
        with self._lifecycle_lock():
            self._reconcile_lifecycle()
            return self._close(run_id, reason)

    def _close(self, run_id: str, reason: str) -> dict[str, Any]:
        manifest = self.read(run_id)
        if manifest.get("status") != "FINALIZED":
            raise SerenityError(
                "invalid_lifecycle",
                f"only a FINALIZED run can be closed: {run_id}",
                3,
                run_id=run_id,
                status=manifest.get("status"),
            )
        manifest["status"] = "CLOSED"
        manifest["close_reason"] = reason
        manifest["current_phase"] = "closed"
        now = utc_now()
        manifest["updated_at"] = now
        manifest["events"].append({"at": now, "type": "run_closed", "detail": reason})
        self._rehash_and_write(run_id, manifest)
        self._clear_active(run_id)
        return manifest

    def _rehash_and_write(self, run_id: str, manifest: dict[str, Any]) -> None:
        manifest["content_hash"] = canonical_hash({key: value for key, value in manifest.items() if key != "content_hash"})
        self._write(run_id, manifest)

    def _write_active(self, manifest: dict[str, Any]) -> None:
        pointer = self._pointer_for(manifest)
        atomic_write_text(
            self.active_path,
            json.dumps(pointer, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            label="active run pointer",
        )

    def _pointer_for(self, manifest: Mapping[str, Any]) -> dict[str, Any]:
        status = manifest.get("status")
        if status not in {"OPEN", "FINALIZED"}:
            raise SerenityError("persistence_conflict", "only an OPEN or FINALIZED run can be active", 5)
        pointer = {"run_id": manifest["run_id"], "status": status, "updated_at": manifest["updated_at"]}
        pointer["content_hash"] = canonical_hash(pointer)
        return pointer

    def _clear_active(self, run_id: str) -> None:
        if not self.active_path.exists():
            return
        try:
            active = json.loads(self.active_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SerenityError("persistence_conflict", "active run pointer cannot be read", 5) from exc
        if not isinstance(active, dict):
            raise SerenityError("persistence_conflict", "active run pointer is not an object", 5)
        unsigned = {key: value for key, value in active.items() if key != "content_hash"}
        if active.get("content_hash") != canonical_hash(unsigned):
            raise SerenityError("persistence_conflict", "active run pointer content hash mismatch", 5)
        if active.get("run_id") != run_id:
            return
        try:
            self.active_path.unlink()
        except OSError as exc:
            raise SerenityError("persistence_conflict", "active run pointer cannot be cleared", 5, run_id=run_id) from exc

    def _path(self, run_id: str) -> Path:
        if not run_id.startswith("run-") or "/" in run_id or "\\" in run_id or ".." in run_id:
            raise SerenityError("usage_or_schema", f"invalid run id: {run_id}", 2, run_id=run_id)
        return self.runs_dir / run_id / "run-manifest.json"

    def _write(self, run_id: str, manifest: dict[str, Any]) -> None:
        try:
            validate_document(manifest, RUN_SCHEMA_ID)
        except SchemaViolation as exc:
            raise SerenityError("persistence_conflict", f"invalid run manifest: {exc}", 5, run_id=run_id) from exc
        path = self._path(run_id)
        encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        atomic_write_text(path, encoded, label=f"run {run_id}")
