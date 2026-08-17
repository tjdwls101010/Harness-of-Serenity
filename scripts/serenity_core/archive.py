"""Create the immutable v1 session archive from its signed Git source."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import zlib
from dataclasses import dataclass
from pathlib import Path


SOURCE_TAG = "v1-final-260817"
SOURCE_COMMIT = "290355655eb1fb0b7b30803879d15eacd52f0416"
ARCHIVE_NAME = "260817-sessions.tar.gz"
MANIFEST_NAME = "260817-sessions.manifest.json"
EXCLUSIONS = [
    {
        "path": "sessions/**/.DS_Store",
        "reason": "untracked macOS metadata is not present in the tagged source tree",
    }
]


@dataclass(frozen=True)
class TaggedBlob:
    path: str
    mode: str
    object_id: str
    data: bytes


def _git(repo_root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
    ).stdout


def _tagged_session_blobs(repo_root: Path) -> list[TaggedBlob]:
    resolved_commit = _git(repo_root, "rev-parse", f"{SOURCE_TAG}^{{commit}}").decode("ascii").strip()
    if resolved_commit != SOURCE_COMMIT:
        raise RuntimeError(f"{SOURCE_TAG} resolves to {resolved_commit}, not pinned {SOURCE_COMMIT}")

    blobs: list[TaggedBlob] = []
    output = _git(repo_root, "ls-tree", "-r", "-z", "--full-tree", SOURCE_TAG, "--", "sessions")
    for record in output.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode, object_type, object_id = metadata.decode("ascii").split()
        if object_type != "blob" or mode not in {"100644", "100755"}:
            raise RuntimeError(f"refusing non-regular session entry: {raw_path!r}")
        path = raw_path.decode("utf-8")
        blobs.append(TaggedBlob(path=path, mode=mode, object_id=object_id, data=_git(repo_root, "cat-file", "blob", object_id)))

    return sorted(blobs, key=lambda blob: blob.path)


def _tar_gz(blobs: list[TaggedBlob]) -> bytes:
    buffer = io.BytesIO()
    with gzip.GzipFile(fileobj=buffer, mode="wb", filename="", mtime=0) as gzip_file:
        with tarfile.open(fileobj=gzip_file, mode="w", format=tarfile.GNU_FORMAT) as archive:
            for blob in blobs:
                info = tarfile.TarInfo(blob.path)
                info.size = len(blob.data)
                info.mode = int(blob.mode, 8) & 0o777
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                archive.addfile(info, io.BytesIO(blob.data))
    return buffer.getvalue()


def build_v1_session_archive(repo_root: Path, output_dir: Path) -> tuple[Path, Path]:
    """Materialize only tagged v1 session blobs into a reproducible tar.gz and manifest."""
    blobs = _tagged_session_blobs(repo_root)
    if len(blobs) != 16:
        raise RuntimeError(f"expected 16 tagged v1 session files, found {len(blobs)}")

    archive_bytes = _tar_gz(blobs)
    archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    manifest = {
        "source": {"tag": SOURCE_TAG, "commit": SOURCE_COMMIT},
        "archive": {
            "format": "tar.gz",
            "sha256": archive_sha256,
            "member_count": len(blobs),
            "deterministic_metadata": {
                "member_order": "ascending UTF-8 relative path",
                "mtime": 0,
                "uid": 0,
                "gid": 0,
                "gzip_mtime": 0,
            },
        },
        "members": [
            {
                "original_relative_path": blob.path,
                "archive_member": blob.path,
                "git_mode": blob.mode,
                "bytes": len(blob.data),
                "sha256": hashlib.sha256(blob.data).hexdigest(),
            }
            for blob in blobs
        ],
        "creation": {
            "command": ["scripts/.venv/bin/python", "scripts/serenity_v2/archive.py"],
            "tool_version": {
                "python": sys.version.split()[0],
                "tarfile": getattr(tarfile, "__version__", "stdlib"),
                "zlib": zlib.ZLIB_VERSION,
            },
        },
        "exclusions": EXCLUSIONS,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / ARCHIVE_NAME
    manifest_path = output_dir / MANIFEST_NAME
    archive_path.write_bytes(archive_bytes)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return archive_path, manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else repo_root / "archive" / "v1"
    archive_path, manifest_path = build_v1_session_archive(repo_root, output_dir)
    print(json.dumps({"archive": str(archive_path), "manifest": str(manifest_path)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
