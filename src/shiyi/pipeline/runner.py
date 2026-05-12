"""Minimal capture pipeline orchestration."""

from __future__ import annotations

from collections.abc import Sequence

from shiyi.domain.models import ArtifactWrite, CaptureEvent, EnrichmentTask
from shiyi.ports.adapter import Adapter
from shiyi.ports.ai_provider import AIProvider
from shiyi.ports.artifact_store import ArtifactStore
from shiyi.ports.event_record_store import EventRecordStore
from shiyi.ports.normalizer import Normalizer


class CapturePipeline:
    """Coordinates adapter discovery, AI enrichment, and persistence writes."""

    # Six dependencies are intentional at this composition root; each is an explicit port.
    def __init__(  # noqa: PLR0913
        self,
        *,
        adapter: Adapter,
        ai_provider: AIProvider,
        artifact_store: ArtifactStore,
        event_record_store: EventRecordStore,
        enrichment_tasks: Sequence[EnrichmentTask],
        normalizer: Normalizer | None = None,
    ) -> None:
        """Create a pipeline from concrete extension implementations."""
        self._adapter = adapter
        self._ai_provider = ai_provider
        self._artifact_store = artifact_store
        self._event_record_store = event_record_store
        self._enrichment_tasks = tuple(enrichment_tasks)
        self._normalizer = normalizer

    async def run_once(self) -> int:
        """Process discovered events once and return the number of events handled."""
        processed = 0
        async for event in self._adapter.discover():
            existing = await self._event_record_store.find_by_idempotency_key(event.idempotency_key)
            if existing is not None and existing.status == "enriched":
                continue

            raw_artifact = await self._artifact_store.put(_raw_artifact_from_event(event))
            normalized_artifact = None
            if self._normalizer is not None:
                normalized_write = await self._normalizer.normalize(event)
                if normalized_write is not None:
                    normalized_artifact = await self._artifact_store.put(normalized_write)

            await self._event_record_store.save_event(
                event,
                raw_artifact=raw_artifact,
                normalized_artifact=normalized_artifact,
            )

            for task in self._enrichment_tasks:
                enrichment = await self._ai_provider.run(task, event)
                enrichment_artifact = await self._artifact_store.put(
                    ArtifactWrite(
                        kind="enrichment",
                        media_type="application/json",
                        content=enrichment.model_dump_json().encode(),
                        suggested_name=f"{event.id}-{task.type}.json",
                    )
                )
                await self._event_record_store.save_enrichment(
                    event, enrichment, enrichment_artifact
                )

            if self._enrichment_tasks:
                await self._event_record_store.mark_enriched(event)

            processed += 1
        return processed


def _raw_artifact_from_event(event: CaptureEvent) -> ArtifactWrite:
    """Convert a capture event payload into its raw artifact representation."""
    match event.payload.type:
        case "html":
            return ArtifactWrite(
                kind="raw",
                media_type="text/html",
                content=event.payload.html.encode(),
                suggested_name=f"{event.id}.html",
            )
        case "text":
            return ArtifactWrite(
                kind="raw",
                media_type=event.payload.content_type,
                content=event.payload.text.encode(),
                suggested_name=f"{event.id}.txt",
            )
        case "binary":
            return ArtifactWrite(
                kind="raw",
                media_type=event.payload.media_type,
                content=event.payload.bytes_ref.encode(),
                suggested_name=f"{event.id}.ref",
            )
