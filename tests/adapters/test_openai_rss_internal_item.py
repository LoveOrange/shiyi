import asyncio
from datetime import UTC, datetime

from shiyi import (
    Adapter,
    CaptureWindow,
    HtmlPayload,
    InternalItem,
    openai_news_adapter,
    payload_content_hash,
)
from shiyi.fetchers.fake import FakeRssFetcher
from shiyi.ports.fetcher import RssEntry, RssFeed

OPENAI_RSS_URL = "https://openai.com/news/rss.xml"


def test_openai_rss_adapter_maps_feed_entry_to_internal_item() -> None:
    feed = RssFeed(
        url=OPENAI_RSS_URL,
        fetched_at=datetime(2026, 5, 13, 1, 30, tzinfo=UTC),
        entries=(
            RssEntry(
                entry_id="running-codex-safely",
                title="Running Codex safely",
                link="https://openai.com/index/running-codex-safely/",
                html="<article><h1>Running Codex safely</h1></article>",
                published_at=datetime(2026, 5, 8, 10, tzinfo=UTC),
            ),
        ),
    )
    rss_fetcher = FakeRssFetcher({OPENAI_RSS_URL: feed})
    adapter = openai_news_adapter(rss_fetcher=rss_fetcher)

    items = asyncio.run(_collect_internal_items(adapter))

    assert rss_fetcher.calls == [OPENAI_RSS_URL]
    assert len(items) == 1

    item: InternalItem = items[0]
    assert item.id == "openai-news:running-codex-safely"
    assert item.idempotency_key == "openai-news:running-codex-safely"
    assert item.source.kind == "openai-news"
    assert str(item.source.uri) == OPENAI_RSS_URL
    assert item.schema_version == "internal-item.v1"
    assert item.captured_at == datetime(2026, 5, 13, 1, 30, tzinfo=UTC)
    assert item.occurred_at == datetime(2026, 5, 8, 10, tzinfo=UTC)
    assert isinstance(item.payload, HtmlPayload)
    assert item.payload.html == "<article><h1>Running Codex safely</h1></article>"
    assert item.content_hash == payload_content_hash(item.payload)
    assert item.provenance.adapter_name == "openai-news-rss"
    assert item.provenance.adapter_version == "0.2.0"
    assert item.provenance.fetched_at == datetime(2026, 5, 13, 1, 30, tzinfo=UTC)
    assert item.provenance.source_item_id == "running-codex-safely"
    assert item.metadata == {
        "title": "Running Codex safely",
        "link": "https://openai.com/index/running-codex-safely/",
    }
    assert "raw_payload" not in item.metadata


def test_openai_rss_adapter_honors_capture_window_before_emitting_internal_items() -> None:
    feed = RssFeed(
        url=OPENAI_RSS_URL,
        fetched_at=datetime(2026, 5, 13, tzinfo=UTC),
        entries=(
            RssEntry(
                entry_id="before-window",
                title="Before",
                link="https://openai.com/before",
                html="<p>before</p>",
                published_at=datetime(2026, 5, 11, tzinfo=UTC),
            ),
            RssEntry(
                entry_id="inside-window",
                title="Inside",
                link="https://openai.com/inside",
                html="<p>inside</p>",
                published_at=datetime(2026, 5, 12, 12, tzinfo=UTC),
            ),
            RssEntry(
                entry_id="until-boundary",
                title="Boundary",
                link="https://openai.com/boundary",
                html="<p>boundary</p>",
                published_at=datetime(2026, 5, 13, tzinfo=UTC),
            ),
        ),
    )
    adapter = openai_news_adapter(
        rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: feed}),
        window=CaptureWindow(
            since=datetime(2026, 5, 12, tzinfo=UTC),
            until=datetime(2026, 5, 13, tzinfo=UTC),
        ),
    )

    items = asyncio.run(_collect_internal_items(adapter))

    assert [item.idempotency_key for item in items] == ["openai-news:inside-window"]


async def _collect_internal_items(adapter: Adapter) -> list[InternalItem]:
    return [item async for item in adapter.discover()]
