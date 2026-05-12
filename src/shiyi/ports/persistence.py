"""Persistence extension port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

from shiyi.domain.models import CaptureEvent, Checkpoint, EnrichmentResult

PersistenceStatus = Literal["committed", "duplicate", "conflict"]


@dataclass(frozen=True, slots=True)
class PersistenceResult:
    """Outcome of a persistence write."""

    status: PersistenceStatus
    record_id: str | None = None
    reason: str | None = None


class Persistence(Protocol):
    """Stores raw events, enriched results, and checkpoints."""

    @property
    def name(self) -> str:
        """Stable persistence implementation name."""
        ...

    async def save_raw(self, event: CaptureEvent) -> PersistenceResult:
        """Persist a raw capture event."""
        ...

    async def save_enriched(
        self,
        event: CaptureEvent,
        result: EnrichmentResult,
    ) -> PersistenceResult:
        """Persist an enriched capture result."""
        ...

    async def commit_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Commit a checkpoint after successful processing."""
        ...
