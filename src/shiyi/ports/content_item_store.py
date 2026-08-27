"""Canonical content persistence port."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from shiyi.domain.models import ContentItem


class ContentItemStore(Protocol):
    """Persists canonical ContentItem documents by deterministic id."""

    async def get(self, item_id: str) -> ContentItem | None:
        """Return a canonical item by id when present."""
        ...

    async def upsert(self, item: ContentItem) -> None:
        """Insert or replace the canonical document with the same id."""
        ...

    async def list_ready(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        source_ids: Sequence[str] = (),
        limit: int = 20,
    ) -> list[ContentItem]:
        """List ready items for local inspection or consumer export."""
        ...

    async def list_missing_summary(self, *, limit: int = 20) -> list[ContentItem]:
        """List ready items whose summary is empty for optional AI backfill."""
        ...
