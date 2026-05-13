"""Adapter extension port."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from shiyi.domain.models import InternalItem


class Adapter(Protocol):
    """Reads from an external source and emits internal items."""

    @property
    def name(self) -> str:
        """Stable adapter name."""
        ...

    @property
    def version(self) -> str:
        """Adapter implementation version."""
        ...

    def discover(self) -> AsyncIterator[InternalItem]:
        """Discover source items and yield Adapter -> Pipeline internal items."""
        ...
