from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
CLI = REPO_ROOT / "scripts" / "serenity.py"
sys.path.insert(0, str(REPO_ROOT / "scripts"))


@pytest.fixture
def run_cli(tmp_path: Path):
    def _run(*args: str, expected_exit: int = 0) -> dict:
        completed = subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=tmp_path,
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == expected_exit, completed.stderr or completed.stdout
        assert completed.stderr == ""
        lines = completed.stdout.splitlines()
        assert len(lines) == 1, completed.stdout
        return json.loads(lines[0])

    return _run
