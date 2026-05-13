"""AI provider extension port."""

from __future__ import annotations

from typing import Protocol

from shiyi.domain.models import EnrichmentResult, EnrichmentTask, InternalItem


class AIProvider(Protocol):
    """Runs typed enrichment tasks for internal items."""

    @property
    def name(self) -> str:
        """Stable provider name."""
        ...

    async def run(self, task: EnrichmentTask, event: InternalItem) -> EnrichmentResult:
        """Execute an enrichment task and return a validated result."""
        ...
