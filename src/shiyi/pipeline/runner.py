"""Briefly-first capture orchestration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from shiyi.domain.models import (
    CaptureConfig,
    ContentItem,
    Source,
    SourceItem,
    source_item_raw_bytes,
    source_item_raw_media_type,
)
from shiyi.ports.blob_store import BlobStore
from shiyi.ports.content_item_store import ContentItemStore
from shiyi.ports.content_processor import ContentProcessor
from shiyi.ports.source_adapter import SourceAdapter


@dataclass(frozen=True, slots=True)
class CaptureRunError:
    """Diagnosable failure for one source or source item."""

    source_id: str
    source_item_id: str | None
    stage: str
    message: str


@dataclass(frozen=True, slots=True)
class CaptureRunSummary:
    """Deterministic outcome counts for one configured capture run."""

    processed: int
    skipped: int
    failed: int
    blobs: int
    errors: tuple[CaptureRunError, ...]


@dataclass(slots=True)
class _CaptureRunState:
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    blobs: int = 0
    errors: list[CaptureRunError] = field(default_factory=list)
    seen_item_ids: set[str] = field(default_factory=set)
    seen_canonical_urls: set[tuple[str, str]] = field(default_factory=set)

    def summary(self) -> CaptureRunSummary:
        return CaptureRunSummary(
            processed=self.processed,
            skipped=self.skipped,
            failed=self.failed,
            blobs=self.blobs,
            errors=tuple(self.errors),
        )


class CaptureRunner:
    """Runs configured sources through adapters into canonical storage."""

    def __init__(  # noqa: PLR0913
        self,
        *,
        config: CaptureConfig,
        adapters: Sequence[SourceAdapter],
        processor: ContentProcessor,
        content_store: ContentItemStore,
        blob_store: BlobStore | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Create the composition root for one capture configuration."""
        self._config = config
        self._adapters = _adapter_map(adapters)
        self._processor = processor
        self._content_store = content_store
        self._blob_store = blob_store
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run_once(self) -> CaptureRunSummary:
        """Capture every enabled source once without cross-source failure coupling."""
        state = _CaptureRunState()
        for source in self._config.sources:
            if source.enabled:
                await self._capture_source(source, state=state)
        return state.summary()

    async def _capture_source(self, source: Source, *, state: _CaptureRunState) -> None:
        adapter = self._adapters.get(source.adapter)
        if adapter is None:
            state.failed += 1
            state.errors.append(
                _error(
                    source=source,
                    item=None,
                    stage="adapter_resolution",
                    error=LookupError(f"no adapter registered as {source.adapter!r}"),
                )
            )
            return
        try:
            async for item in adapter.capture(source):
                await self._capture_item(source=source, item=item, state=state)
        except Exception as error:
            state.failed += 1
            state.errors.append(_error(source=source, item=None, stage="capture", error=error))

    async def _capture_item(
        self,
        *,
        source: Source,
        item: SourceItem,
        state: _CaptureRunState,
    ) -> None:
        stage = "validation"
        try:
            _validate_source_item(source=source, item=item)
            if item.canonical_url is not None:
                canonical_identity = (item.source_id, str(item.canonical_url))
                if canonical_identity in state.seen_canonical_urls:
                    state.skipped += 1
                    return
                state.seen_canonical_urls.add(canonical_identity)
            raw_ref = None
            if self._blob_store is not None:
                stage = "blob_persistence"
                raw_ref = await self._blob_store.put(
                    source_item_raw_bytes(item),
                    media_type=source_item_raw_media_type(item),
                )
                state.blobs += 1

            stage = "content_processing"
            content_item = await self._processor.process(item, raw_ref=raw_ref)
            if content_item.id in state.seen_item_ids:
                state.skipped += 1
                return
            state.seen_item_ids.add(content_item.id)

            stage = "content_lookup"
            existing = await self._content_store.get(content_item.id)
            deterministic_item = _preserve_existing_ai_fields(
                current=content_item,
                existing=existing,
            )
            if existing is not None and _same_durable_content(existing, deterministic_item):
                state.skipped += 1
                return
            stage = "content_upsert"
            await self._content_store.upsert(deterministic_item)
            state.processed += 1
        except Exception as error:
            state.failed += 1
            state.errors.append(_error(source=source, item=item, stage=stage, error=error))


def _adapter_map(adapters: Sequence[SourceAdapter]) -> dict[str, SourceAdapter]:
    resolved: dict[str, SourceAdapter] = {}
    for adapter in adapters:
        if adapter.name in resolved:
            msg = f"duplicate SourceAdapter name: {adapter.name}"
            raise ValueError(msg)
        resolved[adapter.name] = adapter
    return resolved


def _validate_source_item(*, source: Source, item: SourceItem) -> None:
    if item.source_id != source.id:
        msg = f"adapter emitted SourceItem for {item.source_id!r}, expected {source.id!r}"
        raise ValueError(msg)


def _preserve_existing_ai_fields(
    *,
    current: ContentItem,
    existing: ContentItem | None,
) -> ContentItem:
    if existing is None or existing.content_hash != current.content_hash:
        return current
    return ContentItem.model_validate(
        {
            **current.model_dump(mode="python"),
            "language": current.language or existing.language,
            "summary": current.summary or existing.summary,
            "summary_language": (
                current.summary_language
                if _clean_optional(current.summary) is not None
                else current.summary_language or existing.summary_language
            ),
            "categories": existing.categories,
            "tags": existing.tags,
        }
    )


def _same_durable_content(existing: ContentItem, current: ContentItem) -> bool:
    """Compare persisted product fields while ignoring run timestamps."""
    ignored = {"collected_at", "ready_at", "updated_at"}
    existing_fields = existing.model_dump(mode="python", exclude=ignored)
    current_fields = current.model_dump(mode="python", exclude=ignored)
    return existing_fields == current_fields and bool(existing.ready_at) is bool(current.ready_at)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _error(
    *,
    source: Source,
    item: SourceItem | None,
    stage: str,
    error: Exception,
) -> CaptureRunError:
    return CaptureRunError(
        source_id=source.id,
        source_item_id=item.source_item_id if item is not None else None,
        stage=stage,
        message=f"{type(error).__name__}: {error}",
    )
