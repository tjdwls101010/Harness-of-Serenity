from __future__ import annotations

import hashlib
import json
import stat
import subprocess
import sys
import tarfile
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_TAG = "v1-final-260817"
SOURCE_COMMIT = "290355655eb1fb0b7b30803879d15eacd52f0416"
ARCHIVE_PATH = REPO_ROOT / "archive" / "v1" / "260817-sessions.tar.gz"
MANIFEST_PATH = REPO_ROOT / "archive" / "v1" / "260817-sessions.manifest.json"


def _git(*args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout


def _tagged_session_blobs() -> list[tuple[str, str, str]]:
    records: list[tuple[str, str, str]] = []
    for entry in _git("ls-tree", "-r", "-z", "--full-tree", SOURCE_TAG, "--", "sessions").split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split()
        assert object_type == "blob"
        records.append((raw_path.decode("utf-8"), mode, object_id))
    return records


def test_v1_session_archive_preserves_only_the_tagged_session_blobs_byte_exactly(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = _tagged_session_blobs()
    archive_bytes = ARCHIVE_PATH.read_bytes()

    assert manifest["source"] == {"tag": SOURCE_TAG, "commit": SOURCE_COMMIT}
    assert manifest["archive"]["sha256"] == hashlib.sha256(archive_bytes).hexdigest()
    assert manifest["archive"]["member_count"] == len(expected) == 16
    assert manifest["creation"]["command"] == ["scripts/.venv/bin/python", "scripts/serenity_v2/archive.py"]
    assert {"python", "tarfile", "zlib"} <= set(manifest["creation"]["tool_version"])
    assert manifest["archive"]["deterministic_metadata"] == {
        "member_order": "ascending UTF-8 relative path",
        "mtime": 0,
        "uid": 0,
        "gid": 0,
        "gzip_mtime": 0,
    }
    assert archive_bytes[:4] == b"\x1f\x8b\x08\x00"
    assert archive_bytes[4:8] == b"\x00\x00\x00\x00"
    assert manifest["exclusions"] == [
        {
            "path": "sessions/**/.DS_Store",
            "reason": "untracked macOS metadata is not present in the tagged source tree",
        }
    ]

    expected_by_path = {path: (mode, object_id) for path, mode, object_id in expected}
    manifest_by_path = {member["original_relative_path"]: member for member in manifest["members"]}
    assert set(manifest_by_path) == set(expected_by_path)

    with tarfile.open(ARCHIVE_PATH, "r:gz") as archive:
        members = archive.getmembers()
        assert [member.name for member in members] == sorted(expected_by_path)
        assert all(member.isfile() and not member.issym() and not member.islnk() for member in members)
        assert all(member.mtime == 0 and member.uid == 0 and member.gid == 0 for member in members)

        archive.extractall(tmp_path, filter="data")

    extracted_files = sorted(
        path.relative_to(tmp_path).as_posix()
        for path in tmp_path.rglob("*")
        if path.is_file()
    )
    assert extracted_files == sorted(expected_by_path)
    assert not any(path.is_symlink() for path in tmp_path.rglob("*"))

    for path, (mode, object_id) in expected_by_path.items():
        member = manifest_by_path[path]
        extracted = tmp_path / path
        blob = _git("cat-file", "blob", object_id)

        assert member["archive_member"] == path
        assert member["git_mode"] == mode
        assert member["bytes"] == len(blob) == extracted.stat().st_size
        assert member["sha256"] == hashlib.sha256(blob).hexdigest() == hashlib.sha256(extracted.read_bytes()).hexdigest()
        assert stat.S_IMODE(extracted.stat().st_mode) == int(mode, 8) & 0o777


def test_v1_session_archive_rebuilds_to_the_checked_in_deterministic_bytes(tmp_path: Path) -> None:
    output_dir = tmp_path / "archive"
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "serenity_core" / "archive.py"),
            "--repo-root",
            str(REPO_ROOT),
            "--output-dir",
            str(output_dir),
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout
    assert (output_dir / "260817-sessions.tar.gz").read_bytes() == ARCHIVE_PATH.read_bytes()
