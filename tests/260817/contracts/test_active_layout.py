from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_python_runtime_uses_the_version_neutral_serenity_core_namespace() -> None:
    assert importlib.util.find_spec("serenity_core") is not None
    assert importlib.util.find_spec("serenity_" + "v2") is None


def test_versioned_schema_files_live_in_the_neutral_schema_root() -> None:
    expected = {
        "candidate-result-1.schema.json",
        "evidence-catalog-1.schema.json",
        "evidence-request-1.schema.json",
        "evidence-result-1.schema.json",
        "fact-snapshot-2.schema.json",
        "hypothesis-ledger-1.schema.json",
        "lens-result-1.schema.json",
        "lens-spec-1.schema.json",
        "prospective-record-1.schema.json",
        "provider-envelope-1.schema.json",
        "qa-case-1.schema.json",
        "qa-result-1.schema.json",
        "research-decision-1.schema.json",
        "run-manifest-2.schema.json",
        "sector-graph-1.schema.json",
    }

    assert {path.name for path in (ROOT / "schemas").glob("*.schema.json")} == expected
    assert not (ROOT / "schemas" / ("v" + "2")).exists()
