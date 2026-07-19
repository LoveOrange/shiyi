import asyncio
from datetime import UTC, datetime

import pytest

from shiyi import BinaryPayload, HtmlPayload, MarkdownContentProcessor, SourceItem

NOW = datetime(2026, 7, 19, tzinfo=UTC)


def test_processor_builds_canonical_markdown_and_promotes_creators() -> None:
    item = SourceItem(
        source_id="deepmind-blog",
        source_item_id="alpha",
        kind="article",
        canonical_url="https://deepmind.google/blog/alpha/",
        collected_at=NOW,
        published_at=NOW,
        summary="  A source-provided summary.  ",
        payload=HtmlPayload(
            html="<body><nav>Menu</nav><article><h1>Alpha</h1><p>Body.</p></article></body>"
        ),
        metadata={
            "title": "Alpha",
            "author": "DeepMind team",
            "source_metrics": {"views": 10, "invalid": "no"},
            "source_only": "kept",
        },
    )

    content = asyncio.run(MarkdownContentProcessor(clock=lambda: NOW).process(item, raw_ref=None))

    assert content.title == "Alpha"
    assert content.creators == ("DeepMind team",)
    assert content.content == "# Alpha\n\nBody.\n"
    assert content.metrics == {"views": 10}
    assert content.summary == "A source-provided summary."
    assert content.extra == {"source_only": "kept"}
    assert content.ready_at == NOW


def test_binary_payload_requires_a_dedicated_processor() -> None:
    item = SourceItem(
        source_id="video",
        source_item_id="1",
        kind="video",
        collected_at=NOW,
        payload=BinaryPayload(media_type="video/mp4", bytes_ref="cos://bucket/1"),
        metadata={"title": "Video"},
    )

    with pytest.raises(ValueError, match="dedicated ContentProcessor"):
        asyncio.run(MarkdownContentProcessor().process(item, raw_ref=None))


def test_incomplete_source_material_is_persistable_but_not_ready() -> None:
    item = SourceItem(
        source_id="openai-news",
        source_item_id="preview",
        kind="article",
        collected_at=NOW,
        payload=HtmlPayload(html="<article><h1>Preview</h1><p>Short feed preview.</p></article>"),
        metadata={"title": "Preview", "is_complete": False},
    )

    content = asyncio.run(MarkdownContentProcessor(clock=lambda: NOW).process(item, raw_ref=None))

    assert content.content
    assert content.ready_at is None
