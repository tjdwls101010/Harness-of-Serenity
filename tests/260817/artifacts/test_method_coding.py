from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from serenity_core.method import (
    MethodArtifactError,
    MethodArtifactStore,
    aggregate_method_codings,
    build_method_packets,
    canonical_json,
    compile_method_artifact,
    validate_method_artifact,
    write_blind_packets,
)


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "method" / "source.json"
METHOD_CLI = Path(__file__).resolve().parents[3] / "scripts" / "serenity_method.py"
METHOD_ARTIFACTS = Path(__file__).resolve().parents[3] / "method"


def _source() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _rows() -> list[dict]:
    return _source()["rows"]


def _annotations() -> list[dict]:
    return _source()["annotations"]


def _artifact_content_hash(document: dict) -> str:
    body = {key: value for key, value in document.items() if key != "content_hash"}
    return hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _documents(chunks: dict) -> tuple[dict, dict, dict]:
    chunk_id = chunks["chunks"][0]["chunk_id"]
    counterexample_chunk_id = chunks["chunks"][1]["chunk_id"]
    codebook = {
        "format": "serenity-method-codebook/1",
        "axes": [
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
        ],
        "codes": [
            {
                "code_id": "code-qualified-capacity",
                "axis": "value_capture",
                "label": "qualified capacity",
                "source_refs": [chunk_id],
                "rationale": "The chunk attributes pricing power to scarce qualification capacity.",
            }
        ],
    }
    coding = {
        "format": "serenity-method-coding/1",
        "units": [
            {
                "unit_id": "unit-001",
                "source_refs": [chunk_id],
                "trigger": "A supplier qualification is scarce.",
                "evidence_sought": "Qualification lead time and alternative supply evidence.",
                "inference": "The issuer may have pricing power.",
                "action_horizon": {"action": "monitor", "horizon": "next filing"},
                "falsifier": "A qualified substitute enters production.",
                "code_ids": ["code-qualified-capacity"],
            },
            {
                "unit_id": "unit-002",
                "source_refs": [counterexample_chunk_id],
                "trigger": "A later source describes a qualified substitute.",
                "evidence_sought": "Evidence that the alternative is commercially available.",
                "inference": "Pricing power may not persist.",
                "action_horizon": {"action": "retest", "horizon": "next filing"},
                "falsifier": "The alternative never reaches production.",
                "code_ids": ["code-qualified-capacity"],
            }
        ],
    }
    ledger = {
        "format": "serenity-method-claim-ledger/1",
        "claims": [
            {
                "claim_id": "claim-qualified-capacity",
                "claim": "Qualification scarcity can support pricing power.",
                "provenance_tag": "sourced",
                "representative_refs": ["unit-001"],
                "counterexample_refs": ["unit-002"],
                "code_refs": ["code-qualified-capacity"],
            }
        ],
    }
    return codebook, coding, ledger


def test_build_blind_chunks_redacts_ticker_date_and_answer_key_but_preserves_source_hashes() -> None:
    chunks, source_index = build_method_packets(_rows(), _annotations())

    assert chunks["leak_policy"] == {
        "excluded_fields": ["answer_key", "created_at", "date", "ticker"],
        "redactions": {"date": "[DATE]", "ticker": "[TICKER]"},
    }
    assert len(chunks["chunks"]) == 2
    rendered = " ".join(chunk["text"] for chunk in chunks["chunks"])
    assert "ACME" not in rendered
    assert "2024-02-14" not in rendered
    assert "BUY" not in rendered
    assert "[TICKER]" in rendered
    assert all(len(chunk["source_hash"]) == 64 for chunk in chunks["chunks"])
    assert "tweet-001" not in json.dumps(chunks)
    assert "source_index" not in chunks
    assert chunks["source_index_hash"] == source_index["content_hash"]
    assert source_index["cleanroom_policy"] == {
        "forbidden_in_cleanroom_packet": True,
        "forbidden_metadata": ["database", "media_id", "representative_ticker", "source_row_id", "source_type"],
    }
    assert source_index["entries"][0]["source_row_id"] == "tweet-001"
    assert source_index["entries"][1]["media_id"] == "media-001"
    assert chunks["content_hash"]


def test_compile_reconciles_traceability_and_rejects_an_unverified_hard_gate(tmp_path: Path) -> None:
    chunks, source_index = build_method_packets(_rows(), _annotations())
    codebook, coding, ledger = _documents(chunks)

    artifact = compile_method_artifact(
        chunks=chunks, source_index=source_index, codebook=codebook, coding=coding, claim_ledger=ledger
    )

    assert artifact["reconciliation"] == {
        "chunks": 2,
        "codes": 1,
        "coding_units": 2,
        "claims": 1,
        "traceable_codes": 1,
        "traceable_claims": 1,
    }
    assert artifact["input_hashes"]["source_index"] == source_index["content_hash"]
    assert "source_index" not in artifact
    assert validate_method_artifact(artifact, source_index=source_index) == artifact

    ledger["claims"][0] = {
        "claim_id": "claim-unverified-gate",
        "claim": "A tentative rule.",
        "provenance_tag": "unverified",
        "hard_gate": True,
    }
    with pytest.raises(MethodArtifactError, match="unverified"):
        compile_method_artifact(
            chunks=chunks, source_index=source_index, codebook=codebook, coding=coding, claim_ledger=ledger
        )

    stored = MethodArtifactStore(tmp_path).store(artifact, source_index=source_index)
    persisted = json.loads(Path(stored["path"]).read_text(encoding="utf-8"))
    assert persisted == artifact
    assert stored["content_hash"] == artifact["content_hash"]
    assert Path(stored["source_index_path"]).is_file()


def test_compile_rejects_codes_without_a_source_or_rationale() -> None:
    chunks, source_index = build_method_packets(_rows(), _annotations())
    codebook, coding, ledger = _documents(chunks)
    codebook["codes"][0].pop("rationale")

    with pytest.raises(MethodArtifactError, match="rationale"):
        compile_method_artifact(
            chunks=chunks, source_index=source_index, codebook=codebook, coding=coding, claim_ledger=ledger
        )


