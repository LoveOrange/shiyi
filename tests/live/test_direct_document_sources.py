import asyncio
import os

import pytest

from shiyi import build_capture_config, build_source_adapters
from shiyi.domain.models import Source, SourceItem
from shiyi.ports.source_adapter import SourceAdapter

DIRECT_DOCUMENT_SOURCE_NAMES = (
    "openai-gpt-live-system-card",
    "openai-content-provenance",
    "deepmind-synthid",
)
MIN_USABLE_CONTENT_CHARS = 500


@pytest.mark.skipif(
    os.getenv("SHIYI_RUN_LIVE_TESTS") != "1",
    reason="live public source smoke tests are opt-in",
)
@pytest.mark.parametrize("source_name", DIRECT_DOCUMENT_SOURCE_NAMES)
def test_direct_document_source_is_live(source_name: str) -> None:
    config = build_capture_config((source_name,))
    [adapter] = build_source_adapters(config, window=None)

    [item] = asyncio.run(_collect(adapter, config.sources[0]))

    assert item.source_id == config.sources[0].id
    assert item.source_item_id.startswith("https://")
    assert item.canonical_url is not None
    assert item.metadata["title"]
    if item.payload.type == "html":
        assert len(item.payload.html) > MIN_USABLE_CONTENT_CHARS
    else:
        assert item.payload.type == "text"
        assert len(item.payload.text) > MIN_USABLE_CONTENT_CHARS


async def _collect(adapter: SourceAdapter, source: Source) -> list[SourceItem]:
    return [item async for item in adapter.capture(source)]
