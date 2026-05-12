"""Adapter extension port."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from shiyi.domain.models import CaptureEvent


class Adapter(Protocol):
    """Reads from an external source and emits normalized capture events."""

    @property
    def name(self) -> str:
        """Stable adapter name."""
        ...

    @property
    def version(self) -> str:
        """Adapter implementation version."""
        ...

    def discover(self) -> AsyncIterator[CaptureEvent]:
        """Discover source items and yield normalized capture events."""
        ...
