"""Canonical content processing port."""

from __future__ import annotations

from typing import Protocol

from shiyi.domain.models import BlobRef, ContentItem, SourceItem


class ContentProcessor(Protocol):
    """Converts one source item into a canonical content document."""

    async def process(
        self,
        item: SourceItem,
        *,
        raw_ref: BlobRef | None,
    ) -> ContentItem:
        """Return deterministic canonical content for a source item."""
        ...
