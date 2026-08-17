"""Corpus inventory and media provenance for the v2 method corpus.

This module deliberately records corpus material as research-method evidence. It does
not interpret tweet text or turn it into an investment conclusion.
"""

from __future__ import annotations

import json
import sqlite3
import hashlib
import os
import shlex
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator


CORPUS_SCAN_QUERY = "SELECT id, type, media FROM tweets ORDER BY id"


class CorpusError(Exception):
    """A stable command error for an unreadable or malformed corpus."""

    def __init__(self, code: str, message: str, exit_code: int = 2) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


@dataclass(frozen=True)
class MediaReference:
    tweet_id: str
    url: str
    media_index: int

    @property
    def key(self) -> tuple[str, str, int]:
        return (self.tweet_id, self.url, self.media_index)


@dataclass(frozen=True)
class CorpusScan:
    tweet_count: int
    tweet_types: dict[str, int]
    media_references: tuple[MediaReference, ...]
    tweets_with_media: int
    invalid_media_rows: int
    invalid_media_references: int
    database_sha256: str
    sqlite_user_version: int

    def inventory(self) -> dict[str, Any]:
        return {
            "tweet_count": self.tweet_count,
            "tweet_types": self.tweet_types,
            "tweets_with_media": self.tweets_with_media,
            "media_reference_count": len(self.media_references),
            "unique_media_url_count": len({reference.url for reference in self.media_references}),
            "invalid_media_rows": self.invalid_media_rows,
            "invalid_media_references": self.invalid_media_references,
            "source": {
                "database_sha256": self.database_sha256,
                "query": CORPUS_SCAN_QUERY,
                "sqlite_user_version": self.sqlite_user_version,
            },
        }


def scan_corpus(database: Path) -> CorpusScan:
    """Read the corpus's public tweet columns without treating content as a verdict."""
    if not database.is_file():
        raise CorpusError("corpus_unavailable", f"SQLite database not found: {database}", 3)

    try:
        database_sha256 = hashlib.sha256(database.read_bytes()).hexdigest()
    except OSError as exc:
        raise CorpusError("corpus_unavailable", f"SQLite database cannot be read: {database}", 3) from exc

    try:
        connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        raise CorpusError("corpus_unavailable", f"SQLite database cannot be opened: {database}", 3) from exc

    try:
        rows = connection.execute(CORPUS_SCAN_QUERY).fetchall()
        sqlite_user_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    except sqlite3.Error as exc:
        raise CorpusError("corpus_unavailable", "SQLite database does not expose a tweets table", 3) from exc
    finally:
        connection.close()

    try:
        scanned_sha256 = hashlib.sha256(database.read_bytes()).hexdigest()
    except OSError as exc:
        raise CorpusError("corpus_unavailable", f"SQLite database cannot be re-read: {database}", 3) from exc
    if scanned_sha256 != database_sha256:
        raise CorpusError("corpus_unavailable", "SQLite database changed during the corpus scan", 3)

    tweet_types: Counter[str] = Counter()
    references: list[MediaReference] = []
    tweets_with_media = 0
    invalid_media_rows = 0
    invalid_media_references = 0

    for tweet_id, tweet_type, raw_media in rows:
        tweet_types[str(tweet_type)] += 1
        parsed_media, row_invalid = _parse_media(raw_media)
        if row_invalid:
            invalid_media_rows += 1
            continue

        valid_reference_in_row = False
        for media_index, item in enumerate(parsed_media):
            url = _media_url(item)
            if url is None:
                invalid_media_references += 1
                continue
            references.append(MediaReference(tweet_id=str(tweet_id), url=url, media_index=media_index))
            valid_reference_in_row = True
        if valid_reference_in_row:
            tweets_with_media += 1

    return CorpusScan(
        tweet_count=len(rows),
        tweet_types=dict(sorted(tweet_types.items())),
        media_references=tuple(references),
        tweets_with_media=tweets_with_media,
        invalid_media_rows=invalid_media_rows,
        invalid_media_references=invalid_media_references,
        database_sha256=database_sha256,
        sqlite_user_version=sqlite_user_version,
    )


def _parse_media(raw_media: Any) -> tuple[list[Any], bool]:
    if raw_media is None or raw_media == "":
        return [], False
    try:
        parsed = json.loads(raw_media) if isinstance(raw_media, str) else raw_media
    except (TypeError, json.JSONDecodeError):
        return [], True
    if parsed is None:
        return [], False
    if isinstance(parsed, list):
        return parsed, False
    return [], True


def _media_url(item: Any) -> str | None:
    candidate: Any
    if isinstance(item, str):
        candidate = item
    elif isinstance(item, dict):
        candidate = item.get("url") or item.get("media_url") or item.get("media_url_https")
    else:
        return None
    if not isinstance(candidate, str):
        return None
    url = candidate.strip()
    return url if url.startswith(("http://", "https://")) else None


def expected_reference_keys(references: Iterable[MediaReference]) -> set[tuple[str, str, int]]:
    return {reference.key for reference in references}


