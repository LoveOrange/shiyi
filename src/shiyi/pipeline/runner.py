"""Minimal capture pipeline orchestration."""

from __future__ import annotations

from collections.abc import Sequence

from shiyi.domain.models import Checkpoint, EnrichmentTask
from shiyi.ports.adapter import Adapter
from shiyi.ports.ai_provider import AIProvider
from shiyi.ports.persistence import Persistence


class CapturePipeline:
    """Coordinates adapter discovery, AI enrichment, and persistence writes."""

    def __init__(
        self,
        *,
        adapter: Adapter,
        ai_provider: AIProvider,
        persistence: Persistence,
        enrichment_tasks: Sequence[EnrichmentTask],
    ) -> None:
        """Create a pipeline from concrete extension implementations."""
        self._adapter = adapter
        self._ai_provider = ai_provider
        self._persistence = persistence
        self._enrichment_tasks = tuple(enrichment_tasks)

    async def run_once(self, checkpoint: Checkpoint | None = None) -> int:
        """Process discovered events once and return the number of events handled."""
        processed = 0
        async for event in self._adapter.discover(checkpoint):
            raw_result = await self._persistence.save_raw(event)
            if raw_result.status == "conflict":
                continue

            for task in self._enrichment_tasks:
                enrichment = await self._ai_provider.run(task, event)
                await self._persistence.save_enriched(event, enrichment)

            processed += 1
        return processed
