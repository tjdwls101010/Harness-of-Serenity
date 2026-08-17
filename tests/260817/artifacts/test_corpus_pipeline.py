from __future__ import annotations

import base64
import hashlib
import json
import shlex
import shutil
import sqlite3
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Iterator


REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_CLI = REPO_ROOT / "scripts" / "serenity_corpus.py"
FIXTURE_SQL = REPO_ROOT / "tests" / "260817" / "fixtures" / "corpus" / "tweets.sql"
OCR_FIXTURE = REPO_ROOT / "tests" / "260817" / "fixtures" / "corpus" / "ocr_fixture.py"
VISION_FIXTURE = REPO_ROOT / "tests" / "260817" / "fixtures" / "corpus" / "vision_fixture.py"
FAILED_OCR_FIXTURE = REPO_ROOT / "tests" / "260817" / "fixtures" / "corpus" / "ocr_failed_fixture.py"
TEXT_IMAGE = REPO_ROOT / "tests" / "260817" / "fixtures" / "corpus" / "text-bearing-image.png.b64"
CHART_IMAGE = REPO_ROOT / "tests" / "260817" / "fixtures" / "corpus" / "chart-image.png.b64"
VISION_OCR_SOURCE = REPO_ROOT / "scripts" / "tools" / "serenity_vision_ocr.swift"
TESSERACT_OCR_HELPER = REPO_ROOT / "scripts" / "tools" / "serenity_tesseract_ocr.py"
TESSERACT_FIXTURE = REPO_ROOT / "tests" / "260817" / "fixtures" / "corpus" / "tesseract_fixture.py"


def _make_corpus_db(tmp_path: Path, media_base: str = "https://media.example") -> Path:
    database = tmp_path / "corpus.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(FIXTURE_SQL.read_text(encoding="utf-8").replace("__MEDIA_BASE__", media_base))
        connection.commit()
    finally:
        connection.close()
    return database


