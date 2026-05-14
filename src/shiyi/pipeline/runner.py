"""Minimal capture pipeline orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from shiyi.domain.models import (
    ArtifactRef,
    ArtifactWrite,
    EnrichmentTask,
    EventRecord,
    InternalItem,
)
from shiyi.ports.adapter import Adapter
from shiyi.ports.ai_provider import AIProvider
from shiyi.ports.artifact_store import ArtifactStore
from shiyi.ports.event_record_store import EventRecordStore
from shiyi.ports.normalizer import Normalizer


@dataclass(frozen=True, slots=True)
class PipelineRunError:
    """Diagnosable failure for one item handled by a pipeline run."""

    event_id: str
    idempotency_key: str
    source: str
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class PipelineRunSummary:
    """Processing counts for one pipeline run."""

    processed: int
    skipped: int
    failed: int
    artifacts: int
    errors: tuple[PipelineRunError, ...]


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

    async def run_once(self) -> PipelineRunSummary:
        """Process discovered events once and return diagnosable run counts."""
        processed = 0
        skipped = 0
        failed = 0
        artifacts = 0
        errors: list[PipelineRunError] = []
        seen_idempotency_keys: set[str] = set()

        async for event in self._adapter.discover():
            if event.idempotency_key in seen_idempotency_keys:
                skipped += 1
                continue
            seen_idempotency_keys.add(event.idempotency_key)

            existing = await self._event_record_store.find_by_idempotency_key(event.idempotency_key)
            if existing is not None and self._is_complete(existing):
                skipped += 1
                continue

            raw_artifact: ArtifactRef | None = None
            normalized_artifact = None
            stage = "raw_artifact"
            try:
                raw_artifact = await self._artifact_store.put(_raw_artifact_from_event(event))
                artifacts += 1

                if self._normalizer is not None:
                    stage = "normalization"
                    normalized_write = await self._normalizer.normalize(event)
                    if normalized_write is not None:
                        stage = "normalized_artifact"
                        normalized_artifact = await self._artifact_store.put(normalized_write)
                        artifacts += 1

                stage = "event_record"
                await self._event_record_store.save_event(
                    event,
                    raw_artifact=raw_artifact,
                    normalized_artifact=normalized_artifact,
                )

                for task in self._enrichment_tasks:
                    stage = f"enrichment:{task.type}"
                    enrichment = await self._ai_provider.run(task, event)
                    stage = f"enrichment_artifact:{task.type}"
                    enrichment_artifact = await self._artifact_store.put(
                        ArtifactWrite(
                            kind="enrichment",
                            media_type="application/json",
                            content=enrichment.model_dump_json().encode(),
                            suggested_name=f"{event.id}-{task.type}.json",
                        )
                    )
                    artifacts += 1
                    stage = f"enrichment_record:{task.type}"
                    await self._event_record_store.save_enrichment(
                        event, enrichment, enrichment_artifact
                    )

                if self._enrichment_tasks:
                    stage = "mark_enriched"
                    await self._event_record_store.mark_enriched(event)

                processed += 1
            except Exception as error:
                failed += 1
                failure = _pipeline_error(event=event, stage=stage, error=error)
                errors.append(failure)
                await self._event_record_store.save_failure(
                    event,
                    raw_artifact=raw_artifact,
                    normalized_artifact=normalized_artifact,
                    error=failure.message,
                )
        return PipelineRunSummary(
            processed=processed,
            skipped=skipped,
            failed=failed,
            artifacts=artifacts,
            errors=tuple(errors),
        )

    def _is_complete(self, record: EventRecord) -> bool:
        if self._enrichment_tasks:
            return record.status == "enriched"
        return record.status in {"persisted", "enriched"}


def _pipeline_error(*, event: InternalItem, stage: str, error: Exception) -> PipelineRunError:
    message = (
        f"{stage} failed for {event.source.kind}/{event.idempotency_key}: "
        f"{type(error).__name__}: {error}"
    )
    return PipelineRunError(
        event_id=event.id,
        idempotency_key=event.idempotency_key,
        source=event.source.kind,
        stage=stage,
        message=message,
    )


def _raw_artifact_from_event(event: InternalItem) -> ArtifactWrite:
    """Convert an internal item payload into its raw artifact representation."""
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
