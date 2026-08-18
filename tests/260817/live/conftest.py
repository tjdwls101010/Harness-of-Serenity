"""Live probes need the real credentials the adapters read at runtime.

These are skipped by ``-m "not live"`` in pytest.ini, so reaching this file at
all means the run asked for network probes. A missing credential is therefore a
setup error to report, not a reason to pass quietly -- a silently skipped probe
is exactly the "green suite over a dead capability" failure this suite exists to
catch.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session", autouse=True)
def live_environment() -> None:
    from dotenv import load_dotenv

    load_dotenv(REPO_ROOT / ".env")
    if not os.environ.get("EDGAR_IDENTITY"):
        pytest.fail("live probes need EDGAR_IDENTITY in .env; see .env.example for the accepted form")