def _run_corpus(tmp_path: Path, *args: str, expected_exit: int = 0) -> dict:
    completed = subprocess.run(
        [sys.executable, str(CORPUS_CLI), *args],
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


def _run_tesseract_helper(tmp_path: Path, *args: str, expected_exit: int = 0) -> tuple[dict, str]:
    completed = subprocess.run(
        [sys.executable, str(TESSERACT_OCR_HELPER), *args],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == expected_exit, completed.stderr or completed.stdout
    lines = completed.stdout.splitlines()
    assert len(lines) == 1, completed.stdout
    return json.loads(lines[0]), completed.stderr


def _make_reviewable_media(tmp_path: Path) -> tuple[Path, Path, Path, dict[str, str]]:
    database = _make_corpus_db(tmp_path)
    manifest = tmp_path / "corpus-media.jsonl"
    cache_root = tmp_path / ".serenity" / "media-cache"
    alpha = base64.b64decode(TEXT_IMAGE.read_text(encoding="utf-8"))
    bravo = base64.b64decode(CHART_IMAGE.read_text(encoding="utf-8")) + b"chart"
    digests = {"alpha": hashlib.sha256(alpha).hexdigest(), "bravo": hashlib.sha256(bravo).hexdigest()}
    cache_root.mkdir(parents=True)
    (cache_root / digests["alpha"]).write_bytes(alpha)
    (cache_root / digests["bravo"]).write_bytes(bravo)
    records = [
        {
            "tweet_id": "tweet-1",
            "url": "https://media.example/alpha.png",
            "media_index": index,
            "sha256": digests["alpha"],
            "mime": "image/png",
            "dimensions": {"width": 1, "height": 1},
            "fetched_at": "2026-08-17T00:00:00Z",
            "fetch_status": "ok",
            "ocr": {
                "status": "complete",
                "text": "Qualified capacity is constrained.",
                "extractor": {"name": "fixture-ocr", "version": "1.0.0"},
                "source_sha256": digests["alpha"],
                "confidence": 0.93,
                "caveat": "fixture OCR",
                "claim_status": "insufficient",
                "extracted_at": "2026-08-17T00:00:00Z",
                "audit": {"status": "unreviewed", "reviewer": None},
                "error": None,
            },
            "vision_status": "not_requested",
            "error": None,
        }
        for index in (0, 1)
    ] + [
        {
            "tweet_id": "tweet-2",
            "url": "https://media.example/bravo.jpg",
            "media_index": 0,
            "sha256": digests["bravo"],
            "mime": "image/jpeg",
            "dimensions": {"width": 3, "height": 2},
            "fetched_at": "2026-08-17T00:00:00Z",
            "fetch_status": "ok",
            "ocr": {
                "status": "complete",
                "text": "Capacity chart needs visual review.",
                "extractor": {"name": "fixture-ocr", "version": "1.0.0"},
                "source_sha256": digests["bravo"],
                "confidence": 0.88,
                "caveat": "fixture OCR",
                "claim_status": "insufficient",
                "extracted_at": "2026-08-17T00:00:00Z",
                "audit": {"status": "unreviewed", "reviewer": None},
                "error": None,
            },
            "vision_status": "not_requested",
            "error": None,
        }
    ]
    manifest.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    return database, manifest, cache_root, digests


def _review_packet_items(packet_dir: Path) -> list[dict]:
    packet_manifest = json.loads((packet_dir / "packet-manifest.json").read_text(encoding="utf-8"))
    return [
        item
        for packet in packet_manifest["packets"]
        for item in json.loads((packet_dir / packet["file"]).read_text(encoding="utf-8"))["items"]
    ]


def _review_output(
    item: dict, *, claim_status: str, ocr_disposition: str = "approved", reviewer_id: str = "reviewer-fixture"
) -> dict:
    relations = [{key: relation[key] for key in ("tweet_id", "url", "media_index")} for relation in item["relations"]]
    vision = (
        {"disposition": "not_required", "labels": [], "summary": None, "supported_claims": [], "confidence": None}
        if claim_status == "established"
        else {
            "disposition": "complete",
            "labels": ["chart"],
            "summary": "The image needs visual interpretation before its claim can be approved.",
            "supported_claims": [
                {
                    "claim": "The image contains a chart-like visual.",
                    "evidence": "The review labels it chart-like.",
                    "caveat": "No financial claim is approved without its visible source context.",
                }
            ],
            "confidence": 0.9,
        }
    )
    return {
        "schema_id": "urn:serenity:schema:media-review-output:1",
        "packet_id": "media-review-fixture",
        "source_sha256": item["source_sha256"],
        "review_input_sha256": item["review_input_sha256"],
        "relations": relations,
        "reviewer_id": reviewer_id,
        "reviewer_model": "fixture-review-model",
        "prompt_version": "media-review-v1",
        "ocr": {"disposition": ocr_disposition, "claim_status": claim_status},
        "vision": vision,
    }


@contextmanager
def _media_server() -> Iterator[str]:
    payloads = {
        "/alpha.png": ("image/png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"),
        "/bravo.jpg": ("image/jpeg", b"\xff\xd8\xff\xc0\x00\x11\x08\x00\x02\x00\x03\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01\xff\xd9"),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
            content_type, body = payloads.get(self.path, ("text/plain", b"not found"))
            self.send_response(200 if self.path in payloads else 404)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def test_inventory_counts_the_actual_sqlite_media_references_and_types(tmp_path: Path) -> None:
    database = _make_corpus_db(tmp_path)
    database_sha256 = hashlib.sha256(database.read_bytes()).hexdigest()

    result = _run_corpus(tmp_path, "inventory", "--db", str(database))

    assert result == {
        "command": "inventory",
        "ok": True,
        "inventory": {
            "tweet_count": 4,
            "tweet_types": {"post": 2, "reply": 1, "subscriber": 1},
            "tweets_with_media": 2,
            "media_reference_count": 3,
            "unique_media_url_count": 2,
            "invalid_media_rows": 0,
            "invalid_media_references": 0,
            "source": {
                "database_sha256": database_sha256,
                "query": "SELECT id, type, media FROM tweets ORDER BY id",
                "sqlite_user_version": 0,
            },
        },
    }


def test_review_packet_build_dedupes_sha_in_deterministic_batches_with_only_related_tweet_context(tmp_path: Path) -> None:
    database, manifest, cache_root, digests = _make_reviewable_media(tmp_path)
    packet_dir = tmp_path / "review-packets"

    result = _run_corpus(
        tmp_path,
        "review-packets",
        "build",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--packet-dir",
        str(packet_dir),
        "--batch-size",
        "1",
    )

    assert result["command"] == "review-packets.build"
    assert result["packets"]["unique_sources"] == 2
    assert result["packets"]["relations"] == 3
    packet_manifest = json.loads((packet_dir / "packet-manifest.json").read_text(encoding="utf-8"))
    assert packet_manifest["source_manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert packet_manifest["packet_count"] == 2
    assert [packet["source_sha256s"] for packet in packet_manifest["packets"]] == [[digest] for digest in sorted(digests.values())]
    first_packet = json.loads((packet_dir / packet_manifest["packets"][0]["file"]).read_text(encoding="utf-8"))
    assert first_packet["items"][0]["cache_path"] == str(cache_root / first_packet["items"][0]["source_sha256"])
    assert set(first_packet["items"][0]) == {"source_sha256", "review_input_sha256", "cache_path", "mime", "dimensions", "ocr", "relations"}
    alpha_item = next(
        json.loads((packet_dir / packet["file"]).read_text(encoding="utf-8"))["items"][0]
        for packet in packet_manifest["packets"]
        if packet["source_sha256s"] == [digests["alpha"]]
    )
    assert alpha_item["ocr"] == {"text": "Qualified capacity is constrained.", "confidence": 0.93}
    assert alpha_item["relations"] == [
        {"tweet_id": "tweet-1", "url": "https://media.example/alpha.png", "media_index": 0, "tweet_context": {"type": "post", "content": "method note"}},
        {"tweet_id": "tweet-1", "url": "https://media.example/alpha.png", "media_index": 1, "tweet_context": {"type": "post", "content": "method note"}},
    ]


def test_reviews_apply_fans_out_exact_sha_reviews_and_unblocks_strict_audit(tmp_path: Path) -> None:
    database, manifest, cache_root, digests = _make_reviewable_media(tmp_path)
    packet_dir = tmp_path / "review-packets"
    reviews_dir = tmp_path / "reviews"
    _run_corpus(
        tmp_path,
        "review-packets",
        "build",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--packet-dir",
        str(packet_dir),
        "--batch-size",
        "20",
    )
    reviews_dir.mkdir()
    for item in _review_packet_items(packet_dir):
        claim_status = "established" if item["source_sha256"] == digests["alpha"] else "insufficient"
        (reviews_dir / f"{item['source_sha256']}.json").write_text(
            json.dumps(
                _review_output(
                    item,
                    claim_status=claim_status,
                    ocr_disposition="needs_reconciliation" if item["source_sha256"] == digests["bravo"] else "approved",
                )
            ),
            encoding="utf-8",
        )

    applied = _run_corpus(
        tmp_path,
        "reviews",
        "apply",
        "--manifest",
        str(manifest),
        "--reviews-dir",
        str(reviews_dir),
        "--reviewer-model",
        "fixture-review-model",
        "--prompt-version",
        "media-review-v1",
        "--require-complete",
    )

    assert applied["command"] == "reviews.apply"
    assert applied["reviews"] == {"unique_sources": 2, "relations": 3, "applied_sources": 2, "applied_relations": 3}
    records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    assert [record["tweet_id"] for record in records] == ["tweet-1", "tweet-1", "tweet-2"]
    assert records[0]["ocr"]["claim_status"] == records[1]["ocr"]["claim_status"] == "established"
    assert records[0]["ocr"]["audit"] == {"status": "approved", "reviewer": "reviewer-fixture"}
    assert records[0]["vision_review"]["status"] == "not_required"
    assert records[0]["vision_review"] == records[1]["vision_review"]
    assert records[2]["vision_review"]["status"] == "complete"
    assert records[2]["vision_review"]["summary"]
    assert records[2]["ocr"]["audit"] == {"status": "needs_reconciliation", "reviewer": "reviewer-fixture"}
    audited = _run_corpus(
        tmp_path,
        "audit",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--require-extraction",
    )
    assert audited["audit"]["valid"] is True

    records[2]["vision_review"]["audit"] = {"status": "unreviewed", "reviewer": "reviewer-fixture"}
    manifest.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    unapproved_vision = _run_corpus(
        tmp_path,
        "audit",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--require-extraction",
    )
    assert unapproved_vision["audit"]["valid"] is False
    assert len(unapproved_vision["audit"]["issues"]["vision_audit_unapproved"]) == 1
    assert len(unapproved_vision["audit"]["issues"]["ocr_audit_unapproved"]) == 1


def test_reviews_apply_rejects_partial_and_malicious_relation_results_without_writing(tmp_path: Path) -> None:
    database, manifest, cache_root, digests = _make_reviewable_media(tmp_path)
    packet_dir = tmp_path / "review-packets"
    reviews_dir = tmp_path / "reviews"
    _run_corpus(
        tmp_path,
        "review-packets",
        "build",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--packet-dir",
        str(packet_dir),
        "--batch-size",
        "20",
    )
    items = _review_packet_items(packet_dir)
    reviews_dir.mkdir()
    alpha_item = next(item for item in items if item["source_sha256"] == digests["alpha"])
    bravo_item = next(item for item in items if item["source_sha256"] == digests["bravo"])
    (reviews_dir / "alpha.json").write_text(json.dumps(_review_output(alpha_item, claim_status="established")), encoding="utf-8")
    before = manifest.read_bytes()

    partial = _run_corpus(
        tmp_path,
        "reviews",
        "apply",
        "--manifest",
        str(manifest),
        "--reviews-dir",
        str(reviews_dir),
        "--reviewer-model",
        "fixture-review-model",
        "--prompt-version",
        "media-review-v1",
        "--require-complete",
        expected_exit=4,
    )
    assert partial["error"]["code"] == "review_incomplete"
    assert manifest.read_bytes() == before

    malicious = _review_output(bravo_item, claim_status="insufficient")
    malicious["relations"][0]["media_index"] = 999
    (reviews_dir / "bravo.json").write_text(json.dumps(malicious), encoding="utf-8")
    mismatch = _run_corpus(
        tmp_path,
        "reviews",
        "apply",
        "--manifest",
        str(manifest),
        "--reviews-dir",
        str(reviews_dir),
        "--reviewer-model",
        "fixture-review-model",
        "--prompt-version",
        "media-review-v1",
        expected_exit=2,
    )
    assert mismatch["error"]["code"] == "usage_or_schema"
    assert manifest.read_bytes() == before


def test_ingest_media_records_content_addressed_provenance_without_storing_binary_in_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-media.jsonl"
    cache_root = tmp_path / ".serenity" / "media-cache"
    with _media_server() as media_base:
        database = _make_corpus_db(tmp_path, media_base)
        result = _run_corpus(
            tmp_path,
            "ingest-media",
            "--db",
            str(database),
            "--manifest",
            str(manifest),
            "--cache-root",
            str(cache_root),
            "--retries",
            "1",
        )

    assert result["command"] == "ingest-media"
    assert result["ok"] is True
    assert result["ingest"]["expected_references"] == 3
    assert result["ingest"]["fetched_references"] == 3
    assert result["ingest"]["failed_references"] == 0

    records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3
    alpha_records = [record for record in records if record["url"].endswith("/alpha.png")]
    assert len(alpha_records) == 2
    assert alpha_records[0]["sha256"] == alpha_records[1]["sha256"]
    assert alpha_records[0]["mime"] == "image/png"
    assert alpha_records[0]["dimensions"] == {"width": 1, "height": 1}
    assert alpha_records[0]["fetch_status"] == "ok"
    assert alpha_records[0]["ocr_status"] == "not_requested"
    assert alpha_records[0]["vision_status"] == "not_requested"
    assert alpha_records[0]["fetched_at"].endswith("Z")
    assert (cache_root / alpha_records[0]["sha256"]).is_file()
    assert "PNG" not in manifest.read_text(encoding="utf-8")


def test_audit_reports_missing_duplicate_and_hash_mismatched_media_with_denominators(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-media.jsonl"
    cache_root = tmp_path / ".serenity" / "media-cache"
    with _media_server() as media_base:
        database = _make_corpus_db(tmp_path, media_base)
        _run_corpus(
            tmp_path,
            "ingest-media",
            "--db",
            str(database),
            "--manifest",
            str(manifest),
            "--cache-root",
            str(cache_root),
        )

    records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    alpha = next(record for record in records if record["url"].endswith("/alpha.png"))
    bravo = next(record for record in records if record["url"].endswith("/bravo.jpg"))
    (cache_root / alpha["sha256"]).write_bytes(b"wrong raw cache content")
    manifest.write_text(
        "\n".join(json.dumps(record) for record in records if record != bravo) + "\n" + json.dumps(alpha) + "\n",
        encoding="utf-8",
    )

    result = _run_corpus(
        tmp_path,
        "audit",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
    )

    assert result["command"] == "audit"
    assert result["ok"] is True
    assert result["audit"]["valid"] is False
    assert result["audit"]["coverage"] == {
        "manifest": {"covered": 2, "denominator": 3},
        "fetch": {"covered": 2, "denominator": 3},
        "cache_integrity": {"covered": 0, "denominator": 3},
        "ocr": {"covered": 0, "denominator": 3},
        "vision": {"covered": 0, "denominator": 3},
    }
    assert len(result["audit"]["issues"]["missing_manifest"]) == 1
    assert len(result["audit"]["issues"]["duplicate_manifest"]) == 1
    assert len(result["audit"]["issues"]["hash_mismatch"]) == 2


def test_ingest_and_audit_support_a_tracked_json_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-media.json"
    cache_root = tmp_path / ".serenity" / "media-cache"
    with _media_server() as media_base:
        database = _make_corpus_db(tmp_path, media_base)
        _run_corpus(
            tmp_path,
            "ingest-media",
            "--db",
            str(database),
            "--manifest",
            str(manifest),
            "--cache-root",
            str(cache_root),
        )

    stored = json.loads(manifest.read_text(encoding="utf-8"))
    assert stored["schema_id"] == "urn:serenity:corpus-media-manifest:1"
    assert len(stored["records"]) == 3
    audited = _run_corpus(
        tmp_path,
        "audit",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
    )
    assert audited["audit"]["valid"] is True


def test_required_extraction_audit_does_not_treat_not_requested_stages_as_blank(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-media.jsonl"
    cache_root = tmp_path / ".serenity" / "media-cache"
    with _media_server() as media_base:
        database = _make_corpus_db(tmp_path, media_base)
        _run_corpus(
            tmp_path,
            "ingest-media",
            "--db",
            str(database),
            "--manifest",
            str(manifest),
            "--cache-root",
            str(cache_root),
        )

    audited = _run_corpus(
        tmp_path,
        "audit",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--require-extraction",
    )

    assert audited["audit"]["valid"] is False
    assert audited["audit"]["reconciliation_gate"]["passed"] is False
    assert len(audited["audit"]["issues"]["ocr_required"]) == 3


def test_extraction_stages_preserve_provenance_and_reconcile_fixed_text_and_chart_images(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-media.jsonl"
    cache_root = tmp_path / ".serenity" / "media-cache"
    text_image = base64.b64decode(TEXT_IMAGE.read_text(encoding="utf-8"))
    chart_image = base64.b64decode(CHART_IMAGE.read_text(encoding="utf-8"))
    text_hash = hashlib.sha256(text_image).hexdigest()
    chart_hash = hashlib.sha256(chart_image + b"chart").hexdigest()
    cache_root.mkdir(parents=True)
    (cache_root / text_hash).write_bytes(text_image)
    (cache_root / chart_hash).write_bytes(chart_image + b"chart")
    with _media_server() as media_base:
        database = _make_corpus_db(tmp_path, media_base)
    records = [
        {
            "tweet_id": "tweet-1",
            "url": f"{media_base}/alpha.png",
            "media_index": index,
            "sha256": text_hash,
            "mime": "image/png",
            "dimensions": {"width": 1, "height": 1},
            "fetched_at": "2026-08-17T00:00:00Z",
            "fetch_status": "ok",
            "ocr_status": "not_requested",
            "ocr_text": None,
            "ocr_engine": None,
            "ocr_engine_version": None,
            "vision_status": "not_requested",
            "vision_labels": [],
            "vision_engine": None,
            "vision_engine_version": None,
            "error": None,
        }
        for index in (0, 1)
    ] + [
        {
            "tweet_id": "tweet-2",
            "url": f"{media_base}/bravo.jpg",
            "media_index": 0,
            "sha256": chart_hash,
            "mime": "image/jpeg",
            "dimensions": {"width": 3, "height": 2},
            "fetched_at": "2026-08-17T00:00:00Z",
            "fetch_status": "ok",
            "ocr_status": "not_requested",
            "ocr_text": None,
            "ocr_engine": None,
            "ocr_engine_version": None,
            "vision_status": "not_requested",
            "vision_labels": [],
            "vision_engine": None,
            "vision_engine_version": None,
            "error": None,
        }
    ]
    manifest.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    local_ocr = tmp_path / "ocr_fixture.py"
    local_vision = tmp_path / "vision_fixture.py"
    shutil.copy2(OCR_FIXTURE, local_ocr)
    shutil.copy2(VISION_FIXTURE, local_vision)

    extracted = _run_corpus(
        tmp_path,
        "extract-media",
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--ocr-command",
        f"{shlex.quote(sys.executable)} {local_ocr} --input {{input}}",
        "--vision-command",
        f"{shlex.quote(sys.executable)} {local_vision} --input {{input}}",
    )

    assert extracted["extract"]["ocr_unique_sources_executed"] == 2
    assert extracted["extract"]["vision_unique_sources_executed"] == 1
    enriched = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    text_record = enriched[0]
    chart_record = enriched[-1]
    assert text_record["ocr"] == {
        "status": "complete",
        "text": "Allocation is constrained by qualified capacity.",
        "extractor": {"name": "fixture-ocr", "version": "1.0.0"},
        "source_sha256": text_hash,
        "confidence": 0.98,
        "caveat": "deterministic text-bearing fixture",
        "claim_status": "established",
        "extracted_at": text_record["ocr"]["extracted_at"],
        "audit": {"status": "approved", "reviewer": "fixture-reviewer"},
        "error": None,
    }
    assert text_record["vision_review"]["status"] == "not_required"
    assert chart_record["ocr"]["claim_status"] == "insufficient"
    assert chart_record["vision_review"] == {
        "status": "complete",
        "labels": ["chart", "diagram", "screenshot"],
        "summary": "The image is chart-like and requires claim-level visual review.",
        "supported_claims": [
            {
                "claim": "The image contains a chart-like visual.",
                "evidence": "The deterministic fixture labels it chart, diagram, and screenshot.",
                "caveat": "This fixture does not validate a financial claim.",
            }
        ],
        "model": {"name": "fixture-vision", "version": "2.0.0"},
        "prompt_template_version": "chart-review-v1",
        "source_sha256": chart_hash,
        "confidence": 0.91,
        "caveat": "deterministic visual review fixture",
        "extracted_at": chart_record["vision_review"]["extracted_at"],
        "audit": {"status": "approved", "reviewer": "fixture-reviewer"},
        "error": None,
    }
    audited = _run_corpus(
        tmp_path,
        "audit",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--require-extraction",
    )
    assert audited["audit"]["valid"] is True
    assert audited["audit"]["reconciliation_gate"]["passed"] is True

    enriched[0]["ocr"]["source_sha256"] = "0" * 64
    manifest.write_text("".join(json.dumps(record) + "\n" for record in enriched), encoding="utf-8")
    mismatched = _run_corpus(
        tmp_path,
        "audit",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--require-extraction",
    )
    assert mismatched["audit"]["reconciliation_gate"]["passed"] is False
    assert len(mismatched["audit"]["issues"]["ocr_provenance_invalid"]) == 1

    enriched[0]["ocr"]["source_sha256"] = text_hash
    enriched[-1]["vision_review"].pop("summary")
    manifest.write_text("".join(json.dumps(record) + "\n" for record in enriched), encoding="utf-8")
    missing_explanation = _run_corpus(
        tmp_path,
        "audit",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--require-extraction",
    )
    assert missing_explanation["audit"]["reconciliation_gate"]["passed"] is False
    assert len(missing_explanation["audit"]["issues"]["vision_provenance_invalid"]) == 1


def test_audit_preserves_http_404_downloads_as_non_blocking_unavailable_evidence(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-media.jsonl"
    cache_root = tmp_path / ".serenity" / "media-cache"
    with _media_server() as media_base:
        database = _make_corpus_db(tmp_path, f"{media_base}/missing")
        ingested = _run_corpus(
            tmp_path,
            "ingest-media",
            "--db",
            str(database),
            "--manifest",
            str(manifest),
            "--cache-root",
            str(cache_root),
            "--retries",
            "0",
        )

    assert ingested["ingest"]["failed_references"] == 3
    audited = _run_corpus(
        tmp_path,
        "audit",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
    )
    assert audited["audit"]["valid"] is True
    assert audited["audit"]["issues"]["failed_fetch"] == []
    assert len(audited["audit"]["issues"]["unavailable_fetch"]) == 3
    assert {issue["availability"] for issue in audited["audit"]["issues"]["unavailable_fetch"]} == {"unavailable"}
    assert {issue["reason"] for issue in audited["audit"]["issues"]["unavailable_fetch"]} == {"http_404"}


def test_ingest_resumes_existing_verified_records_and_keeps_an_incremental_checkpoint(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-media.jsonl"
    checkpoint = tmp_path / "corpus-media.checkpoint.json"
    cache_root = tmp_path / ".serenity" / "media-cache"
    with _media_server() as media_base:
        database = _make_corpus_db(tmp_path, media_base)
        first = _run_corpus(
            tmp_path,
            "ingest-media",
            "--db",
            str(database),
            "--manifest",
            str(manifest),
            "--cache-root",
            str(cache_root),
            "--checkpoint",
            str(checkpoint),
            "--retries",
            "0",
        )

    assert first["ingest"]["fetched_references"] == 3
    records = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    records[0]["continuity_marker"] = "must-survive-resume"
    manifest.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")

    resumed = _run_corpus(
        tmp_path,
        "ingest-media",
        "--db",
        str(database),
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--checkpoint",
        str(checkpoint),
        "--retries",
        "0",
    )

    assert resumed["ingest"]["fetched_references"] == 0
    assert resumed["ingest"]["resumed_references"] == 3
    assert json.loads(manifest.read_text(encoding="utf-8").splitlines()[0])["continuity_marker"] == "must-survive-resume"
    assert json.loads(checkpoint.read_text(encoding="utf-8")) == {
        "schema_id": "urn:serenity:corpus-media-checkpoint:1",
        "manifest": str(manifest),
        "record_count": 3,
        "processed_records": 3,
        "completed_records": 3,
        "pending_records": 0,
        "complete": True,
        "updated_at": json.loads(checkpoint.read_text(encoding="utf-8"))["updated_at"],
    }


def test_apple_vision_ocr_helper_has_a_no_network_json_contract_without_running_macos_vision(tmp_path: Path) -> None:
    source = VISION_OCR_SOURCE.read_text(encoding="utf-8")

    assert "VNRecognizeTextRequest" in source
    assert "recognitionLevel = .accurate" in source
    assert "automaticallyDetectsLanguage" in source
    assert "JSONEncoder" in source
    assert "--input" in source

    status = _run_corpus(tmp_path, "ocr-helper", "status")

    assert status["command"] == "ocr-helper.status"
    assert status["ocr_helper"]["source"] == "scripts/tools/serenity_vision_ocr.swift"
    assert status["ocr_helper"]["command_template"].endswith(" --input {input}")
    assert status["ocr_helper"]["network"] == "none"


def test_tesseract_helper_emits_unreviewed_insufficient_ocr_from_an_injected_binary(tmp_path: Path) -> None:
    image_path = tmp_path / "text-bearing-image.png"
    image_path.write_bytes(base64.b64decode(TEXT_IMAGE.read_text(encoding="utf-8")))
    tesseract_binary = tmp_path / "tesseract-fixture"
    shutil.copy2(TESSERACT_FIXTURE, tesseract_binary)
    tesseract_binary.chmod(0o755)

    result, diagnostic = _run_tesseract_helper(
        tmp_path,
        "--input",
        str(image_path),
        "--tesseract",
        str(tesseract_binary),
    )

    assert diagnostic == ""
    assert result == {
        "status": "complete",
        "text": "Qualified capacity is constrained",
        "extractor_name": "tesseract",
        "extractor_version": "tesseract 9.9.9-fixture",
        "confidence": 0.94,
        "caveat": "OCR text and confidence cannot establish a claim without visual review; chart, diagram, and screenshot possibilities remain.",
        "claim_status": "insufficient",
        "audit_status": "unreviewed",
        "reviewer": None,
        "error": None,
    }


def test_tesseract_helper_status_reports_an_injected_binary_and_copyable_template(tmp_path: Path) -> None:
    tesseract_binary = tmp_path / "tesseract-fixture"
    shutil.copy2(TESSERACT_FIXTURE, tesseract_binary)
    tesseract_binary.chmod(0o755)

    result = _run_corpus(tmp_path, "ocr-helper", "tesseract-status", "--tesseract", str(tesseract_binary))

    assert result == {
        "command": "ocr-helper.tesseract-status",
        "ok": True,
        "ocr_helper": {
            "source": "scripts/tools/serenity_tesseract_ocr.py",
            "source_exists": True,
            "tesseract_binary": str(tesseract_binary),
            "available": True,
            "version": "tesseract 9.9.9-fixture",
            "network": "none",
            "command_template": f"{shlex.quote(str(TESSERACT_OCR_HELPER))} --tesseract {shlex.quote(str(tesseract_binary))} --input {{input}}",
        },
    }


def test_extractor_reported_failure_keeps_its_typed_identity_and_error(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-media.jsonl"
    cache_root = tmp_path / ".serenity" / "media-cache"
    image = base64.b64decode(TEXT_IMAGE.read_text(encoding="utf-8"))
    digest = hashlib.sha256(image).hexdigest()
    cache_root.mkdir(parents=True)
    (cache_root / digest).write_bytes(image)
    manifest.write_text(
        json.dumps(
            {
                "tweet_id": "tweet-1",
                "url": "https://fixture.example/alpha.png",
                "media_index": 0,
                "sha256": digest,
                "mime": "image/png",
                "dimensions": {"width": 1, "height": 1},
                "fetched_at": "2026-08-17T00:00:00Z",
                "fetch_status": "ok",
                "ocr_status": "not_requested",
                "vision_status": "not_requested",
                "error": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    local_failed_ocr = tmp_path / "ocr_failed_fixture.py"
    shutil.copy2(FAILED_OCR_FIXTURE, local_failed_ocr)

    _run_corpus(
        tmp_path,
        "extract-media",
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--ocr-command",
        f"{shlex.quote(sys.executable)} {local_failed_ocr} --input {{input}}",
    )

    record = json.loads(manifest.read_text(encoding="utf-8"))
    assert record["ocr"]["status"] == "failed"
    assert record["ocr"]["extractor"] == {"name": "fixture-ocr", "version": "1.0.0"}
    assert record["ocr"]["error"] == "fixed Vision unavailable"
    assert record["vision_review"]["status"] == "not_requested"


def test_complete_vision_without_a_reviewable_explanation_becomes_typed_reconciliation_failure(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-media.jsonl"
    cache_root = tmp_path / ".serenity" / "media-cache"
    image = base64.b64decode(TEXT_IMAGE.read_text(encoding="utf-8"))
    digest = hashlib.sha256(image).hexdigest()
    cache_root.mkdir(parents=True)
    (cache_root / digest).write_bytes(image)
    manifest.write_text(
        json.dumps(
            {
                "tweet_id": "tweet-1",
                "url": "https://fixture.example/alpha.png",
                "media_index": 0,
                "sha256": digest,
                "mime": "image/png",
                "dimensions": {"width": 1, "height": 1},
                "fetched_at": "2026-08-17T00:00:00Z",
                "fetch_status": "ok",
                "ocr": {
                    "status": "complete",
                    "text": "unresolved visual claim",
                    "extractor": {"name": "fixture-ocr", "version": "1.0.0"},
                    "source_sha256": digest,
                    "confidence": 0.98,
                    "caveat": "fixture",
                    "claim_status": "insufficient",
                    "extracted_at": "2026-08-17T00:00:00Z",
                    "audit": {"status": "approved", "reviewer": "fixture-reviewer"},
                    "error": None,
                },
                "ocr_status": "complete",
                "vision_status": "not_requested",
                "error": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    incomplete_vision = tmp_path / "incomplete_vision_fixture.py"
    incomplete_vision.write_text(
        """import json
print(json.dumps({
    'status': 'complete',
    'labels': ['chart'],
    'model_name': 'fixture-vision',
    'model_version': '1.0.0',
    'prompt_template_version': 'fixture-v1',
    'confidence': 0.9,
    'caveat': 'missing reviewable explanation',
    'audit_status': 'unreviewed',
    'reviewer': None,
    'error': None,
}))
""",
        encoding="utf-8",
    )

    _run_corpus(
        tmp_path,
        "extract-media",
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--vision-command",
        f"{shlex.quote(sys.executable)} {incomplete_vision} --input {{input}}",
    )

    record = json.loads(manifest.read_text(encoding="utf-8"))
    assert record["vision_review"]["status"] == "failed"
    assert record["vision_review"]["summary"] is None
    assert record["vision_review"]["supported_claims"] == []
    assert record["vision_review"]["audit"] == {"status": "needs_reconciliation", "reviewer": None}


def test_parallel_extraction_dedupes_sources_merges_manifest_order_and_resumes_after_out_of_order_completion(tmp_path: Path) -> None:
    manifest = tmp_path / "corpus-media.jsonl"
    checkpoint = tmp_path / "extract.checkpoint.json"
    cache_root = tmp_path / ".serenity" / "media-cache"
    cache_root.mkdir(parents=True)
    sources = {"slow": b"slow", "fast-a": b"fast-a", "fast-b": b"fast-b"}
    digests = {name: hashlib.sha256(body).hexdigest() for name, body in sources.items()}
    for body in sources.values():
        (cache_root / hashlib.sha256(body).hexdigest()).write_bytes(body)
    records = [
        {
            "tweet_id": f"tweet-{index}",
            "url": f"https://fixture.example/{name}",
            "media_index": 0,
            "sha256": digests[name],
            "mime": "image/png",
            "dimensions": {"width": 1, "height": 1},
            "fetched_at": "2026-08-17T00:00:00Z",
            "fetch_status": "ok",
            "ocr_status": "not_requested",
            "vision_status": "not_requested",
            "error": None,
        }
        for index, name in enumerate(("slow", "fast-a", "fast-b", "slow"), start=1)
    ]
    manifest.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    extractor = tmp_path / "delayed_ocr_fixture.py"
    extractor.write_text(
        """#!/usr/bin/env python3
from __future__ import annotations
import json
import sys
import time
from pathlib import Path

input_path = Path(sys.argv[sys.argv.index('--input') + 1])
if input_path.read_bytes() == b'slow':
    time.sleep(0.2)
else:
    time.sleep(0.01)
with Path('ocr-completion.log').open('a', encoding='utf-8') as log:
    log.write(input_path.name + '\\n')
print(json.dumps({
    'status': 'complete',
    'text': input_path.name,
    'extractor_name': 'delayed-fixture',
    'extractor_version': '1.0.0',
    'confidence': 0.99,
    'caveat': 'deterministic delayed fixture',
    'claim_status': 'established',
    'audit_status': 'approved',
    'reviewer': 'fixture-reviewer',
    'error': None,
}))
""",
        encoding="utf-8",
    )

    first = _run_corpus(
        tmp_path,
        "extract-media",
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--checkpoint",
        str(checkpoint),
        "--max-workers",
        "2",
        "--ocr-command",
        f"{shlex.quote(sys.executable)} {extractor} --input {{input}}",
    )

    assert first["extract"]["ocr_unique_sources_executed"] == 3
    assert first["extract"]["resumed_ocr_records"] == 1
    completion_order = (tmp_path / "ocr-completion.log").read_text(encoding="utf-8").splitlines()
    assert len(completion_order) == 3
    assert completion_order[0] != digests["slow"]
    enriched = [json.loads(line) for line in manifest.read_text(encoding="utf-8").splitlines()]
    assert [record["tweet_id"] for record in enriched] == ["tweet-1", "tweet-2", "tweet-3", "tweet-4"]
    assert [record["ocr"]["text"] for record in enriched] == [digests["slow"], digests["fast-a"], digests["fast-b"], digests["slow"]]
    assert json.loads(checkpoint.read_text(encoding="utf-8"))["complete"] is True

    resumed = _run_corpus(
        tmp_path,
        "extract-media",
        "--manifest",
        str(manifest),
        "--cache-root",
        str(cache_root),
        "--checkpoint",
        str(checkpoint),
        "--max-workers",
        "2",
        "--ocr-command",
        f"{shlex.quote(sys.executable)} {extractor} --input {{input}}",
    )

    assert resumed["extract"]["ocr_unique_sources_executed"] == 0
    assert resumed["extract"]["resumed_ocr_records"] == 4
    assert (tmp_path / "ocr-completion.log").read_text(encoding="utf-8").splitlines() == completion_order
