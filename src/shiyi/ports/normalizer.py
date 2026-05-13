"""Content normalizer extension port."""

from __future__ import annotations

from typing import Protocol

from shiyi.domain.models import ArtifactWrite, InternalItem


class Normalizer(Protocol):
    """Converts raw capture payloads into canonical artifacts for AI processing."""

    @property
    def name(self) -> str:
        """Stable normalizer implementation name."""
        ...

    async def normalize(self, event: InternalItem) -> ArtifactWrite | None:
        """Return a canonical artifact for an event, or None if no normalization is needed."""
        ...
