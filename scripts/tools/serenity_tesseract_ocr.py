#!/usr/bin/env python3
"""Emit one provenance-compatible OCR JSON object using a local Tesseract binary."""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


_INSUFFICIENT_CAVEAT = (
    "OCR text and confidence cannot establish a claim without visual review; chart, diagram, and screenshot possibilities remain."
)


def _emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=False))


def _failure(error: str, version: str = "unavailable") -> dict[str, Any]:
    return {
        "status": "failed",
        "text": None,
        "extractor_name": "tesseract",
        "extractor_version": version,
        "confidence": None,
        "caveat": _INSUFFICIENT_CAVEAT,
        "claim_status": "insufficient",
        "audit_status": "needs_reconciliation",
        "reviewer": None,
        "error": error,
    }


def _run(arguments: list[str], timeout_seconds: float) -> subprocess.CompletedProcess[str]:
    return subprocess.run(arguments, check=False, capture_output=True, text=True, timeout=timeout_seconds)


def _tesseract_version(binary: str, timeout_seconds: float) -> tuple[str | None, str | None]:
    try:
        completed = _run([binary, "--version"], timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic"
        return None, f"tesseract --version exited {completed.returncode}: {diagnostic}"
    version = next((line.strip() for line in completed.stdout.splitlines() if line.strip()), None)
    return version, None if version is not None else "tesseract --version returned no version"


def _tsv_text_and_confidence(raw_tsv: str) -> tuple[str, float | None]:
    words: list[str] = []
    confidences: list[float] = []
    for row in csv.DictReader(io.StringIO(raw_tsv), delimiter="\t"):
        text = (row.get("text") or "").strip()
        if text:
            words.append(text)
        try:
            confidence = float(row.get("conf") or "")
        except ValueError:
            continue
        if confidence >= 0:
            confidences.append(confidence)
    average = round(sum(confidences) / len(confidences) / 100, 4) if confidences else None
    return " ".join(words), average


def run_ocr(input_path: Path, tesseract: str, psm: int, timeout_seconds: float) -> tuple[dict[str, Any], str | None]:
    if not input_path.is_file():
        return _failure(f"input file not found: {input_path}"), None
    version, version_error = _tesseract_version(tesseract, timeout_seconds)
    if version_error is not None:
        return _failure(version_error), version_error
    assert version is not None
    try:
        completed = _run([tesseract, str(input_path), "stdout", "--psm", str(psm), "tsv"], timeout_seconds)
    except (OSError, subprocess.TimeoutExpired) as exc:
        error = f"{type(exc).__name__}: {exc}"
        return _failure(error, version), error
    if completed.returncode != 0:
        diagnostic = completed.stderr.strip() or completed.stdout.strip() or "no diagnostic"
        error = f"tesseract OCR exited {completed.returncode}: {diagnostic}"
        return _failure(error, version), diagnostic
    text, confidence = _tsv_text_and_confidence(completed.stdout)
    return {
        "status": "complete",
        "text": text or None,
        "extractor_name": "tesseract",
        "extractor_version": version,
        "confidence": confidence,
        "caveat": _INSUFFICIENT_CAVEAT,
        "claim_status": "insufficient",
        "audit_status": "unreviewed",
        "reviewer": None,
        "error": None,
    }, None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run local Tesseract OCR and emit one corpus extractor JSON object; no network is used.",
        epilog="Example: serenity_tesseract_ocr.py --input .serenity/media-cache/<sha256> --tesseract /opt/homebrew/bin/tesseract",
    )
    parser.add_argument("--input", required=True, type=Path, help="Cached media file to inspect.")
    parser.add_argument("--tesseract", default="tesseract", help="Tesseract binary path or command (default: tesseract).")
    parser.add_argument("--psm", type=int, default=6, help="Tesseract page segmentation mode (default: 6).")
    parser.add_argument("--timeout-seconds", type=float, default=60.0, help="Per-Tesseract-process timeout (default: 60).")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.timeout_seconds <= 0:
        _emit(_failure("--timeout-seconds must be greater than zero"))
        return 0
    result, diagnostic = run_ocr(args.input, args.tesseract, args.psm, args.timeout_seconds)
    if diagnostic:
        print(diagnostic, file=sys.stderr)
    _emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
