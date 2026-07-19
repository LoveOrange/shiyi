"""Canonical ContentItem export helpers."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from shiyi.domain.models import ContentItem
from shiyi.ports.content_item_store import ContentItemStore


async def export_items(
    *,
    store: ContentItemStore,
    since: datetime | None = None,
    until: datetime | None = None,
    source_ids: Sequence[str] = (),
    limit: int = 20,
) -> list[ContentItem]:
    """Return ready canonical items without constructing a second export schema."""
    return await store.list_ready(
        since=since,
        until=until,
        source_ids=source_ids,
        limit=limit,
    )
