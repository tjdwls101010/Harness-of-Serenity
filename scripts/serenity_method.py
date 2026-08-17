#!/usr/bin/env python3
"""Public artifact CLI for cleanroom method coding; it never creates an investment rule."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, NoReturn

from serenity_v2.method import (
    MethodArtifactError,
    MethodArtifactStore,
    MethodIncompleteError,
    aggregate_method_codings,
    build_method_packets,
    build_method_packets_from_sqlite,
    compile_method_artifact,
    write_blind_packets,
)
from serenity_v2.storage import atomic_write_json


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise MethodArtifactError(message)


def _load(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MethodArtifactError(f"{label} must be readable JSON: {path}") from exc


def _emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_completed_results(path: Path, *, packet_manifest_path: Path) -> list[dict[str, Any]]:
    selected = _load(path, "completed results")
    if not isinstance(selected, list):
        raise MethodArtifactError("completed results must be a JSON list of explicit execution/output paths")
    results: list[dict[str, Any]] = []
    manifest_sha256 = _file_sha256(packet_manifest_path)
    for item in selected:
        item = item if isinstance(item, dict) else None
        if item is None or not isinstance(item.get("execution"), str) or not isinstance(item.get("output"), str):
            raise MethodArtifactError("completed results entries require explicit execution and output paths")
        execution_path = Path(item["execution"])
        output_path = Path(item["output"])
        execution = _load(execution_path, "completed execution")
        output = _load(output_path, "completed output")
        if execution.get("output_sha256") != _file_sha256(output_path):
            raise MethodArtifactError("completed output file hash does not match execution record")
        if execution.get("full_manifest_sha256") != manifest_sha256:
            raise MethodArtifactError("completed execution does not bind the supplied packet manifest file")
        results.append({"execution": execution, "output": output, "output_sha256": execution["output_sha256"], "manifest_sha256": manifest_sha256})
    return results


def build_parser() -> JsonArgumentParser:
    formatter = argparse.RawDescriptionHelpFormatter
    parser = JsonArgumentParser(
        prog="serenity_method.py",
        description="Create, validate, and store cleanroom open-coding artifacts without creating investment doctrine.",
        epilog="""Artifacts:
  blind chunks     coder-facing text only; ticker/date/answer-key metadata is excluded or redacted.
  source index     private recovery metadata for opaque source refs; never put it in a cleanroom packet.
  packet manifest  deterministic batch list with packet hashes, chunk IDs, and counts.

Forbidden leakage boundary:
  Do not pass source indexes, ticker/date/type fields, answer keys, prior verdicts, or source databases to coders.

Exit codes:
  0 success (including --help); 2 usage or artifact-contract error; 70 unexpected internal error.

Examples:
  serenity_method.py chunks --rows rows.json --out chunks.json --source-index-out source-index.private.json
  serenity_method.py chunks-db --db corpus.db --media-manifest media.json --out chunks.json --source-index-out source-index.private.json --batch-size 50 --packet-dir packets/
  serenity_method.py validate --chunks chunks.json --source-index source-index.private.json --codebook codebook.json --coding coding.json --ledger ledger.json""",
        formatter_class=formatter,
    )
    commands = parser.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)
    chunks = commands.add_parser(
        "chunks",
        help="Build one blind coder packet and a separate private source index.",
        description="""Purpose:
  Build a blind chunks artifact from normalized corpus rows and optional derived media annotations.

Input artifact:
  --rows is a JSON list of source rows. --annotations is an optional JSON list of derived media annotations.

Output artifacts:
  --out receives serenity-method-blind-chunks/1. --source-index-out receives the private
  serenity-method-source-index/1 recovery artifact.

Forbidden leakage boundary:
  The blind output never contains the source index, source row IDs, ticker/date/type metadata, or answer keys.

Exit codes:
  0 success (including --help); 2 usage or artifact-contract error; 70 unexpected internal error.

