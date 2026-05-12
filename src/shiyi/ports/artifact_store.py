"""Artifact store extension port."""

from __future__ import annotations

from typing import Protocol

from shiyi.domain.models import ArtifactRead, ArtifactRef, ArtifactWrite


class ArtifactStore(Protocol):
    """Stores raw, normalized, and enrichment artifacts."""

    @property
    def name(self) -> str:
        """Stable artifact store implementation name."""
        ...

    async def put(self, artifact: ArtifactWrite) -> ArtifactRef:
        """Persist an artifact and return a stable reference."""
        ...

    async def get(self, ref: ArtifactRef) -> ArtifactRead:
        """Read a stored artifact by reference."""
        ...

    async def exists(self, ref: ArtifactRef) -> bool:
        """Return whether the artifact exists."""
        ...
