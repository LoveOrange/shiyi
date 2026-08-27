import asyncio
from datetime import UTC, datetime
from typing import Any

from shiyi import (
    AIEnrichmentRunner,
    AIProviderACL,
    AIProviderRequest,
    ContentItem,
    MemoryContentItemStore,
    content_item_id,
)

NOW = datetime(2026, 7, 19, tzinfo=UTC)


class SummaryProvider:
    name = "summary-provider"

    async def complete(self, request: AIProviderRequest) -> dict[str, Any]:
        requested_id = request.prompt.split('"id":"', maxsplit=1)[1].split('"', maxsplit=1)[0]
        return {
            "items": [
                {
                    "id": requested_id,
                    "language": "fr",
                    "summary": "摘要",
                    "categories": ["technology", "technology"],
                    "tags": ["release"],
                }
            ]
        }


class FailingProvider:
    name = "failing-provider"

    async def complete(self, _request: AIProviderRequest) -> dict[str, Any]:
        message = "model unavailable"
        raise RuntimeError(message)


def test_enrichment_uses_summary_as_the_only_completion_gate() -> None:
    store = MemoryContentItemStore()
    missing = _item("missing")
    source_summary = _item("source-summary", summary="Official summary")
    asyncio.run(store.upsert(missing))
    asyncio.run(store.upsert(source_summary))
    runner = AIEnrichmentRunner(
        content_store=store,
        acl=AIProviderACL(SummaryProvider(), summary_language="zh"),
        clock=lambda: NOW,
    )

    first = asyncio.run(runner.run(limit=5))
    second = asyncio.run(runner.run(limit=5))

    assert first.selected == 1
    assert first.enriched == 1
    assert first.failed == 0
    assert second.selected == 0
    assert store.items[missing.id].summary == "摘要"
    assert store.items[missing.id].summary_language == "zh"
    assert store.items[missing.id].language == "en"
    assert store.items[missing.id].categories == ("technology",)
    assert store.items[source_summary.id].summary == "Official summary"


def test_provider_failure_leaves_deterministic_content_durable() -> None:
    store = MemoryContentItemStore()
    item = _item("missing")
    asyncio.run(store.upsert(item))
    runner = AIEnrichmentRunner(
        content_store=store,
        acl=AIProviderACL(FailingProvider()),
    )

    result = asyncio.run(runner.run(limit=5))

    assert result.enriched == 0
    assert result.failed == 1
    assert store.items[item.id] == item


def _item(source_item_id: str, *, summary: str | None = None) -> ContentItem:
    return ContentItem(
        id=content_item_id(source_id="source", source_item_id=source_item_id),
        source_id="source",
        source_item_id=source_item_id,
        kind="article",
        title=source_item_id,
        collected_at=NOW,
        language="en",
        content="Article content",
        summary=summary,
        content_hash="a" * 64,
        ready_at=NOW,
        updated_at=NOW,
    )
