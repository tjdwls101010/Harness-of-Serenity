from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any

from serenity_core.runtime import SerenityError, canonical_hash


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}")
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except OSError as exc:
        raise SerenityError("persistence_conflict", f"cannot persist {path}", 5, path=str(path)) from exc
    finally:
        if temporary.exists():
            temporary.unlink(missing_ok=True)


def atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write_text(path, canonical_json(value))


def immutable_directory(path: Path, files: dict[str, str]) -> None:
    """Publish a complete record directory once, without replacing an old version."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    try:
        temporary.mkdir()
        for filename, content in files.items():
            (temporary / filename).write_text(content, encoding="utf-8")
        try:
            os.rename(temporary, path)
        except FileExistsError as exc:
            raise SerenityError("persistence_conflict", f"decision version already exists: {path}", 5, path=str(path)) from exc
        except OSError as exc:
            if path.exists():
                raise SerenityError("persistence_conflict", f"decision version already exists: {path}", 5, path=str(path)) from exc
            raise SerenityError("persistence_conflict", f"cannot publish decision version: {path}", 5, path=str(path)) from exc
    finally:
        if temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)


def json_document_hash(value: dict[str, Any]) -> str:
    return canonical_hash(value)
