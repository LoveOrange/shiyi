import asyncio

import httpx
import respx

from shiyi.adapters.anthropic import ANTHROPIC_NEWS_URL, anthropic_news_adapter
from shiyi.domain.models import CaptureEvent


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


async def _collect_anthropic_events(*, limit: int) -> list[CaptureEvent]:
    adapter = anthropic_news_adapter(limit=limit)
    return [event async for event in adapter.discover()]
