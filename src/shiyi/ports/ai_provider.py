"""AI provider extension port."""

from __future__ import annotations

from typing import Protocol

from shiyi.domain.models import CaptureEvent, EnrichmentResult, EnrichmentTask


class AIProvider(Protocol):
    """Runs typed enrichment tasks for capture events."""

    @property
    def name(self) -> str:
        """Stable provider name."""
        ...

    async def run(self, task: EnrichmentTask, event: CaptureEvent) -> EnrichmentResult:
        """Execute an enrichment task and return a validated result."""
        ...
