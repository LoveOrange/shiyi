"""Event record store extension port."""

from __future__ import annotations

from typing import Protocol

from shiyi.domain.models import ArtifactRef, EnrichmentResult, EventRecord, InternalItem


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
        event: InternalItem,
        *,
        raw_artifact: ArtifactRef | None,
        normalized_artifact: ArtifactRef | None,
    ) -> EventRecord:
        """Create or update an event processing record."""
        ...

    async def save_enrichment(
        self,
        event: InternalItem,
        result: EnrichmentResult,
        artifact: ArtifactRef,
    ) -> EventRecord:
        """Record a validated enrichment result and its artifact reference."""
        ...

    async def save_failure(
        self,
        event: InternalItem,
        *,
        raw_artifact: ArtifactRef | None,
        normalized_artifact: ArtifactRef | None,
        error: str,
    ) -> EventRecord:
        """Record a failed item attempt with available artifact context."""
        ...

    async def mark_enriched(self, event: InternalItem) -> EventRecord:
        """Mark an event fully enriched after all configured tasks succeed."""
        ...
