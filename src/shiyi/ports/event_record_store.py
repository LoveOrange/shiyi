"""Event record store extension port."""

from __future__ import annotations

from typing import Protocol

from shiyi.domain.models import ArtifactRef, CaptureEvent, EnrichmentResult, EventRecord


class EventRecordStore(Protocol):
    """Tracks event status, idempotency, and artifact references."""

    @property
    def name(self) -> str:
        """Stable event record store implementation name."""
        ...

    async def find_by_idempotency_key(self, idempotency_key: str) -> EventRecord | None:
        """Find an existing event record by idempotency key."""
        ...

    async def save_event(
        self,
        event: CaptureEvent,
        *,
        raw_artifact: ArtifactRef | None,
        normalized_artifact: ArtifactRef | None,
    ) -> EventRecord:
        """Create or update an event processing record."""
        ...

    async def save_enrichment(
        self,
        event: CaptureEvent,
        result: EnrichmentResult,
        artifact: ArtifactRef,
    ) -> EventRecord:
        """Record a validated enrichment result and its artifact reference."""
        ...
