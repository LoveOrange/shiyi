"""Source collection extension port."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from shiyi.domain.models import Source, SourceItem


class SourceAdapter(Protocol):
    """Captures configured external sources into transient source items."""

    @property
    def name(self) -> str:
        """Return the stable adapter key used by `Source.adapter`."""
        ...

    @property
    def version(self) -> str:
        """Return the adapter implementation version."""
        ...

    def capture(self, source: Source) -> AsyncIterator[SourceItem]:
        """Capture one configured source target."""
        ...
