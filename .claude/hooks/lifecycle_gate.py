#!/usr/bin/env python3
"""Stop gate that reads only a content-hashed active-run pointer and its manifest."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _payload() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _root(payload: dict[str, Any]) -> Path:
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd:
        candidate = Path(cwd).resolve()
        for path in (candidate, *candidate.parents):
            if (path / ".claude" / "settings.json").is_file():
                return path
        return candidate
    return Path(__file__).resolve().parents[2]


def _block(reason: str) -> None:
    json.dump({"decision": "block", "reason": reason}, sys.stdout, ensure_ascii=False)
    print()


def _verified_open_run(root: Path) -> tuple[str | None, str | None]:
    pointer_path = root / ".serenity" / "active-run.json"
    if not pointer_path.exists():
        return None, None
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        if not isinstance(pointer, dict):
            raise ValueError("pointer is not an object")
        unsigned = {key: value for key, value in pointer.items() if key != "content_hash"}
        if pointer.get("content_hash") != _hash(unsigned):
            raise ValueError("pointer content hash mismatch")
        run_id = pointer.get("run_id")
        status = pointer.get("status")
        if not isinstance(run_id, str) or not re.fullmatch(r"run-[A-Za-z0-9_-]+", run_id):
            raise ValueError("pointer run identity is invalid")
        if not isinstance(status, str):
            raise ValueError("pointer lifecycle status is invalid")
        manifest_path = root / ".serenity" / "runs" / run_id / "run-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("run manifest is not an object")
        manifest_unsigned = {key: value for key, value in manifest.items() if key != "content_hash"}
        if manifest.get("content_hash") != _hash(manifest_unsigned):
            raise ValueError("run manifest content hash mismatch")
        if manifest.get("run_id") != run_id or manifest.get("status") != status:
            raise ValueError("pointer and run lifecycle disagree")
        return run_id, status
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, str(exc)


def main() -> int:
    payload = _payload()
    if payload.get("stop_hook_active") is True:
        return 0
    run_id, result = _verified_open_run(_root(payload))
    if result is None:
        return 0
    if run_id is None:
        _block(f"The claimed active research run cannot be verified: {result}.")
        return 0
    if result != "OPEN":
        return 0
    _block(f"An OPEN research run ({run_id}) remains active; its lifecycle is not resolved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
