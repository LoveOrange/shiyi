"""In-memory canonical ContentItem store for deterministic tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from shiyi.domain.models import ContentItem


class MemoryContentItemStore:
    """Stores one immutable canonical document per deterministic id."""

    def __init__(self) -> None:
        """Create an empty store."""
        self.items: dict[str, ContentItem] = {}

    async def get(self, item_id: str) -> ContentItem | None:
        """Return an item by id."""
        return self.items.get(item_id)

    async def upsert(self, item: ContentItem) -> None:
        """Insert or replace one item."""
        self.items[item.id] = item

    async def list_ready(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        source_ids: Sequence[str] = (),
        limit: int = 20,
    ) -> list[ContentItem]:
        """List ready items with deterministic ordering."""
        source_filter = set(source_ids)
        items = [
            item
            for item in self.items.values()
            if item.ready_at is not None
            and (since is None or item.collected_at >= since)
            and (until is None or item.collected_at < until)
            and (not source_filter or item.source_id in source_filter)
        ]
        items.sort(
            key=lambda item: (
                -(item.published_at or item.collected_at).timestamp(),
                item.id,
            )
        )
        return items[: max(limit, 0)]
