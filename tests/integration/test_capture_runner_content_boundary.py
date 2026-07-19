import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from shiyi import (
    CaptureConfig,
    CaptureRunner,
    FileSystemBlobStore,
    HtmlPayload,
    MarkdownContentProcessor,
    MemoryContentItemStore,
    Source,
    SourceItem,
    export_items,
)

NOW = datetime(2026, 7, 19, tzinfo=UTC)


class BlogAdapter:
    name = "blog"
    version = "1"

    async def capture(self, source: Source) -> AsyncIterator[SourceItem]:
        yield SourceItem(
            source_id=source.id,
            source_item_id="launch",
            kind="article",
            canonical_url=f"{source.target}/launch",
            collected_at=NOW,
            published_at=NOW,
            payload=HtmlPayload(
                html="<article><h1>Launch</h1><p>Canonical article body.</p></article>"
            ),
            metadata={"title": "Launch", "creators": ["Example team"], "is_complete": True},
        )


def test_briefly_reads_only_canonical_content_without_pipeline_state(tmp_path: Path) -> None:
    source = Source(
        id="example-blog",
        adapter="blog",
        target="https://example.com/blog",
        options={"content_kind": "article"},
    )
    store = MemoryContentItemStore()
    runner = CaptureRunner(
        config=CaptureConfig(sources=(source,)),
        adapters=(BlogAdapter(),),
        processor=MarkdownContentProcessor(clock=lambda: NOW),
        content_store=store,
        blob_store=FileSystemBlobStore(tmp_path / "blobs"),
    )

    result = asyncio.run(runner.run_once())
    [item] = asyncio.run(export_items(store=store))

    assert result.processed == 1
    assert item.source_id == "example-blog"
    assert item.creators == ("Example team",)
    assert item.content == "# Launch\n\nCanonical article body.\n"
    assert item.raw_ref is not None
    assert not hasattr(item, "status")
    assert not hasattr(item, "idempotency_key")