Example:
  serenity_method.py chunks --rows rows.json --annotations media.json --out chunks.json --source-index-out source-index.private.json""",
        formatter_class=formatter,
    )
    chunks.add_argument("--rows", required=True, type=Path, help="JSON list of normalized source rows.")
    chunks.add_argument("--annotations", type=Path, help="Optional JSON list of derived media annotations.")
    chunks.add_argument("--out", required=True, type=Path, help="Blind chunks artifact output path.")
    chunks.add_argument("--source-index-out", required=True, type=Path, help="Private source-index artifact output path; never send to coders.")
    chunks_db = commands.add_parser(
        "chunks-db",
        help="Read the corpus SQLite file into blind chunks plus a private source index.",
        description="""Purpose:
  Read-only SQLite normalization from tweets into a blind coder packet and separately stored source index.

Input artifact:
  --db is a SQLite corpus. It is read using the fixed id/type/content/tickers/media query in stable id order.

Output artifacts:
  --out receives blind chunks; --source-index-out receives private DB provenance and recovery metadata.
  With --batch-size and --packet-dir, deterministic packet batching writes regular blind packets and a hash-listed packet manifest.
  Full method reconstruction requires --media-manifest (JSON object or JSONL): approved OCR/vision relations become blind chunks, while terminal 404 fetches are privately recorded as excluded unavailable media.

Forbidden leakage boundary:
  Source type, source row IDs, representative tickers, media IDs, and DB provenance stay only in the source index.

Exit codes:
  0 success (including --help); 2 usage or artifact-contract error; 70 unexpected internal error.

Example:
  serenity_method.py chunks-db --db corpus.db --media-manifest media.json --out chunks.json --source-index-out source-index.private.json --batch-size 50 --packet-dir packets/""",
        formatter_class=formatter,
    )
    chunks_db.add_argument("--db", required=True, type=Path, help="Read-only SQLite corpus input.")
    chunks_db.add_argument("--out", required=True, type=Path, help="Blind chunks artifact output path.")
    chunks_db.add_argument("--source-index-out", required=True, type=Path, help="Private source-index artifact output path.")
    chunks_db.add_argument("--media-manifest", type=Path, help="Corpus media manifest (JSON object or JSONL); required for full method reconstruction and approved media derivatives.")
    chunks_db.add_argument("--full-audit", action="store_true", help="Return typed exit 4 only for missing, ambiguous, retryable, or unreviewed media; terminal unavailable fetches are excluded with private provenance.")
    chunks_db.add_argument("--batch-size", type=int, help="Chunks per deterministic packet; requires --packet-dir.")
    chunks_db.add_argument("--packet-dir", type=Path, help="Directory for blind packets and packet manifest; requires --batch-size.")
    aggregate = commands.add_parser(
        "aggregate",
        help="Validate every explicitly selected completed packet result and write review candidates.",
        description="""Purpose:
  Aggregate schema-valid blind-coder outputs into codebook, coding, claim-ledger candidates, and a bounded candidate digest. This command never invents doctrine or merges semantically similar labels.

Input artifacts:
  --packet-manifest is the complete hash-listed packet manifest. Completed results arrive through --completed-results as a JSON list of explicit {execution, output} paths; every manifest packet needs one result exactly. A Sol --synthesis must bind the explicit baseline --candidate-digest by both content hash and raw file SHA.

Output artifacts:
  --out-dir receives codebook.json, coding.json, claim-ledger.json, and candidate-digest.json. Granular coding remains complete; the digest uses a declared deterministic truncation policy with omitted counts and hashes for final cleanroom review.

Validation and leakage boundary:
  Packet identity, full-manifest binding, output file SHA, schema, and exact chunk coverage are verified. Missing, duplicate, blocked, tampered, or stale results fail. There is no implicit resume or result discovery. Sol may emit only sourced or unverified claims through shown refs; --augmentations is a separate explicit post-synthesis artifact restricted to augmented claims with a rationale.

Exit codes:
  0 success (including --help); 2 usage or artifact-contract error; 70 unexpected internal error.

