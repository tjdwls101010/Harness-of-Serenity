"""Content-addressed raw provider payload cache.

``source.content_sha256`` resolves to ``.serenity/cache/provider-raw/sha256/<digest>`` by default.
Only the ignored cache contains response bytes; envelopes and cache results retain hashes and paths only.
"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal

from serenity_v2.providers.base import ProviderEnvelope


RAW_PAYLOAD_CACHE_ROOT = Path(".serenity") / "cache" / "provider-raw"
_SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")


class RawPayloadConflictError(ValueError):
    pass


@dataclass(frozen=True)
class RawPayloadCacheResult:
    status: Literal["stored", "already_present", "no_raw_payload"]
    content_sha256: str | None
    path: Path | None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "status": self.status,
            "content_sha256": self.content_sha256,
            "cache_path": str(self.path) if self.path is not None else None,
        }


class RawPayloadStore:
    """Persist exact response bytes under the stable SHA-256 path convention."""

    def __init__(self, root: Path | str = RAW_PAYLOAD_CACHE_ROOT) -> None:
        self.root = Path(root)

    def path_for(self, content_sha256: str) -> Path:
        if _SHA256_PATTERN.fullmatch(content_sha256) is None:
            raise ValueError("content_sha256 must be a lowercase SHA-256 digest")
        return self.root / "sha256" / content_sha256

    def cache(self, envelope: ProviderEnvelope) -> RawPayloadCacheResult:
        results = self.cache_all(envelope)
        source_sha256 = envelope.to_dict()["source"]["content_sha256"]
        for result in results:
            if result.content_sha256 == source_sha256:
                return result
        return results[0]

    def cache_all(self, envelope: ProviderEnvelope) -> list[RawPayloadCacheResult]:
        document = envelope.to_dict()
        raw_payloads = envelope._raw_payloads
        if not raw_payloads:
            return [RawPayloadCacheResult("no_raw_payload", document["source"]["content_sha256"], None)]
        return [self._cache_payload(content_sha256, raw_content) for content_sha256, raw_content in raw_payloads.items()]

    def _cache_payload(self, content_sha256: str, raw_content: bytes) -> RawPayloadCacheResult:
        if hashlib.sha256(raw_content).hexdigest() != content_sha256:
            raise RawPayloadConflictError("private raw payload content hash does not match the envelope")
        path = self.path_for(content_sha256)
        if path.exists():
            self._verify_existing(path, content_sha256)
            return RawPayloadCacheResult("already_present", content_sha256, path)

        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{content_sha256}.", dir=path.parent)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as temporary:
                temporary.write(raw_content)
                temporary.flush()
                os.fsync(temporary.fileno())
            try:
                os.link(temporary_path, path)
            except FileExistsError:
                self._verify_existing(path, content_sha256)
                return RawPayloadCacheResult("already_present", content_sha256, path)
            self._fsync_directory(path.parent)
            return RawPayloadCacheResult("stored", content_sha256, path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def read(self, content_sha256: str) -> bytes:
        path = self.path_for(content_sha256)
        raw_content = path.read_bytes()
        self._verify_bytes(raw_content, content_sha256)
        return raw_content

    @staticmethod
    def _verify_existing(path: Path, content_sha256: str) -> None:
        RawPayloadStore._verify_bytes(path.read_bytes(), content_sha256)

    @staticmethod
    def _verify_bytes(raw_content: bytes, content_sha256: str) -> None:
        if hashlib.sha256(raw_content).hexdigest() != content_sha256:
            raise RawPayloadConflictError("cached raw payload content hash does not match its path")

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        descriptor = os.open(path, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def cache_provider_raw_payloads(
    envelopes: Iterable[ProviderEnvelope], *, root: Path | str = RAW_PAYLOAD_CACHE_ROOT
) -> list[RawPayloadCacheResult]:
    """Cache live provider envelopes without adding raw bytes to their serialized documents."""
    store = RawPayloadStore(root)
    return [result for envelope in envelopes for result in store.cache_all(envelope)]
