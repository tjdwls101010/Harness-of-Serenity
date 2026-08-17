#!/usr/bin/env python3
"""Public CLI for auditing the historical method corpus without issuing a thesis."""

from __future__ import annotations

import argparse
import json
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, NoReturn

from serenity_v2.corpus import CorpusError, apply_reviews, audit_media, build_review_packets, extract_media, ingest_media, scan_corpus


EXIT_CODES = "Exit codes: 0 success; 2 usage/schema; 3 unavailable input; 4 provider/helper unavailable; 5 persistence conflict; 70 internal."


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        raise CorpusError("usage_or_schema", message, 2)


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def build_parser() -> JsonArgumentParser:
    parser = JsonArgumentParser(
        prog="serenity_corpus.py",
        description="Corpus-method evidence tooling; it never produces an investment recommendation.",
        epilog=(
            "Workflow: inventory -> ingest-media -> extract-media -> review-packets build -> reviews apply -> audit --require-extraction.\n"
            "Example:\n  scripts/.venv/bin/python scripts/serenity_corpus.py inventory --db data/analysis_Serenity.db\n"
            f"{EXIT_CODES}\n"
            "Run `serenity_corpus.py <command> --help` for manifest, cache, checkpoint, and extractor contracts."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True, parser_class=JsonArgumentParser)
    inventory = _command_parser(
        commands,
        "inventory",
        "Count corpus rows, media references, URLs, and tweet types.",
        "Read-only SQLite inventory.\n\nInput: --db is the SQLite database containing the tweets table.\nOutput: one JSON object with row, reference, URL, and type denominators; no cache or manifest is written.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py inventory --db data/analysis_Serenity.db",
    )
    inventory.add_argument("--db", required=True, type=Path, help="SQLite database with a tweets table (read-only).")
    ingest_media_command = _command_parser(
        commands,
        "ingest-media",
        "Download media into a content-addressed raw cache and write provenance.",
        "Fetch each corpus media URL into a content-addressed raw cache; do not put binary data in the manifest.\n\nInput: --db supplies tweet IDs and media URLs.\nManifest: --manifest is JSONL or JSON metadata containing URL, tweet ID, source hash, fetch status, and extraction fields.\nCache: --cache-root stores raw bytes by SHA-256 and is intentionally separate from tracked manifest metadata.\nCheckpoint: --checkpoint records incremental progress; its default is <manifest>.checkpoint.json.\nResume: verified manifest records whose cached SHA-256 still matches are reused; failed or invalid records are retried.\nOutput: one JSON object reports fetched, failed, resumed, and denominator counts.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py ingest-media --db data/analysis_Serenity.db --manifest data/corpus-media-manifest.v1.jsonl --cache-root .serenity/media-cache",
    )
    ingest_media_command.add_argument("--db", required=True, type=Path, help="SQLite tweets database.")
    ingest_media_command.add_argument("--manifest", required=True, type=Path, help="JSONL or JSON provenance manifest to create or resume.")
    ingest_media_command.add_argument("--cache-root", type=Path, default=Path(".serenity/media-cache"), help="Content-addressed raw-byte cache.")
    ingest_media_command.add_argument("--checkpoint", type=Path, help="Incremental checkpoint path; defaults beside the manifest.")
    ingest_media_command.add_argument("--retries", type=int, default=2, help="Retry count after the initial URL request (default: 2).")
    ingest_media_command.add_argument("--timeout-seconds", type=float, default=15.0, help="Per-request network timeout (default: 15).")
    extract = _command_parser(
        commands,
        "extract-media",
        "Run injected OCR and optional vision-review commands over cached media.",
        "Input: --manifest must describe downloaded media and --cache-root must contain matching SHA-256 bytes.\nCheckpoint: --checkpoint records incremental OCR/vision work; its default is <manifest>.checkpoint.json.\nResume: a terminal stage with the same source_sha256 is reused, so duplicate URLs and duplicate bytes do not rerun an extractor.\nConcurrency: --max-workers bounds simultaneous extractor processes (default: 1). Results are merged in manifest order and each completed bounded batch atomically updates manifest and checkpoint.\n\nOCR command JSON contract: the command receives `{input}` and `{source_sha256}` placeholders and emits one JSON object with status, text, extractor_name, extractor_version, confidence, caveat, claim_status, audit_status, reviewer, and error.\nVision command JSON contract: the command emits one JSON object with status, labels, summary, supported_claims, model_name, model_version, prompt_template_version, confidence, caveat, audit_status, reviewer, and error. A complete review requires a reviewable summary and claim evidence/caveat.\nA non-established OCR claim requires vision review; command output determines image semantics, not this CLI.\nOutput: one JSON object reports unique source executions and resumed records.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py extract-media --manifest data/corpus-media-manifest.v1.jsonl --cache-root .serenity/media-cache --max-workers 4 --ocr-command 'scripts/tools/serenity_tesseract_ocr.py --input {input}'",
    )
    extract.add_argument("--manifest", required=True, type=Path, help="JSONL or JSON provenance manifest to enrich.")
    extract.add_argument("--cache-root", type=Path, default=Path(".serenity/media-cache"), help="Content-addressed raw-byte cache.")
    extract.add_argument("--ocr-command", help="Quoted executable template with {input} and optional {source_sha256}.")
    extract.add_argument("--vision-command", help="Quoted vision-review executable template with {input} and optional {source_sha256}.")
    extract.add_argument("--checkpoint", type=Path, help="Incremental extraction checkpoint; defaults beside the manifest.")
    extract.add_argument("--timeout-seconds", type=float, default=60.0, help="Per-extractor timeout (default: 60).")
    extract.add_argument("--max-workers", type=int, default=1, help="Maximum simultaneous extractor processes (default: 1).")
    review_packets = _command_parser(
        commands,
        "review-packets",
        "Build deterministic visual-review packets from cached corpus media.",
        "Review packets are evidence packets, never investment answers. The build command writes only packet JSON and a packet-manifest with packet hashes/counts; it does not modify the corpus manifest.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py review-packets build --db data/analysis_Serenity.db --manifest data/corpus-media-manifest.v1.jsonl --cache-root .serenity/media-cache --packet-dir .serenity/review-packets --batch-size 20",
    )
    review_packet_commands = review_packets.add_subparsers(dest="review_packet_command", required=True, parser_class=JsonArgumentParser)
    review_packet_build = _command_parser(
        review_packet_commands,
        "build",
        "Write fetch-ok unique-SHA visual-review packets and a hash manifest.",
        "Input: --db provides only the related tweet type/content context; --manifest provides fetch/OCR provenance; --cache-root provides the local raw cache.\nOutput: --packet-dir must be empty and receives deterministic packets plus packet-manifest.json with source-manifest, packet, and item counts/hashes.\nBatching: --batch-size bounds unique SHA items per packet; source SHA order is lexicographic and relation order follows the manifest.\nSafety: no network, secrets, raw bytes, or unrelated tweet content are written.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py review-packets build --db data/analysis_Serenity.db --manifest data/corpus-media-manifest.v1.jsonl --cache-root .serenity/media-cache --packet-dir .serenity/review-packets --batch-size 20",
    )
    review_packet_build.add_argument("--db", required=True, type=Path, help="SQLite tweets database for related context only.")
    review_packet_build.add_argument("--manifest", required=True, type=Path, help="JSONL or JSON media provenance manifest.")
    review_packet_build.add_argument("--cache-root", type=Path, default=Path(".serenity/media-cache"), help="Content-addressed raw-byte cache.")
    review_packet_build.add_argument("--packet-dir", required=True, type=Path, help="Empty output directory for review packets and packet-manifest.json.")
    review_packet_build.add_argument("--batch-size", type=int, default=20, help="Unique SHA items per packet (default: 20).")
    reviews = _command_parser(
        commands,
        "reviews",
        "Validate and atomically apply per-SHA visual-review output.",
        "Review application validates every per-SHA result before modifying the manifest. It preserves raw cache/fetch/OCR provenance and atomically fans one exact-SHA disposition out to every matching relation.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py reviews apply --manifest data/corpus-media-manifest.v1.jsonl --reviews-dir .serenity/review-results --reviewer-model gpt-5.6-terra --prompt-version media-review-v1 --require-complete",
    )
    review_commands = reviews.add_subparsers(dest="review_command", required=True, parser_class=JsonArgumentParser)
    reviews_apply = _command_parser(
        review_commands,
        "apply",
        "Schema-check review results and atomically fan them into manifest relations.",
        "Input: --reviews-dir contains one JSON result per reviewed source SHA using config/media-review-output.schema.json. Each result must match its source SHA, deterministic relation hash, and exact relation set.\nOutput: the manifest remains in original order; raw cache/fetch/OCR extractor provenance is preserved while review disposition/audit fields are applied.\nCompleteness: --require-complete fails with exit 4 before writing unless every fetch-ok unique SHA has exactly one reviewed result.\nSafety: duplicate, conflict, out-of-scope, relation mismatch, schema mismatch, reviewer-model mismatch, or prompt-version mismatch fail before any manifest write.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py reviews apply --manifest data/corpus-media-manifest.v1.jsonl --reviews-dir .serenity/review-results --reviewer-model gpt-5.6-terra --prompt-version media-review-v1 --require-complete",
    )
    reviews_apply.add_argument("--manifest", required=True, type=Path, help="JSONL or JSON media provenance manifest to update atomically.")
    reviews_apply.add_argument("--reviews-dir", required=True, type=Path, help="Directory of one schema-valid JSON review result per source SHA.")
    reviews_apply.add_argument("--reviewer-model", required=True, help="Exact reviewer model string required in every result.")
    reviews_apply.add_argument("--prompt-version", required=True, help="Exact review prompt version required in every result.")
    reviews_apply.add_argument("--require-complete", action="store_true", help="Require all fetch-ok unique SHA review results before writing (exit 4 if incomplete).")
    ocr_helper = _command_parser(
        commands,
        "ocr-helper",
        "Inspect or build local OCR helpers without network access.",
        "The local OCR helpers do not make network requests. Apple Vision requires a compiled macOS helper; Tesseract uses its directly executable JSON wrapper. Use a status command to obtain a copyable command_template, then supply it to extract-media --ocr-command.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py ocr-helper tesseract-status",
    )
    ocr_helper_commands = ocr_helper.add_subparsers(dest="ocr_helper_command", required=True, parser_class=JsonArgumentParser)
    helper_status = _command_parser(
        ocr_helper_commands,
        "status",
        "Show Apple Vision OCR helper availability and its copyable command template.",
        "Does not compile or write files.\nOutput: one JSON object with source availability, compiled output availability, platform, compiler availability, and command_template.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py ocr-helper status",
    )
    helper_status.add_argument("--output", type=Path, help="Expected helper binary path instead of the default scripts/tools output.")
    helper_build = _command_parser(
        ocr_helper_commands,
        "build",
        "Compile the local Apple Vision OCR helper.",
        "Builds the local Apple Vision OCR helper from scripts/tools/serenity_vision_ocr.swift.\nInput: macOS with a compatible Swift/Xcode toolchain.\nOutput: compiled executable at --output or scripts/tools/serenity_vision_ocr; status returns its command_template.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py ocr-helper build --output .serenity/tools/serenity_vision_ocr",
    )
    helper_build.add_argument("--output", type=Path, help="Compiled helper output path.")
    helper_build.add_argument("--swiftc", default="swiftc", help="Swift compiler executable (default: swiftc).")
    tesseract_status = _command_parser(
        ocr_helper_commands,
        "tesseract-status",
        "Show local Tesseract wrapper availability and its copyable command template.",
        "Does not write files or use the network.\nInput: --tesseract selects the local Tesseract binary to probe.\nOutput: one JSON object with helper source, binary availability/version, and a command_template for extract-media --ocr-command.\nThe wrapper emits one JSON object with status, text, extractor identity/version, TSV-derived confidence, conservative claim_status, audit status, reviewer, and error.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py ocr-helper tesseract-status --tesseract /opt/homebrew/bin/tesseract",
    )
    tesseract_status.add_argument("--tesseract", default="tesseract", help="Tesseract binary path or command to inspect (default: tesseract).")
    audit = _command_parser(
        commands,
        "audit",
        "Check manifest/cache integrity and optional extraction reconciliation.",
        "Input: --db supplies the expected tweet/media references; --manifest and --cache-root supply stored provenance and raw bytes.\nOutput: one JSON object with coverage denominators, missing/duplicate/hash issues, and a reconciliation gate.\n--require-extraction turns the reconciliation gate on: failed, missing, or not_requested OCR/vision stages; source-hash/provenance mismatch; and unapproved audit status remain explicit blockers.\nWithout --require-extraction, structural manifest/cache integrity is still checked but unfinished extraction is reported without blocking validity.\n\nExample:\n  scripts/.venv/bin/python scripts/serenity_corpus.py audit --db data/analysis_Serenity.db --manifest data/corpus-media-manifest.v1.jsonl --cache-root .serenity/media-cache --require-extraction",
    )
    audit.add_argument("--db", required=True, type=Path, help="SQLite tweets database used as the expected-reference denominator.")
    audit.add_argument("--manifest", required=True, type=Path, help="JSONL or JSON provenance manifest to verify.")
    audit.add_argument("--cache-root", type=Path, default=Path(".serenity/media-cache"), help="Content-addressed raw-byte cache to hash-check.")
    audit.add_argument("--require-extraction", action="store_true", help="Fail the reconciliation gate for unfinished or unreconciled OCR/vision stages.")
    return parser


def _command_parser(
    commands: argparse._SubParsersAction[argparse.ArgumentParser],
    name: str,
    help_text: str,
    description: str,
) -> JsonArgumentParser:
    return commands.add_parser(
        name,
        help=help_text,
        description=description,
        epilog=EXIT_CODES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def dispatch(args: argparse.Namespace) -> dict[str, Any]:
    if args.command == "inventory":
        return {"command": "inventory", "ok": True, "inventory": scan_corpus(args.db).inventory()}
    if args.command == "ingest-media":
        return {
            "command": "ingest-media",
            "ok": True,
            "ingest": ingest_media(
                args.db,
                args.manifest,
                args.cache_root,
                retries=args.retries,
                timeout_seconds=args.timeout_seconds,
                checkpoint_path=args.checkpoint,
            ),
        }
    if args.command == "extract-media":
        return {
            "command": "extract-media",
            "ok": True,
            "extract": extract_media(
                args.manifest,
                args.cache_root,
                ocr_command=args.ocr_command,
                vision_command=args.vision_command,
                checkpoint_path=args.checkpoint,
                timeout_seconds=args.timeout_seconds,
                max_workers=args.max_workers,
            ),
        }
    if args.command == "review-packets" and args.review_packet_command == "build":
        return {
            "command": "review-packets.build",
            "ok": True,
            "packets": build_review_packets(args.db, args.manifest, args.cache_root, args.packet_dir, batch_size=args.batch_size),
        }
    if args.command == "reviews" and args.review_command == "apply":
        return {
            "command": "reviews.apply",
            "ok": True,
            "reviews": apply_reviews(
                args.manifest,
                args.reviews_dir,
                reviewer_model=args.reviewer_model,
                prompt_version=args.prompt_version,
                require_complete=args.require_complete,
            ),
        }
    if args.command == "ocr-helper" and args.ocr_helper_command == "status":
        return {"command": "ocr-helper.status", "ok": True, "ocr_helper": ocr_helper_status(args.output)}
    if args.command == "ocr-helper" and args.ocr_helper_command == "build":
        return {"command": "ocr-helper.build", "ok": True, "ocr_helper": build_ocr_helper(args.output, args.swiftc)}
    if args.command == "ocr-helper" and args.ocr_helper_command == "tesseract-status":
        return {"command": "ocr-helper.tesseract-status", "ok": True, "ocr_helper": tesseract_helper_status(args.tesseract)}
    if args.command == "audit":
        return {
            "command": "audit",
            "ok": True,
            "audit": audit_media(args.db, args.manifest, args.cache_root, require_extraction=args.require_extraction),
        }
    raise CorpusError("usage_or_schema", "unsupported command", 2)


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ocr_source() -> Path:
    return _repository_root() / "scripts" / "tools" / "serenity_vision_ocr.swift"


def _ocr_output() -> Path:
    return _repository_root() / "scripts" / "tools" / "serenity_vision_ocr"


def _tesseract_source() -> Path:
    return _repository_root() / "scripts" / "tools" / "serenity_tesseract_ocr.py"


def ocr_helper_status(output: Path | None) -> dict[str, Any]:
    source = _ocr_source()
    binary = output or _ocr_output()
    return {
        "source": "scripts/tools/serenity_vision_ocr.swift",
        "source_exists": source.is_file(),
        "output": str(binary),
        "compiled": binary.is_file(),
        "platform": platform.system(),
        "swiftc_available": shutil.which("swiftc") is not None,
        "network": "none",
        "command_template": f"{shlex.quote(str(binary))} --input {{input}}",
    }


def build_ocr_helper(output: Path | None, swiftc: str) -> dict[str, Any]:
    if platform.system() != "Darwin":
        raise CorpusError("ocr_helper_unavailable", "Apple Vision OCR helper can only be built on macOS", 4)
    compiler = shutil.which(swiftc)
    if compiler is None:
        raise CorpusError("ocr_helper_unavailable", f"Swift compiler not found: {swiftc}", 4)
    source = _ocr_source()
    if not source.is_file():
        raise CorpusError("ocr_helper_unavailable", f"OCR helper source not found: {source}", 4)
    binary = output or _ocr_output()
    binary.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run([compiler, str(source), "-O", "-o", str(binary)], check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip() or completed.stdout.strip()
        raise CorpusError("ocr_helper_build_failed", diagnostic or "Swift compiler failed", 4)
    return {**ocr_helper_status(binary), "built": True}


def tesseract_helper_status(tesseract: str) -> dict[str, Any]:
    binary = shutil.which(tesseract) if Path(tesseract).name == tesseract else tesseract
    version: str | None = None
    if binary is not None:
        try:
            completed = subprocess.run([binary, "--version"], check=False, capture_output=True, text=True, timeout=10)
            if completed.returncode == 0:
                version = next((line.strip() for line in completed.stdout.splitlines() if line.strip()), None)
        except (OSError, subprocess.TimeoutExpired):
            binary = None
    source = _tesseract_source()
    resolved_binary = binary or tesseract
    return {
        "source": "scripts/tools/serenity_tesseract_ocr.py",
        "source_exists": source.is_file(),
        "tesseract_binary": resolved_binary,
        "available": binary is not None and version is not None,
        "version": version,
        "network": "none",
        "command_template": f"{shlex.quote(str(source))} --tesseract {shlex.quote(str(resolved_binary))} --input {{input}}",
    }


def main(argv: list[str] | None = None) -> int:
    try:
        emit(dispatch(build_parser().parse_args(argv)))
        return 0
    except CorpusError as exc:
        emit({"ok": False, "error": {"code": exc.code, "message": str(exc), "exit_code": exc.exit_code}})
        return exc.exit_code
    except Exception as exc:  # pragma: no cover - stable process boundary
        emit({"ok": False, "error": {"code": "internal_error", "message": str(exc), "exit_code": 70}})
        return 70


if __name__ == "__main__":
    sys.exit(main())