Example:
  serenity_method.py aggregate --packet-manifest packets/packet-manifest.json --completed-results selected-results.json --candidate-digest baseline/candidate-digest.json --synthesis sol-claims.json --augmentations engineering.json --out-dir method-candidates/""",
        formatter_class=formatter,
    )
    aggregate.add_argument("--packet-manifest", required=True, type=Path, help="Complete packet-manifest.json used for every coding run.")
    aggregate.add_argument("--completed-results", required=True, type=Path, help="JSON list of caller-selected {execution, output} result paths; no implicit resume.")
    aggregate.add_argument("--candidate-digest", type=Path, help="Baseline candidate-digest.json read by Sol; required with --synthesis and verified by content hash plus raw file SHA.")
    aggregate.add_argument("--synthesis", type=Path, help="Optional Sol serenity-method-claim-synthesis/1 JSON artifact; it can only emit sourced or unverified claims.")
    aggregate.add_argument("--augmentations", type=Path, help="Optional separate serenity-method-augmentations/1 post-synthesis artifact; every claim must be augmented with a rationale.")
    aggregate.add_argument("--out-dir", required=True, type=Path, help="Directory for candidate codebook, coding, ledger, and bounded digest artifacts.")
    for name in ("validate", "store"):
        description = (
            """Purpose:
  Reconcile blind chunks, the private source index, codebook, coding units, and claim ledger without writing an artifact.

Input artifacts:
  All inputs are JSON artifacts. The source index hash must match blind chunks, and all source/code/unit links are checked.

Output:
  A single JSON reconciliation summary on stdout; this command does not write files.

Forbidden leakage boundary:
  The source index is validation-only private metadata and must never be put in a coder packet.

Exit codes:
  0 success (including --help); 2 usage or artifact-contract error; 70 unexpected internal error.

Example:
  serenity_method.py validate --chunks chunks.json --source-index source-index.private.json --codebook codebook.json --coding coding.json --ledger ledger.json"""
            if name == "validate"
            else """Purpose:
  Reconcile the supplied artifacts, then store a content-addressed method artifact and private source index under --root.

Input artifacts:
  All inputs are JSON artifacts. The private source index is verified but is stored separately from the public method artifact.

Output artifacts:
  records/method/<hash>.json and records/method/source-index/<hash>.json, plus a JSON summary on stdout.

Forbidden leakage boundary:
  The content-addressed method artifact contains only the source index hash, never private source-index content.

Exit codes:
  0 success (including --help); 2 usage or artifact-contract error; 70 unexpected internal error.

