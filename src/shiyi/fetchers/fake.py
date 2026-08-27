"""In-memory fetchers for adapter tests and examples."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import NamedTuple

from shiyi.ports.fetcher import (
    FetcherError,
    FetchErrorKind,
    FetchResult,
    RssFeed,
    Sitemap,
)


class WebFetchCall(NamedTuple):
    """Recorded fake web fetch call."""

    url: str
    source: str | None
    raw_key: str | None


class FakeWebFetcher:
    """Deterministic WebFetcher implementation backed by an in-memory mapping."""

    def __init__(
        self,
        pages: Mapping[str, str | FetchResult],
        *,
        fetched_at: datetime | None = None,
    ) -> None:
        """Create a fake web fetcher from URL to text/result mappings."""
        self._pages = pages
        self._fetched_at = fetched_at or datetime.now(UTC)
        self.calls: list[WebFetchCall] = []

    async def fetch(
        self,
        url: str,
        *,
        source: str | None = None,
        raw_key: str | None = None,
    ) -> FetchResult:
        """Return a configured fetch result and record the adapter call shape."""
        self.calls.append(WebFetchCall(url=url, source=source, raw_key=raw_key))
        value = self._pages.get(url)
        if value is None:
            message = f"No fake response configured for {url}"
            raise FetcherError(
                url=url,
                kind=FetchErrorKind.TRANSPORT,
                message=message,
                source=source,
            )
        if isinstance(value, FetchResult):
            return value
        return FetchResult(
            url=url,
            status_code=200,
            content=value,
            body=value.encode(),
            fetched_at=self._fetched_at,
        )


class FakeRssFetcher:
    """Deterministic RssFetcher implementation returning preconfigured feeds."""

    def __init__(self, feeds: Mapping[str, RssFeed]) -> None:
        """Create a fake RSS fetcher from feed URL to feed mappings."""
        self._feeds = feeds
        self.calls: list[str] = []

    async def fetch(self, feed_url: str) -> RssFeed:
        """Return a configured RSS feed."""
        self.calls.append(feed_url)
        feed = self._feeds.get(feed_url)
        if feed is None:
            message = f"No fake RSS feed configured for {feed_url}"
            raise FetcherError(url=feed_url, kind=FetchErrorKind.TRANSPORT, message=message)
        return feed


class FakeSitemapFetcher:
    """Deterministic SitemapFetcher implementation returning preconfigured sitemaps."""

    def __init__(self, sitemaps: Mapping[str, Sitemap]) -> None:
        """Create a fake sitemap fetcher from sitemap URL to sitemap mappings."""
        self._sitemaps = sitemaps
        self.calls: list[str] = []

    async def fetch(self, sitemap_url: str) -> Sitemap:
        """Return a configured sitemap."""
        self.calls.append(sitemap_url)
        sitemap = self._sitemaps.get(sitemap_url)
        if sitemap is None:
            message = f"No fake sitemap configured for {sitemap_url}"
            raise FetcherError(url=sitemap_url, kind=FetchErrorKind.TRANSPORT, message=message)
        return sitemap
