import asyncio

import httpx
import respx

from shiyi.adapters.rss import openai_news_adapter
from shiyi.domain.models import CaptureEvent


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


async def _collect_openai_events() -> list[CaptureEvent]:
    adapter = openai_news_adapter()
    return [event async for event in adapter.discover()]
