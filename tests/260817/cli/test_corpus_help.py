from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_CLI = REPO_ROOT / "scripts" / "serenity_corpus.py"


def _help(tmp_path: Path, *args: str) -> str:
    completed = subprocess.run(
        [sys.executable, str(CORPUS_CLI), *args, "--help"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stderr == ""
    assert list(tmp_path.iterdir()) == []
    return completed.stdout


def test_root_help_explains_the_corpus_evidence_boundary_and_exit_codes_without_io(tmp_path: Path) -> None:
    help_text = _help(tmp_path)

    assert "Corpus-method evidence tooling; it never produces an investment recommendation." in help_text
    assert "inventory" in help_text
    assert "ingest-media" in help_text
    assert "extract-media" in help_text
    assert "review-packets" in help_text
    assert "reviews" in help_text
    assert "Example:" in help_text
    assert "Exit codes: 0 success; 2 usage/schema; 3 unavailable input; 4 provider/helper unavailable; 5 persistence conflict; 70 internal." in help_text


@pytest.mark.parametrize(
    ("args", "required_phrases"),
    [
        (("inventory",), ("Read-only SQLite inventory.", "Input: --db", "Output: one JSON object", "Example:")),
        (("ingest-media",), ("content-addressed raw cache", "Manifest: --manifest", "Checkpoint: --checkpoint", "Resume:", "Example:")),
        (("extract-media",), ("OCR command JSON contract", "Vision command JSON contract", "source_sha256", "Checkpoint: --checkpoint", "--max-workers", "supported_claims", "Example:")),
        (("review-packets",), ("Review packets", "packet-manifest", "Example:")),
        (("review-packets", "build"), ("--packet-dir", "--batch-size", "deterministic", "no network", "Exit codes:", "Example:")),
        (("reviews",), ("atomically", "per-SHA", "Example:")),
        (("reviews", "apply"), ("media-review-output.schema.json", "--require-complete", "exit 4", "before any manifest write", "Example:")),
        (("ocr-helper",), ("local OCR helpers", "status", "build", "tesseract-status", "Example:")),
        (("ocr-helper", "status"), ("Does not compile or write files.", "command_template", "Example:")),
        (("ocr-helper", "build"), ("Builds the local Apple Vision OCR helper", "--output", "Exit codes:", "Example:")),
        (("ocr-helper", "tesseract-status"), ("Tesseract", "command_template", "--tesseract", "Exit codes:", "Example:")),
        (("audit",), ("--require-extraction", "reconciliation gate", "not_requested", "Output: one JSON object", "Example:")),
    ],
)
def test_subcommand_help_documents_inputs_outputs_resume_and_strict_contracts_without_io(
    tmp_path: Path, args: tuple[str, ...], required_phrases: tuple[str, ...]
) -> None:
    help_text = _help(tmp_path, *args)

    for phrase in required_phrases:
        assert phrase in help_text
