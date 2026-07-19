"""Optional neutral AI processing port."""

from __future__ import annotations

from typing import Protocol

from shiyi.domain.models import AIContentFields, ContentItem


class AIProcessor(Protocol):
    """Proposes neutral reusable fields for canonical content."""

    async def process(self, item: ContentItem) -> AIContentFields:
        """Return neutral fields; do not summarize when ``item.summary`` is non-empty."""
        ...