def test_sourced_claim_requires_an_independent_counterexample_or_a_recorded_empty_search() -> None:
    chunks, source_index = build_method_packets(_rows(), _annotations())
    codebook, coding, ledger = _documents(chunks)
    ledger["claims"][0]["counterexample_refs"] = ["unit-001"]

    with pytest.raises(MethodArtifactError, match="counterexample"):
        compile_method_artifact(
            chunks=chunks, source_index=source_index, codebook=codebook, coding=coding, claim_ledger=ledger
        )

    ledger["claims"][0]["counterexample_refs"] = []
    ledger["claims"][0]["counterexample_search_scope"] = "all supplied blind chunks"
    ledger["claims"][0]["counterexample_status"] = "none_found"
    coding["units"] = coding["units"][:1]
    artifact = compile_method_artifact(
        chunks=chunks, source_index=source_index, codebook=codebook, coding=coding, claim_ledger=ledger
    )
    assert artifact["reconciliation"]["traceable_claims"] == 1


def test_compile_rejects_an_orphan_code_or_coding_unit() -> None:
    chunks, source_index = build_method_packets(_rows(), _annotations())
    codebook, coding, ledger = _documents(chunks)
    codebook["codes"].append(
        {
            "code_id": "code-orphaned",
            "axis": "lens",
            "label": "orphaned",
            "source_refs": [chunks["chunks"][0]["chunk_id"]],
            "rationale": "This must not silently inflate traceability coverage.",
        }
    )

    with pytest.raises(MethodArtifactError, match="orphan code"):
        compile_method_artifact(
            chunks=chunks, source_index=source_index, codebook=codebook, coding=coding, claim_ledger=ledger
        )


def test_public_validate_keeps_unadopted_coding_units_and_rejects_dangling_claim_refs(tmp_path: Path) -> None:
    chunks, source_index = build_method_packets(_rows(), _annotations())
    codebook, coding, ledger = _documents(chunks)
    ledger["claims"][0]["counterexample_refs"] = []
    ledger["claims"][0]["counterexample_search_scope"] = "all supplied blind chunks"
    ledger["claims"][0]["counterexample_status"] = "none_found"
    for document in (codebook, coding, ledger):
        document["content_hash"] = _artifact_content_hash(document)
    paths = {"chunks": tmp_path / "chunks.json", "source_index": tmp_path / "source-index.json"}
    paths.update({name: tmp_path / f"{name}.json" for name in ("codebook", "coding", "ledger")})
    for name, document in (("chunks", chunks), ("source_index", source_index), ("codebook", codebook), ("coding", coding), ("ledger", ledger)):
        paths[name].write_text(canonical_json(document) + "\n", encoding="utf-8")
    argv = [
        sys.executable,
        str(METHOD_CLI),
        "validate",
        "--chunks",
        str(paths["chunks"]),
        "--source-index",
        str(paths["source_index"]),
        "--codebook",
        str(paths["codebook"]),
        "--coding",
        str(paths["coding"]),
        "--ledger",
        str(paths["ledger"]),
    ]

    validated = subprocess.run(argv, check=False, capture_output=True, text=True)
    assert validated.returncode == 0, validated.stderr or validated.stdout
    assert json.loads(validated.stdout)["reconciliation"] == {
        "chunks": 2,
        "codes": 1,
        "coding_units": 2,
        "claims": 1,
        "traceable_codes": 1,
        "traceable_claims": 1,
    }

    dangling = json.loads(canonical_json(ledger))
    dangling["claims"][0]["representative_refs"] = ["unit-missing"]
    dangling["content_hash"] = _artifact_content_hash(dangling)
    paths["ledger"].write_text(canonical_json(dangling) + "\n", encoding="utf-8")
    rejected = subprocess.run(argv, check=False, capture_output=True, text=True)
    assert rejected.returncode == 2
    assert "traceable" in json.loads(rejected.stdout)["error"]["message"]

    paths["ledger"].write_text(canonical_json(ledger) + "\n", encoding="utf-8")
    tampered_coding = json.loads(canonical_json(coding))
    tampered_coding["units"][1]["trigger"] = "tampered after hashing"
    paths["coding"].write_text(canonical_json(tampered_coding) + "\n", encoding="utf-8")
    rejected = subprocess.run(argv, check=False, capture_output=True, text=True)
    assert rejected.returncode == 2
    assert "content_hash" in json.loads(rejected.stdout)["error"]["message"]