def build_review_packets(
    database: Path, manifest_path: Path, cache_root: Path, packet_dir: Path, *, batch_size: int
) -> dict[str, Any]:
    """Build deterministic, review-only packets for each fetched raw-media hash."""
    if batch_size <= 0:
        raise CorpusError("usage_or_schema", "--batch-size must be greater than zero", 2)
    records_with_lines, invalid = _read_manifest(manifest_path)
    if invalid:
        raise CorpusError("usage_or_schema", "media manifest has invalid records", 2)
    if packet_dir.exists() and any(packet_dir.iterdir()):
        raise CorpusError("persistence_conflict", f"packet directory must be empty: {packet_dir}", 5)
    context_by_tweet = _tweet_context_by_id(database)
    records = [record for _line, record in records_with_lines]
    by_digest: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if record.get("fetch_status") != "ok":
            continue
        digest = record.get("sha256")
        relation = _record_relation(record)
        if not isinstance(digest, str) or relation is None or not _cached_hash_matches(cache_root, digest):
            raise CorpusError("corpus_unavailable", "fetched media is missing a valid source hash, relation, or cache object", 3)
        if relation["tweet_id"] not in context_by_tweet:
            raise CorpusError("corpus_unavailable", f"tweet context is unavailable for {relation['tweet_id']}", 3)
        by_digest.setdefault(digest, []).append(record)

    packet_dir.mkdir(parents=True, exist_ok=True)
    packets: list[dict[str, Any]] = []
    source_digests = sorted(by_digest)
    for offset in range(0, len(source_digests), batch_size):
        digests = source_digests[offset : offset + batch_size]
        packet_id = f"media-review-{offset // batch_size + 1:04d}"
        packet = {
            "schema_id": "urn:serenity:media-review-packet:1",
            "packet_id": packet_id,
            "items": [_review_packet_item(digest, by_digest[digest], cache_root, context_by_tweet) for digest in digests],
        }
        filename = f"{packet_id}.json"
        packet_path = packet_dir / filename
        _write_packet_json(packet_path, packet)
        packets.append(
            {
                "packet_id": packet_id,
                "file": filename,
                "sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
                "item_count": len(digests),
                "source_sha256s": digests,
            }
        )
    packet_manifest = {
        "schema_id": "urn:serenity:media-review-packet-manifest:1",
        "source_manifest": str(manifest_path),
        "source_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "unique_sources": len(source_digests),
        "relations": sum(len(source_records) for source_records in by_digest.values()),
        "packet_count": len(packets),
        "packets": packets,
    }
    _write_packet_json(packet_dir / "packet-manifest.json", packet_manifest)
    return {
        "packet_dir": str(packet_dir),
        "packet_manifest": str(packet_dir / "packet-manifest.json"),
        "unique_sources": len(source_digests),
        "relations": sum(len(source_records) for source_records in by_digest.values()),
        "packet_count": len(packets),
        "batch_size": batch_size,
    }


def _tweet_context_by_id(database: Path) -> dict[str, dict[str, str | None]]:
    if not database.is_file():
        raise CorpusError("corpus_unavailable", f"SQLite database not found: {database}", 3)
    try:
        connection = sqlite3.connect(f"file:{database.resolve()}?mode=ro", uri=True)
        rows = connection.execute("SELECT id, type, content FROM tweets").fetchall()
    except sqlite3.Error as exc:
        raise CorpusError("corpus_unavailable", "SQLite database does not expose tweet context columns", 3) from exc
    finally:
        if "connection" in locals():
            connection.close()
    return {
        str(tweet_id): {"type": str(tweet_type), "content": content if isinstance(content, str) else None}
        for tweet_id, tweet_type, content in rows
    }


def _record_relation(record: dict[str, Any]) -> dict[str, str | int] | None:
    key = _record_key(record)
    if key is None:
        return None
    tweet_id, url, media_index = key
    return {"tweet_id": tweet_id, "url": url, "media_index": media_index}


def _review_packet_item(
    digest: str, source_records: list[dict[str, Any]], cache_root: Path, context_by_tweet: dict[str, dict[str, str | None]]
) -> dict[str, Any]:
    relations: list[dict[str, Any]] = []
    for record in source_records:
        relation = _record_relation(record)
        assert relation is not None
        relations.append({**relation, "tweet_context": context_by_tweet[relation["tweet_id"]]})
    first = source_records[0]
    ocr = _nested_stage(first, "ocr") or {}
    return {
        "source_sha256": digest,
        "review_input_sha256": _review_input_sha256(digest, relations),
        "cache_path": str(cache_root / digest),
        "mime": first.get("mime"),
        "dimensions": first.get("dimensions"),
        "ocr": {"text": ocr.get("text"), "confidence": ocr.get("confidence")},
        "relations": relations,
    }


def _review_input_sha256(digest: str, relations: list[dict[str, Any]]) -> str:
    core_relations = [
        {"tweet_id": relation["tweet_id"], "url": relation["url"], "media_index": relation["media_index"]}
        for relation in relations
    ]
    return hashlib.sha256(_canonical_json({"source_sha256": digest, "relations": core_relations}).encode("utf-8")).hexdigest()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_packet_json(path: Path, value: dict[str, Any]) -> None:
    try:
        path.write_text(_canonical_json(value) + "\n", encoding="utf-8")
    except OSError as exc:
        raise CorpusError("persistence_conflict", f"review packet cannot be written: {path}", 5) from exc


def apply_reviews(
    manifest_path: Path,
    reviews_dir: Path,
    *,
    reviewer_model: str,
    prompt_version: str,
    require_complete: bool,
) -> dict[str, Any]:
    """Validate an entire review batch before atomically fanning it into the manifest."""
    if not reviews_dir.is_dir():
        raise CorpusError("corpus_unavailable", f"reviews directory not found: {reviews_dir}", 3)
    records_with_lines, invalid = _read_manifest(manifest_path)
    if invalid:
        raise CorpusError("usage_or_schema", "media manifest has invalid records", 2)
    records = [dict(record) for _line, record in records_with_lines]
    expected = _reviewable_relations_by_digest(records)
    outputs = _load_review_outputs(reviews_dir)
    reviewed: dict[str, dict[str, Any]] = {}
    for path, output in outputs:
        _validate_review_output(output, path, expected, reviewer_model, prompt_version)
        digest = output["source_sha256"]
        if digest in reviewed:
            raise CorpusError("usage_or_schema", f"duplicate or conflicting review result for source SHA: {digest}", 2)
        reviewed[digest] = output
    missing = sorted(set(expected) - set(reviewed))
    if require_complete and missing:
        raise CorpusError("review_incomplete", f"review results are missing {len(missing)} fetch-ok source SHA values", 4)

    applied_relations = 0
    for digest, output in reviewed.items():
        reviewed_at = _utc_now()
        for index in expected[digest]["indices"]:
            _apply_review_to_record(records[index], output, reviewer_model, prompt_version, reviewed_at)
            applied_relations += 1
    _write_manifest(manifest_path, records)
    return {
        "unique_sources": len(expected),
        "relations": sum(len(value["indices"]) for value in expected.values()),
        "applied_sources": len(reviewed),
        "applied_relations": applied_relations,
    }


