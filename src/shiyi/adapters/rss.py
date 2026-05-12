"""RSS/Atom feed adapter."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import cast

import feedparser  # type: ignore[import-untyped]
import httpx

from shiyi.domain.models import CaptureEvent, HtmlPayload, Provenance, SourceIdentity, TextPayload


class RssFeedAdapter:
    """Reads RSS/Atom feeds and emits capture events for feed entries."""

    version = "0.1.0"

    def __init__(
        self,
        *,
        name: str,
        feed_url: str,
        source_kind: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Create an RSS adapter for one feed URL."""
        self._name = name
        self._feed_url = feed_url
        self._source_kind = source_kind
        self._client = client

    @property
    def name(self) -> str:
        """Stable adapter name."""
        return self._name

    async def discover(self) -> AsyncIterator[CaptureEvent]:
        """Fetch and parse the feed into capture events."""
        fetched_at = datetime.now(UTC)
        feed_xml = await self._fetch_feed()
        parsed = feedparser.parse(feed_xml)
        for raw_entry in parsed.entries:
            entry = cast(Mapping[str, object], raw_entry)
            entry_id = _entry_id(entry)
            link = str(entry.get("link", "")) or None
            title = str(entry.get("title", "")).strip()
            html = _entry_html(entry)
            payload = (
                HtmlPayload(html=html, url=link) if html else TextPayload(text=title or entry_id)
            )
            yield CaptureEvent(
                id=f"{self._source_kind}:{entry_id}",
                source=SourceIdentity(kind=self._source_kind, uri=self._feed_url),
                occurred_at=_entry_datetime(entry) or fetched_at,
                payload=payload,
                provenance=Provenance(
                    adapter_name=self.name,
                    adapter_version=self.version,
                    fetched_at=fetched_at,
                    source_item_id=entry_id,
                ),
                idempotency_key=f"{self._source_kind}:{entry_id}",
                metadata={"title": title, "link": link},
            )

    async def _fetch_feed(self) -> str:
        if self._client is not None:
            response = await self._client.get(self._feed_url)
            response.raise_for_status()
            return response.text

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(self._feed_url)
            response.raise_for_status()
            return response.text


def openai_news_adapter(client: httpx.AsyncClient | None = None) -> RssFeedAdapter:
    """Create the default OpenAI news RSS adapter."""
    return RssFeedAdapter(
        name="openai-news-rss",
        feed_url="https://openai.com/news/rss.xml",
        source_kind="openai-news",
        client=client,
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
        value = content[0].get("value", "")
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
            parsed = parsedate_to_datetime(value)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=UTC)
            return parsed.astimezone(UTC)
    return None
