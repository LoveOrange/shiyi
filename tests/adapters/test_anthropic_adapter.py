import asyncio
from datetime import UTC, datetime

import httpx
import respx

from shiyi.adapters.anthropic import (
    ANTHROPIC_NEWS_URL,
    AnthropicNewsAdapter,
    anthropic_news_adapter,
)
from shiyi.domain.models import CaptureEvent, CaptureWindow
from shiyi.ports.fetcher import FetchResult


class FakeWebFetcher:
    def __init__(self) -> None:
        self.pages = {
            ANTHROPIC_NEWS_URL: """
            <a href="/news/old">Old</a>
            <a href="/news/inside">Inside</a>
            <a href="/news/boundary">Boundary</a>
            """,
            "https://www.anthropic.com/news/old": _article("Old", "2026-05-11T00:00:00Z"),
            "https://www.anthropic.com/news/inside": _article("Inside", "2026-05-12T12:00:00Z"),
            "https://www.anthropic.com/news/boundary": _article("Boundary", "2026-05-13T00:00:00Z"),
        }

    async def fetch(
        self,
        url: str,
        *,
        source: str | None = None,
        raw_key: str | None = None,
    ) -> FetchResult:
        _ = (source, raw_key)
        return FetchResult(
            url=url,
            status_code=200,
            content=self.pages[url],
            fetched_at=datetime(2026, 5, 14, tzinfo=UTC),
        )


def test_anthropic_news_adapter_fetches_index_and_article_pages() -> None:
    index_html = """
    <html><body>
      <a href="/news/claude-design-anthropic-labs">Claude Design</a>
      <a href="/news/claude-design-anthropic-labs">Duplicate</a>
      <a href="/company">Company</a>
      <a href="https://www.anthropic.com/news/project-glasswing">Project Glasswing</a>
    </body></html>
    """
    article_html = (
        "<html><head><title>Claude Design</title></head><body><h1>Claude Design</h1></body></html>"
    )
    with respx.mock:
        respx.get(ANTHROPIC_NEWS_URL).mock(return_value=httpx.Response(200, text=index_html))
        respx.get("https://www.anthropic.com/news/claude-design-anthropic-labs").mock(
            return_value=httpx.Response(200, text=article_html)
        )
        events = asyncio.run(_collect_anthropic_events(limit=1))

    assert len(events) == 1
    event = events[0]
    assert event.idempotency_key == "anthropic-news:claude-design-anthropic-labs"
    assert event.metadata["title"] == "Claude Design"
    assert event.payload.type == "html"


def test_anthropic_news_adapter_filters_by_article_date_window() -> None:
    adapter = anthropic_news_adapter(
        web_fetcher=FakeWebFetcher(),
        window=CaptureWindow(
            since=datetime(2026, 5, 12, tzinfo=UTC),
            until=datetime(2026, 5, 13, tzinfo=UTC),
        ),
    )

    events = asyncio.run(_collect_events(adapter))

    assert [event.idempotency_key for event in events] == ["anthropic-news:inside"]


async def _collect_anthropic_events(*, limit: int) -> list[CaptureEvent]:
    adapter = anthropic_news_adapter(limit=limit)
    return [event async for event in adapter.discover()]


def _article(title: str, published: str) -> str:
    return f"""
    <html><head>
      <title>{title}</title>
      <meta property="article:published_time" content="{published}">
    </head><body><h1>{title}</h1></body></html>
    """


async def _collect_events(adapter: AnthropicNewsAdapter) -> list[CaptureEvent]:
    return [event async for event in adapter.discover()]
