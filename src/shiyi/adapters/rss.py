"""RSS/Atom feed adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator

from shiyi.domain.models import (
    CaptureEvent,
    CaptureWindow,
    HtmlPayload,
    Provenance,
    SourceIdentity,
    TextPayload,
)
from shiyi.fetchers.http import HttpRssFetcher, HttpWebFetcher
from shiyi.ports.fetcher import RssFetcher


class RssFeedAdapter:
    """Reads RSS/Atom feeds and emits capture events for feed entries."""

    version = "0.2.0"

    def __init__(  # noqa: PLR0913
        self,
        *,
        name: str,
        feed_url: str,
        source_kind: str,
        rss_fetcher: RssFetcher | None = None,
        limit: int | None = None,
        window: CaptureWindow | None = None,
    ) -> None:
        """Create an RSS adapter for one feed URL."""
        self._name = name
        self._feed_url = feed_url
        self._source_kind = source_kind
        self._rss_fetcher = rss_fetcher or HttpRssFetcher(HttpWebFetcher())
        self._window = window or CaptureWindow(max_items=limit)

    @property
    def name(self) -> str:
        """Stable adapter name."""
        return self._name

    async def discover(self) -> AsyncIterator[CaptureEvent]:
        """Fetch and parse the feed into capture events."""
        feed = await self._rss_fetcher.fetch(self._feed_url)
        emitted = 0
        for entry in feed.entries:
            occurred_at = entry.published_at or feed.fetched_at
            if not self._window.includes(occurred_at):
                continue
            payload = (
                HtmlPayload(html=entry.html, url=entry.link)
                if entry.html
                else TextPayload(text=entry.title or entry.entry_id)
            )
            yield CaptureEvent(
                id=f"{self._source_kind}:{entry.entry_id}",
                source=SourceIdentity(kind=self._source_kind, uri=self._feed_url),
                occurred_at=occurred_at,
                payload=payload,
                provenance=Provenance(
                    adapter_name=self.name,
                    adapter_version=self.version,
                    fetched_at=feed.fetched_at,
                    source_item_id=entry.entry_id,
                ),
                idempotency_key=f"{self._source_kind}:{entry.entry_id}",
                metadata={"title": entry.title, "link": entry.link},
            )
            emitted += 1
            if self._window.max_items is not None and emitted >= self._window.max_items:
                break


def openai_news_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    rss_fetcher: RssFetcher | None = None,
) -> RssFeedAdapter:
    """Create the default OpenAI news RSS adapter."""
    return RssFeedAdapter(
        name="openai-news-rss",
        feed_url="https://openai.com/news/rss.xml",
        source_kind="openai-news",
        limit=limit,
        window=window,
        rss_fetcher=rss_fetcher,
    )
