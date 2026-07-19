import asyncio
from datetime import UTC, datetime

from shiyi import ContentItem, MemoryContentItemStore, content_item_id, export_items

NOW = datetime(2026, 7, 19, tzinfo=UTC)


def test_export_returns_the_canonical_content_item_without_a_second_schema() -> None:
    store = MemoryContentItemStore()
    item = ContentItem(
        id=content_item_id(source_id="openai-news", source_item_id="1"),
        source_id="openai-news",
        source_item_id="1",
        kind="article",
        title="News",
        collected_at=NOW,
        content="News body\n",
        content_hash="a" * 64,
        ready_at=NOW,
        updated_at=NOW,
    )
    asyncio.run(store.upsert(item))

    exported = asyncio.run(export_items(store=store))

    assert exported == [item]
