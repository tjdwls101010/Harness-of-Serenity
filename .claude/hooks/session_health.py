#!/usr/bin/env python3
"""Local, network-free SessionStart health for the typed v2 harness."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _load_stdin() -> dict[str, Any]:
    try:
        value = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
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


def _check_active(root: Path, problems: list[str]) -> None:
    pointer_path = root / ".serenity" / "active-run.json"
    if not pointer_path.exists():
        return
    try:
        pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
        if not isinstance(pointer, dict):
            raise ValueError("pointer is not an object")
        unsigned = {key: value for key, value in pointer.items() if key != "content_hash"}
        if pointer.get("content_hash") != _hash(unsigned):
            raise ValueError("pointer content hash mismatch")
        run_id = pointer.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("pointer run identity is invalid")
        manifest_path = root / ".serenity" / "runs" / run_id / "run-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            raise ValueError("run manifest is not an object")
        manifest_unsigned = {key: value for key, value in manifest.items() if key != "content_hash"}
        if manifest.get("content_hash") != _hash(manifest_unsigned):
            raise ValueError("run manifest content hash mismatch")
        if manifest.get("run_id") != run_id or manifest.get("status") != pointer.get("status"):
            raise ValueError("pointer and run lifecycle disagree")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        problems.append(f"active-run state is not verifiable ({exc})")


def main() -> int:
    root = _root(_load_stdin())
    problems: list[str] = []
    if not (root / "AGENTS.md").is_symlink() or (root / "AGENTS.md").readlink() != Path("CLAUDE.md"):
        problems.append("AGENTS.md is not the CLAUDE.md symlink")
    if not (root / ".codex").is_symlink() or (root / ".codex").readlink() != Path(".claude"):
        problems.append(".codex is not the .claude symlink")
    settings_path = root / ".claude" / "settings.json"
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
        hooks = settings.get("hooks") if isinstance(settings, dict) else None
        if not isinstance(hooks, dict) or set(hooks) != {"SessionStart", "Stop"}:
            raise ValueError("settings does not expose exactly SessionStart and Stop")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        problems.append(f"hook settings are unavailable ({exc})")
    for path in (root / "scripts" / "serenity.py", root / "scripts" / "serenity_harness.py", root / "schemas" / "run-manifest-2.schema.json"):
        if not path.is_file():
            problems.append(f"required local file is missing ({path.relative_to(root)})")
    _check_active(root, problems)
    if not problems:
        return 0
    json.dump({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "Harness v2 local health is degraded: " + "; ".join(problems)}}, sys.stdout, ensure_ascii=False)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
