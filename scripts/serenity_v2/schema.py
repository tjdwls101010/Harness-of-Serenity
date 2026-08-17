from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker


SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas" / "v2"
SCHEMA_FILES = {
    "urn:serenity:schema:run-manifest:2": "run-manifest-2.schema.json",
    "urn:serenity:schema:fact-snapshot:2": "fact-snapshot-2.schema.json",
    "urn:serenity:schema:provider-envelope:1": "provider-envelope-1.schema.json",
    "urn:serenity:schema:evidence-catalog:1": "evidence-catalog-1.schema.json",
    "urn:serenity:schema:evidence-request:1": "evidence-request-1.schema.json",
    "urn:serenity:schema:evidence-result:1": "evidence-result-1.schema.json",
    "urn:serenity:schema:hypothesis-ledger:1": "hypothesis-ledger-1.schema.json",
    "urn:serenity:schema:lens-spec:1": "lens-spec-1.schema.json",
    "urn:serenity:schema:lens-result:1": "lens-result-1.schema.json",
    "urn:serenity:schema:sector-graph:1": "sector-graph-1.schema.json",
    "urn:serenity:schema:research-decision:1": "research-decision-1.schema.json",
    "urn:serenity:schema:prospective-record:1": "prospective-record-1.schema.json",
    "urn:serenity:schema:qa-case:1": "qa-case-1.schema.json",
    "urn:serenity:schema:qa-result:1": "qa-result-1.schema.json",
    "urn:serenity:schema:candidate-result:1": "candidate-result-1.schema.json",
}


class SchemaViolation(ValueError):
    pass


@lru_cache(maxsize=None)
def _validator(schema_id: str) -> Draft202012Validator:
    filename = SCHEMA_FILES.get(schema_id)
    if filename is None:
        raise SchemaViolation(f"unknown schema_id: {schema_id!r}")
    schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_document(document: dict[str, Any], expected_schema_id: str | None = None) -> None:
    schema_id = document.get("schema_id")
    if expected_schema_id is not None and schema_id != expected_schema_id:
        raise SchemaViolation(f"expected {expected_schema_id}, got {schema_id!r}")
    if not isinstance(schema_id, str):
        raise SchemaViolation("schema_id is required")
    errors = sorted(_validator(schema_id).iter_errors(document), key=lambda error: list(error.absolute_path))
    if errors:
        first = errors[0]
        location = ".".join(str(part) for part in first.absolute_path) or "$"
        raise SchemaViolation(f"{schema_id} at {location}: {first.message}")
