"""Filesystem-backed content-addressed Blob storage."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from shiyi.domain.models import BlobRef


class FileSystemBlobStore:
    """Stores raw, large, or cold bytes by SHA-256."""

    name = "filesystem"

    def __init__(self, root: Path) -> None:
        """Create a Blob store rooted at the given directory."""
        self._root = root

    async def put(self, content: bytes, *, media_type: str) -> BlobRef:
        """Persist bytes once and return their content-addressed reference."""
        digest = sha256(content).hexdigest()
        relative_path = Path(digest[:2]) / digest
        path = self._root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(content)
        return BlobRef(
            store=self.name,
            key=relative_path.as_posix(),
            sha256=digest,
            media_type=media_type,
            size=len(content),
        )

    async def get(self, ref: BlobRef) -> bytes:
        """Read Blob bytes after validating the referenced store."""
        return self._resolve(ref).read_bytes()

    async def exists(self, ref: BlobRef) -> bool:
        """Return whether a Blob exists."""
        return self._resolve(ref).exists()

    def _resolve(self, ref: BlobRef) -> Path:
        if ref.store != self.name:
            msg = f"BlobRef belongs to {ref.store!r}, not {self.name!r}"
            raise ValueError(msg)
        path = (self._root / ref.key).resolve()
        root = self._root.resolve()
        if not path.is_relative_to(root):
            msg = f"Blob reference escapes store root: {ref.key}"
            raise ValueError(msg)
        return path
