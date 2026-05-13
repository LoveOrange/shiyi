import asyncio
from datetime import UTC, datetime

import httpx
import respx

from shiyi.adapters.rss import RssFeedAdapter, openai_news_adapter
from shiyi.domain.models import CaptureWindow, InternalItem
from shiyi.ports.fetcher import RssEntry, RssFeed


class FakeRssFetcher:
    async def fetch(self, feed_url: str) -> RssFeed:
        return RssFeed(
            url=feed_url,
            fetched_at=datetime(2026, 5, 14, tzinfo=UTC),
            entries=(
                RssEntry(
                    entry_id="old",
                    title="Old",
                    link="https://openai.com/old",
                    html="<p>old</p>",
                    published_at=datetime(2026, 5, 11, tzinfo=UTC),
                ),
                RssEntry(
                    entry_id="in-window",
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


def test_openai_news_adapter_parses_feed_entries() -> None:
    feed = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>OpenAI News</title>
      <item>
        <guid>post-1</guid>
        <title>Running Codex safely</title>
        <link>https://openai.com/index/running-codex-safely/</link>
        <pubDate>Fri, 08 May 2026 10:00:00 GMT</pubDate>
        <description><![CDATA[<p>Safety post</p>]]></description>
      </item>
    </channel></rss>
    """
    with respx.mock:
        respx.get("https://openai.com/news/rss.xml").mock(
            return_value=httpx.Response(200, text=feed)
        )
        events = asyncio.run(_collect_openai_events())

    assert len(events) == 1
    event = events[0]
    assert event.idempotency_key == "openai-news:post-1"
    assert event.metadata["title"] == "Running Codex safely"
    assert event.payload.type == "html"


def test_openai_news_adapter_filters_by_capture_window() -> None:
    adapter = openai_news_adapter(
        rss_fetcher=FakeRssFetcher(),
        window=CaptureWindow(
            since=datetime(2026, 5, 12, tzinfo=UTC),
            until=datetime(2026, 5, 13, tzinfo=UTC),
        ),
    )

    events = asyncio.run(_collect_events(adapter))

    assert [event.idempotency_key for event in events] == ["openai-news:in-window"]


async def _collect_openai_events() -> list[InternalItem]:
    adapter = openai_news_adapter()
    return [event async for event in adapter.discover()]


async def _collect_events(adapter: RssFeedAdapter) -> list[InternalItem]:
    return [event async for event in adapter.discover()]