Example:
  serenity_method.py store --chunks chunks.json --source-index source-index.private.json --codebook codebook.json --coding coding.json --ledger ledger.json --root ."""
        )
        command = commands.add_parser(
            name,
            help="Reconcile artifacts without writing." if name == "validate" else "Reconcile and content-addressedly store artifacts.",
            description=description,
            formatter_class=formatter,
        )
        command.add_argument("--chunks", required=True, type=Path, help="Blind chunks JSON artifact.")
        command.add_argument("--codebook", required=True, type=Path, help="Open-coding codebook JSON artifact.")
        command.add_argument("--coding", required=True, type=Path, help="Coding units JSON artifact.")
        command.add_argument("--ledger", required=True, type=Path, help="Claim ledger JSON artifact.")
        command.add_argument("--source-index", required=True, type=Path, help="Private source-index JSON artifact; hash must match chunks.")
        if name == "store":
            command.add_argument("--root", type=Path, default=Path.cwd(), help="Root directory for content-addressed records (default: current directory).")
    return parser


def _artifact(args: argparse.Namespace) -> dict[str, Any]:
    return compile_method_artifact(
        chunks=_load(args.chunks, "chunks"),
        source_index=_load(args.source_index, "source index"),
        codebook=_load(args.codebook, "codebook"),
        coding=_load(args.coding, "coding"),
        claim_ledger=_load(args.ledger, "claim ledger"),
    )


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "chunks":
        rows = _load(args.rows, "rows")
        annotations = _load(args.annotations, "annotations") if args.annotations else []
        document, source_index = build_method_packets(rows, annotations)
        atomic_write_json(args.out, document)
        atomic_write_json(args.source_index_out, source_index)
        return {
            "command": "chunks",
            "ok": True,
            "chunks": len(document["chunks"]),
            "content_hash": document["content_hash"],
            "source_index_hash": source_index["content_hash"],
        }
    if args.command == "chunks-db":
        if (args.batch_size is None) != (args.packet_dir is None):
            raise MethodArtifactError("--batch-size and --packet-dir must be supplied together")
        if args.full_audit and args.media_manifest is None:
            raise MethodArtifactError("--full-audit requires --media-manifest")
        document, source_index = build_method_packets_from_sqlite(args.db, media_manifest=args.media_manifest)
        media_derivatives = document.get("media_derivatives")
        if args.full_audit and isinstance(media_derivatives, dict) and media_derivatives.get("status") != "complete":
            raise MethodIncompleteError(media_derivatives)
        atomic_write_json(args.out, document)
        atomic_write_json(args.source_index_out, source_index)
        result: dict[str, Any] = {
            "command": "chunks-db",
            "ok": True,
            "chunks": len(document["chunks"]),
            "content_hash": document["content_hash"],
            "source_index_hash": source_index["content_hash"],
        }
        if args.packet_dir is not None:
            manifest = write_blind_packets(document, packet_dir=args.packet_dir, batch_size=args.batch_size)
            result["packet_manifest"] = {"path": str(args.packet_dir / "packet-manifest.json"), "content_hash": manifest["content_hash"]}
        if isinstance(media_derivatives, dict):
            result["media_derivatives"] = media_derivatives
        return result
    if args.command == "aggregate":
        if args.synthesis is None and (args.candidate_digest is not None or args.augmentations is not None):
            raise MethodArtifactError("--candidate-digest and --augmentations require --synthesis")
        if args.synthesis is not None and args.candidate_digest is None:
            raise MethodArtifactError("--synthesis requires --candidate-digest")
        packet_manifest = _load(args.packet_manifest, "packet manifest")
        candidates = aggregate_method_codings(
            packet_manifest,
            _load_completed_results(args.completed_results, packet_manifest_path=args.packet_manifest),
            synthesis=_load(args.synthesis, "claim synthesis") if args.synthesis else None,
            candidate_digest=_load(args.candidate_digest, "candidate digest") if args.candidate_digest else None,
            candidate_digest_sha256=_file_sha256(args.candidate_digest) if args.candidate_digest else None,
            augmentations=_load(args.augmentations, "method augmentations") if args.augmentations else None,
        )
        paths = {
            "codebook": args.out_dir / "codebook.json",
            "coding": args.out_dir / "coding.json",
            "claim_ledger": args.out_dir / "claim-ledger.json",
            "candidate_digest": args.out_dir / "candidate-digest.json",
        }
        for key, path in paths.items():
            atomic_write_json(path, candidates[key])
        return {
            "command": "aggregate",
            "ok": True,
            "coverage": candidates["candidate_digest"]["coverage"],
            "paths": {key: str(path) for key, path in paths.items()},
            "content_hashes": {key: candidates[key]["content_hash"] for key in paths},
        }
    artifact = _artifact(args)
    if args.command == "validate":
        return {"command": "validate", "ok": True, "content_hash": artifact["content_hash"], "reconciliation": artifact["reconciliation"]}
    if args.command == "store":
        stored = MethodArtifactStore(args.root).store(artifact, source_index=_load(args.source_index, "source index"))
        return {
            "command": "store",
            "ok": True,
            "content_hash": artifact["content_hash"],
            "reconciliation": artifact["reconciliation"],
            "stored": stored,
        }
    raise MethodArtifactError("unsupported command")


def main(argv: list[str] | None = None) -> int:
    try:
        _emit(dispatch(build_parser().parse_args(argv)))
        return 0
    except MethodIncompleteError as exc:
        _emit(
            {
                "ok": False,
                "error": {
                    "code": "media_incomplete",
                    "message": str(exc),
                    "exit_code": 4,
                    "media_derivatives": exc.media_derivatives,
                },
            }
        )
        return 4
    except MethodArtifactError as exc:
        _emit({"ok": False, "error": {"code": "usage_or_schema", "message": str(exc), "exit_code": 2}})
        return 2
    except Exception as exc:  # pragma: no cover - stable process boundary
        _emit({"ok": False, "error": {"code": "internal_error", "message": str(exc), "exit_code": 70}})
        return 70


if __name__ == "__main__":
    sys.exit(main())
