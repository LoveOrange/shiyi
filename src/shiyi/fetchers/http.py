"""HTTP-based web, RSS, and sitemap fetchers."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import cast

import feedparser  # type: ignore[import-untyped]
import httpx
from defusedxml import ElementTree

from shiyi.ports.fetcher import (
    FetcherError,
    FetchErrorKind,
    FetchResult,
    RssEntry,
    RssFeed,
    Sitemap,
    SitemapEntry,
)

DEFAULT_USER_AGENT = "Shiyi/0.1 (+https://github.com/LoveOrange/shiyi)"


class HttpWebFetcher:
    """Fetches text resources over HTTP with timeout and bounded retry."""

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        timeout_seconds: float = 30.0,
        user_agent: str = DEFAULT_USER_AGENT,
        retries: int = 1,
        raw_cache_root: Path | None = None,
    ) -> None:
        """Create a web fetcher."""
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self._retries = retries
        self._raw_cache_root = raw_cache_root

    async def fetch(
        self,
        url: str,
        *,
        source: str | None = None,
        raw_key: str | None = None,
    ) -> FetchResult:
        """Fetch a URL and optionally reuse event-level raw content from cache."""
        fetched_at = datetime.now(UTC)
        raw_cache_path = self._raw_cache_path(source=source, raw_key=raw_key)
        if raw_cache_path is not None and raw_cache_path.exists():
            return FetchResult(
                url=url,
                status_code=200,
                content=raw_cache_path.read_text(),
                content_type=None,
                fetched_at=fetched_at,
                from_cache=True,
                raw_cache_path=raw_cache_path,
            )

        response = await self._get(url)
        content = response.text
        if raw_cache_path is not None:
            raw_cache_path.parent.mkdir(parents=True, exist_ok=True)
            raw_cache_path.write_text(content)
        return FetchResult(
            url=str(response.url),
            status_code=response.status_code,
            content=content,
            content_type=response.headers.get("content-type"),
            fetched_at=fetched_at,
            raw_cache_path=raw_cache_path,
        )

    def _raw_cache_path(self, *, source: str | None, raw_key: str | None) -> Path | None:
        if self._raw_cache_root is None or source is None or raw_key is None:
            return None
        return self._raw_cache_root / source / raw_key / "raw.html"

    async def _get(self, url: str) -> httpx.Response:
        attempts = self._retries + 1
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                response = await self._request(url)
                response.raise_for_status()
            except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as error:
                last_error = error
                if attempt == attempts - 1 or not _is_retryable(error):
                    raise _to_fetcher_error(error, url=url) from error
                await asyncio.sleep(0.2 * (attempt + 1))
            else:
                return response
        msg = "unreachable fetch retry state"
        raise RuntimeError(msg) from last_error

    async def _request(self, url: str) -> httpx.Response:
        headers = {"user-agent": self._user_agent}
        if self._client is not None:
            return await self._client.get(
                url,
                headers=headers,
                timeout=self._timeout_seconds,
                follow_redirects=True,
            )
        async with httpx.AsyncClient(
            timeout=self._timeout_seconds,
            follow_redirects=True,
            headers=headers,
        ) as client:
            return await client.get(url)


class HttpRssFetcher:
    """Fetches RSS/Atom feeds using a WebFetcher."""

    def __init__(self, web_fetcher: HttpWebFetcher | None = None) -> None:
        """Create an RSS fetcher."""
        self._web_fetcher = web_fetcher or HttpWebFetcher()

    async def fetch(self, feed_url: str) -> RssFeed:
        """Fetch and parse RSS/Atom entries."""
        result = await self._web_fetcher.fetch(feed_url)
        parsed = feedparser.parse(result.content)
        entries = tuple(_rss_entry(cast(Mapping[str, object], entry)) for entry in parsed.entries)
        return RssFeed(url=str(result.url), fetched_at=result.fetched_at, entries=entries)


class HttpSitemapFetcher:
    """Fetches XML sitemaps using a WebFetcher."""

    def __init__(self, web_fetcher: HttpWebFetcher | None = None) -> None:
        """Create a sitemap fetcher."""
        self._web_fetcher = web_fetcher or HttpWebFetcher()

    async def fetch(self, sitemap_url: str) -> Sitemap:
        """Fetch and parse sitemap URL entries."""
        result = await self._web_fetcher.fetch(sitemap_url)
        root = ElementTree.fromstring(result.content)
        entries: list[SitemapEntry] = []
        for url_node in root.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url"):
            loc_node = url_node.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
            if loc_node is None or loc_node.text is None:
                continue
            lastmod_node = url_node.find("{http://www.sitemaps.org/schemas/sitemap/0.9}lastmod")
            entries.append(
                SitemapEntry(
                    loc=loc_node.text.strip(),
                    lastmod=_parse_datetime(
                        lastmod_node.text if lastmod_node is not None else None
                    ),
                )
            )
        return Sitemap(url=str(result.url), fetched_at=result.fetched_at, entries=tuple(entries))


def _rss_entry(entry: Mapping[str, object]) -> RssEntry:
    return RssEntry(
        entry_id=_entry_id(entry),
        title=str(entry.get("title", "")).strip(),
        link=str(entry.get("link", "")) or None,
        html=_entry_html(entry),
        published_at=_entry_datetime(entry),
    )


def _entry_id(entry: Mapping[str, object]) -> str:
    for key in ("id", "guid", "link"):
        value = str(entry.get(key, "")).strip()
        if value:
            return value
    title = str(entry.get("title", "")).strip()
    if title:
        return title
    msg = "RSS entry has no stable id, guid, link, or title"
    raise ValueError(msg)


def _entry_html(entry: Mapping[str, object]) -> str:
    content = entry.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, Mapping):
            value = first.get("value", "")
            if isinstance(value, str) and value.strip():
                return value

    summary = entry.get("summary")
    if isinstance(summary, str) and summary.strip():
        return summary
    return ""


def _entry_datetime(entry: Mapping[str, object]) -> datetime | None:
    for key in ("published", "updated"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return _parse_datetime(value)
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = parsedate_to_datetime(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in {408, 429, 500, 502, 503, 504}
    return True


def _to_fetcher_error(error: Exception, *, url: str) -> FetcherError:
    if isinstance(error, httpx.TimeoutException):
        message = f"Timed out while fetching {url}"
        return FetcherError(url=url, kind=FetchErrorKind.TIMEOUT, message=message)
    if isinstance(error, httpx.HTTPStatusError):
        status_code = error.response.status_code
        message = f"HTTP {status_code} while fetching {url}"
        return FetcherError(
            url=url,
            kind=FetchErrorKind.HTTP_STATUS,
            message=message,
            status_code=status_code,
        )
    message = f"Transport error while fetching {url}"
    return FetcherError(url=url, kind=FetchErrorKind.TRANSPORT, message=message)
