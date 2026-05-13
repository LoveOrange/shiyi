"""Content normalizer extension port."""

from __future__ import annotations

from typing import Protocol

from shiyi.domain.models import ArtifactWrite, InternalItem


class Normalizer(Protocol):
    """Converts an InternalItem payload into an optional canonical artifact.

    Implementations return a normalized ArtifactWrite when they can produce
    canonical content, return None for unsupported/already-canonical payloads,
    and raise exceptions for real normalization failures.
    """

    @property
    def name(self) -> str:
        """Stable normalizer implementation name."""
        ...

    async def normalize(self, event: InternalItem) -> ArtifactWrite | None:
        """Return a canonical artifact for an event, or None if no normalization is needed."""
        ...
