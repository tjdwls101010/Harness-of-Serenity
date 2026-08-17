from __future__ import annotations

from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]


def test_historical_runtime_is_external_while_format_versions_remain_explicit() -> None:
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout.decode().split("\0")
    tracked = [relative for relative in tracked if relative]
    archive_version = "v" + "1"
    forbidden_paths = {
        f"archive/{archive_version}/260817-sessions.manifest.json",
        f"archive/{archive_version}/260817-sessions.tar.gz",
        "scripts/serenity_core/archive.py",
        f"tests/260817/artifacts/test_{archive_version}_session_archive.py",
    }
    versioned_formats = {
        "config/evidence-catalog.v1.json",
        "method/claim-ledger.v1.json",
        "method/codebook.v1.json",
        "method/coding.v1.json",
        "data/corpus-media-manifest.v1.jsonl",
    }

    assert forbidden_paths.isdisjoint(tracked)
    assert versioned_formats.issubset(tracked)
    legacy_namespace = "serenity_" + "v" + "2"
    offenders = []
    for relative in tracked:
        if Path(relative).suffix not in {".json", ".jsonl", ".md", ".py", ".yml", ".yaml"}:
            continue
        try:
            text = (ROOT / relative).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if legacy_namespace in text:
            offenders.append(relative)
    assert offenders == []
    for relative in ("scripts/eval", "scripts/modules", "scripts/pipeline", "scripts/tests", "archive"):
        assert not (ROOT / relative).exists()


def test_current_documentation_is_separate_from_cutover_history() -> None:
    assert not (ROOT / "docs" / "plans").exists()
    assert {
        "README.md",
        "contracts-and-runtime.md",
        "corpus-and-method.md",
        "harness-and-evaluation.md",
    } == {path.name for path in (ROOT / "docs" / "architecture").iterdir()}
    assert (ROOT / "docs" / "evaluation" / "evaluation-report.json").is_file()
