"""Anthropic news index adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from hashlib import sha256
from urllib.parse import urljoin, urlparse

from selectolax.parser import HTMLParser

from shiyi.domain.models import (
    CaptureWindow,
    HtmlPayload,
    InternalItem,
    Provenance,
    SourceIdentity,
    payload_content_hash,
)
from shiyi.fetchers.http import HttpWebFetcher
from shiyi.ports.fetcher import SitemapFetcher, WebFetcher

ANTHROPIC_NEWS_URL = "https://www.anthropic.com/news"


class AnthropicNewsAdapter:
    """Reads Anthropic's news index and emits internal items for linked article pages."""

    name = "anthropic-news-index"
    version = "0.2.0"

    def __init__(  # noqa: PLR0913
        self,
        *,
        index_url: str = ANTHROPIC_NEWS_URL,
        limit: int | None = 10,
        web_fetcher: WebFetcher | None = None,
        sitemap_fetcher: SitemapFetcher | None = None,
        sitemap_url: str | None = None,
        window: CaptureWindow | None = None,
    ) -> None:
        """Create an Anthropic news adapter."""
        self._index_url = index_url
        self._web_fetcher = web_fetcher or HttpWebFetcher()
        self._sitemap_fetcher = sitemap_fetcher
        self._sitemap_url = sitemap_url
        self._window = window or CaptureWindow(max_items=limit)

    async def discover(self) -> AsyncIterator[InternalItem]:
        """Fetch Anthropic news index and article pages."""
        index_result = await self._web_fetcher.fetch(self._index_url)
        sitemap_dates = await self._sitemap_dates()
        emitted = 0
        for url in _extract_article_urls(index_result.content, self._index_url):
            article_result = await self._web_fetcher.fetch(
                url,
                source="anthropic-news",
                raw_key=_entry_metadata_hash(source="anthropic-news", url=url),
            )
            article_date = _extract_article_date(article_result.content) or sitemap_dates.get(url)
            occurred_at = article_date or article_result.fetched_at
            if not self._window.includes(article_date):
                continue
            article_id = _article_id(url)
            title = _require_title(_extract_title(article_result.content), url=url)
            payload = HtmlPayload(html=article_result.content, url=url)
            yield InternalItem(
                id=f"anthropic-news:{article_id}",
                source=SourceIdentity(kind="anthropic-news", uri=url),
                captured_at=article_result.fetched_at,
                occurred_at=occurred_at,
                payload=payload,
                content_hash=payload_content_hash(payload),
                provenance=Provenance(
                    adapter_name=self.name,
                    adapter_version=self.version,
                    fetched_at=article_result.fetched_at,
                    source_item_id=article_id,
                ),
                idempotency_key=f"anthropic-news:{article_id}",
                metadata={"title": title, "link": url, "content_depth": "complete"},
            )
            emitted += 1
            if self._window.max_items is not None and emitted >= self._window.max_items:
                break

    async def _sitemap_dates(self) -> dict[str, datetime]:
        if self._sitemap_fetcher is None or self._sitemap_url is None:
            return {}
        sitemap = await self._sitemap_fetcher.fetch(self._sitemap_url)
        return {
            str(entry.loc).rstrip("/"): entry.lastmod for entry in sitemap.entries if entry.lastmod
        }


def anthropic_news_adapter(
    *,
    limit: int | None = 10,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
    sitemap_fetcher: SitemapFetcher | None = None,
    sitemap_url: str | None = None,
) -> AnthropicNewsAdapter:
    """Create the default Anthropic news adapter."""
    return AnthropicNewsAdapter(
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
        sitemap_fetcher=sitemap_fetcher,
        sitemap_url=sitemap_url,
    )


def _extract_article_urls(html: str, base_url: str, limit: int | None = None) -> list[str]:
    parser = HTMLParser(html)
    seen: set[str] = set()
    urls: list[str] = []
    for node in parser.css("a[href]"):
        href = node.attributes.get("href")
        if href is None:
            continue
        url = urljoin(base_url, href)
        parsed = urlparse(url)
        if parsed.netloc != "www.anthropic.com" or not parsed.path.startswith("/news/"):
            continue
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
        if normalized in seen:
            continue
        seen.add(normalized)
        urls.append(normalized)
        if limit is not None and len(urls) >= limit:
            break
    return urls


def _article_id(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.removeprefix("news/") or path


def _entry_metadata_hash(*, source: str, url: str) -> str:
    """Adapter-defined raw cache key from entry-level metadata."""
    return sha256(f"{source}\n{url}".encode()).hexdigest()


def _extract_title(html: str) -> str:
    parser = HTMLParser(html)
    for selector in ("h1", "title"):
        node = parser.css_first(selector)
        if node is not None:
            text = node.text(strip=True)
            if text:
                return text
    return ""


def _require_title(title: str, *, url: str) -> str:
    if title:
        return title
    msg = f"Anthropic article missing required title: {url}"
    raise ValueError(msg)


def _extract_article_date(html: str) -> datetime | None:
    parser = HTMLParser(html)
    selectors = (
        "meta[property='article:published_time']",
        "meta[name='article:published_time']",
        "meta[name='date']",
        "meta[name='publishdate']",
        "meta[name='pubdate']",
    )
    for selector in selectors:
        node = parser.css_first(selector)
        if node is not None:
            value = node.attributes.get("content")
            if parsed := _parse_datetime(value):
                return parsed
    for selector in ("time[datetime]", "time"):
        node = parser.css_first(selector)
        if node is None:
            continue
        value = node.attributes.get("datetime") or node.text(strip=True)
        if parsed := _parse_datetime(value):
            return parsed
    for selector in (".body-3.agate", "[class*='agate']"):
        node = parser.css_first(selector)
        if node is not None and (parsed := _parse_datetime(node.text(strip=True))):
            return parsed
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None or not value.strip():
        return None
    stripped = value.strip()
    try:
        parsed = datetime.fromisoformat(stripped.replace("Z", "+00:00"))
    except ValueError:
        for format_ in ("%b %d, %Y", "%B %d, %Y"):
            try:
                parsed = datetime.strptime(stripped, format_).replace(tzinfo=UTC)
                break
            except ValueError:
                continue
        else:
            try:
                parsed = parsedate_to_datetime(stripped)
            except (TypeError, ValueError):
                return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
