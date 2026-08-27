"""Optional post-capture AI enrichment orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from shiyi.ai.acl import AIProviderACL
from shiyi.pipeline.ai_fields import merge_ai_content_fields
from shiyi.ports.content_item_store import ContentItemStore


@dataclass(frozen=True, slots=True)
class AIEnrichmentSummary:
    """Machine-readable result of one bounded enrichment run."""

    provider: str
    selected: int
    enriched: int
    failed: int
    errors: tuple[str, ...]


class AIEnrichmentRunner:
    """Backfills missing summaries without introducing persistent workflow state."""

    def __init__(
        self,
        *,
        content_store: ContentItemStore,
        acl: AIProviderACL,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        """Configure the canonical store and provider ACL."""
        self._content_store = content_store
        self._acl = acl
        self._clock = clock or (lambda: datetime.now(UTC))

    async def run(self, *, limit: int) -> AIEnrichmentSummary:
        """Enrich a bounded newest-first batch whose summary is empty."""
        items = await self._content_store.list_missing_summary(limit=limit)
        if not items:
            return AIEnrichmentSummary(
                provider=self._acl.provider_name,
                selected=0,
                enriched=0,
                failed=0,
                errors=(),
            )
        try:
            fields_by_id = await self._acl.process_many(items)
        except Exception as error:
            return AIEnrichmentSummary(
                provider=self._acl.provider_name,
                selected=len(items),
                enriched=0,
                failed=len(items),
                errors=(f"provider: {type(error).__name__}: {error}",),
            )

        enriched = 0
        errors: list[str] = []
        for item in items:
            try:
                fields = fields_by_id[item.id]
                enriched_item = merge_ai_content_fields(
                    item=item,
                    fields=fields,
                    updated_at=self._clock(),
                )
                await self._content_store.upsert(enriched_item)
                enriched += 1
            except Exception as error:
                errors.append(f"{item.id}: {type(error).__name__}: {error}")
        return AIEnrichmentSummary(
            provider=self._acl.provider_name,
            selected=len(items),
            enriched=enriched,
            failed=len(errors),
            errors=tuple(errors),
        )
