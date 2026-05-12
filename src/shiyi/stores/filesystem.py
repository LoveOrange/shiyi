"""Filesystem-backed artifact store."""

from __future__ import annotations

import hashlib
from pathlib import Path

from shiyi.domain.models import ArtifactRead, ArtifactRef, ArtifactWrite


class FileSystemArtifactStore:
    """Stores artifacts on the local filesystem using content-addressed paths."""

    name = "filesystem-artifact-store"

    def __init__(self, root: Path) -> None:
        """Create a store rooted at the given directory."""
        self._root = root

    async def put(self, artifact: ArtifactWrite) -> ArtifactRef:
        """Persist an artifact and return its content-addressed reference."""
        digest = hashlib.sha256(artifact.content).hexdigest()
        relative_path = Path(artifact.kind) / digest[:2] / digest
        path = self._root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes(artifact.content)

        return ArtifactRef(
            uri=relative_path.as_posix(),
            kind=artifact.kind,
            media_type=artifact.media_type,
            size_bytes=len(artifact.content),
            sha256=digest,
        )

    async def get(self, ref: ArtifactRef) -> ArtifactRead:
        """Read an artifact by reference."""
        path = self._resolve(ref)
        return ArtifactRead(ref=ref, content=path.read_bytes())

    async def exists(self, ref: ArtifactRef) -> bool:
        """Return whether an artifact exists."""
        return self._resolve(ref).exists()

    def _resolve(self, ref: ArtifactRef) -> Path:
        path = (self._root / ref.uri).resolve()
        root = self._root.resolve()
        if not path.is_relative_to(root):
            msg = f"artifact reference escapes store root: {ref.uri}"
            raise ValueError(msg)
        return path
