"""Briefly-first capture orchestration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from shiyi.domain.models import (
    AIContentFields,
    CaptureConfig,
    ContentItem,
    Source,
    SourceItem,
    payload_bytes,
    payload_media_type,
)
from shiyi.ports.ai_processor import AIProcessor
from shiyi.ports.blob_store import BlobStore
from shiyi.ports.content_item_store import ContentItemStore
from shiyi.ports.content_processor import ContentProcessor
from shiyi.ports.source_adapter import SourceAdapter

MAX_LABELS = 32
MAX_LABEL_LENGTH = 100


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
    ai_failed: int
    blobs: int
    errors: tuple[CaptureRunError, ...]


@dataclass(slots=True)
class _CaptureRunState:
    processed: int = 0
    skipped: int = 0
    failed: int = 0
    ai_failed: int = 0
    blobs: int = 0
    errors: list[CaptureRunError] = field(default_factory=list)
    seen_item_ids: set[str] = field(default_factory=set)
    seen_canonical_urls: set[tuple[str, str]] = field(default_factory=set)

    def summary(self) -> CaptureRunSummary:
        return CaptureRunSummary(
            processed=self.processed,
            skipped=self.skipped,
            failed=self.failed,
            ai_failed=self.ai_failed,
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
        ai_processor: AIProcessor | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Create the composition root for one capture configuration."""
        self._config = config
        self._adapters = _adapter_map(adapters)
        self._processor = processor
        self._content_store = content_store
        self._blob_store = blob_store
        self._ai_processor = ai_processor
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
                    payload_bytes(item.payload),
                    media_type=payload_media_type(item.payload),
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
            if (
                existing is not None
                and _same_durable_content(existing, deterministic_item)
                and self._ai_processor is None
            ):
                state.skipped += 1
                return
            stage = "content_upsert"
            await self._content_store.upsert(deterministic_item)
            state.processed += 1
            await self._apply_ai(
                source=source,
                source_item=item,
                content_item=deterministic_item,
                state=state,
            )
        except Exception as error:
            state.failed += 1
            state.errors.append(_error(source=source, item=item, stage=stage, error=error))

    async def _apply_ai(
        self,
        *,
        source: Source,
        source_item: SourceItem,
        content_item: ContentItem,
        state: _CaptureRunState,
    ) -> None:
        if self._ai_processor is None:
            return
        try:
            proposed_fields = await self._ai_processor.process(content_item)
            fields = AIContentFields.model_validate(proposed_fields)
            enriched_item = _merge_ai_fields(
                item=content_item,
                fields=fields,
                updated_at=self._clock(),
            )
            await self._content_store.upsert(enriched_item)
        except Exception as error:
            state.ai_failed += 1
            state.errors.append(
                _error(
                    source=source,
                    item=source_item,
                    stage="ai_processing",
                    error=error,
                )
            )


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


def _merge_ai_fields(
    *,
    item: ContentItem,
    fields: AIContentFields,
    updated_at: datetime,
) -> ContentItem:
    source_summary = _clean_optional(item.summary)
    update: dict[str, Any] = {
        "language": item.language or _clean_optional(fields.language),
        "summary": source_summary or _clean_optional(fields.summary),
        "summary_language": (
            item.summary_language
            if source_summary is not None
            else _clean_optional(fields.summary_language) or item.summary_language
        ),
        "categories": _labels(fields.categories) or item.categories,
        "tags": _labels(fields.tags) or item.tags,
        "updated_at": updated_at,
    }
    return ContentItem.model_validate({**item.model_dump(mode="python"), **update})


def _same_durable_content(existing: ContentItem, current: ContentItem) -> bool:
    """Compare persisted product fields while ignoring run timestamps."""
    ignored = {"collected_at", "ready_at", "updated_at"}
    existing_fields = existing.model_dump(mode="python", exclude=ignored)
    current_fields = current.model_dump(mode="python", exclude=ignored)
    return existing_fields == current_fields and bool(existing.ready_at) is bool(current.ready_at)


def _labels(values: Sequence[str]) -> tuple[str, ...]:
    cleaned = (
        value.strip()
        for value in values[:MAX_LABELS]
        if value.strip() and len(value.strip()) <= MAX_LABEL_LENGTH
    )
    return tuple(dict.fromkeys(cleaned))


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
