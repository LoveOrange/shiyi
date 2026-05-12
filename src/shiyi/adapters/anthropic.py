"""Anthropic news index adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

from shiyi.domain.models import CaptureEvent, HtmlPayload, Provenance, SourceIdentity

ANTHROPIC_NEWS_URL = "https://www.anthropic.com/news"


class AnthropicNewsAdapter:
    """Reads Anthropic's news index and emits events for linked article pages."""

    name = "anthropic-news-index"
    version = "0.1.0"

    def __init__(
        self,
        *,
        index_url: str = ANTHROPIC_NEWS_URL,
        limit: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Create an Anthropic news adapter."""
        self._index_url = index_url
        self._limit = limit
        self._client = client

    async def discover(self) -> AsyncIterator[CaptureEvent]:
        """Fetch Anthropic news index and article pages."""
        fetched_at = datetime.now(UTC)
        index_html = await self._fetch_text(self._index_url)
        for url in _extract_article_urls(index_html, self._index_url, self._limit):
            article_html = await self._fetch_text(url)
            article_id = _article_id(url)
            yield CaptureEvent(
                id=f"anthropic-news:{article_id}",
                source=SourceIdentity(kind="anthropic-news", uri=url),
                occurred_at=fetched_at,
                payload=HtmlPayload(html=article_html, url=url),
                provenance=Provenance(
                    adapter_name=self.name,
                    adapter_version=self.version,
                    fetched_at=fetched_at,
                    source_item_id=article_id,
                ),
                idempotency_key=f"anthropic-news:{article_id}",
                metadata={"title": _extract_title(article_html), "link": url},
            )

    async def _fetch_text(self, url: str) -> str:
        if self._client is not None:
            response = await self._client.get(url)
            response.raise_for_status()
            return response.text

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text


def anthropic_news_adapter(
    *,
    limit: int = 10,
    client: httpx.AsyncClient | None = None,
) -> AnthropicNewsAdapter:
    """Create the default Anthropic news adapter."""
    return AnthropicNewsAdapter(limit=limit, client=client)


def _extract_article_urls(html: str, base_url: str, limit: int) -> list[str]:
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
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if normalized in seen:
            continue
        seen.add(normalized)
        urls.append(normalized)
        if len(urls) >= limit:
            break
    return urls


def _article_id(url: str) -> str:
    path = urlparse(url).path.strip("/")
    return path.removeprefix("news/") or path


def _extract_title(html: str) -> str:
    parser = HTMLParser(html)
    for selector in ("h1", "title"):
        node = parser.css_first(selector)
        if node is not None:
            text = node.text(strip=True)
            if text:
                return text
    return ""