def test_public_cli_builds_and_stores_a_hashed_method_artifact(tmp_path: Path) -> None:
    rows = tmp_path / "rows.json"
    annotations = tmp_path / "annotations.json"
    chunks_path = tmp_path / "chunks.json"
    source_index_path = tmp_path / "source-index.json"
    rows.write_text(json.dumps(_rows()), encoding="utf-8")
    annotations.write_text(json.dumps(_annotations()), encoding="utf-8")

    built = subprocess.run(
        [
            sys.executable,
            str(METHOD_CLI),
            "chunks",
            "--rows",
            str(rows),
            "--annotations",
            str(annotations),
            "--out",
            str(chunks_path),
            "--source-index-out",
            str(source_index_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert built.returncode == 0, built.stderr or built.stdout
    assert json.loads(built.stdout)["chunks"] == 2
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    source_index = json.loads(source_index_path.read_text(encoding="utf-8"))
    assert "tweet-001" not in chunks_path.read_text(encoding="utf-8")
    assert "tweet-001" in source_index_path.read_text(encoding="utf-8")
    codebook, coding, ledger = _documents(chunks)
    paths = {}
    for name, document in (("codebook", codebook), ("coding", coding), ("ledger", ledger)):
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths[name] = path

    stored = subprocess.run(
        [
            sys.executable,
            str(METHOD_CLI),
            "store",
            "--chunks",
            str(chunks_path),
            "--codebook",
            str(paths["codebook"]),
            "--coding",
            str(paths["coding"]),
            "--ledger",
            str(paths["ledger"]),
            "--source-index",
            str(source_index_path),
            "--root",
            str(tmp_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert stored.returncode == 0, stored.stderr or stored.stdout
    result = json.loads(stored.stdout)
    assert result["reconciliation"]["claims"] == 1
    assert Path(result["stored"]["path"]).is_file()


def test_chunks_db_reads_only_corpus_input_columns_in_stable_id_order_and_keeps_type_private(tmp_path: Path) -> None:
    database = tmp_path / "corpus.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            """
            CREATE TABLE tweets (id TEXT PRIMARY KEY, type TEXT, content TEXT, tickers TEXT, media TEXT, created_at TEXT);
            INSERT INTO tweets VALUES ('tweet-b', 'reply', 'ACME reply', '["ACME"]', '[]', '2025-02-02');
            INSERT INTO tweets VALUES ('tweet-a', 'post', 'ACME post', '["ACME"]', '[]', '2025-02-01');
            INSERT INTO tweets VALUES ('tweet-c', 'subscriber', 'quiet note', '[]', '[]', '2025-02-03');
            """
        )
        connection.commit()
    finally:
        connection.close()
    chunks_path = tmp_path / "chunks.json"
    source_index_path = tmp_path / "source-index.json"

    completed = subprocess.run(
        [
            sys.executable,
            str(METHOD_CLI),
            "chunks-db",
            "--db",
            str(database),
            "--out",
            str(chunks_path),
            "--source-index-out",
            str(source_index_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    source_index = json.loads(source_index_path.read_text(encoding="utf-8"))
    assert [chunk["text"] for chunk in chunks["chunks"]] == ["[TICKER] post", "[TICKER] reply", "quiet note"]
    assert "subscriber" not in json.dumps(chunks)
    assert source_index["database"]["query"] == "SELECT id, type, content, tickers, media FROM tweets ORDER BY id"
    assert len(source_index["database"]["sha256"]) == 64
    assert [entry["source_type"] for entry in source_index["entries"]] == ["post", "reply", "subscriber"]


def test_chunks_db_writes_deterministic_blind_packets_and_a_hash_manifest(tmp_path: Path) -> None:
    database = tmp_path / "corpus.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            """
            CREATE TABLE tweets (id TEXT PRIMARY KEY, type TEXT, content TEXT, tickers TEXT, media TEXT);
            INSERT INTO tweets VALUES ('tweet-3', 'subscriber', 'third', '[]', '[]');
            INSERT INTO tweets VALUES ('tweet-1', 'post', 'first', '[]', '[]');
            INSERT INTO tweets VALUES ('tweet-2', 'reply', 'second', '[]', '[]');
            """
        )
        connection.commit()
    finally:
        connection.close()
    chunks_path = tmp_path / "chunks.json"
    source_index_path = tmp_path / "source-index.json"
    packet_dir = tmp_path / "packets"
    command = [
        sys.executable,
        str(METHOD_CLI),
        "chunks-db",
        "--db",
        str(database),
        "--out",
        str(chunks_path),
        "--source-index-out",
        str(source_index_path),
        "--batch-size",
        "2",
        "--packet-dir",
        str(packet_dir),
    ]

    first = subprocess.run(command, check=False, capture_output=True, text=True)
    assert first.returncode == 0, first.stderr or first.stdout
    manifest_path = packet_dir / "packet-manifest.json"
    first_manifest = manifest_path.read_text(encoding="utf-8")
    manifest = json.loads(first_manifest)
    assert [(entry["count"], entry["chunk_ids"]) for entry in manifest["packets"]] == [
        (2, [json.loads(chunks_path.read_text(encoding="utf-8"))["chunks"][0]["chunk_id"], json.loads(chunks_path.read_text(encoding="utf-8"))["chunks"][1]["chunk_id"]]),
        (1, [json.loads(chunks_path.read_text(encoding="utf-8"))["chunks"][2]["chunk_id"]]),
    ]
    assert (packet_dir / "packet-001.json").is_file()
    assert (packet_dir / "packet-002.json").is_file()
    packet_text = (packet_dir / "packet-001.json").read_text(encoding="utf-8")
    assert "source_row_id" not in packet_text
    assert "source_type" not in packet_text

    second = subprocess.run(command, check=False, capture_output=True, text=True)
    assert second.returncode == 0, second.stderr or second.stdout
    assert manifest_path.read_text(encoding="utf-8") == first_manifest


def test_chunks_db_full_audit_excludes_terminal_unavailable_fetches_and_reports_them_privately(tmp_path: Path) -> None:
    database = tmp_path / "corpus.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            """
            CREATE TABLE tweets (id TEXT PRIMARY KEY, type TEXT, content TEXT, tickers TEXT, media TEXT);
            INSERT INTO tweets VALUES ('tweet-1', 'post', 'ACME text thesis', '["ACME"]', '["https://media.example/one.png", "https://media.example/two.png"]');
            """
        )
        connection.commit()
    finally:
        connection.close()
    approved_sha = "a" * 64
    manifest = tmp_path / "media.json"
    manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "tweet_id": "tweet-1",
                        "url": "https://media.example/one.png",
                        "media_index": 0,
                        "fetch_status": "ok",
                        "sha256": approved_sha,
                        "ocr": {
                            "status": "complete",
                            "text": "ACME allocation remains qualified.",
                            "source_sha256": approved_sha,
                            "audit": {"status": "unreviewed"},
                        },
                        "vision_review": {
                            "status": "complete",
                            "labels": ["diagram", "capacity"],
                            "claim_explanation": "The image supports an allocation constraint.",
                            "caveat": "Illustrative only.",
                            "source_sha256": approved_sha,
                            "audit": {"status": "approved"},
                        },
                    },
                    {
                        "tweet_id": "tweet-1",
                        "url": "https://media.example/two.png",
                        "media_index": 1,
                        "fetch_status": "failed",
                        "error": "HTTPError: HTTP Error 404: Not Found",
                        "fetched_at": "2026-08-17T04:53:59.807206Z",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    chunks_path = tmp_path / "chunks.json"
    source_index_path = tmp_path / "source-index.json"
    command = [
        sys.executable,
        str(METHOD_CLI),
        "chunks-db",
        "--db",
        str(database),
        "--media-manifest",
        str(manifest),
        "--out",
        str(chunks_path),
        "--source-index-out",
        str(source_index_path),
        "--batch-size",
        "10",
        "--packet-dir",
        str(tmp_path / "packets"),
    ]

    completed = subprocess.run([*command, "--full-audit"], check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr or completed.stdout
    result = json.loads(completed.stdout)
    assert result["media_derivatives"] == {
        "coverage": {
            "available_relations": 1,
            "denominator": 2,
            "incomplete": 0,
            "manifest_records": 2,
            "unavailable_relations": 1,
            "unique_available_media": 1,
        },
        "excluded_media": {"unavailable_fetch": 1},
        "failure_taxonomy": {},
        "status": "complete",
    }
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    source_index = json.loads(source_index_path.read_text(encoding="utf-8"))
    assert [chunk["kind"] for chunk in chunks["chunks"]] == ["text", "media"]
    media_text = chunks["chunks"][1]["text"]
    assert "ACME" not in media_text
    assert "Review labels: diagram, capacity" in media_text
    assert "The image supports an allocation constraint." in media_text
    assert "Illustrative only." in media_text
    assert "https://media.example" not in json.dumps(chunks)
    assert "tweet-1" not in json.dumps(chunks)
    assert approved_sha not in json.dumps(chunks)
    assert source_index["entries"][1]["media_source_sha256"] == approved_sha
    assert source_index["media_manifest"]["coverage"] == result["media_derivatives"]["coverage"]
    assert source_index["media_manifest"]["excluded_relations"] == [
        {
            "media_index": 1,
            "reason": "HTTPError: HTTP Error 404: Not Found",
            "source_row_id": "tweet-1",
            "status": "unavailable_fetch",
            "provenance": {"fetch_status": "failed", "fetched_at": "2026-08-17T04:53:59.807206Z"},
        }
    ]
    packet_manifest = json.loads((tmp_path / "packets" / "packet-manifest.json").read_text(encoding="utf-8"))
    assert packet_manifest["media_derivatives"] == result["media_derivatives"]

    bad = json.loads(manifest.read_text(encoding="utf-8"))
    bad["records"][0]["ocr"]["source_sha256"] = "c" * 64
    manifest.write_text(json.dumps(bad), encoding="utf-8")
    rejected = subprocess.run(command, check=False, capture_output=True, text=True)
    assert rejected.returncode == 2
    assert "provenance mismatch" in json.loads(rejected.stdout)["error"]["message"]


def test_chunks_db_deduplicates_media_sha_but_retains_each_private_relation_ref(tmp_path: Path) -> None:
    database = tmp_path / "corpus.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            """
            CREATE TABLE tweets (id TEXT PRIMARY KEY, type TEXT, content TEXT, tickers TEXT, media TEXT);
            INSERT INTO tweets VALUES ('tweet-1', 'post', 'first', '[]', '["https://media.example/shared-a.png"]');
            INSERT INTO tweets VALUES ('tweet-2', 'reply', 'second', '[]', '["https://media.example/shared-b.png"]');
            """
        )
        connection.commit()
    finally:
        connection.close()
    source_sha = "f" * 64
    manifest = tmp_path / "media.json"
    manifest.write_text(
        json.dumps(
            {
                "records": [
                    {
                        "tweet_id": "tweet-1",
                        "url": "https://media.example/shared-a.png",
                        "media_index": 0,
                        "fetch_status": "ok",
                        "sha256": source_sha,
                        "ocr": {"status": "complete", "text": "shared 2026-08-17 media evidence", "source_sha256": source_sha, "audit": {"status": "approved"}},
                        "vision_review": {"status": "not_required", "source_sha256": source_sha, "audit": {"status": "approved"}},
                    },
                    {
                        "tweet_id": "tweet-2",
                        "url": "https://media.example/shared-b.png",
                        "media_index": 0,
                        "fetch_status": "ok",
                        "sha256": source_sha,
                        "ocr": {"status": "complete", "text": "shared 2026-08-17 media evidence", "source_sha256": source_sha, "audit": {"status": "approved"}},
                        "vision_review": {"status": "not_required", "source_sha256": source_sha, "audit": {"status": "approved"}},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    chunks_path = tmp_path / "chunks.json"
    source_index_path = tmp_path / "source-index.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(METHOD_CLI),
            "chunks-db",
            "--db",
            str(database),
            "--media-manifest",
            str(manifest),
            "--full-audit",
            "--out",
            str(chunks_path),
            "--source-index-out",
            str(source_index_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    result = json.loads(completed.stdout)
    assert result["chunks"] == 3
    assert result["media_derivatives"]["coverage"] == {
        "available_relations": 2,
        "denominator": 2,
        "incomplete": 0,
        "manifest_records": 2,
        "unavailable_relations": 0,
        "unique_available_media": 1,
    }
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    media = [chunk for chunk in chunks["chunks"] if chunk["kind"] == "media"]
    assert len(media) == 1
    assert len(media[0]["source_refs"]) == 2
    assert "2026-08-17" not in media[0]["text"]
    source_index = json.loads(source_index_path.read_text(encoding="utf-8"))
    media_entries = [entry for entry in source_index["entries"] if entry["media_id"] is not None]
    assert [entry["source_ref"] for entry in media_entries] == media[0]["source_refs"]
    assert [entry["relation_provenance"]["media_index"] for entry in media_entries] == [0, 0]
    assert all(len(entry["relation_provenance"]["manifest_record_hash"]) == 64 for entry in media_entries)
    assert all(entry["source_hash"] == media[0]["source_hash"] for entry in media_entries)


def test_media_derivative_batches_append_after_unchanged_text_packets(tmp_path: Path) -> None:
    database = tmp_path / "corpus.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            """
            CREATE TABLE tweets (id TEXT PRIMARY KEY, type TEXT, content TEXT, tickers TEXT, media TEXT);
            INSERT INTO tweets VALUES ('tweet-1', 'post', 'first', '[]', '["https://media.example/one.png"]');
            INSERT INTO tweets VALUES ('tweet-2', 'reply', 'second', '[]', '[]');
            INSERT INTO tweets VALUES ('tweet-3', 'subscriber', 'third', '[]', '[]');
            """
        )
        connection.commit()
    finally:
        connection.close()
    baseline_dir = tmp_path / "baseline-packets"
    with_media_dir = tmp_path / "with-media-packets"
    common = [sys.executable, str(METHOD_CLI), "chunks-db", "--db", str(database), "--out", str(tmp_path / "chunks.json"), "--source-index-out", str(tmp_path / "source-index.json"), "--batch-size", "2"]
    baseline = subprocess.run([*common, "--packet-dir", str(baseline_dir)], check=False, capture_output=True, text=True)
    assert baseline.returncode == 0, baseline.stderr or baseline.stdout
    baseline_packet = (baseline_dir / "packet-001.json").read_bytes()
    baseline_packet_two = (baseline_dir / "packet-002.json").read_bytes()
    source_sha = "d" * 64
    manifest = tmp_path / "media.json"
    manifest.write_text(json.dumps({"records": [{"tweet_id": "tweet-1", "url": "https://media.example/one.png", "media_index": 0, "fetch_status": "ok", "sha256": source_sha, "ocr": {"status": "complete", "text": "media text", "source_sha256": source_sha, "audit": {"status": "approved"}}, "vision_review": {"status": "not_required", "source_sha256": source_sha, "audit": {"status": "approved"}}}]}), encoding="utf-8")

    enriched = subprocess.run([*common, "--media-manifest", str(manifest), "--packet-dir", str(with_media_dir)], check=False, capture_output=True, text=True)
    assert enriched.returncode == 0, enriched.stderr or enriched.stdout
    assert (with_media_dir / "packet-001.json").read_bytes() == baseline_packet
    assert (with_media_dir / "packet-002.json").read_bytes() == baseline_packet_two
    assert (with_media_dir / "packet-003.json").is_file()


def test_chunks_db_accepts_jsonl_manifest_for_vision_review_and_rejects_bad_lines_before_writes(tmp_path: Path) -> None:
    database = tmp_path / "corpus.db"
    connection = sqlite3.connect(database)
    try:
        connection.executescript(
            """
            CREATE TABLE tweets (id TEXT PRIMARY KEY, type TEXT, content TEXT, tickers TEXT, media TEXT);
            INSERT INTO tweets VALUES ('tweet-1', 'post', 'text', '[]', '["https://media.example/chart.png"]');
            """
        )
        connection.commit()
    finally:
        connection.close()
    source_sha = "e" * 64
    vision_record = {
        "tweet_id": "tweet-1",
        "url": "https://media.example/chart.png",
        "media_index": 0,
        "fetch_status": "ok",
        "sha256": source_sha,
        "ocr": {
            "status": "complete",
            "text": "unreliable chart OCR",
            "claim_status": "insufficient",
            "source_sha256": source_sha,
            "audit": {"status": "approved"},
        },
        "vision_review": {
            "status": "complete",
            "labels": ["chart"],
            "claim_explanation": "The chart supports a capacity ramp.",
            "caveat": "Read against filing evidence.",
            "source_sha256": source_sha,
            "audit": {"status": "approved"},
        },
    }
    manifest = tmp_path / "media.jsonl"
    manifest.write_text(json.dumps(vision_record) + "\n", encoding="utf-8")
    chunks_path = tmp_path / "chunks.json"
    source_index_path = tmp_path / "source-index.json"
    command = [
        sys.executable,
        str(METHOD_CLI),
        "chunks-db",
        "--db",
        str(database),
        "--media-manifest",
        str(manifest),
        "--full-audit",
        "--out",
        str(chunks_path),
        "--source-index-out",
        str(source_index_path),
    ]

    accepted = subprocess.run(command, check=False, capture_output=True, text=True)
    assert accepted.returncode == 0, accepted.stderr or accepted.stdout
    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    assert chunks["media_derivatives"]["status"] == "complete"
    assert chunks["chunks"][-1]["text"] == "Review labels: chart\nThe chart supports a capacity ramp.\nRead against filing evidence."

    for name, contents in {
        "malformed.jsonl": "{not JSON}\n",
        "mixed.jsonl": json.dumps({"records": [vision_record]}) + "\n",
        "non-object.jsonl": "[]\n",
    }.items():
        malformed = tmp_path / name
        malformed.write_text(contents, encoding="utf-8")
        bad_chunks = tmp_path / f"{name}.chunks.json"
        bad_index = tmp_path / f"{name}.index.json"
        rejected = subprocess.run(
            [
                sys.executable,
                str(METHOD_CLI),
                "chunks-db",
                "--db",
                str(database),
                "--media-manifest",
                str(malformed),
                "--out",
                str(bad_chunks),
                "--source-index-out",
                str(bad_index),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert rejected.returncode == 2
        assert json.loads(rejected.stdout)["error"]["code"] == "usage_or_schema"
        assert not bad_chunks.exists()
        assert not bad_index.exists()


def test_aggregate_method_codings_requires_one_completed_result_per_packet_and_preserves_candidates(tmp_path: Path) -> None:
    chunks, _ = build_method_packets(
        [
            {"source_row_id": "row-001", "source_type": "post", "text": "first blind observation"},
            {"source_row_id": "row-002", "source_type": "reply", "text": "second blind observation"},
        ]
    )
    packet_dir = tmp_path / "packets"
    manifest = write_blind_packets(chunks, packet_dir=packet_dir, batch_size=1)
    manifest_path = packet_dir / "packet-manifest.json"
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    completed_results: list[dict] = []
    selection: list[dict[str, str]] = []
    for ordinal, packet_record in enumerate(manifest["packets"], start=1):
        packet_path = packet_dir / packet_record["path"]
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        chunk_id = packet["chunks"][0]["chunk_id"]
        output = {
            "schema_id": "urn:serenity:schema:method-coding-output:1",
            "packet_id": packet_record["packet_id"],
            "packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            "dispositions": [
                {
                    "chunk_id": chunk_id,
                    "disposition": "coded",
                    "coding": {
                        "trigger": f"trigger {ordinal}",
                        "evidence_sought": f"evidence {ordinal}",
                        "inference": f"inference {ordinal}",
                        "action_horizon": {"action": "monitor", "horizon": f"horizon {ordinal}"},
                        "falsifier": f"falsifier {ordinal}",
                        "codes": [{"axis": "value_capture", "label": "capacity lock" if ordinal == 1 else "capacity locking", "rationale": f"rationale {ordinal}"}],
                    },
                    "uncertainty_notes": [f"uncertainty {ordinal}"],
                    "contradiction_notes": [f"contradiction {ordinal}"],
                }
            ],
        }
        run_dir = tmp_path / "runs" / packet_record["packet_id"]
        run_dir.mkdir(parents=True)
        output_path = run_dir / "model-output.json"
        output_path.write_text(canonical_json(output) + "\n", encoding="utf-8")
        execution = {
            "format": "serenity-method-coding-execution/1",
            "packet_id": packet_record["packet_id"],
            "status": "completed",
            "output_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
            "package_sha256": {packet_record["path"]: output["packet_sha256"]},
            "full_manifest_content_hash": manifest["content_hash"],
            "full_manifest_sha256": manifest_sha256,
            "selected_packet_ids": [record["packet_id"] for record in manifest["packets"]],
        }
        execution_path = run_dir / "execution.json"
        execution_path.write_text(canonical_json(execution) + "\n", encoding="utf-8")
        completed_results.append({"execution": execution, "output": output, "output_sha256": execution["output_sha256"], "manifest_sha256": manifest_sha256})
        selection.append({"execution": str(execution_path), "output": str(output_path)})

    candidate = aggregate_method_codings(manifest, completed_results)
    assert [code["label"] for code in candidate["codebook"]["codes"]] == ["capacity lock", "capacity locking"]
    assert [unit["uncertainty_notes"] for unit in candidate["coding"]["units"]] == [["uncertainty 1"], ["uncertainty 2"]]
    assert [claim["provenance_tag"] for claim in candidate["claim_ledger"]["claims"]] == ["unverified", "unverified"]
    assert {key: candidate["candidate_digest"]["coverage"][key] for key in ("chunks", "coded_chunks", "no_reusable_move_chunks", "packets")} == {"chunks": 2, "coded_chunks": 2, "no_reusable_move_chunks": 0, "packets": 2}
    digest_labels = candidate["candidate_digest"]["bounded_summary"]["axis_label_frequency"]
    value_capture = next(item for item in digest_labels if item["axis"] == "value_capture")
    assert [(item["label"], item["frequency"]) for item in value_capture["entries"]] == [("capacity lock", 1), ("capacity locking", 1)]
    representative = value_capture["entries"][0]["representatives"][0]
    assert representative["semantic_content"] == {
        "trigger": {"text": "trigger 1", "omitted_character_count": 0, "omitted_hash": hashlib.sha256(b'""').hexdigest()},
        "evidence_sought": {"text": "evidence 1", "omitted_character_count": 0, "omitted_hash": hashlib.sha256(b'""').hexdigest()},
        "inference": {"text": "inference 1", "omitted_character_count": 0, "omitted_hash": hashlib.sha256(b'""').hexdigest()},
        "action_horizon": {"action": {"text": "monitor", "omitted_character_count": 0, "omitted_hash": hashlib.sha256(b'""').hexdigest()}, "horizon": {"text": "horizon 1", "omitted_character_count": 0, "omitted_hash": hashlib.sha256(b'""').hexdigest()}},
        "falsifier": {"text": "falsifier 1", "omitted_character_count": 0, "omitted_hash": hashlib.sha256(b'""').hexdigest()},
        "matching_code": {"axis": "value_capture", "label": "capacity lock", "rationale": {"text": "rationale 1", "omitted_character_count": 0, "omitted_hash": hashlib.sha256(b'""').hexdigest()}},
        "uncertainty_notes": [{"text": "uncertainty 1", "omitted_character_count": 0, "omitted_hash": hashlib.sha256(b'""').hexdigest()}],
        "contradiction_notes": [{"text": "contradiction 1", "omitted_character_count": 0, "omitted_hash": hashlib.sha256(b'""').hexdigest()}],
    }
    assert candidate["candidate_digest"]["bounded_summary"]["policy_hash"]

    unit_ids = [unit["unit_id"] for unit in candidate["coding"]["units"]]
    code_ids = [code["code_id"] for code in candidate["codebook"]["codes"]]
    digest_path = tmp_path / "candidate-digest.json"
    digest_path.write_text(canonical_json(candidate["candidate_digest"]) + "\n", encoding="utf-8")
    digest_sha256 = hashlib.sha256(digest_path.read_bytes()).hexdigest()
    synthesis = {
        "schema_id": "urn:serenity:schema:method-claim-synthesis:1",
        "format": "serenity-method-claim-synthesis/1",
        "candidate_digest_content_hash": candidate["candidate_digest"]["content_hash"],
        "candidate_digest_sha256": digest_sha256,
        "claims": [
            {
                "claim_id": "claim-capacity",
                "claim": "Capacity language may be a reusable candidate.",
                "provenance_tag": "sourced",
                "shown_unit_refs": [unit_ids[0]],
                "shown_code_refs": [{"axis": "value_capture", "label": "capacity lock"}, {"axis": "value_capture", "label": "capacity locking"}],
                "counterexample_refs": [unit_ids[1]],
                "counterexample_search_scope": "shown candidate counterexample units",
                "counterexample_status": "found",
                "why": "Both shown units frame the same move differently.",
                "uncertainty_notes": ["The sample is narrow."],
                "contradiction_notes": ["A counterexample is present."],
            }
        ],
    }
    synthesized = aggregate_method_codings(manifest, completed_results, synthesis=synthesis, candidate_digest=candidate["candidate_digest"], candidate_digest_sha256=digest_sha256)
    assert synthesized["claim_ledger"]["claims"] == [
        {
            "claim_id": "claim-capacity",
            "claim": "Capacity language may be a reusable candidate.",
            "provenance_tag": "sourced",
            "representative_refs": [unit_ids[0]],
            "counterexample_refs": [unit_ids[1]],
            "code_refs": code_ids,
            "counterexample_search_scope": "shown candidate counterexample units",
            "counterexample_status": "found",
            "why": "Both shown units frame the same move differently.",
            "uncertainty_notes": ["The sample is narrow."],
            "contradiction_notes": ["A counterexample is present."],
            "hard_gate": False,
        }
    ]
    assert synthesized["candidate_digest"] == candidate["candidate_digest"]
    for invalid_synthesis in (
        {**synthesis, "candidate_digest_content_hash": "0" * 64},
        {**synthesis, "claims": [{**synthesis["claims"][0], "shown_code_refs": [{"axis": "value_capture", "label": "unknown"}]}]},
        {**synthesis, "claims": [{**synthesis["claims"][0], "provenance_tag": "augmented"}]},
    ):
        with pytest.raises(MethodArtifactError):
            aggregate_method_codings(manifest, completed_results, synthesis=invalid_synthesis, candidate_digest=candidate["candidate_digest"], candidate_digest_sha256=digest_sha256)
    with pytest.raises(MethodArtifactError, match="candidate digest SHA"):
        aggregate_method_codings(manifest, completed_results, synthesis=synthesis, candidate_digest=candidate["candidate_digest"], candidate_digest_sha256="0" * 64)
    augmentations = {
        "format": "serenity-method-augmentations/1",
        "claims": [
            {
                "claim_id": "claim-safety",
                "claim": "Keep an explicit safety check.",
                "provenance_tag": "augmented",
                "augmentation_rationale": "A deliberate v2 engineering addition.",
                "why": "The synthesis boundary cannot invent engineering safeguards.",
                "uncertainty_notes": ["Needs periodic review."],
                "contradiction_notes": [],
            }
        ],
    }
    augmented = aggregate_method_codings(manifest, completed_results, synthesis=synthesis, candidate_digest=candidate["candidate_digest"], candidate_digest_sha256=digest_sha256, augmentations=augmentations)
    assert [claim["provenance_tag"] for claim in augmented["claim_ledger"]["claims"]] == ["sourced", "augmented"]

    for invalid in (
        completed_results[:-1],
        [completed_results[0], completed_results[0]],
        [{**completed_results[0], "execution": {**completed_results[0]["execution"], "status": "blocked"}}, *completed_results[1:]],
        [{**completed_results[0], "output": {**completed_results[0]["output"], "packet_sha256": "0" * 64}}, *completed_results[1:]],
        [{**completed_results[0], "output": {key: value for key, value in completed_results[0]["output"].items() if key != "schema_id"}}, *completed_results[1:]],
    ):
        with pytest.raises(MethodArtifactError):
            aggregate_method_codings(manifest, invalid)

    selection_path = tmp_path / "completed-results.json"
    selection_path.write_text(canonical_json(selection) + "\n", encoding="utf-8")
    out_dir = tmp_path / "candidate"
    (tmp_path / "synthesis.json").write_text(canonical_json(synthesis) + "\n", encoding="utf-8")
    completed = subprocess.run(
        [
            sys.executable,
            str(METHOD_CLI),
            "aggregate",
            "--packet-manifest",
            str(manifest_path),
            "--completed-results",
            str(selection_path),
            "--candidate-digest",
            str(digest_path),
            "--synthesis",
            str(tmp_path / "synthesis.json"),
            "--out-dir",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert json.loads(completed.stdout)["coverage"] == candidate["candidate_digest"]["coverage"]
    assert json.loads((out_dir / "claim-ledger.json").read_text(encoding="utf-8")) == synthesized["claim_ledger"]


def test_candidate_digest_prefers_frequency_then_spans_manifest_occurrences(tmp_path: Path) -> None:
    labels = [*[f"A-{ordinal:02d}" for ordinal in range(1, 11)], "M-mid", "Z-recurring", "Z-recurring", "Z-recurring", "Y-late", "Z-late"]
    chunks, _ = build_method_packets(
        [{"source_row_id": f"row-{ordinal:03d}", "source_type": "post", "text": f"blind observation {ordinal}"} for ordinal in range(1, len(labels) + 1)]
    )
    packet_dir = tmp_path / "packets"
    manifest = write_blind_packets(chunks, packet_dir=packet_dir, batch_size=1)
    manifest_sha256 = hashlib.sha256((packet_dir / "packet-manifest.json").read_bytes()).hexdigest()
    completed_results: list[dict] = []
    for ordinal, (packet_record, label) in enumerate(zip(manifest["packets"], labels, strict=True), start=1):
        packet_path = packet_dir / packet_record["path"]
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        output = {
            "schema_id": "urn:serenity:schema:method-coding-output:1",
            "packet_id": packet_record["packet_id"],
            "packet_sha256": hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            "dispositions": [
                {
                    "chunk_id": packet["chunks"][0]["chunk_id"],
                    "disposition": "coded",
                    "coding": {
                        "trigger": f"trigger {ordinal}",
                        "evidence_sought": f"evidence {ordinal}",
                        "inference": f"inference {ordinal}",
                        "action_horizon": {"action": "monitor", "horizon": f"horizon {ordinal}"},
                        "falsifier": f"falsifier {ordinal}",
                        "codes": [{"axis": "catalyst_mechanism", "label": label, "rationale": f"rationale {ordinal}"}],
                    },
                    "uncertainty_notes": [],
                    "contradiction_notes": [],
                }
            ],
        }
        output_bytes = (canonical_json(output) + "\n").encode()
        execution = {
            "format": "serenity-method-coding-execution/1",
            "packet_id": packet_record["packet_id"],
            "status": "completed",
            "output_sha256": hashlib.sha256(output_bytes).hexdigest(),
            "package_sha256": {packet_record["path"]: output["packet_sha256"]},
            "full_manifest_content_hash": manifest["content_hash"],
            "full_manifest_sha256": manifest_sha256,
            "selected_packet_ids": [record["packet_id"] for record in manifest["packets"]],
        }
        completed_results.append({"execution": execution, "output": output, "output_sha256": execution["output_sha256"], "manifest_sha256": manifest_sha256})

    candidate = aggregate_method_codings(manifest, completed_results)
    axis = next(item for item in candidate["candidate_digest"]["bounded_summary"]["axis_label_frequency"] if item["axis"] == "catalyst_mechanism")
    shown = [entry["label"] for entry in axis["entries"]]
    assert "Z-recurring" in shown
    assert "Z-late" in shown
    assert "A-10" not in shown
    assert axis["selection_rationale"]["priority"] == "descending_exact_label_frequency"
    assert axis["selection_rationale"]["tie_break"] == "first_manifest_occurrence_span"
    assert all(entry["first_manifest_occurrence"] >= 0 for entry in axis["entries"])
    assert candidate["candidate_digest"]["bounded_summary"]["policy_hash"]


def test_checked_in_method_reconstruction_artifacts_are_hash_bound_and_non_advisory() -> None:
    paths = {
        "codebook": METHOD_ARTIFACTS / "codebook.v1.json",
        "coding": METHOD_ARTIFACTS / "coding.v1.json",
        "claim_ledger": METHOD_ARTIFACTS / "claim-ledger.v1.json",
        "candidate_digest": METHOD_ARTIFACTS / "candidate-digest.v1.json",
        "synthesis": METHOD_ARTIFACTS / "claim-synthesis.v1.json",
        "augmentations": METHOD_ARTIFACTS / "augmentations.v1.json",
        "evidence": METHOD_ARTIFACTS / "synthesis-evidence.v1.json",
    }
    assert all(path.is_file() for path in paths.values())
    documents = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
    codebook = documents["codebook"]
    coding = documents["coding"]
    ledger = documents["claim_ledger"]
    candidate = documents["candidate_digest"]
    synthesis = documents["synthesis"]
    augmentations = documents["augmentations"]
    evidence = documents["evidence"]

    for name in ("codebook", "coding", "claim_ledger", "candidate_digest"):
        assert documents[name]["content_hash"] == _artifact_content_hash(documents[name])

    assert candidate["input_hashes"] == {
        "codebook": codebook["content_hash"],
        "coding": coding["content_hash"],
        "claim_ledger": "b072a376c8da55302259e1dc95328e740bf0c275bea646a0b54a1922a1b38e6c",
    }
    assert candidate["coverage"] == {
        "all_disposition_coverage_hash": "b2390301001d19c1dce126875c5575f2c0c24381ba0e6bc38675df4c6b603301",
        "packets": 76,
        "chunks": 3766,
        "coded_chunks": 1953,
        "no_reusable_move_chunks": 1813,
    }

    candidate_sha256 = hashlib.sha256(paths["candidate_digest"].read_bytes()).hexdigest()
    synthesis_sha256 = hashlib.sha256(paths["synthesis"].read_bytes()).hexdigest()
    ledger_sha256 = hashlib.sha256(paths["claim_ledger"].read_bytes()).hexdigest()
    assert synthesis["candidate_digest_content_hash"] == candidate["content_hash"]
    assert synthesis["candidate_digest_sha256"] == candidate_sha256
    assert evidence["candidate_digest"] == {"content_hash": candidate["content_hash"], "sha256": candidate_sha256}
    assert evidence["package_sha256"]["candidate-digest.json"] == candidate_sha256
    assert evidence["read_only_revalidation"]["output_sha256"] == synthesis_sha256
    assert evidence["final_claim_ledger"]["content_hash"] == ledger["content_hash"]
    assert evidence["final_claim_ledger"]["sha256"] == ledger_sha256

    code_ids_by_axis_label = {(code["axis"], code["label"]): code["code_id"] for code in codebook["codes"]}
    unit_by_id = {unit["unit_id"]: unit for unit in coding["units"]}
    assert len(code_ids_by_axis_label) == len(codebook["codes"])
    assert len(unit_by_id) == len(coding["units"])
    digest_unit_refs: set[str] = set()
    digest_code_refs: set[tuple[str, str]] = set()
    for axis in candidate["bounded_summary"]["axis_label_frequency"]:
        for entry in axis["entries"]:
            digest_code_refs.add((axis["axis"], entry["label"]))
            digest_unit_refs.update(representative["unit_id"] for representative in entry["representatives"])

    ledger_by_id = {claim["claim_id"]: claim for claim in ledger["claims"]}
    synthesis_by_id = {claim["claim_id"]: claim for claim in synthesis["claims"]}
    augmentation_by_id = {claim["claim_id"]: claim for claim in augmentations["claims"]}
    assert len(ledger_by_id) == len(ledger["claims"])
    assert len(synthesis_by_id) == len(synthesis["claims"])
    assert len(augmentation_by_id) == len(augmentations["claims"])
    sourced_ledger = [claim for claim in ledger["claims"] if claim["provenance_tag"] == "sourced"]
    augmented_ledger = [claim for claim in ledger["claims"] if claim["provenance_tag"] == "augmented"]
    assert len(sourced_ledger) == 12
    assert len(augmented_ledger) == 8
    assert not [claim for claim in ledger["claims"] if claim["provenance_tag"] == "unverified"]
    assert set(synthesis_by_id) == {claim["claim_id"] for claim in sourced_ledger}
    assert set(augmentation_by_id) == {claim["claim_id"] for claim in augmented_ledger}

    for claim_id, synthesis_claim in synthesis_by_id.items():
        shown_pairs = [(ref["axis"], ref["label"]) for ref in synthesis_claim["shown_code_refs"]]
        assert synthesis_claim["provenance_tag"] == "sourced"
        assert set(synthesis_claim["shown_unit_refs"]) <= digest_unit_refs
        assert set(shown_pairs) <= digest_code_refs
        assert set(synthesis_claim["shown_unit_refs"]) <= set(unit_by_id)
        assert set(synthesis_claim["counterexample_refs"]) <= set(unit_by_id)
        assert set(shown_pairs) <= set(code_ids_by_axis_label)
        resolved_codes = [code_ids_by_axis_label[pair] for pair in shown_pairs]
        resolved_unit_pairs = {
            (raw_code["axis"], raw_code["label"])
            for unit_id in synthesis_claim["shown_unit_refs"]
            for raw_code in unit_by_id[unit_id]["raw_codes"]
        }
        assert set(shown_pairs) <= resolved_unit_pairs
        assert ledger_by_id[claim_id] == {
            "claim_id": claim_id,
            "claim": synthesis_claim["claim"],
            "provenance_tag": "sourced",
            "representative_refs": synthesis_claim["shown_unit_refs"],
            "counterexample_refs": synthesis_claim["counterexample_refs"],
            "code_refs": resolved_codes,
            "counterexample_search_scope": synthesis_claim["counterexample_search_scope"],
            "counterexample_status": synthesis_claim["counterexample_status"],
            "why": synthesis_claim["why"],
            "uncertainty_notes": synthesis_claim["uncertainty_notes"],
            "contradiction_notes": synthesis_claim["contradiction_notes"],
            "hard_gate": False,
        }

    for claim_id, augmentation in augmentation_by_id.items():
        assert augmentation["provenance_tag"] == "augmented"
        assert augmentation["augmentation_rationale"]
        assert ledger_by_id[claim_id] == {**augmentation, "hard_gate": False}
    augmented_text = "\n".join(claim["claim"] for claim in augmentations["claims"])
    assert "do not provide portfolio weights, position sizes" in augmented_text
    assert not re.search(r"\b(?:allocate|allocation|weight|size)\s+(?:the\s+)?(?:portfolio|position)?\s*\d", augmented_text, flags=re.IGNORECASE)
    assert not re.search(r"\b\d+(?:\.\d+)?%\s*(?:portfolio|position)?\s*(?:allocation|weight|size)", augmented_text, flags=re.IGNORECASE)


@pytest.mark.parametrize(
    ("args", "required_terms"),
    [
        ([], ["blind chunks", "source index", "packet manifest", "Forbidden leakage boundary", "Exit codes", "Examples"]),
        (["chunks"], ["Purpose", "Input artifact", "Output artifacts", "source-index-out", "Example"]),
        (["chunks-db"], ["read-only SQLite", "packet batching", "source index", "media-manifest", "JSONL", "full method reconstruction", "Example"]),
        (["aggregate"], ["Purpose", "packet manifest", "completed results", "candidate digest", "synthesis", "augmentations", "one result", "no implicit resume", "Example"]),
        (["validate"], ["Purpose", "reconcile", "does not write", "source index", "Exit codes"]),
        (["store"], ["Purpose", "content-addressed", "private source index", "Example", "Exit codes"]),
    ],
)
def test_every_method_help_is_detailed_and_performs_no_io(tmp_path: Path, args: list[str], required_terms: list[str]) -> None:
    completed = subprocess.run(
        [sys.executable, str(METHOD_CLI), *args, "--help"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout
    assert all(term.casefold() in completed.stdout.casefold() for term in required_terms)
    assert list(tmp_path.iterdir()) == []
