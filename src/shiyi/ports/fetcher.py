"""Fetcher extension ports."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, HttpUrl


class FetchResult(BaseModel):
    """Raw HTTP fetch result."""

    model_config = ConfigDict(frozen=True)

    url: HttpUrl
    status_code: int
    content: str
    content_type: str | None = None
    fetched_at: datetime


class RssEntry(BaseModel):
    """Normalized RSS/Atom entry exposed by the RSS fetcher."""

    model_config = ConfigDict(frozen=True)

    entry_id: str
    title: str
    link: str | None
    html: str
    published_at: datetime | None


class RssFeed(BaseModel):
    """Normalized RSS/Atom feed."""

    model_config = ConfigDict(frozen=True)

    url: HttpUrl
    fetched_at: datetime
    entries: tuple[RssEntry, ...]


class SitemapEntry(BaseModel):
    """One sitemap URL entry."""

    model_config = ConfigDict(frozen=True)

    loc: HttpUrl
    lastmod: datetime | None = None


class Sitemap(BaseModel):
    """Parsed sitemap."""

    model_config = ConfigDict(frozen=True)

    url: HttpUrl
    fetched_at: datetime
    entries: tuple[SitemapEntry, ...]


class WebFetcher(Protocol):
    """Fetches web resources as text."""

    async def fetch(self, url: str) -> FetchResult:
        """Fetch a URL and return text content plus metadata."""
        ...


class RssFetcher(Protocol):
    """Fetches and parses RSS/Atom feeds."""

    async def fetch(self, feed_url: str) -> RssFeed:
        """Fetch and parse an RSS/Atom feed."""
        ...


class SitemapFetcher(Protocol):
    """Fetches and parses XML sitemaps."""

    async def fetch(self, sitemap_url: str) -> Sitemap:
        """Fetch and parse a sitemap."""
        ...
