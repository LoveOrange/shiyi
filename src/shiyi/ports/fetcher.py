"""Fetcher extension ports."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, HttpUrl


class FetchErrorKind(StrEnum):
    """Portable fetch failure categories exposed by fetcher implementations."""

    TIMEOUT = "timeout"
    TRANSPORT = "transport"
    HTTP_STATUS = "http_status"


class FetcherError(Exception):
    """Fetcher-level error mapped from transport/provider-specific failures."""

    def __init__(
        self,
        *,
        url: str,
        kind: FetchErrorKind,
        message: str,
        status_code: int | None = None,
        source: str | None = None,
    ) -> None:
        """Create a fetcher error with stable adapter-facing fields."""
        super().__init__(message)
        self.url = url
        self.kind = kind
        self.status_code = status_code
        self.source = source


class FetchResult(BaseModel):
    """Raw HTTP fetch result."""

    model_config = ConfigDict(frozen=True)

    url: HttpUrl
    status_code: int
    content: str
    content_type: str | None = None
    fetched_at: datetime
    from_cache: bool = False
    raw_cache_path: Path | None = None


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

    async def fetch(
        self,
        url: str,
        *,
        source: str | None = None,
        raw_key: str | None = None,
    ) -> FetchResult:
        """Fetch a URL and optionally cache event-level raw content by adapter-defined key."""
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
