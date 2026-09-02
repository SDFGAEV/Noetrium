from __future__ import annotations

import hashlib
from pathlib import Path

from noetrium_platform.capabilities.model.request.api import ContentRef
from noetrium_platform.foundation.kernel.kernel.durability.durable_file import atomic_replace_bytes


class DirectoryContentAddressedStore:
    durability = "crash_durable"

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sha(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def _path(self, digest: str) -> Path:
        return self.root / digest[:2] / f"{digest}.blob"

    def put(self, payload: bytes, *, media_type: str) -> ContentRef:
        payload = bytes(payload)
        digest = self._sha(payload)
        ref = ContentRef(digest, len(payload), media_type)
        path = self._path(digest)
        if path.exists():
            current = path.read_bytes()
            if self._sha(current) != digest:
                raise RuntimeError("existing content-addressed blob failed integrity verification")
            return ref
        atomic_replace_bytes(path, payload)
        return ref

    def get(self, ref: ContentRef) -> bytes:
        payload = self._path(ref.sha256).read_bytes()
        if len(payload) != ref.size_bytes or self._sha(payload) != ref.sha256:
            raise RuntimeError("content-addressed blob integrity mismatch")
        return payload


__all__ = ["DirectoryContentAddressedStore"]
