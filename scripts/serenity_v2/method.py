"""Cleanroom open-coding artifacts for reconstructing method, never a thesis engine.

The service has only mechanical responsibilities: remove declared answer-key metadata,
validate coders' explicit tags, retain source links, and persist reproducible artifacts.
It intentionally makes no inference about investment quality or doctrine.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from serenity_v2.storage import atomic_write_json


CODEBOOK_AXES = (
    "observation_type",
    "causal_hop",
    "value_capture",
    "identity_provenance",
    "lens",
    "catalyst_mechanism",
    "funding_capital_structure",
    "bear_falsifier",
    "timing_entry",
    "recommendation_scope",
    "confidence_hedge",
    "contradiction",
    "outcome_postmortem",
)
PROVENANCE_TAGS = frozenset({"sourced", "augmented", "unverified"})
_DATE_PATTERN = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{2,127}$")
_LEAK_POLICY = {
    "excluded_fields": ["answer_key", "created_at", "date", "ticker"],
    "redactions": {"date": "[DATE]", "ticker": "[TICKER]"},
}
_SOURCE_INDEX_POLICY = {
    "forbidden_in_cleanroom_packet": True,
    "forbidden_metadata": ["database", "media_id", "representative_ticker", "source_row_id", "source_type"],
}
_METHOD_CODING_OUTPUT_SCHEMA = Path(__file__).resolve().parents[2] / "config" / "method-coding-output.schema.json"
_METHOD_CLAIM_SYNTHESIS_SCHEMA = Path(__file__).resolve().parents[2] / "config" / "method-claim-synthesis.schema.json"
_CANDIDATE_DIGEST_POLICY = {
    "format": "serenity-method-candidate-digest-policy/1",
    "selection": {
        "label_identity": "exact axis plus label only; no semantic label merge",
        "priority": "descending exact-label frequency",
        "equal_frequency_selection": "stable first-manifest-occurrence span quantiles; exact label is only the final deterministic tie-break",
        "representatives": "first manifest packet/chunk occurrences only",
    },
    "max_axis_labels_per_axis": 8,
    "max_representatives_per_label": 2,
    "max_reference_entries_per_section": 20,
    "max_semantic_field_characters": 320,
}


class MethodArtifactError(ValueError):
    """A method artifact has an incomplete, leaking, or contradictory contract."""


class MethodIncompleteError(MethodArtifactError):
    """Full-audit media coverage is incomplete, with a typed public summary."""

    def __init__(self, media_derivatives: Mapping[str, Any]) -> None:
        super().__init__("media derivatives are incomplete for full method reconstruction")
        self.media_derivatives = dict(media_derivatives)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _document_hash(document: Mapping[str, Any]) -> str:
    return _hash({key: value for key, value in document.items() if key != "content_hash"})


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise MethodArtifactError(f"{label} must be an object")
    return value


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MethodArtifactError(f"{label} must be a non-empty string")
    return value.strip()


def _identifier(value: Any, label: str) -> str:
    value = _nonempty_string(value, label)
    if _ID_PATTERN.fullmatch(value) is None:
        raise MethodArtifactError(f"{label} is not a stable identifier: {value!r}")
    return value


def _identifiers(value: Any, label: str, *, required: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise MethodArtifactError(f"{label} must be a list")
    normalized = [_identifier(item, f"{label} item") for item in value]
    if required and not normalized:
        raise MethodArtifactError(f"{label} must not be empty")
    if len(set(normalized)) != len(normalized):
        raise MethodArtifactError(f"{label} cannot contain duplicates")
    return normalized


def _validate_hash(document: Mapping[str, Any], label: str) -> None:
    content_hash = document.get("content_hash")
    if content_hash is not None and content_hash != _document_hash(document):
        raise MethodArtifactError(f"{label} content_hash does not match its canonical content")


def _redact_text(text: str, ticker: str | None) -> str:
    result = _DATE_PATTERN.sub("[DATE]", text)
    if ticker:
        result = re.sub(re.escape(ticker), "[TICKER]", result, flags=re.IGNORECASE)
    return result


def _chunk_source(record: Mapping[str, Any], *, kind: str, index: int) -> tuple[dict[str, Any], dict[str, Any]]:
    row_id = _identifier(record.get("source_row_id"), f"{kind} source_row_id")
    text = _nonempty_string(record.get("text"), f"{kind} text")
    ticker = record.get("ticker")
    if ticker is not None and not isinstance(ticker, str):
        raise MethodArtifactError(f"{kind} ticker must be a string when provided")
    raw_source_ref = row_id
    if kind == "media":
        raw_source_ref = f"{row_id}:{_identifier(record.get('media_id'), 'media media_id')}"
    raw_hash = _hash(dict(record))
    source_ref = f"source-{_hash({'kind': kind, 'source_ref': raw_source_ref})[:20]}"
    chunk = {
        "chunk_id": f"chunk-{_hash({'kind': kind, 'source_ref': source_ref, 'source_hash': raw_hash, 'index': index})[:20]}",
        "source_refs": [source_ref],
        "source_hash": raw_hash,
        "kind": kind,
        "text": _redact_text(text, ticker),
    }
    index_entry: dict[str, Any] = {
        "source_ref": source_ref,
        "source_row_id": row_id,
        "media_id": record.get("media_id") if kind == "media" else None,
        "source_hash": raw_hash,
    }
    if ticker:
        index_entry["representative_ticker"] = ticker
    source_type = record.get("source_type")
    if source_type is not None:
        index_entry["source_type"] = _nonempty_string(source_type, "source_type")
    media_source_sha256 = record.get("media_source_sha256")
    if media_source_sha256 is not None:
        if not isinstance(media_source_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", media_source_sha256) is None:
            raise MethodArtifactError("media_source_sha256 must be a SHA-256 digest")
        index_entry["media_source_sha256"] = media_source_sha256
    return chunk, index_entry


def _chunk_media_group(record: Mapping[str, Any], *, index: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Emit one blind chunk for one source SHA while retaining every private relation."""

    source_sha256 = record.get("media_source_sha256")
    if not isinstance(source_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", source_sha256) is None:
        raise MethodArtifactError("media group requires a source SHA-256 digest")
    text = _nonempty_string(record.get("text"), "media group text")
    relations = record.get("source_relations")
    if not isinstance(relations, list) or not relations:
        raise MethodArtifactError("media group source_relations must be a non-empty list")
    source_hash = _hash({"kind": "media", "media_source_sha256": source_sha256, "text": text})
    source_refs: list[str] = []
    index_entries: list[dict[str, Any]] = []
    redacted_text = _redact_text(text, None)
    for relation in relations:
        relation = _require_mapping(relation, "media group source relation")
        row_id = _identifier(relation.get("source_row_id"), "media source_row_id")
        media_id = _identifier(relation.get("media_id"), "media media_id")
        source_ref = f"source-{_hash({'kind': 'media', 'source_ref': f'{row_id}:{media_id}'})[:20]}"
        source_refs.append(source_ref)
        ticker = relation.get("ticker")
        if ticker is not None:
            ticker = _nonempty_string(ticker, "media ticker")
            redacted_text = _redact_text(redacted_text, ticker)
        source_type = _nonempty_string(relation.get("source_type"), "source_type")
        provenance = _require_mapping(relation.get("relation_provenance"), "media relation provenance")
        media_index = provenance.get("media_index")
        if isinstance(media_index, bool) or not isinstance(media_index, int) or media_index < 0:
            raise MethodArtifactError("media relation provenance media_index must be a non-negative integer")
        manifest_record_hash = provenance.get("manifest_record_hash")
        if not isinstance(manifest_record_hash, str) or re.fullmatch(r"[0-9a-f]{64}", manifest_record_hash) is None:
            raise MethodArtifactError("media relation provenance requires manifest_record_hash")
        index_entry: dict[str, Any] = {
            "source_ref": source_ref,
            "source_row_id": row_id,
            "media_id": media_id,
            "source_hash": source_hash,
            "source_type": source_type,
            "media_source_sha256": source_sha256,
            "relation_provenance": {"media_index": media_index, "manifest_record_hash": manifest_record_hash},
        }
        if ticker:
            index_entry["representative_ticker"] = ticker
        index_entries.append(index_entry)
    if len(set(source_refs)) != len(source_refs):
        raise MethodArtifactError("media group cannot repeat a source relation")
    chunk = {
        "chunk_id": f"chunk-{_hash({'kind': 'media', 'source_sha256': source_sha256, 'source_hash': source_hash, 'index': index})[:20]}",
        "source_refs": source_refs,
        "source_hash": source_hash,
        "kind": "media",
        "text": redacted_text,
    }
    return chunk, index_entries


def build_blind_chunks(
    corpus_rows: Sequence[Mapping[str, Any]], derived_media_annotations: Sequence[Mapping[str, Any]] = ()
) -> dict[str, Any]:
    """Build deterministic coder packets while stripping declared ticker/date/answer-key leaks."""

    return build_method_packets(corpus_rows, derived_media_annotations)[0]


def build_source_index(
    corpus_rows: Sequence[Mapping[str, Any]],
    derived_media_annotations: Sequence[Mapping[str, Any]] = (),
    *,
    database: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return private source recovery metadata that is explicitly forbidden from cleanrooms."""

    return build_method_packets(corpus_rows, derived_media_annotations, database=database)[1]


def build_method_packets(
    corpus_rows: Sequence[Mapping[str, Any]],
    derived_media_annotations: Sequence[Mapping[str, Any]] = (),
    *,
    database: Mapping[str, Any] | None = None,
    source_index_metadata: Mapping[str, Any] | None = None,
    output_metadata: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build a cleanroom packet and separate private recovery index from identical inputs."""

    if not isinstance(corpus_rows, Sequence) or isinstance(corpus_rows, (str, bytes)):
        raise MethodArtifactError("corpus_rows must be a list of source rows")
    if not isinstance(derived_media_annotations, Sequence) or isinstance(derived_media_annotations, (str, bytes)):
        raise MethodArtifactError("derived_media_annotations must be a list")
    chunks: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for index, row in enumerate(corpus_rows):
        chunk, entry = _chunk_source(_require_mapping(row, "corpus row"), kind="text", index=index)
        chunks.append(chunk)
        entries.append(entry)
    for index, annotation in enumerate(derived_media_annotations):
        annotation = _require_mapping(annotation, "media annotation")
        if "source_relations" in annotation:
            chunk, annotation_entries = _chunk_media_group(annotation, index=index)
        else:
            chunk, entry = _chunk_source(annotation, kind="media", index=index)
            annotation_entries = [entry]
        chunks.append(chunk)
        entries.extend(annotation_entries)
    if len({chunk["chunk_id"] for chunk in chunks}) != len(chunks):
        raise MethodArtifactError("source rows create duplicate blind chunk identifiers")
    source_index: dict[str, Any] = {
        "format": "serenity-method-source-index/1",
        "cleanroom_policy": _SOURCE_INDEX_POLICY,
        "entries": entries,
    }
    if database is not None:
        source_index["database"] = json.loads(canonical_json(_require_mapping(database, "source index database")))
    text_source_index: dict[str, Any] | None = None
    if entries and any(entry["media_id"] is not None for entry in entries):
        text_source_index = {key: value for key, value in source_index.items() if key != "entries"}
        text_source_index["entries"] = [entry for entry in entries if entry["media_id"] is None]
        text_source_index["content_hash"] = _document_hash(text_source_index)
    if source_index_metadata is not None:
        source_index["media_manifest"] = json.loads(canonical_json(_require_mapping(source_index_metadata, "source index media metadata")))
    source_index["content_hash"] = _document_hash(source_index)
    document: dict[str, Any] = {
        "format": "serenity-method-blind-chunks/1",
        "leak_policy": _LEAK_POLICY,
        "source_index_hash": source_index["content_hash"],
        "chunks": chunks,
    }
    if text_source_index is not None:
        document["text_source_index_hash"] = text_source_index["content_hash"]
    if output_metadata is not None:
        document["media_derivatives"] = json.loads(canonical_json(_require_mapping(output_metadata, "media derivatives metadata")))
    document["content_hash"] = _document_hash(document)
    return document, source_index


def _validate_chunks(chunks: Mapping[str, Any]) -> set[str]:
    _validate_hash(chunks, "blind chunks")
    if chunks.get("format") != "serenity-method-blind-chunks/1":
        raise MethodArtifactError("blind chunks use an unsupported format")
    if chunks.get("leak_policy") != _LEAK_POLICY:
        raise MethodArtifactError("blind chunks must state the fixed ticker/date/answer-key leak policy")
    source_index_hash = chunks.get("source_index_hash")
    if not isinstance(source_index_hash, str) or re.fullmatch(r"[0-9a-f]{64}", source_index_hash) is None:
        raise MethodArtifactError("blind chunks must reference a source index hash")
    text_source_index_hash = chunks.get("text_source_index_hash")
    if text_source_index_hash is not None and (
        not isinstance(text_source_index_hash, str) or re.fullmatch(r"[0-9a-f]{64}", text_source_index_hash) is None
    ):
        raise MethodArtifactError("blind chunks text_source_index_hash must be a SHA-256 digest")
    entries = chunks.get("chunks")
    if not isinstance(entries, list):
        raise MethodArtifactError("blind chunks must include a chunks list")
    ids: set[str] = set()
    for entry in entries:
        entry = _require_mapping(entry, "blind chunk")
        chunk_id = _identifier(entry.get("chunk_id"), "chunk_id")
        if chunk_id in ids:
            raise MethodArtifactError("blind chunks cannot repeat chunk_id")
        ids.add(chunk_id)
        if entry.get("kind") not in {"text", "media"}:
            raise MethodArtifactError("blind chunk kind must be text or media")
        _identifiers(entry.get("source_refs"), "chunk source_refs")
        text = _nonempty_string(entry.get("text"), "chunk text")
        if _DATE_PATTERN.search(text):
            raise MethodArtifactError("blind chunk leaks an ISO date")
        source_hash = entry.get("source_hash")
        if not isinstance(source_hash, str) or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None:
            raise MethodArtifactError("blind chunk requires a source_hash")
    return ids


def _validate_source_index(source_index: Mapping[str, Any], chunks: Mapping[str, Any]) -> None:
    _validate_hash(source_index, "source index")
    if source_index.get("format") != "serenity-method-source-index/1":
        raise MethodArtifactError("source index uses an unsupported format")
    if source_index.get("cleanroom_policy") != _SOURCE_INDEX_POLICY:
        raise MethodArtifactError("source index must declare its cleanroom exclusion policy")
    if chunks.get("source_index_hash") != source_index.get("content_hash"):
        raise MethodArtifactError("blind chunks source_index_hash does not match the supplied private source index")
    entries = source_index.get("entries")
    if not isinstance(entries, list):
        raise MethodArtifactError("source index entries must be a list")
    chunk_hashes = {
        source_ref: chunk["source_hash"] for chunk in chunks["chunks"] for source_ref in chunk["source_refs"]
    }
    indexed: dict[str, str] = {}
    for entry in entries:
        entry = _require_mapping(entry, "source index entry")
        source_ref = _identifier(entry.get("source_ref"), "source index source_ref")
        if source_ref in indexed:
            raise MethodArtifactError("source index cannot repeat source_ref")
        _identifier(entry.get("source_row_id"), "source index source_row_id")
        media_id = entry.get("media_id")
        if media_id is not None:
            _identifier(media_id, "source index media_id")
        source_hash = entry.get("source_hash")
        if not isinstance(source_hash, str) or re.fullmatch(r"[0-9a-f]{64}", source_hash) is None:
            raise MethodArtifactError("source index entry requires a source_hash")
        if "representative_ticker" in entry:
            _nonempty_string(entry["representative_ticker"], "source index representative_ticker")
        if "source_type" in entry:
            _nonempty_string(entry["source_type"], "source index source_type")
        if "media_source_sha256" in entry and (
            not isinstance(entry["media_source_sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", entry["media_source_sha256"]) is None
        ):
            raise MethodArtifactError("source index media_source_sha256 must be a SHA-256 digest")
        if "relation_provenance" in entry:
            provenance = _require_mapping(entry["relation_provenance"], "source index relation_provenance")
            media_index = provenance.get("media_index")
            if isinstance(media_index, bool) or not isinstance(media_index, int) or media_index < 0:
                raise MethodArtifactError("source index relation_provenance media_index must be a non-negative integer")
            record_hash = provenance.get("manifest_record_hash")
            if not isinstance(record_hash, str) or re.fullmatch(r"[0-9a-f]{64}", record_hash) is None:
                raise MethodArtifactError("source index relation_provenance requires manifest_record_hash")
        indexed[source_ref] = source_hash
    if indexed != chunk_hashes:
        raise MethodArtifactError("source index entries must exactly recover blind chunk source references and hashes")
    database = source_index.get("database")
    if database is not None:
        database = _require_mapping(database, "source index database")
        if database.get("query") != "SELECT id, type, content, tickers, media FROM tweets ORDER BY id":
            raise MethodArtifactError("source index database query is not the approved read-only corpus query")
        if not isinstance(database.get("sha256"), str) or re.fullmatch(r"[0-9a-f]{64}", database["sha256"]) is None:
            raise MethodArtifactError("source index database requires a SHA-256 hash")
        if not isinstance(database.get("sqlite_user_version"), int):
            raise MethodArtifactError("source index database requires sqlite_user_version")


def _validate_codebook(codebook: Mapping[str, Any], chunk_ids: set[str]) -> set[str]:
    _validate_hash(codebook, "codebook")
    if codebook.get("format") != "serenity-method-codebook/1":
        raise MethodArtifactError("codebook uses an unsupported format")
    if codebook.get("axes") != list(CODEBOOK_AXES):
        raise MethodArtifactError("codebook axes must match the open-coding contract exactly")
    codes = codebook.get("codes")
    if not isinstance(codes, list):
        raise MethodArtifactError("codebook codes must be a list")
    code_ids: set[str] = set()
    for code in codes:
        code = _require_mapping(code, "codebook code")
        code_id = _identifier(code.get("code_id"), "code_id")
        if code_id in code_ids:
            raise MethodArtifactError("codebook cannot repeat code_id")
        code_ids.add(code_id)
        if code.get("axis") not in CODEBOOK_AXES:
            raise MethodArtifactError("code axis is not in the required codebook axes")
        _nonempty_string(code.get("label"), "code label")
        refs = _identifiers(code.get("source_refs"), "code source_refs")
        if not set(refs) <= chunk_ids:
            raise MethodArtifactError("code source_refs must point to blind chunks")
        _nonempty_string(code.get("rationale"), "code rationale")
    return code_ids


def _validate_coding(coding: Mapping[str, Any], chunk_ids: set[str], code_ids: set[str]) -> tuple[set[str], set[str]]:
    _validate_hash(coding, "coding units")
    if coding.get("format") != "serenity-method-coding/1":
        raise MethodArtifactError("coding units use an unsupported format")
    units = coding.get("units")
    if not isinstance(units, list):
        raise MethodArtifactError("coding units must be a list")
    unit_ids: set[str] = set()
    referenced_code_ids: set[str] = set()
    for unit in units:
        unit = _require_mapping(unit, "coding unit")
        unit_id = _identifier(unit.get("unit_id"), "unit_id")
        if unit_id in unit_ids:
            raise MethodArtifactError("coding units cannot repeat unit_id")
        unit_ids.add(unit_id)
        refs = _identifiers(unit.get("source_refs"), "coding unit source_refs")
        if not set(refs) <= chunk_ids:
            raise MethodArtifactError("coding unit source_refs must point to blind chunks")
        for field in ("trigger", "evidence_sought", "inference", "falsifier"):
            _nonempty_string(unit.get(field), f"coding unit {field}")
        action_horizon = _require_mapping(unit.get("action_horizon"), "coding unit action_horizon")
        _nonempty_string(action_horizon.get("action"), "coding unit action_horizon.action")
        _nonempty_string(action_horizon.get("horizon"), "coding unit action_horizon.horizon")
        unit_codes = _identifiers(unit.get("code_ids"), "coding unit code_ids")
        if not set(unit_codes) <= code_ids:
            raise MethodArtifactError("coding unit code_ids must point to codebook codes")
        referenced_code_ids.update(unit_codes)
    return unit_ids, referenced_code_ids


def _validate_claim_ledger(ledger: Mapping[str, Any], unit_ids: set[str], code_ids: set[str]) -> tuple[set[str], int]:
    _validate_hash(ledger, "claim ledger")
    if ledger.get("format") != "serenity-method-claim-ledger/1":
        raise MethodArtifactError("claim ledger uses an unsupported format")
    claims = ledger.get("claims")
    if not isinstance(claims, list):
        raise MethodArtifactError("claim ledger claims must be a list")
    claim_ids: set[str] = set()
    referenced_unit_ids: set[str] = set()
    traceable_claims = 0
    for claim in claims:
        claim = _require_mapping(claim, "claim ledger item")
        claim_id = _identifier(claim.get("claim_id"), "claim_id")
        if claim_id in claim_ids:
            raise MethodArtifactError("claim ledger cannot repeat claim_id")
        claim_ids.add(claim_id)
        _nonempty_string(claim.get("claim"), "claim")
        tag = claim.get("provenance_tag")
        if tag not in PROVENANCE_TAGS:
            raise MethodArtifactError("claim requires exactly one provenance_tag: sourced, augmented, or unverified")
        if tag == "sourced":
            representatives = _identifiers(claim.get("representative_refs"), "sourced representative_refs")
            counterexamples = _identifiers(claim.get("counterexample_refs"), "sourced counterexample_refs", required=False)
            code_refs = _identifiers(claim.get("code_refs"), "sourced code_refs")
            if not set(representatives + counterexamples) <= unit_ids or not set(code_refs) <= code_ids:
                raise MethodArtifactError("sourced claim refs must remain traceable to coding units and codes")
            if counterexamples and set(representatives) & set(counterexamples):
                raise MethodArtifactError("sourced counterexample_refs must not reuse representative_refs")
            if not counterexamples:
                _nonempty_string(claim.get("counterexample_search_scope"), "sourced counterexample_search_scope")
                if claim.get("counterexample_status") != "none_found":
                    raise MethodArtifactError("sourced counterexample_status must be none_found when no counterexample is linked")
            referenced_unit_ids.update(representatives)
            referenced_unit_ids.update(counterexamples)
            traceable_claims += 1
        elif tag == "augmented":
            _nonempty_string(claim.get("augmentation_rationale"), "augmented augmentation_rationale")
        elif claim.get("hard_gate") is True:
            raise MethodArtifactError("unverified claim cannot become a hard gate")
    return referenced_unit_ids, traceable_claims


def compile_method_artifact(
    *,
    chunks: Mapping[str, Any],
    source_index: Mapping[str, Any],
    codebook: Mapping[str, Any],
    coding: Mapping[str, Any],
    claim_ledger: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and combine a human-authored coding pass without deriving a rule from it."""

    chunks = json.loads(canonical_json(_require_mapping(chunks, "blind chunks")))
    source_index = json.loads(canonical_json(_require_mapping(source_index, "source index")))
    codebook = json.loads(canonical_json(_require_mapping(codebook, "codebook")))
    coding = json.loads(canonical_json(_require_mapping(coding, "coding units")))
    claim_ledger = json.loads(canonical_json(_require_mapping(claim_ledger, "claim ledger")))
    chunk_ids = _validate_chunks(chunks)
    _validate_source_index(source_index, chunks)
    code_ids = _validate_codebook(codebook, chunk_ids)
    unit_ids, referenced_code_ids = _validate_coding(coding, chunk_ids, code_ids)
    _, traceable_claims = _validate_claim_ledger(claim_ledger, unit_ids, code_ids)
    orphan_codes = code_ids - referenced_code_ids
    if orphan_codes:
        raise MethodArtifactError(f"orphan code is not linked from a coding unit: {sorted(orphan_codes)}")
    reconciliation = {
        "chunks": len(chunk_ids),
        "codes": len(code_ids),
        "coding_units": len(unit_ids),
        "claims": len(claim_ledger["claims"]),
        "traceable_codes": len(referenced_code_ids),
        "traceable_claims": traceable_claims,
    }
    artifact: dict[str, Any] = {
        "format": "serenity-method-artifact/1",
        "chunks": chunks,
        "codebook": codebook,
        "coding": coding,
        "claim_ledger": claim_ledger,
        "input_hashes": {
            "chunks": _document_hash(chunks),
            "source_index": _document_hash(source_index),
            "codebook": _document_hash(codebook),
            "coding": _document_hash(coding),
            "claim_ledger": _document_hash(claim_ledger),
        },
        "reconciliation": reconciliation,
    }
    artifact["content_hash"] = _document_hash(artifact)
    return artifact


def validate_method_artifact(artifact: Mapping[str, Any], *, source_index: Mapping[str, Any]) -> dict[str, Any]:
    """Re-run all mechanical traceability checks and verify every content hash."""

    artifact = dict(_require_mapping(artifact, "method artifact"))
    if artifact.get("format") != "serenity-method-artifact/1":
        raise MethodArtifactError("method artifact uses an unsupported format")
    _validate_hash(artifact, "method artifact")
    rebuilt = compile_method_artifact(
        chunks=_require_mapping(artifact.get("chunks"), "artifact chunks"),
        source_index=source_index,
        codebook=_require_mapping(artifact.get("codebook"), "artifact codebook"),
        coding=_require_mapping(artifact.get("coding"), "artifact coding"),
        claim_ledger=_require_mapping(artifact.get("claim_ledger"), "artifact claim ledger"),
    )
    if rebuilt != artifact:
        raise MethodArtifactError("method artifact reconciliation or input hashes do not match")
    return artifact


class MethodArtifactStore:
    """Persist an immutable, content-addressed method artifact under the caller's root."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def store(self, artifact: Mapping[str, Any], *, source_index: Mapping[str, Any]) -> dict[str, str]:
        validated = validate_method_artifact(artifact, source_index=source_index)
        digest = validated["content_hash"]
        path = self.root / "records" / "method" / f"{digest}.json"
        source_index_hash = _document_hash(_require_mapping(source_index, "source index"))
        source_index_path = self.root / "records" / "method" / "source-index" / f"{source_index_hash}.json"
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise MethodArtifactError(f"stored method artifact cannot be read: {path}") from exc
            if existing != validated:
                raise MethodArtifactError(f"stored method artifact conflicts with its content hash: {path}")
        else:
            atomic_write_json(path, validated)
        if source_index_path.exists():
            try:
                existing_index = json.loads(source_index_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise MethodArtifactError(f"stored source index cannot be read: {source_index_path}") from exc
            if existing_index != source_index:
                raise MethodArtifactError(f"stored source index conflicts with its content hash: {source_index_path}")
        else:
            atomic_write_json(source_index_path, dict(source_index))
        return {"path": str(path), "content_hash": digest, "source_index_path": str(source_index_path)}


def aggregate_method_codings(
    packet_manifest: Mapping[str, Any],
    completed_results: Sequence[Mapping[str, Any]],
    *,
    synthesis: Mapping[str, Any] | None = None,
    candidate_digest: Mapping[str, Any] | None = None,
    candidate_digest_sha256: str | None = None,
    augmentations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Mechanically aggregate caller-selected completed coding results into review candidates."""

    packets = _validate_aggregate_manifest(packet_manifest)
    if not isinstance(completed_results, Sequence) or isinstance(completed_results, (str, bytes)):
        raise MethodArtifactError("completed_results must be a list of explicitly selected results")
    selected: dict[str, Mapping[str, Any]] = {}
    for item in completed_results:
        item = _require_mapping(item, "completed result")
        execution = _require_mapping(item.get("execution"), "completed result execution")
        output = _require_mapping(item.get("output"), "completed result output")
        packet_id = _validate_completed_result(packet_manifest, packets, execution, output, item)
        if packet_id in selected:
            raise MethodArtifactError(f"aggregate cannot select duplicate completed results for packet: {packet_id}")
        selected[packet_id] = {"execution": execution, "output": output, "output_sha256": item.get("output_sha256")}
    missing = [packet_id for packet_id in packets if packet_id not in selected]
    if missing:
        raise MethodArtifactError(f"aggregate is missing a selected completed result for packet: {missing[0]}")

    code_occurrences: dict[tuple[str, str], list[dict[str, str]]] = {}
    units: list[dict[str, Any]] = []
    coverage: list[dict[str, Any]] = []
    coded_chunks = 0
    no_reusable_move_chunks = 0
    for packet_id, packet in packets.items():
        result_by_chunk = {item["chunk_id"]: item for item in selected[packet_id]["output"]["dispositions"]}
        for chunk_id in packet["chunk_ids"]:
            disposition = result_by_chunk[chunk_id]
            coverage.append({"packet_id": packet_id, "chunk_id": chunk_id, "disposition": disposition["disposition"], "uncertainty_notes": list(disposition["uncertainty_notes"]), "contradiction_notes": list(disposition["contradiction_notes"])})
            if disposition["disposition"] == "no_reusable_move":
                no_reusable_move_chunks += 1
                continue
            coded_chunks += 1
            raw_coding = _require_mapping(disposition["coding"], "coded disposition coding")
            unit_code_ids: list[str] = []
            raw_codes: list[dict[str, str]] = []
            for raw_code in raw_coding["codes"]:
                raw_code = _require_mapping(raw_code, "coded disposition code")
                axis = raw_code.get("axis")
                label = _nonempty_string(raw_code.get("label"), "coded disposition code label")
                rationale = _nonempty_string(raw_code.get("rationale"), "coded disposition code rationale")
                if axis not in CODEBOOK_AXES:
                    raise MethodArtifactError("method coding output uses a noncanonical axis")
                code_id = f"code-{_hash({'axis': axis, 'label': label})[:20]}"
                unit_code_ids.append(code_id)
                raw_codes.append({"axis": axis, "label": label, "rationale": rationale})
                code_occurrences.setdefault((axis, label), []).append({"source_ref": chunk_id, "rationale": rationale})
            if len(set(unit_code_ids)) != len(unit_code_ids):
                raise MethodArtifactError("coded disposition cannot repeat an exact axis/label code")
            unit_id = f"unit-{_hash({'packet_id': packet_id, 'chunk_id': chunk_id})[:20]}"
            units.append({"unit_id": unit_id, "packet_id": packet_id, "source_refs": [chunk_id], "trigger": raw_coding["trigger"], "evidence_sought": raw_coding["evidence_sought"], "inference": raw_coding["inference"], "action_horizon": dict(_require_mapping(raw_coding["action_horizon"], "coded disposition action_horizon")), "falsifier": raw_coding["falsifier"], "code_ids": unit_code_ids, "raw_codes": raw_codes, "uncertainty_notes": list(disposition["uncertainty_notes"]), "contradiction_notes": list(disposition["contradiction_notes"])})
    codebook = {"format": "serenity-method-codebook/1", "axes": list(CODEBOOK_AXES), "codes": [{"code_id": f"code-{_hash({'axis': axis, 'label': label})[:20]}", "axis": axis, "label": label, "source_refs": [item["source_ref"] for item in occurrences], "rationale": "\n\n".join(item["rationale"] for item in occurrences), "rationales": occurrences} for (axis, label), occurrences in sorted(code_occurrences.items())]}
    codebook["content_hash"] = _document_hash(codebook)
    coding = {"format": "serenity-method-coding/1", "units": units, "disposition_coverage": coverage}
    coding["content_hash"] = _document_hash(coding)
    baseline_ledger = _aggregate_claim_ledger(codebook, coding)
    digest: dict[str, Any] = {
        "format": "serenity-method-candidate-digest/1",
        "packet_manifest_content_hash": packet_manifest["content_hash"],
        "packet_results": [{"packet_id": packet_id, "packet_content_hash": packet["content_hash"], "output_sha256": selected[packet_id]["output_sha256"]} for packet_id, packet in packets.items()],
        "coverage": {"packets": len(packets), "chunks": len(coverage), "coded_chunks": coded_chunks, "no_reusable_move_chunks": no_reusable_move_chunks, "all_disposition_coverage_hash": _hash(coverage)},
        "bounded_summary": _build_candidate_digest_summary(codebook, coding, baseline_ledger),
        "input_hashes": {"codebook": codebook["content_hash"], "coding": coding["content_hash"], "claim_ledger": baseline_ledger["content_hash"]},
    }
    digest["content_hash"] = _document_hash(digest)
    if synthesis is None:
        if candidate_digest is not None or candidate_digest_sha256 is not None or augmentations is not None:
            raise MethodArtifactError("candidate digest and augmentations require an explicit Sol synthesis")
        claim_ledger = baseline_ledger
    else:
        claim_ledger = _aggregate_claim_ledger(
            codebook,
            coding,
            synthesis=synthesis,
            candidate_digest=digest,
            candidate_digest_sha256=candidate_digest_sha256,
            supplied_candidate_digest=candidate_digest,
            augmentations=augmentations,
        )
    return {"codebook": codebook, "coding": coding, "claim_ledger": claim_ledger, "candidate_digest": digest}


def _validate_aggregate_manifest(packet_manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    packet_manifest = _require_mapping(packet_manifest, "packet manifest")
    _validate_hash(packet_manifest, "packet manifest")
    if packet_manifest.get("format") != "serenity-method-packet-manifest/1":
        raise MethodArtifactError("packet manifest uses an unsupported format")
    for field in ("source_chunks_hash", "source_index_hash"):
        value = packet_manifest.get(field)
        if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise MethodArtifactError(f"packet manifest requires {field}")
    if isinstance(packet_manifest.get("batch_size"), bool) or not isinstance(packet_manifest.get("batch_size"), int) or packet_manifest["batch_size"] <= 0:
        raise MethodArtifactError("packet manifest requires a positive batch_size")
    packets = packet_manifest.get("packets")
    if not isinstance(packets, list) or not packets:
        raise MethodArtifactError("packet manifest must list packets")
    by_id: dict[str, Mapping[str, Any]] = {}
    seen_chunks: set[str] = set()
    for packet in packets:
        packet = _require_mapping(packet, "packet manifest packet")
        packet_id = _identifier(packet.get("packet_id"), "packet manifest packet_id")
        if packet_id in by_id:
            raise MethodArtifactError("packet manifest cannot repeat a packet_id")
        path = _nonempty_string(packet.get("path"), "packet manifest packet path")
        if Path(path).stem != packet_id:
            raise MethodArtifactError("packet manifest packet path must match packet_id")
        content_hash = packet.get("content_hash")
        if not isinstance(content_hash, str) or re.fullmatch(r"[0-9a-f]{64}", content_hash) is None:
            raise MethodArtifactError("packet manifest packet requires a content hash")
        chunk_ids = _identifiers(packet.get("chunk_ids"), "packet manifest chunk_ids")
        if packet.get("count") != len(chunk_ids):
            raise MethodArtifactError("packet manifest packet count must match chunk_ids")
        if seen_chunks & set(chunk_ids):
            raise MethodArtifactError("packet manifest cannot repeat a chunk across packets")
        seen_chunks.update(chunk_ids)
        by_id[packet_id] = packet
    return by_id


def _validate_completed_result(packet_manifest: Mapping[str, Any], packets: Mapping[str, Mapping[str, Any]], execution: Mapping[str, Any], output: Mapping[str, Any], item: Mapping[str, Any]) -> str:
    if execution.get("format") != "serenity-method-coding-execution/1" or execution.get("status") != "completed":
        raise MethodArtifactError("aggregate requires a completed method-runner execution record")
    packet_id = _identifier(execution.get("packet_id"), "completed execution packet_id")
    if packet_id not in packets:
        raise MethodArtifactError("completed result packet is not in the packet manifest")
    if execution.get("full_manifest_content_hash") != packet_manifest.get("content_hash"):
        raise MethodArtifactError("completed execution does not bind the full packet manifest hash")
    manifest_sha256 = item.get("manifest_sha256")
    if not isinstance(manifest_sha256, str) or execution.get("full_manifest_sha256") != manifest_sha256:
        raise MethodArtifactError("completed execution does not bind the supplied packet manifest file")
    if packet_id not in execution.get("selected_packet_ids", []):
        raise MethodArtifactError("completed execution does not select its packet_id")
    packet = packets[packet_id]
    packet_sha256 = output.get("packet_sha256")
    if output.get("packet_id") != packet_id or not isinstance(packet_sha256, str):
        raise MethodArtifactError("completed output packet identity does not match execution")
    package_hashes = _require_mapping(execution.get("package_sha256"), "completed execution package_sha256")
    if package_hashes.get(packet["path"]) != packet_sha256:
        raise MethodArtifactError("completed output packet SHA does not match execution package")
    expected_output_sha256 = execution.get("output_sha256")
    if not isinstance(expected_output_sha256, str) or item.get("output_sha256") != expected_output_sha256:
        raise MethodArtifactError("completed output SHA does not match execution record")
    _validate_method_coding_output(output, packet_id=packet_id, packet_sha256=packet_sha256, expected_chunk_ids=list(packet["chunk_ids"]))
    return packet_id


def _validate_method_coding_output(output: Mapping[str, Any], *, packet_id: str, packet_sha256: str, expected_chunk_ids: Sequence[str]) -> None:
    try:
        schema = json.loads(_METHOD_CODING_OUTPUT_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MethodArtifactError("method coding output schema must be readable JSON") from exc
    errors = list(Draft202012Validator(schema).iter_errors(output))
    if errors:
        raise MethodArtifactError(f"method coding output does not match schema: {errors[0].message}")
    if output.get("packet_id") != packet_id or output.get("packet_sha256") != packet_sha256:
        raise MethodArtifactError("method coding output packet identity does not match execution")
    observed = [item["chunk_id"] for item in output["dispositions"]]
    if len(observed) != len(set(observed)) or set(observed) != set(expected_chunk_ids):
        raise MethodArtifactError("method coding output does not exactly cover its manifest packet chunks")


def _aggregate_claim_ledger(
    codebook: Mapping[str, Any],
    coding: Mapping[str, Any],
    *,
    synthesis: Mapping[str, Any] | None = None,
    candidate_digest: Mapping[str, Any] | None = None,
    candidate_digest_sha256: str | None = None,
    supplied_candidate_digest: Mapping[str, Any] | None = None,
    augmentations: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    code_ids = {code["code_id"] for code in codebook["codes"]}
    unit_ids = {unit["unit_id"] for unit in coding["units"]}
    if synthesis is None:
        if candidate_digest is not None or candidate_digest_sha256 is not None or supplied_candidate_digest is not None or augmentations is not None:
            raise MethodArtifactError("candidate digest, synthesis, and augmentations must be supplied together after baseline aggregation")
        claims = [{"claim_id": f"claim-{_hash({'unit_id': unit['unit_id'], 'inference': unit['inference']})[:20]}", "claim": unit["inference"], "provenance_tag": "unverified", "hard_gate": False, "candidate_unit_refs": [unit["unit_id"]], "uncertainty_notes": unit["uncertainty_notes"], "contradiction_notes": unit["contradiction_notes"]} for unit in coding["units"]]
    else:
        if candidate_digest is None or supplied_candidate_digest is None or candidate_digest_sha256 is None:
            raise MethodArtifactError("claim synthesis requires the baseline candidate digest and its raw file SHA-256")
        _validate_hash(candidate_digest, "baseline candidate digest")
        if supplied_candidate_digest != candidate_digest:
            raise MethodArtifactError("supplied candidate digest does not match the deterministic baseline digest")
        if not isinstance(candidate_digest_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", candidate_digest_sha256) is None:
            raise MethodArtifactError("claim synthesis requires a candidate digest SHA-256")
        claims = _translate_synthesis_claims(codebook, coding, candidate_digest, candidate_digest_sha256, synthesis)
        claims.extend(_translate_augmentations(augmentations, existing_claim_ids={claim["claim_id"] for claim in claims}))
    ledger = {"format": "serenity-method-claim-ledger/1", "claims": claims}
    _validate_claim_ledger(ledger, unit_ids, code_ids)
    ledger["content_hash"] = _document_hash(ledger)
    return ledger


def _translate_synthesis_claims(
    codebook: Mapping[str, Any], coding: Mapping[str, Any], candidate_digest: Mapping[str, Any], candidate_digest_sha256: str, synthesis: Mapping[str, Any]
) -> list[dict[str, Any]]:
    synthesis = _require_mapping(synthesis, "claim synthesis")
    try:
        schema = json.loads(_METHOD_CLAIM_SYNTHESIS_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MethodArtifactError("method claim synthesis schema must be readable JSON") from exc
    errors = list(Draft202012Validator(schema).iter_errors(synthesis))
    if errors:
        raise MethodArtifactError(f"claim synthesis does not match schema: {errors[0].message}")
    if synthesis.get("candidate_digest_content_hash") != candidate_digest.get("content_hash"):
        raise MethodArtifactError("claim synthesis candidate digest content hash mismatch")
    if synthesis.get("candidate_digest_sha256") != candidate_digest_sha256:
        raise MethodArtifactError("claim synthesis candidate digest SHA mismatch")
    shown_units, shown_codes = _shown_candidate_digest_refs(candidate_digest, codebook=codebook, coding=coding)
    code_by_label = {(code["axis"], code["label"]): code["code_id"] for code in codebook["codes"]}
    translated: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    for raw_claim in synthesis["claims"]:
        claim_id = _identifier(raw_claim.get("claim_id"), "synthesis claim_id")
        if claim_id in seen_claim_ids:
            raise MethodArtifactError("claim synthesis cannot repeat claim_id")
        seen_claim_ids.add(claim_id)
        representatives = _identifiers(raw_claim.get("shown_unit_refs"), "synthesis shown_unit_refs")
        counterexamples = _identifiers(raw_claim.get("counterexample_refs"), "synthesis counterexample_refs", required=False)
        shown_code_refs = raw_claim.get("shown_code_refs")
        if not isinstance(shown_code_refs, list) or not shown_code_refs:
            raise MethodArtifactError("claim synthesis shown_code_refs must be a non-empty list")
        code_refs: list[str] = []
        seen_labels: set[tuple[str, str]] = set()
        for shown_code in shown_code_refs:
            shown_code = _require_mapping(shown_code, "synthesis shown_code_ref")
            axis, label = shown_code.get("axis"), _nonempty_string(shown_code.get("label"), "synthesis shown_code_ref label")
            key = (axis, label)
            if key not in shown_codes or key not in code_by_label:
                raise MethodArtifactError("claim synthesis references an unknown or unshown axis/label")
            if key in seen_labels:
                raise MethodArtifactError("claim synthesis cannot repeat shown_code_refs")
            seen_labels.add(key)
            code_refs.append(code_by_label[key])
        if not set(representatives + counterexamples) <= shown_units:
            raise MethodArtifactError("claim synthesis references an unknown or unshown unit")
        if set(representatives) & set(counterexamples):
            raise MethodArtifactError("claim synthesis counterexample refs must differ from shown unit refs")
        tag = raw_claim.get("provenance_tag")
        claim: dict[str, Any] = {
            "claim_id": claim_id,
            "claim": _nonempty_string(raw_claim.get("claim"), "synthesis claim"),
            "provenance_tag": tag,
            "why": _nonempty_string(raw_claim.get("why"), "synthesis why"),
            "uncertainty_notes": _string_notes(raw_claim.get("uncertainty_notes"), "synthesis uncertainty_notes"),
            "contradiction_notes": _string_notes(raw_claim.get("contradiction_notes"), "synthesis contradiction_notes"),
            "hard_gate": False,
        }
        scope, status = raw_claim.get("counterexample_search_scope"), raw_claim.get("counterexample_status")
        if tag == "sourced":
            if counterexamples:
                if status != "found" or not isinstance(scope, str) or not scope.strip():
                    raise MethodArtifactError("sourced synthesis counterexamples require found status and scope")
            elif status != "none_found" or not isinstance(scope, str) or not scope.strip():
                raise MethodArtifactError("sourced synthesis without counterexamples requires none_found scope")
            claim.update(representative_refs=representatives, counterexample_refs=counterexamples, code_refs=code_refs, counterexample_search_scope=scope, counterexample_status=status)
        elif tag == "unverified":
            if counterexamples or scope is not None or status is not None:
                raise MethodArtifactError("unverified synthesis claim cannot present sourced counterexample evidence")
            claim.update(candidate_unit_refs=representatives, candidate_code_refs=code_refs)
        else:
            raise MethodArtifactError("Sol claim synthesis may only emit sourced or unverified claims")
        translated.append(claim)
    return translated


def _translate_augmentations(augmentations: Mapping[str, Any] | None, *, existing_claim_ids: set[str]) -> list[dict[str, Any]]:
    if augmentations is None:
        return []
    augmentations = _require_mapping(augmentations, "method augmentations")
    if augmentations.get("format") != "serenity-method-augmentations/1":
        raise MethodArtifactError("method augmentations uses an unsupported format")
    raw_claims = augmentations.get("claims")
    if not isinstance(raw_claims, list):
        raise MethodArtifactError("method augmentations claims must be a list")
    translated: list[dict[str, Any]] = []
    for raw_claim in raw_claims:
        raw_claim = _require_mapping(raw_claim, "method augmentation claim")
        claim_id = _identifier(raw_claim.get("claim_id"), "method augmentation claim_id")
        if claim_id in existing_claim_ids or any(claim["claim_id"] == claim_id for claim in translated):
            raise MethodArtifactError("method augmentations cannot repeat a synthesis claim_id")
        if raw_claim.get("provenance_tag") != "augmented":
            raise MethodArtifactError("method augmentations claims must be tagged augmented")
        translated.append(
            {
                "claim_id": claim_id,
                "claim": _nonempty_string(raw_claim.get("claim"), "method augmentation claim"),
                "provenance_tag": "augmented",
                "augmentation_rationale": _nonempty_string(raw_claim.get("augmentation_rationale"), "method augmentation rationale"),
                "why": _nonempty_string(raw_claim.get("why"), "method augmentation why"),
                "uncertainty_notes": _string_notes(raw_claim.get("uncertainty_notes"), "method augmentation uncertainty_notes"),
                "contradiction_notes": _string_notes(raw_claim.get("contradiction_notes"), "method augmentation contradiction_notes"),
                "hard_gate": False,
            }
        )
    return translated


def _shown_candidate_digest_refs(candidate_digest: Mapping[str, Any], *, codebook: Mapping[str, Any], coding: Mapping[str, Any]) -> tuple[set[str], set[tuple[str, str]]]:
    summary = _require_mapping(candidate_digest.get("bounded_summary"), "candidate digest bounded_summary")
    units: set[str] = set()
    codes: set[tuple[str, str]] = set()
    frequency = summary.get("axis_label_frequency")
    if not isinstance(frequency, list):
        raise MethodArtifactError("candidate digest requires shown axis labels")
    for axis_entry in frequency:
        axis_entry = _require_mapping(axis_entry, "candidate digest axis labels")
        entries = axis_entry.get("entries")
        if not isinstance(entries, list):
            raise MethodArtifactError("candidate digest axis labels are invalid")
        for entry in entries:
            entry = _require_mapping(entry, "candidate digest label entry")
            representatives = entry.get("representatives")
            if not isinstance(representatives, list):
                raise MethodArtifactError("candidate digest representatives are invalid")
            for representative in representatives:
                representative = _require_mapping(representative, "candidate digest representative")
                unit_id = _identifier(representative.get("unit_id"), "candidate digest representative unit_id")
                semantic = _require_mapping(representative.get("semantic_content"), "candidate digest representative semantic_content")
                matching = _require_mapping(semantic.get("matching_code"), "candidate digest representative matching_code")
                axis, label = matching.get("axis"), _nonempty_string(matching.get("label"), "candidate digest matching code label")
                units.add(unit_id)
                codes.add((axis, label))
    for section_name in ("counterexample_refs", "contradiction_refs", "uncertainty_refs"):
        section = _require_mapping(summary.get(section_name), f"candidate digest {section_name}")
        entries = section.get("entries")
        if not isinstance(entries, list):
            raise MethodArtifactError(f"candidate digest {section_name} entries must be a list")
        for entry in entries:
            entry = _require_mapping(entry, f"candidate digest {section_name} entry")
            if isinstance(entry.get("unit_id"), str):
                units.add(_identifier(entry["unit_id"], f"candidate digest {section_name} unit_id"))
            counterexample = entry.get("counterexample")
            if isinstance(counterexample, Mapping):
                units.add(_identifier(counterexample.get("unit_id"), f"candidate digest {section_name} counterexample unit_id"))
    known_units = {unit["unit_id"] for unit in coding["units"]}
    known_codes = {(code["axis"], code["label"]) for code in codebook["codes"]}
    if not units or not codes or not units <= known_units or not codes <= known_codes:
        raise MethodArtifactError("candidate digest shown refs do not match its granular candidates")
    return units, codes


def _string_notes(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(note, str) and note.strip() for note in value):
        raise MethodArtifactError(f"{label} must be a list of non-empty strings")
    return list(value)


def _build_candidate_digest_summary(codebook: Mapping[str, Any], coding: Mapping[str, Any], ledger: Mapping[str, Any]) -> dict[str, Any]:
    units_by_code: dict[str, list[Mapping[str, Any]]] = {}
    units_by_id = {unit["unit_id"]: unit for unit in coding["units"]}
    manifest_position_by_chunk = {entry["chunk_id"]: position for position, entry in enumerate(coding["disposition_coverage"])}
    for unit in coding["units"]:
        for code_id in unit["code_ids"]:
            units_by_code.setdefault(code_id, []).append(unit)
    labels_by_axis: dict[str, list[dict[str, Any]]] = {axis: [] for axis in CODEBOOK_AXES}
    for code in codebook["codes"]:
        units = units_by_code.get(code["code_id"], [])
        first_manifest_occurrence = min(manifest_position_by_chunk[unit["source_refs"][0]] for unit in units)
        labels_by_axis[code["axis"]].append(
            {
                "axis": code["axis"],
                "label": code["label"],
                "frequency": len(code["source_refs"]),
                "first_manifest_occurrence": first_manifest_occurrence,
                "representatives": [
                    _digest_unit_semantic(unit, code=code)
                    for unit in units[: _CANDIDATE_DIGEST_POLICY["max_representatives_per_label"]]
                ],
                "representatives_omitted_count": max(0, len(units) - _CANDIDATE_DIGEST_POLICY["max_representatives_per_label"]),
                "representatives_omitted_hash": _hash(units[_CANDIDATE_DIGEST_POLICY["max_representatives_per_label"] :]),
            }
        )
    counterexamples = [
        {
            "claim_id": claim["claim_id"],
            "claim": _bounded_digest_text(claim["claim"]),
            "unit_id": unit_id,
            "counterexample": _digest_unit_semantic(units_by_id[unit_id]),
        }
        for claim in ledger["claims"]
        if claim.get("provenance_tag") == "sourced"
        for unit_id in claim.get("counterexample_refs", [])
    ]
    contradictions = [
        {"unit_id": unit["unit_id"], "source_refs": unit["source_refs"], "note_count": len(unit["contradiction_notes"]), "notes": [_bounded_digest_text(note) for note in unit["contradiction_notes"]]}
        for unit in coding["units"]
        if unit["contradiction_notes"]
    ]
    uncertainties = [
        {"unit_id": unit["unit_id"], "source_refs": unit["source_refs"], "note_count": len(unit["uncertainty_notes"]), "notes": [_bounded_digest_text(note) for note in unit["uncertainty_notes"]]}
        for unit in coding["units"]
        if unit["uncertainty_notes"]
    ]
    return {
        "policy": _CANDIDATE_DIGEST_POLICY,
        "policy_hash": _hash(_CANDIDATE_DIGEST_POLICY),
        "axis_label_frequency": [
            {"axis": axis, **_select_axis_digest_labels(labels_by_axis[axis], _CANDIDATE_DIGEST_POLICY["max_axis_labels_per_axis"])}
            for axis in CODEBOOK_AXES
        ],
        "counterexample_refs": _bounded_digest_entries(counterexamples, _CANDIDATE_DIGEST_POLICY["max_reference_entries_per_section"]),
        "contradiction_refs": _bounded_digest_entries(contradictions, _CANDIDATE_DIGEST_POLICY["max_reference_entries_per_section"]),
        "uncertainty_refs": _bounded_digest_entries(uncertainties, _CANDIDATE_DIGEST_POLICY["max_reference_entries_per_section"]),
    }


def _select_axis_digest_labels(entries: Sequence[Mapping[str, Any]], limit: int) -> dict[str, Any]:
    """Keep exact labels, prioritising recurring labels without alphabetical-prefix bias."""

    by_frequency: dict[int, list[dict[str, Any]]] = {}
    for entry in entries:
        copied = dict(entry)
        by_frequency.setdefault(copied["frequency"], []).append(copied)
    selected: list[dict[str, Any]] = []
    tier_audit: list[dict[str, Any]] = []
    remaining = limit
    for frequency in sorted(by_frequency, reverse=True):
        tier = sorted(by_frequency[frequency], key=lambda entry: (entry["first_manifest_occurrence"], entry["label"]))
        if remaining <= 0:
            tier_audit.append({"frequency": frequency, "label_count": len(tier), "shown_count": 0, "selection": "lower_frequency_omitted_after_capacity"})
            continue
        if len(tier) <= remaining:
            for entry in tier:
                entry["selection_basis"] = "frequency_priority_all_fit"
            selected.extend(tier)
            tier_audit.append({"frequency": frequency, "label_count": len(tier), "shown_count": len(tier), "selection": "frequency_priority_all_fit"})
            remaining -= len(tier)
            continue
        selected_indexes = _manifest_span_indexes(len(tier), remaining)
        for index in selected_indexes:
            tier[index]["selection_basis"] = "frequency_tie_manifest_span"
            tier[index]["selection_rank_in_tier"] = selected_indexes.index(index) + 1
        selected.extend(tier[index] for index in selected_indexes)
        tier_audit.append({"frequency": frequency, "label_count": len(tier), "shown_count": len(selected_indexes), "selection": "first_manifest_occurrence_span"})
        remaining = 0
    selected_ids = {(entry["axis"], entry["label"]) for entry in selected}
    omitted = [dict(entry) for entry in entries if (entry["axis"], entry["label"]) not in selected_ids]
    selected.sort(key=lambda entry: (-entry["frequency"], entry["first_manifest_occurrence"], entry["label"]))
    return {
        "entries": selected,
        "omitted_count": len(omitted),
        "omitted_hash": _hash(omitted),
        "selection_rationale": {
            "priority": "descending_exact_label_frequency",
            "tie_break": "first_manifest_occurrence_span",
            "limit": limit,
            "shown_first_manifest_occurrence_range": _manifest_occurrence_range(selected),
            "omitted_first_manifest_occurrence_range": _manifest_occurrence_range(omitted),
            "frequency_tier_count": len(tier_audit),
            "frequency_tier_hash": _hash(tier_audit),
        },
    }


def _manifest_span_indexes(size: int, count: int) -> list[int]:
    if count >= size:
        return list(range(size))
    if count == 1:
        return [size // 2]
    return [(position * (size - 1)) // (count - 1) for position in range(count)]


def _manifest_occurrence_range(entries: Sequence[Mapping[str, Any]]) -> dict[str, int] | None:
    if not entries:
        return None
    positions = [entry["first_manifest_occurrence"] for entry in entries]
    return {"first": min(positions), "last": max(positions)}


def _bounded_digest_entries(entries: Sequence[Mapping[str, Any]], limit: int) -> dict[str, Any]:
    shown = [dict(entry) for entry in entries[:limit]]
    omitted = [dict(entry) for entry in entries[limit:]]
    return {"entries": shown, "omitted_count": len(omitted), "omitted_hash": _hash(omitted)}


def _digest_unit_semantic(unit: Mapping[str, Any], *, code: Mapping[str, Any] | None = None) -> dict[str, Any]:
    semantic: dict[str, Any] = {
        "trigger": _bounded_digest_text(unit["trigger"]),
        "evidence_sought": _bounded_digest_text(unit["evidence_sought"]),
        "inference": _bounded_digest_text(unit["inference"]),
        "action_horizon": {
            "action": _bounded_digest_text(unit["action_horizon"]["action"]),
            "horizon": _bounded_digest_text(unit["action_horizon"]["horizon"]),
        },
        "falsifier": _bounded_digest_text(unit["falsifier"]),
        "uncertainty_notes": [_bounded_digest_text(note) for note in unit["uncertainty_notes"]],
        "contradiction_notes": [_bounded_digest_text(note) for note in unit["contradiction_notes"]],
    }
    if code is not None:
        matching = next((raw for raw in unit["raw_codes"] if raw["axis"] == code["axis"] and raw["label"] == code["label"]), None)
        if matching is None:
            raise MethodArtifactError("candidate digest representative cannot recover its matching code rationale")
        semantic["matching_code"] = {
            "axis": code["axis"],
            "label": code["label"],
            "rationale": _bounded_digest_text(matching["rationale"]),
        }
    return {"unit_id": unit["unit_id"], "source_refs": unit["source_refs"], "semantic_content": semantic}


def _bounded_digest_text(value: str) -> dict[str, Any]:
    value = _nonempty_string(value, "candidate digest text")
    limit = _CANDIDATE_DIGEST_POLICY["max_semantic_field_characters"]
    shown, omitted = value[:limit], value[limit:]
    return {"text": shown, "omitted_character_count": len(omitted), "omitted_hash": _hash(omitted)}


def build_method_packets_from_sqlite(
    database: Path, *, media_manifest: Path | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read only the declared corpus columns and produce stable, private-provenance packets."""

    database = Path(database)
    if not database.is_file():
        raise MethodArtifactError(f"SQLite database not found: {database}")
    query = "SELECT id, type, content, tickers, media FROM tweets ORDER BY id"
    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
        rows = connection.execute(query).fetchall()
        sqlite_user_version = connection.execute("PRAGMA user_version").fetchone()[0]
    except sqlite3.Error as exc:
        raise MethodArtifactError(f"SQLite corpus cannot be read: {database}") from exc
    finally:
        if connection is not None:
            connection.close()
    database_sha256 = hashlib.sha256(database.read_bytes()).hexdigest()
    normalized: list[dict[str, Any]] = []
    media_relations: dict[tuple[str, int], dict[str, Any]] = {}
    for row_id, source_type, content, raw_tickers, raw_media in rows:
        source_row_id = str(row_id)
        if not isinstance(content, str) or not content.strip():
            ticker = _representative_ticker(raw_tickers)
        else:
            ticker = _representative_ticker(raw_tickers)
            normalized.append(
                {
                    "source_row_id": source_row_id,
                    "source_type": str(source_type),
                    "text": content,
                    **({"ticker": ticker} if ticker else {}),
                }
            )
        if media_manifest is not None:
            for media_index, url in enumerate(_media_urls(raw_media)):
                media_relations[(source_row_id, media_index)] = {
                    "source_row_id": source_row_id,
                    "source_type": str(source_type),
                    "media_index": media_index,
                    "url": url,
                    **({"ticker": ticker} if ticker else {}),
                }
    metadata = {
        "sha256": database_sha256,
        "query": query,
        "sqlite_user_version": sqlite_user_version,
        "rows_read": len(rows),
        "rows_normalized": len(normalized),
    }
    if media_manifest is None:
        return build_method_packets(normalized, database=metadata)
    annotations, media_metadata, source_index_media = _media_annotations_from_manifest(
        media_manifest=Path(media_manifest), relations=media_relations, database_sha256=database_sha256
    )
    return build_method_packets(
        normalized,
        annotations,
        database=metadata,
        source_index_metadata=source_index_media,
        output_metadata=media_metadata,
    )


def _media_urls(raw_media: Any) -> list[str]:
    if raw_media is None or raw_media == "":
        return []
    try:
        parsed = json.loads(raw_media) if isinstance(raw_media, str) else raw_media
    except (TypeError, json.JSONDecodeError) as exc:
        raise MethodArtifactError("tweets.media must be a JSON list when a media manifest is supplied") from exc
    if not isinstance(parsed, list):
        raise MethodArtifactError("tweets.media must be a JSON list when a media manifest is supplied")
    urls: list[str] = []
    for item in parsed:
        url = item if isinstance(item, str) else item.get("url") if isinstance(item, Mapping) else None
        if not isinstance(url, str) or not url:
            raise MethodArtifactError("tweets.media must contain URL strings when a media manifest is supplied")
        urls.append(url)
    return urls


def _media_annotations_from_manifest(
    *, media_manifest: Path, relations: Mapping[tuple[str, int], Mapping[str, Any]], database_sha256: str
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    try:
        raw = media_manifest.read_bytes()
        decoded = _read_method_media_manifest(raw, media_manifest)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, MethodArtifactError) as exc:
        if isinstance(exc, MethodArtifactError):
            raise
        raise MethodArtifactError(f"media manifest must be readable JSON: {media_manifest}") from exc
    records, manifest_metadata = decoded
    for binding_key in ("source_db_sha256", "database_sha256"):
        binding = manifest_metadata.get(binding_key)
        if binding is not None and binding != database_sha256:
            raise MethodArtifactError("media manifest database hash mismatch")
    manifest_by_relation: dict[tuple[str, int], Mapping[str, Any]] = {}
    for record in records:
        record = _require_mapping(record, "media manifest record")
        tweet_id = _identifier(record.get("tweet_id"), "media manifest tweet_id")
        media_index = record.get("media_index")
        if isinstance(media_index, bool) or not isinstance(media_index, int) or media_index < 0:
            raise MethodArtifactError("media manifest media_index must be a non-negative integer")
        key = (tweet_id, media_index)
        relation = relations.get(key)
        if relation is None:
            raise MethodArtifactError("media manifest tweet/media index mismatch with corpus database")
        if record.get("url") != relation["url"]:
            raise MethodArtifactError("media manifest URL mismatch with corpus database")
        record_binding = record.get("source_db_sha256") or record.get("database_sha256")
        if record_binding is not None and record_binding != database_sha256:
            raise MethodArtifactError("media manifest database hash mismatch")
        if key in manifest_by_relation:
            raise MethodArtifactError("media manifest cannot repeat a tweet/media index relation")
        manifest_by_relation[key] = record
    available_annotations: list[dict[str, Any]] = []
    failures: dict[str, int] = {}
    excluded_relations: list[dict[str, Any]] = []
    available = 0
    for key in sorted(relations):
        relation = relations[key]
        record = manifest_by_relation.get(key)
        if record is None:
            _count_failure(failures, "missing_manifest")
            continue
        annotation, relation_failures, excluded_relation = _approved_media_annotation(record, relation)
        for failure in relation_failures:
            _count_failure(failures, failure)
        if excluded_relation is not None:
            excluded_relations.append(excluded_relation)
        if annotation is not None:
            available_annotations.append(annotation)
            available += 1
    annotations = _deduplicate_media_annotations(available_annotations)
    coverage = {
        "available_relations": available,
        "denominator": len(relations),
        "incomplete": len(relations) - available - len(excluded_relations),
        "manifest_records": len(records),
        "unavailable_relations": len(excluded_relations),
        "unique_available_media": len(annotations),
    }
    media_metadata = {
        "coverage": coverage,
        "excluded_media": {"unavailable_fetch": len(excluded_relations)} if excluded_relations else {},
        "failure_taxonomy": dict(sorted(failures.items())),
        "status": "complete" if not failures and coverage["incomplete"] == 0 else "incomplete",
    }
    source_index_media = {
        "content_hash": hashlib.sha256(raw).hexdigest(),
        **media_metadata,
        "excluded_relations": excluded_relations,
    }
    return annotations, media_metadata, source_index_media


def _deduplicate_media_annotations(annotations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Collapse repeated binary media by SHA, never by coder-facing text or labels."""

    by_source_sha: dict[str, list[Mapping[str, Any]]] = {}
    for annotation in annotations:
        source_sha = annotation.get("media_source_sha256")
        if not isinstance(source_sha, str) or re.fullmatch(r"[0-9a-f]{64}", source_sha) is None:
            raise MethodArtifactError("approved media annotation requires a source SHA-256 digest")
        by_source_sha.setdefault(source_sha, []).append(annotation)
    grouped: list[dict[str, Any]] = []
    for source_sha, relations in by_source_sha.items():
        first = relations[0]
        text = _nonempty_string(first.get("text"), "approved media text")
        if any(_nonempty_string(relation.get("text"), "approved media text") != text for relation in relations[1:]):
            raise MethodArtifactError("same media source SHA has conflicting approved derivative text")
        grouped.append({"media_source_sha256": source_sha, "text": text, "source_relations": [dict(relation) for relation in relations]})
    return grouped


def _read_method_media_manifest(raw: bytes, path: Path) -> tuple[list[Mapping[str, Any]], Mapping[str, Any]]:
    text = raw.decode("utf-8")
    if path.suffix.casefold() == ".jsonl":
        records: list[Mapping[str, Any]] = []
        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                raise MethodArtifactError(f"media manifest JSONL line {line_number} is blank")
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise MethodArtifactError(f"media manifest JSONL line {line_number} is malformed") from exc
            if not isinstance(record, Mapping):
                raise MethodArtifactError(f"media manifest JSONL line {line_number} must be an object")
            if "records" in record:
                raise MethodArtifactError(f"media manifest JSONL line {line_number} cannot be a wrapped records object")
            records.append(record)
        return records, {}
    decoded = json.loads(text)
    records = decoded.get("records") if isinstance(decoded, Mapping) else decoded
    if not isinstance(records, list):
        raise MethodArtifactError("media manifest must be a JSON list or contain a records list")
    if not all(isinstance(record, Mapping) for record in records):
        raise MethodArtifactError("media manifest records must be objects")
    return list(records), decoded if isinstance(decoded, Mapping) else {}


def _approved_media_annotation(
    record: Mapping[str, Any], relation: Mapping[str, Any]
) -> tuple[dict[str, Any] | None, list[str], dict[str, Any] | None]:
    failures: list[str] = []
    fetch_status = record.get("fetch_status")
    digest = record.get("sha256")
    unavailable = _terminal_unavailable_fetch(record, relation)
    if unavailable is not None:
        return None, failures, unavailable
    if fetch_status != "ok":
        failures.append(f"fetch_{fetch_status}" if isinstance(fetch_status, str) and fetch_status else "fetch_missing")
    if fetch_status == "ok" and (not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None):
        raise MethodArtifactError("media source SHA mismatch")
    ocr = _optional_mapping(record.get("ocr"), "media OCR")
    vision = _optional_mapping(record.get("vision_review"), "media vision review")
    _assert_stage_provenance(ocr, digest, "OCR")
    _assert_stage_provenance(vision, digest, "vision")
    parts: list[str] = []
    ocr_approved = False
    if ocr is None:
        failures.append("ocr_missing")
    elif ocr.get("status") == "complete" and _audit_status(ocr) == "approved" and ocr.get("claim_status") == "insufficient":
        pass
    elif ocr.get("status") == "complete" and _audit_status(ocr) == "approved":
        if isinstance(ocr.get("text"), str) and ocr["text"].strip():
            parts.append(ocr["text"].strip())
            ocr_approved = True
        else:
            failures.append("ocr_empty")
    else:
        failures.append(_stage_failure("ocr", ocr))
    vision_approved = False
    if vision is None:
        failures.append("vision_missing")
    elif vision.get("status") == "not_required" and ocr_approved:
        pass
    elif vision.get("status") == "complete" and _audit_status(vision) == "approved":
        vision_parts: list[str] = []
        labels = vision.get("labels")
        if isinstance(labels, list) and all(isinstance(label, str) and label.strip() for label in labels) and labels:
            vision_parts.append(f"Review labels: {', '.join(label.strip() for label in labels)}")
        explanation = vision.get("claim_explanation")
        if isinstance(explanation, str) and explanation.strip():
            vision_parts.append(explanation.strip())
        caveat = vision.get("caveat")
        if isinstance(caveat, str) and caveat.strip():
            vision_parts.append(caveat.strip())
        parts.extend(vision_parts)
        vision_approved = bool(vision_parts)
        if not vision_approved:
            failures.append("vision_empty")
    else:
        failures.append(_stage_failure("vision", vision))
    if fetch_status != "ok" or not isinstance(digest, str) or not (ocr_approved or vision_approved):
        return None, failures, None
    # OCR and vision are alternative approved evidence paths. A rejected or
    # unavailable non-winning path must not turn an otherwise complete relation
    # into a full-audit blocker.
    failures = []
    return (
        {
            "source_row_id": relation["source_row_id"],
            "source_type": relation["source_type"],
            "media_id": f"media-{_hash({'source_row_id': relation['source_row_id'], 'media_index': relation['media_index']})[:20]}",
            "media_source_sha256": digest,
            "text": "\n".join(parts),
            "relation_provenance": {
                "media_index": relation["media_index"],
                "manifest_record_hash": _hash(record),
            },
            **({"ticker": relation["ticker"]} if relation.get("ticker") else {}),
        },
        failures,
        None,
    )


def _terminal_unavailable_fetch(record: Mapping[str, Any], relation: Mapping[str, Any]) -> dict[str, Any] | None:
    """Classify a recorded HTTP 404 as terminal absence, never a missing derivative."""

    if record.get("fetch_status") != "failed":
        return None
    reason = record.get("error")
    fetched_at = record.get("fetched_at")
    if not isinstance(reason, str) or "404" not in reason or not isinstance(fetched_at, str) or not fetched_at.strip():
        return None
    return {
        "source_row_id": relation["source_row_id"],
        "media_index": relation["media_index"],
        "status": "unavailable_fetch",
        "reason": reason,
        "provenance": {"fetch_status": "failed", "fetched_at": fetched_at},
    }


def _optional_mapping(value: Any, label: str) -> Mapping[str, Any] | None:
    if value is None:
        return None
    return _require_mapping(value, label)


def _assert_stage_provenance(stage: Mapping[str, Any] | None, digest: Any, label: str) -> None:
    if stage is None or stage.get("source_sha256") is None:
        return
    if not isinstance(digest, str) or stage.get("source_sha256") != digest:
        raise MethodArtifactError(f"media {label} provenance mismatch")


def _audit_status(stage: Mapping[str, Any]) -> str | None:
    audit = stage.get("audit")
    return audit.get("status") if isinstance(audit, Mapping) and isinstance(audit.get("status"), str) else None


def _stage_failure(prefix: str, stage: Mapping[str, Any]) -> str:
    status = stage.get("status")
    if status == "complete" and _audit_status(stage) != "approved":
        return f"{prefix}_unapproved"
    return f"{prefix}_{status}" if isinstance(status, str) and status else f"{prefix}_missing"


def _count_failure(failures: dict[str, int], category: str) -> None:
    failures[category] = failures.get(category, 0) + 1


def _representative_ticker(raw_tickers: Any) -> str | None:
    if raw_tickers is None:
        return None
    try:
        tickers = json.loads(raw_tickers) if isinstance(raw_tickers, str) else raw_tickers
    except (TypeError, json.JSONDecodeError) as exc:
        raise MethodArtifactError("tweets.tickers must be a JSON list") from exc
    if not isinstance(tickers, list):
        raise MethodArtifactError("tweets.tickers must be a JSON list")
    for ticker in tickers:
        if isinstance(ticker, str) and ticker.strip():
            return ticker.strip().upper()
    return None


def write_blind_packets(chunks: Mapping[str, Any], *, packet_dir: Path, batch_size: int) -> dict[str, Any]:
    """Split an already blinded packet into deterministic, hash-listed coder packets."""

    _validate_chunks(chunks)
    if batch_size <= 0:
        raise MethodArtifactError("batch_size must be greater than zero")
    packet_dir = Path(packet_dir)
    records: list[dict[str, Any]] = []
    text_entries = [chunk for chunk in chunks["chunks"] if chunk["kind"] == "text"]
    media_entries = [chunk for chunk in chunks["chunks"] if chunk["kind"] == "media"]
    packet_entries = [
        *[text_entries[offset : offset + batch_size] for offset in range(0, len(text_entries), batch_size)],
        *[media_entries[offset : offset + batch_size] for offset in range(0, len(media_entries), batch_size)],
    ]
    for ordinal, batch in enumerate(packet_entries, start=1):
        name = f"packet-{ordinal:03d}.json"
        packet: dict[str, Any] = {
            "format": "serenity-method-blind-packet/1",
            "leak_policy": _LEAK_POLICY,
            "source_index_hash": (
                chunks.get("text_source_index_hash", chunks["source_index_hash"])
                if all(chunk["kind"] == "text" for chunk in batch)
                else chunks["source_index_hash"]
            ),
            "chunks": batch,
        }
        packet["content_hash"] = _document_hash(packet)
        atomic_write_json(packet_dir / name, packet)
        records.append(
            {
                "packet_id": f"packet-{ordinal:03d}",
                "path": name,
                "content_hash": packet["content_hash"],
                "chunk_ids": [chunk["chunk_id"] for chunk in packet["chunks"]],
                "count": len(packet["chunks"]),
            }
        )
    manifest: dict[str, Any] = {
        "format": "serenity-method-packet-manifest/1",
        "source_chunks_hash": chunks["content_hash"],
        "source_index_hash": chunks["source_index_hash"],
        "batch_size": batch_size,
        "packets": records,
    }
    if isinstance(chunks.get("media_derivatives"), Mapping):
        manifest["media_derivatives"] = json.loads(canonical_json(chunks["media_derivatives"]))
    manifest["content_hash"] = _document_hash(manifest)
    atomic_write_json(packet_dir / "packet-manifest.json", manifest)
    return manifest