def _reviewable_relations_by_digest(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    expected: dict[str, dict[str, Any]] = {}
    for index, record in enumerate(records):
        if record.get("fetch_status") != "ok":
            continue
        digest = record.get("sha256")
        relation = _record_relation(record)
        if not isinstance(digest, str) or relation is None:
            raise CorpusError("usage_or_schema", "fetch-ok media requires a source SHA and exact relation", 2)
        source = expected.setdefault(digest, {"indices": [], "relations": []})
        source["indices"].append(index)
        source["relations"].append(relation)
    return expected


def _load_review_outputs(reviews_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    outputs: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(reviews_dir.glob("*.json")):
        try:
            decoded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CorpusError("usage_or_schema", f"review result is not valid JSON: {path}", 2) from exc
        if not isinstance(decoded, dict):
            raise CorpusError("usage_or_schema", f"review result is not an object: {path}", 2)
        outputs.append((path, decoded))
    return outputs


@lru_cache(maxsize=1)
def _review_output_validator() -> Draft202012Validator:
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "media-review-output.schema.json"
    return Draft202012Validator(json.loads(schema_path.read_text(encoding="utf-8")))


def _validate_review_output(
    output: dict[str, Any], path: Path, expected: dict[str, dict[str, Any]], reviewer_model: str, prompt_version: str
) -> None:
    errors = sorted(_review_output_validator().iter_errors(output), key=lambda error: list(error.absolute_path))
    if errors:
        location = ".".join(str(part) for part in errors[0].absolute_path) or "$"
        raise CorpusError("usage_or_schema", f"review result schema invalid at {path}:{location}: {errors[0].message}", 2)
    digest = output["source_sha256"]
    if digest not in expected:
        raise CorpusError("usage_or_schema", f"review result is out of scope for source SHA: {digest}", 2)
    expected_relations = expected[digest]["relations"]
    if output["relations"] != expected_relations:
        raise CorpusError("usage_or_schema", f"review result relations do not exactly match source SHA: {digest}", 2)
    if output["review_input_sha256"] != _review_input_sha256(digest, expected_relations):
        raise CorpusError("usage_or_schema", f"review result hash does not match source relations: {digest}", 2)
    if output["reviewer_model"] != reviewer_model or output["prompt_version"] != prompt_version:
        raise CorpusError("usage_or_schema", f"reviewer model or prompt version does not match apply command: {path}", 2)


def _apply_review_to_record(
    record: dict[str, Any], output: dict[str, Any], reviewer_model: str, prompt_version: str, reviewed_at: str
) -> None:
    ocr = _nested_stage(record, "ocr")
    if ocr is None or ocr.get("source_sha256") != output["source_sha256"]:
        raise CorpusError("usage_or_schema", f"review cannot replace missing or mismatched OCR provenance: {output['source_sha256']}", 2)
    reviewer = output["reviewer_id"]
    ocr["claim_status"] = output["ocr"]["claim_status"]
    ocr["audit"] = {"status": output["ocr"]["disposition"], "reviewer": reviewer}
    record["ocr"] = ocr
    vision = output["vision"]
    if vision["disposition"] == "not_required":
        record["vision_review"] = _not_required_vision(output["source_sha256"])
        record["vision_review"]["audit"] = {"status": "approved", "reviewer": reviewer}
    else:
        record["vision_review"] = {
            "status": vision["disposition"],
            "labels": vision["labels"],
            "summary": vision["summary"],
            "supported_claims": vision["supported_claims"],
            "model": {"name": "visual-review", "version": reviewer_model},
            "prompt_template_version": prompt_version,
            "source_sha256": output["source_sha256"],
            "confidence": vision["confidence"],
            "caveat": None,
            "extracted_at": reviewed_at,
            "audit": {"status": "approved" if vision["disposition"] == "complete" else "needs_reconciliation", "reviewer": reviewer},
            "error": None if vision["disposition"] == "complete" else "visual review failed",
        }
    _sync_legacy_stage_fields(record)


def ingest_media(
    database: Path,
    manifest_path: Path,
    cache_root: Path,
    *,
    retries: int,
    timeout_seconds: float,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    """Fetch corpus media into a content-addressed cache and write only metadata."""
    if retries < 0:
        raise CorpusError("usage_or_schema", "--retries must be zero or greater", 2)
    if timeout_seconds <= 0:
        raise CorpusError("usage_or_schema", "--timeout-seconds must be greater than zero", 2)

    scan = scan_corpus(database)
    checkpoint = checkpoint_path or manifest_path.with_name(f"{manifest_path.name}.checkpoint.json")
    existing_by_key = _existing_records_by_key(manifest_path)
    results_by_url: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    resumed_references = 0
    for processed_records, reference in enumerate(scan.media_references, start=1):
        existing = existing_by_key.get(reference.key)
        if existing is not None and _record_cache_is_valid(existing, cache_root):
            record = dict(existing)
            record.update({"tweet_id": reference.tweet_id, "url": reference.url, "media_index": reference.media_index})
            results_by_url.setdefault(reference.url, _media_fields(record))
            resumed_references += 1
        else:
            result = results_by_url.get(reference.url)
            if result is None:
                result = _fetch_one(reference.url, cache_root, retries=retries, timeout_seconds=timeout_seconds)
                results_by_url[reference.url] = result
            record = {"tweet_id": reference.tweet_id, "url": reference.url, "media_index": reference.media_index, **result}
        records.append(record)
        _write_manifest(manifest_path, records)
        _write_ingest_checkpoint(checkpoint, manifest_path, len(scan.media_references), processed_records)

    if not records:
        _write_manifest(manifest_path, records)
        _write_ingest_checkpoint(checkpoint, manifest_path, 0, 0)
    fetched_references = sum(record["fetch_status"] == "ok" for record in records) - resumed_references
    return {
        "expected_references": len(scan.media_references),
        "unique_urls": len(results_by_url),
        "fetched_references": fetched_references,
        "failed_references": sum(record["fetch_status"] != "ok" for record in records),
        "resumed_references": resumed_references,
        "manifest": str(manifest_path),
        "cache_root": str(cache_root),
        "checkpoint": str(checkpoint),
        "invalid_media_rows": scan.invalid_media_rows,
        "invalid_media_references": scan.invalid_media_references,
    }


def _existing_records_by_key(path: Path) -> dict[tuple[str, str, int], dict[str, Any]]:
    if not path.exists():
        return {}
    records, invalid = _read_manifest(path)
    if invalid:
        raise CorpusError("persistence_conflict", f"existing manifest has invalid records: {path}", 5)
    existing: dict[tuple[str, str, int], dict[str, Any]] = {}
    for _line, record in records:
        key = _record_key(record)
        if key is None or key in existing:
            raise CorpusError("persistence_conflict", f"existing manifest has conflicting record identity: {path}", 5)
        existing[key] = record
    return existing


def _record_cache_is_valid(record: dict[str, Any], cache_root: Path) -> bool:
    digest = record.get("sha256")
    return record.get("fetch_status") == "ok" and isinstance(digest, str) and _cached_hash_matches(cache_root, digest)


def _media_fields(record: dict[str, Any]) -> dict[str, Any]:
    excluded = {"tweet_id", "url", "media_index"}
    return {name: value for name, value in record.items() if name not in excluded}


def _write_ingest_checkpoint(path: Path, manifest_path: Path, record_count: int, processed_records: int) -> None:
    _write_json(
        path,
        {
            "schema_id": "urn:serenity:corpus-media-checkpoint:1",
            "manifest": str(manifest_path),
            "record_count": record_count,
            "processed_records": processed_records,
            "completed_records": processed_records,
            "pending_records": record_count - processed_records,
            "complete": processed_records == record_count,
            "updated_at": _utc_now(),
        },
    )


def extract_media(
    manifest_path: Path,
    cache_root: Path,
    *,
    ocr_command: str | None,
    vision_command: str | None,
    checkpoint_path: Path | None = None,
    timeout_seconds: float = 60.0,
    max_workers: int = 1,
) -> dict[str, Any]:
    """Enrich downloaded media through injected OCR and visual-review boundaries."""
    if timeout_seconds <= 0:
        raise CorpusError("usage_or_schema", "--timeout-seconds must be greater than zero", 2)
    if max_workers <= 0:
        raise CorpusError("usage_or_schema", "--max-workers must be greater than zero", 2)
    records_with_lines, invalid = _read_manifest(manifest_path)
    if invalid:
        raise CorpusError("usage_or_schema", "media manifest has invalid records; audit and reconcile it before extraction", 2)

    records = [dict(record) for _line, record in records_with_lines]
    checkpoint = checkpoint_path or manifest_path.with_name(f"{manifest_path.name}.checkpoint.json")
    valid_by_digest = _valid_record_indices_by_digest(records, cache_root)
    ocr_stages, ocr_pending, resumed_ocr_sources = _plan_stage_sources(
        records, valid_by_digest, "ocr", ocr_command, _not_requested_ocr
    )
    for batch_results in _run_source_batches(ocr_pending, max_workers, lambda digest: _run_ocr(ocr_command, cache_root / digest, digest, timeout_seconds)):
        ocr_stages.update(batch_results)
        _apply_stage(records, valid_by_digest, "ocr", ocr_stages)
        _write_manifest(manifest_path, records)
        _write_checkpoint(checkpoint, manifest_path, records, _staged_record_count(records))
    _apply_stage(records, valid_by_digest, "ocr", ocr_stages)

    vision_stages, vision_pending, resumed_vision_sources = _plan_vision_sources(
        records, valid_by_digest, vision_command
    )
    for batch_results in _run_source_batches(vision_pending, max_workers, lambda digest: _run_vision(vision_command, cache_root / digest, digest, timeout_seconds)):
        vision_stages.update(batch_results)
        _apply_stage(records, valid_by_digest, "vision_review", vision_stages)
        _sync_legacy_stages(records, valid_by_digest)
        _write_manifest(manifest_path, records)
        _write_checkpoint(checkpoint, manifest_path, records, _staged_record_count(records))
    _apply_stage(records, valid_by_digest, "vision_review", vision_stages)
    _sync_legacy_stages(records, valid_by_digest)
    _write_manifest(manifest_path, records)
    _write_checkpoint(checkpoint, manifest_path, records, len(records))

    return {
        "manifest": str(manifest_path),
        "checkpoint": str(checkpoint),
        "record_count": len(records),
        "ocr_unique_sources_executed": len(ocr_pending),
        "vision_unique_sources_executed": len(vision_pending),
        "resumed_ocr_records": sum(len(valid_by_digest[digest]) for digest in resumed_ocr_sources) + sum(len(indices) - 1 for digest, indices in valid_by_digest.items() if digest in ocr_pending),
        "resumed_vision_records": sum(len(valid_by_digest[digest]) for digest in resumed_vision_sources) + sum(len(indices) - 1 for digest, indices in valid_by_digest.items() if digest in vision_pending),
    }


def _valid_record_indices_by_digest(records: list[dict[str, Any]], cache_root: Path) -> dict[str, list[int]]:
    valid: dict[str, list[int]] = {}
    for index, record in enumerate(records):
        digest = record.get("sha256")
        if record.get("fetch_status") == "ok" and isinstance(digest, str) and _cached_hash_matches(cache_root, digest):
            valid.setdefault(digest, []).append(index)
    return valid


def _plan_stage_sources(
    records: list[dict[str, Any]],
    indices_by_digest: dict[str, list[int]],
    stage_name: str,
    command: str | None,
    not_requested: Callable[[str], dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], list[str], set[str]]:
    stages: dict[str, dict[str, Any]] = {}
    pending: list[str] = []
    resumed: set[str] = set()
    for digest, indices in indices_by_digest.items():
        current = next(
            (stage for index in indices if _stage_is_current(stage := _nested_stage(records[index], stage_name), digest)),
            None,
        )
        if current is not None:
            stages[digest] = current
            resumed.add(digest)
        elif command is None:
            stages[digest] = not_requested(digest)
        else:
            pending.append(digest)
    return stages, pending, resumed


def _plan_vision_sources(
    records: list[dict[str, Any]], indices_by_digest: dict[str, list[int]], vision_command: str | None
) -> tuple[dict[str, dict[str, Any]], list[str], set[str]]:
    stages: dict[str, dict[str, Any]] = {}
    pending: list[str] = []
    resumed: set[str] = set()
    for digest, indices in indices_by_digest.items():
        ocr = _nested_stage(records[indices[0]], "ocr")
        if ocr is not None and ocr.get("claim_status") == "established":
            stages[digest] = _not_required_vision(digest)
            continue
        current = next(
            (stage for index in indices if _stage_is_current(stage := _nested_stage(records[index], "vision_review"), digest)),
            None,
        )
        if current is not None:
            stages[digest] = current
            resumed.add(digest)
        elif vision_command is None:
            stages[digest] = _not_requested_vision(digest)
        else:
            pending.append(digest)
    return stages, pending, resumed


def _run_source_batches(
    pending: list[str], max_workers: int, run_source: Callable[[str], dict[str, Any]]
) -> Iterable[dict[str, dict[str, Any]]]:
    for start in range(0, len(pending), max_workers):
        batch = pending[start : start + max_workers]
        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            futures = {executor.submit(run_source, digest): digest for digest in batch}
            completed: dict[str, dict[str, Any]] = {}
            for future in as_completed(futures):
                completed[futures[future]] = future.result()
        yield completed


def _apply_stage(
    records: list[dict[str, Any]], indices_by_digest: dict[str, list[int]], stage_name: str, stages: dict[str, dict[str, Any]]
) -> None:
    for digest, indices in indices_by_digest.items():
        stage = stages.get(digest)
        if stage is None:
            continue
        for index in indices:
            records[index][stage_name] = dict(stage)


def _sync_legacy_stages(records: list[dict[str, Any]], indices_by_digest: dict[str, list[int]]) -> None:
    for indices in indices_by_digest.values():
        for index in indices:
            record = records[index]
            if isinstance(record.get("ocr"), dict) and isinstance(record.get("vision_review"), dict):
                _sync_legacy_stage_fields(record)


def _staged_record_count(records: list[dict[str, Any]]) -> int:
    return sum(record.get("fetch_status") != "ok" or "ocr" in record for record in records)


def _nested_stage(record: dict[str, Any], name: str) -> dict[str, Any] | None:
    stage = record.get(name)
    return dict(stage) if isinstance(stage, dict) else None


def _stage_is_current(stage: dict[str, Any] | None, digest: str) -> bool:
    return bool(stage and stage.get("source_sha256") == digest and stage.get("status") in {"complete", "not_required", "not_applicable"})


def _not_requested_ocr(digest: str) -> dict[str, Any]:
    return {
        "status": "not_requested",
        "text": None,
        "extractor": {"name": None, "version": None},
        "source_sha256": digest,
        "confidence": None,
        "caveat": "no OCR command was supplied",
        "claim_status": "unknown",
        "extracted_at": None,
        "audit": {"status": "not_requested", "reviewer": None},
        "error": None,
    }


def _not_requested_vision(digest: str) -> dict[str, Any]:
    return {
        "status": "not_requested",
        "labels": [],
        "summary": None,
        "supported_claims": [],
        "model": {"name": None, "version": None},
        "prompt_template_version": None,
        "source_sha256": digest,
        "confidence": None,
        "caveat": "no vision command was supplied",
        "extracted_at": None,
        "audit": {"status": "not_requested", "reviewer": None},
        "error": None,
    }


def _not_required_vision(digest: str) -> dict[str, Any]:
    return {
        "status": "not_required",
        "labels": [],
        "summary": None,
        "supported_claims": [],
        "model": {"name": None, "version": None},
        "prompt_template_version": None,
        "source_sha256": digest,
        "confidence": None,
        "caveat": "OCR extractor marked the claim established",
        "extracted_at": None,
        "audit": {"status": "not_required", "reviewer": None},
        "error": None,
    }


def _run_ocr(command: str, cache_file: Path, digest: str, timeout_seconds: float) -> dict[str, Any]:
    response, error = _run_extractor(command, cache_file, digest, timeout_seconds)
    extracted_at = _utc_now()
    if error is not None:
        return _failed_ocr(digest, extracted_at, error)
    try:
        if response.get("status") == "failed":
            return {
                "status": "failed",
                "text": _optional_string(response, "text"),
                "extractor": _named_version(response, "extractor"),
                "source_sha256": digest,
                "confidence": _confidence(response),
                "caveat": _optional_string(response, "caveat"),
                "claim_status": response.get("claim_status") if isinstance(response.get("claim_status"), str) else "unknown",
                "extracted_at": extracted_at,
                "audit": _audit(response),
                "error": _required_string(response, "error"),
            }
        status = _extract_status(response)
        extractor = _named_version(response, "extractor")
        text = _optional_string(response, "text")
        claim_status = response.get("claim_status")
        if claim_status not in {"established", "insufficient", "not_applicable"}:
            raise ValueError("claim_status must be established, insufficient, or not_applicable")
        return {
            "status": status,
            "text": text,
            "extractor": extractor,
            "source_sha256": digest,
            "confidence": _confidence(response),
            "caveat": _optional_string(response, "caveat"),
            "claim_status": claim_status,
            "extracted_at": extracted_at,
            "audit": _audit(response),
            "error": None,
        }
    except ValueError as exc:
        return _failed_ocr(digest, extracted_at, f"invalid OCR extractor response: {exc}")


def _run_vision(command: str, cache_file: Path, digest: str, timeout_seconds: float) -> dict[str, Any]:
    response, error = _run_extractor(command, cache_file, digest, timeout_seconds)
    extracted_at = _utc_now()
    if error is not None:
        return _failed_vision(digest, extracted_at, error)
    try:
        labels = response.get("labels")
        if not isinstance(labels, list) or not all(isinstance(label, str) and label for label in labels):
            raise ValueError("labels must be a list of non-empty strings")
        prompt_template_version = _required_string(response, "prompt_template_version")
        return {
            "status": _extract_status(response),
            "labels": labels,
            "summary": _required_string(response, "summary"),
            "supported_claims": _supported_claims(response),
            "model": _named_version(response, "model"),
            "prompt_template_version": prompt_template_version,
            "source_sha256": digest,
            "confidence": _confidence(response),
            "caveat": _optional_string(response, "caveat"),
            "extracted_at": extracted_at,
            "audit": _audit(response),
            "error": None,
        }
    except ValueError as exc:
        return _failed_vision(digest, extracted_at, f"invalid vision extractor response: {exc}")


def _run_extractor(command: str, cache_file: Path, digest: str, timeout_seconds: float) -> tuple[dict[str, Any], str | None]:
    try:
        arguments = [argument.format(input=str(cache_file), source_sha256=digest) for argument in shlex.split(command)]
        if not arguments:
            raise ValueError("command is empty")
        completed = subprocess.run(arguments, check=False, capture_output=True, text=True, timeout=timeout_seconds)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {}, f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip() or completed.stdout.strip()
        return {}, f"extractor exited {completed.returncode}: {diagnostic}"
    try:
        response = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {}, f"extractor did not emit one JSON object: {exc.msg}"
    if not isinstance(response, dict):
        return {}, "extractor did not emit a JSON object"
    return response, None


def _extract_status(response: dict[str, Any]) -> str:
    status = response.get("status")
    if status not in {"complete", "not_applicable"}:
        raise ValueError("status must be complete or not_applicable")
    return status


def _named_version(response: dict[str, Any], kind: str) -> dict[str, str]:
    return {
        "name": _required_string(response, f"{kind}_name"),
        "version": _required_string(response, f"{kind}_version"),
    }


def _required_string(response: dict[str, Any], name: str) -> str:
    value = response.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _optional_string(response: dict[str, Any], name: str) -> str | None:
    value = response.get(name)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{name} must be a string or null")
    return value


def _confidence(response: dict[str, Any]) -> float | None:
    value = response.get("confidence")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1:
        raise ValueError("confidence must be between zero and one")
    return float(value)


def _supported_claims(response: dict[str, Any]) -> list[str | dict[str, str]]:
    claims = response.get("supported_claims")
    if not isinstance(claims, list):
        raise ValueError("supported_claims must be a list")
    normalized: list[str | dict[str, str]] = []
    for claim in claims:
        if isinstance(claim, str) and claim.strip():
            normalized.append(claim)
            continue
        if not isinstance(claim, dict):
            raise ValueError("each supported_claim must be a non-empty string or object")
        text = claim.get("claim")
        evidence = claim.get("evidence")
        caveat = claim.get("caveat")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("each supported_claim object must include a non-empty claim")
        if not (isinstance(evidence, str) and evidence.strip()) and not (isinstance(caveat, str) and caveat.strip()):
            raise ValueError("each supported_claim object must include non-empty evidence or caveat")
        normalized.append(
            {
                name: value
                for name, value in (("claim", text), ("evidence", evidence), ("caveat", caveat))
                if isinstance(value, str) and value.strip()
            }
        )
    return normalized


def _audit(response: dict[str, Any]) -> dict[str, str | None]:
    status = response.get("audit_status")
    if status not in {"approved", "unreviewed", "needs_reconciliation"}:
        raise ValueError("audit_status must be approved, unreviewed, or needs_reconciliation")
    reviewer = _optional_string(response, "reviewer")
    return {"status": status, "reviewer": reviewer}


def _failed_ocr(digest: str, extracted_at: str, error: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "text": None,
        "extractor": {"name": None, "version": None},
        "source_sha256": digest,
        "confidence": None,
        "caveat": None,
        "claim_status": "unknown",
        "extracted_at": extracted_at,
        "audit": {"status": "needs_reconciliation", "reviewer": None},
        "error": error,
    }


def _failed_vision(digest: str, extracted_at: str, error: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "labels": [],
        "summary": None,
        "supported_claims": [],
        "model": {"name": None, "version": None},
        "prompt_template_version": None,
        "source_sha256": digest,
        "confidence": None,
        "caveat": None,
        "extracted_at": extracted_at,
        "audit": {"status": "needs_reconciliation", "reviewer": None},
        "error": error,
    }


def _sync_legacy_stage_fields(record: dict[str, Any]) -> None:
    ocr = record["ocr"]
    vision = record["vision_review"]
    record["ocr_status"] = ocr["status"]
    record["ocr_text"] = ocr["text"]
    record["ocr_engine"] = ocr["extractor"]["name"]
    record["ocr_engine_version"] = ocr["extractor"]["version"]
    record["vision_status"] = vision["status"]
    record["vision_labels"] = vision["labels"]
    record["vision_engine"] = vision["model"]["name"]
    record["vision_engine_version"] = vision["model"]["version"]


def _write_checkpoint(path: Path, manifest_path: Path, records: list[dict[str, Any]], processed_records: int) -> None:
    completed = sum(record.get("fetch_status") != "ok" or "ocr" in record for record in records)
    checkpoint = {
        "schema_id": "urn:serenity:corpus-media-checkpoint:1",
        "manifest": str(manifest_path),
        "record_count": len(records),
        "processed_records": processed_records,
        "completed_records": completed,
        "pending_records": len(records) - completed,
        "updated_at": _utc_now(),
        "complete": completed == len(records),
    }
    _write_json(path, checkpoint)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise CorpusError("persistence_conflict", f"checkpoint cannot be written: {path}", 5) from exc


def _cached_hash_matches(cache_root: Path, digest: str) -> bool:
    if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
        return False
    cached_file = cache_root / digest
    try:
        return cached_file.is_file() and hashlib.sha256(cached_file.read_bytes()).hexdigest() == digest
    except OSError:
        return False


def audit_media(database: Path, manifest_path: Path, cache_root: Path, *, require_extraction: bool = False) -> dict[str, Any]:
    """Check an external manifest against corpus references and raw-cache hashes."""
    scan = scan_corpus(database)
    records, invalid_manifest = _read_manifest(manifest_path)
    expected = expected_reference_keys(scan.media_references)
    selected: dict[tuple[str, str, int], dict[str, Any]] = {}
    duplicate_manifest: list[dict[str, Any]] = []
    unexpected_manifest: list[dict[str, Any]] = []

    for line, record in records:
        key = _record_key(record)
        if key is None:
            invalid_manifest.append({"line": line, "reason": "missing or invalid tweet_id, url, or media_index"})
            continue
        reference = _reference_payload(key)
        if key not in expected:
            unexpected_manifest.append({"line": line, **reference})
            continue
        if key in selected:
            duplicate_manifest.append({"line": line, **reference})
            continue
        selected[key] = record

    missing_manifest = [_reference_payload(key) for key in sorted(expected - set(selected))]
    fetch_covered = sum(record.get("fetch_status") == "ok" for record in selected.values())
    failed_fetch: list[dict[str, Any]] = []
    unavailable_fetch: list[dict[str, Any]] = []
    for key, record in selected.items():
        if record.get("fetch_status") == "ok":
            continue
        failure = {**_reference_payload(key), "error": record.get("error")}
        if _is_http_404(record.get("error")):
            unavailable_fetch.append({**failure, "availability": "unavailable", "reason": "http_404"})
        else:
            failed_fetch.append(failure)
    ocr_covered = sum(record.get("ocr_status") == "complete" for record in selected.values())
    vision_covered = sum(record.get("vision_status") == "complete" for record in selected.values())

    missing_cache: list[dict[str, Any]] = []
    hash_mismatch: list[dict[str, Any]] = []
    integrity_covered = 0
    for key, record in selected.items():
        if record.get("fetch_status") != "ok":
            continue
        digest = record.get("sha256")
        reference = _reference_payload(key)
        if not isinstance(digest, str) or len(digest) != 64:
            hash_mismatch.append({**reference, "reason": "missing or invalid sha256"})
            continue
        cached_file = cache_root / digest
        if not cached_file.is_file():
            missing_cache.append({**reference, "sha256": digest})
            continue
        try:
            actual_digest = hashlib.sha256(cached_file.read_bytes()).hexdigest()
        except OSError as exc:
            missing_cache.append({**reference, "sha256": digest, "error": f"{type(exc).__name__}: {exc}"})
            continue
        if actual_digest != digest:
            hash_mismatch.append({**reference, "expected_sha256": digest, "actual_sha256": actual_digest})
            continue
        integrity_covered += 1

    extraction_issues = _required_extraction_issues(selected) if require_extraction else {
        "ocr_required": [],
        "vision_required": [],
        "ocr_provenance_invalid": [],
        "vision_provenance_invalid": [],
        "ocr_audit_unapproved": [],
        "vision_audit_unapproved": [],
    }

    denominator = len(scan.media_references)
    issues = {
        "missing_manifest": missing_manifest,
        "duplicate_manifest": duplicate_manifest,
        "unexpected_manifest": unexpected_manifest,
        "invalid_manifest": invalid_manifest,
        "failed_fetch": failed_fetch,
        "unavailable_fetch": unavailable_fetch,
        "missing_cache": missing_cache,
        "hash_mismatch": hash_mismatch,
        **extraction_issues,
    }
    reconciliation_gate = {
        "required": require_extraction,
        "passed": not any(extraction_issues.values()),
        "blocking_issue_count": sum(len(value) for value in extraction_issues.values()),
    }
    return {
        "valid": not any(value for name, value in issues.items() if name != "unavailable_fetch") and reconciliation_gate["passed"],
        "manifest_records": len(records),
        "coverage": {
            "manifest": {"covered": len(selected), "denominator": denominator},
            "fetch": {"covered": fetch_covered, "denominator": denominator},
            "cache_integrity": {"covered": integrity_covered, "denominator": denominator},
            "ocr": {"covered": ocr_covered, "denominator": denominator},
            "vision": {"covered": vision_covered, "denominator": denominator},
        },
        "issues": issues,
        "reconciliation_gate": reconciliation_gate,
        "inventory": scan.inventory(),
    }


def _is_http_404(error: Any) -> bool:
    return isinstance(error, str) and "http error 404" in error.lower()


def _required_extraction_issues(selected: dict[tuple[str, str, int], dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    issues = {
        "ocr_required": [],
        "vision_required": [],
        "ocr_provenance_invalid": [],
        "vision_provenance_invalid": [],
        "ocr_audit_unapproved": [],
        "vision_audit_unapproved": [],
    }
    for key, record in selected.items():
        if record.get("fetch_status") != "ok":
            continue
        reference = _reference_payload(key)
        digest = record.get("sha256")
        ocr = _nested_stage(record, "ocr")
        ocr_status = ocr.get("status") if ocr else record.get("ocr_status")
        if ocr_status not in {"complete", "not_applicable"}:
            issues["ocr_required"].append({**reference, "status": ocr_status or "missing"})
            continue
        if not isinstance(digest, str) or not _ocr_provenance_is_valid(ocr, digest):
            issues["ocr_provenance_invalid"].append({**reference, "reason": "source hash, extractor identity, or extracted_at is missing or mismatched"})
            continue
        claim_status = ocr.get("claim_status")
        if ocr_status == "complete" and claim_status == "established":
            ocr_audit_status = _nested_audit_status(ocr)
            if ocr_audit_status != "approved":
                issues["ocr_audit_unapproved"].append({**reference, "status": ocr_audit_status or "missing"})
            continue
        vision = _nested_stage(record, "vision_review")
        vision_status = vision.get("status") if vision else record.get("vision_status")
        vision_resolves_ocr = False
        if vision_status != "complete":
            issues["vision_required"].append({**reference, "status": vision_status or "missing"})
        elif not _vision_provenance_is_valid(vision, digest):
            issues["vision_provenance_invalid"].append({**reference, "reason": "source hash, model identity, prompt version, or extracted_at is missing or mismatched"})
        elif _nested_audit_status(vision) != "approved":
            vision_audit_status = _nested_audit_status(vision)
            issues["vision_audit_unapproved"].append({**reference, "status": vision_audit_status or "missing"})
        else:
            vision_resolves_ocr = True
        ocr_audit_status = _nested_audit_status(ocr)
        if ocr_audit_status != "approved" and not (ocr_status == "complete" and claim_status == "insufficient" and vision_resolves_ocr):
            issues["ocr_audit_unapproved"].append({**reference, "status": ocr_audit_status or "missing"})
    return issues


def _ocr_provenance_is_valid(stage: dict[str, Any] | None, digest: str) -> bool:
    if stage is None or stage.get("source_sha256") != digest or not isinstance(stage.get("extracted_at"), str):
        return False
    extractor = stage.get("extractor")
    return isinstance(extractor, dict) and isinstance(extractor.get("name"), str) and bool(extractor["name"]) and isinstance(extractor.get("version"), str) and bool(extractor["version"])


def _vision_provenance_is_valid(stage: dict[str, Any] | None, digest: str) -> bool:
    if stage is None or stage.get("source_sha256") != digest or not isinstance(stage.get("extracted_at"), str):
        return False
    model = stage.get("model")
    return (
        isinstance(model, dict)
        and isinstance(model.get("name"), str)
        and bool(model["name"])
        and isinstance(model.get("version"), str)
        and bool(model["version"])
        and isinstance(stage.get("prompt_template_version"), str)
        and bool(stage["prompt_template_version"])
        and isinstance(stage.get("summary"), str)
        and bool(stage["summary"])
        and _supported_claims_are_valid(stage.get("supported_claims"))
    )


def _supported_claims_are_valid(value: Any) -> bool:
    try:
        _supported_claims({"supported_claims": value})
    except ValueError:
        return False
    return True


def _nested_audit_status(stage: dict[str, Any] | None) -> str | None:
    audit = stage.get("audit") if stage else None
    return audit.get("status") if isinstance(audit, dict) and isinstance(audit.get("status"), str) else None


def _read_manifest(path: Path) -> tuple[list[tuple[int, dict[str, Any]]], list[dict[str, Any]]]:
    if not path.is_file():
        raise CorpusError("manifest_unavailable", f"media manifest not found: {path}", 3)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorpusError("manifest_unavailable", f"media manifest cannot be read: {path}", 3) from exc

    records: list[tuple[int, dict[str, Any]]] = []
    invalid: list[dict[str, Any]] = []
    if path.suffix.lower() == ".json":
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            return records, [{"line": 1, "reason": f"invalid JSON: {exc.msg}"}]
        candidates = decoded.get("records") if isinstance(decoded, dict) else decoded
        if not isinstance(candidates, list):
            return records, [{"line": 1, "reason": "JSON manifest must be a list or contain a records list"}]
        for line, candidate in enumerate(candidates, start=1):
            if isinstance(candidate, dict):
                records.append((line, candidate))
            else:
                invalid.append({"line": line, "reason": "manifest record is not an object"})
        return records, invalid

    for line, raw_record in enumerate(raw.splitlines(), start=1):
        if not raw_record.strip():
            continue
        try:
            decoded = json.loads(raw_record)
        except json.JSONDecodeError as exc:
            invalid.append({"line": line, "reason": f"invalid JSON: {exc.msg}"})
            continue
        if not isinstance(decoded, dict):
            invalid.append({"line": line, "reason": "manifest record is not an object"})
            continue
        records.append((line, decoded))
    return records, invalid


def _record_key(record: dict[str, Any]) -> tuple[str, str, int] | None:
    tweet_id = record.get("tweet_id")
    url = record.get("url")
    media_index = record.get("media_index")
    if not isinstance(tweet_id, str) or not isinstance(url, str) or isinstance(media_index, bool) or not isinstance(media_index, int):
        return None
    return (tweet_id, url, media_index)


def _reference_payload(key: tuple[str, str, int]) -> dict[str, Any]:
    tweet_id, url, media_index = key
    return {"tweet_id": tweet_id, "url": url, "media_index": media_index}


def _fetch_one(url: str, cache_root: Path, *, retries: int, timeout_seconds: float) -> dict[str, Any]:
    fetched_at = _utc_now()
    error: str | None = None
    for _attempt in range(retries + 1):
        try:
            request = Request(url, headers={"User-Agent": "SerenityCorpus/2.0"})
            with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310 - corpus URLs are explicit input
                body = response.read()
                content_type = response.headers.get_content_type()
            digest = hashlib.sha256(body).hexdigest()
            cache_root.mkdir(parents=True, exist_ok=True)
            _write_binary_if_absent(cache_root / digest, body)
            mime = _detect_mime(body, content_type)
            return _media_result(
                sha256=digest,
                mime=mime,
                dimensions=_dimensions(body, mime),
                fetched_at=fetched_at,
                fetch_status="ok",
                error=None,
            )
        except (HTTPError, URLError, OSError, ValueError) as exc:
            error = f"{type(exc).__name__}: {exc}"
    return _media_result(
        sha256=None,
        mime=None,
        dimensions=None,
        fetched_at=fetched_at,
        fetch_status="failed",
        error=error,
    )


def _media_result(
    *,
    sha256: str | None,
    mime: str | None,
    dimensions: dict[str, int] | None,
    fetched_at: str,
    fetch_status: str,
    error: str | None,
) -> dict[str, Any]:
    return {
        "sha256": sha256,
        "mime": mime,
        "dimensions": dimensions,
        "fetched_at": fetched_at,
        "fetch_status": fetch_status,
        "ocr_status": "not_requested",
        "ocr_text": None,
        "ocr_engine": None,
        "ocr_engine_version": None,
        "vision_status": "not_requested",
        "vision_labels": [],
        "vision_engine": None,
        "vision_engine_version": None,
        "error": error,
    }


def _write_binary_if_absent(path: Path, body: bytes) -> None:
    if path.exists():
        return
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        temporary.write_bytes(body)
        try:
            os.link(temporary, path)
        except FileExistsError:
            pass
    finally:
        temporary.unlink(missing_ok=True)


def _write_manifest(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    if path.suffix.lower() == ".json":
        encoded = json.dumps(
            {"schema_id": "urn:serenity:corpus-media-manifest:1", "records": records},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
    else:
        encoded = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for record in records)
    try:
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise CorpusError("persistence_conflict", f"manifest cannot be written: {path}", 5) from exc


def _detect_mime(body: bytes, header_mime: str) -> str | None:
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if body.startswith(b"\xff\xd8"):
        return "image/jpeg"
    return header_mime if header_mime and header_mime != "application/octet-stream" else None


def _dimensions(body: bytes, mime: str | None) -> dict[str, int] | None:
    if mime == "image/png" and len(body) >= 24:
        return {"width": int.from_bytes(body[16:20], "big"), "height": int.from_bytes(body[20:24], "big")}
    if mime != "image/jpeg":
        return None
    position = 2
    while position + 9 <= len(body):
        if body[position] != 0xFF:
            position += 1
            continue
        marker = body[position + 1]
        position += 2
        if marker in {0xD8, 0xD9}:
            continue
        if position + 2 > len(body):
            return None
        size = int.from_bytes(body[position : position + 2], "big")
        if size < 2 or position + size > len(body):
            return None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF} and size >= 7:
            return {"width": int.from_bytes(body[position + 5 : position + 7], "big"), "height": int.from_bytes(body[position + 3 : position + 5], "big")}
        position += size
    return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
