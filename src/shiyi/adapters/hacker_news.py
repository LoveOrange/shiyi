"""Hacker News structured API adapter."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape, unescape
from typing import Any

from shiyi.domain.models import (
    CaptureWindow,
    HtmlPayload,
    InternalItem,
    Provenance,
    SourceIdentity,
    payload_content_hash,
)
from shiyi.fetchers.http import HttpWebFetcher
from shiyi.ports.fetcher import WebFetcher

HACKER_NEWS_API_BASE_URL = "https://hacker-news.firebaseio.com/v0"
HACKER_NEWS_TOP_STORIES_URL = f"{HACKER_NEWS_API_BASE_URL}/topstories.json"
HACKER_NEWS_ITEM_URL_TEMPLATE = f"{HACKER_NEWS_API_BASE_URL}/item/{{item_id}}.json"
HACKER_NEWS_DISCUSSION_URL_TEMPLATE = "https://news.ycombinator.com/item?id={item_id}"
HACKER_NEWS_SOURCE_KIND = "hacker-news"
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")


@dataclass(frozen=True, slots=True)
class HackerNewsStory:
    """Neutral HN story material captured from the public API."""

    item_id: int
    title: str
    captured_at: datetime
    occurred_at: datetime
    canonical_discussion_url: str
    external_target_url: str | None
    score: int
    descendants: int
    rank: int
    text_html: str | None = None


class HackerNewsTopStoriesAdapter:
    """Reads Hacker News top stories and emits neutral community-source items."""

    version = "0.1.0"

    def __init__(
        self,
        *,
        web_fetcher: WebFetcher | None = None,
        limit: int | None = None,
        window: CaptureWindow | None = None,
    ) -> None:
        """Create an HN top-stories adapter."""
        self._web_fetcher = web_fetcher or HttpWebFetcher()
        self._window = window or CaptureWindow(max_items=limit)

    @property
    def name(self) -> str:
        """Stable adapter name."""
        return "hacker-news-topstories-api"

    async def discover(self) -> AsyncIterator[InternalItem]:
        """Fetch top-story IDs, then fetch and emit source-ready story metadata."""
        topstories = await self._fetch_topstory_ids()
        emitted = 0
        for rank, item_id in enumerate(topstories, start=1):
            fetched_story = await self._fetch_story_payload(item_id)
            if fetched_story is None:
                continue
            story_payload, fetched_at = fetched_story
            story = _story_from_payload(
                story_payload,
                expected_id=item_id,
                rank=rank,
                captured_at=fetched_at,
            )
            if story is None or not self._window.includes(story.occurred_at):
                continue
            yield _internal_item(story=story, adapter_name=self.name, adapter_version=self.version)
            emitted += 1
            if self._window.max_items is not None and emitted >= self._window.max_items:
                break

    async def _fetch_topstory_ids(self) -> tuple[int, ...]:
        result = await self._web_fetcher.fetch(HACKER_NEWS_TOP_STORIES_URL)
        decoded = json.loads(result.content)
        if not isinstance(decoded, list) or not all(isinstance(item, int) for item in decoded):
            msg = "HN topstories response must be a JSON array of integer item IDs"
            raise ValueError(msg)
        return tuple(decoded)

    async def _fetch_story_payload(self, item_id: int) -> tuple[Mapping[str, Any], datetime] | None:
        result = await self._web_fetcher.fetch(
            HACKER_NEWS_ITEM_URL_TEMPLATE.format(item_id=item_id),
            source=HACKER_NEWS_SOURCE_KIND,
            raw_key=str(item_id),
        )
        decoded = json.loads(result.content)
        if decoded is None:
            return None
        if not isinstance(decoded, Mapping):
            msg = f"HN item {item_id} response must be a JSON object or null"
            raise TypeError(msg)
        return decoded, result.fetched_at


def hacker_news_topstories_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> HackerNewsTopStoriesAdapter:
    """Create the default HN top-stories adapter."""
    return HackerNewsTopStoriesAdapter(limit=limit, window=window, web_fetcher=web_fetcher)


def _story_from_payload(
    payload: Mapping[str, Any], *, expected_id: int, rank: int, captured_at: datetime
) -> HackerNewsStory | None:
    if payload.get("deleted") is True or payload.get("dead") is True:
        return None
    if payload.get("type") != "story":
        return None
    item_id = _required_int(payload, "id", context=f"HN item {expected_id}")
    if item_id != expected_id:
        msg = f"HN item ID mismatch: expected {expected_id}, got {item_id}"
        raise ValueError(msg)
    title = _required_clean_text(payload, "title", context=f"HN item {item_id}")
    occurred_at = datetime.fromtimestamp(
        _required_int(payload, "time", context=f"HN item {item_id}"),
        tz=UTC,
    )
    return HackerNewsStory(
        item_id=item_id,
        title=title,
        captured_at=captured_at,
        occurred_at=occurred_at,
        canonical_discussion_url=HACKER_NEWS_DISCUSSION_URL_TEMPLATE.format(item_id=item_id),
        external_target_url=_optional_url(payload.get("url")),
        score=_optional_int(payload, "score", default=0),
        descendants=_optional_int(payload, "descendants", default=0),
        rank=rank,
        text_html=_optional_story_text(payload.get("text")),
    )


def _internal_item(
    *, story: HackerNewsStory, adapter_name: str, adapter_version: str
) -> InternalItem:
    payload = HtmlPayload(
        html=_story_html(story),
        url=story.canonical_discussion_url,
    )
    item_id = f"{HACKER_NEWS_SOURCE_KIND}:{story.item_id}"
    return InternalItem(
        id=item_id,
        source=SourceIdentity(kind=HACKER_NEWS_SOURCE_KIND, uri=story.canonical_discussion_url),
        captured_at=story.captured_at,
        occurred_at=story.occurred_at,
        payload=payload,
        content_hash=payload_content_hash(payload),
        provenance=Provenance(
            adapter_name=adapter_name,
            adapter_version=adapter_version,
            fetched_at=story.captured_at,
            source_item_id=str(story.item_id),
        ),
        idempotency_key=item_id,
        metadata={
            "title": story.title,
            "link": story.external_target_url,
            "content_depth": "complete",
            "upstream_id": str(story.item_id),
            "canonical_discussion_url": story.canonical_discussion_url,
            "external_target_url": story.external_target_url,
            "source_metrics": {
                "score": story.score,
                "descendants": story.descendants,
                "rank": story.rank,
            },
        },
    )


def _story_html(story: HackerNewsStory) -> str:
    parts = [f"<h1>{escape(story.title)}</h1>"]
    parts.append(
        "<p>Hacker News discussion: "
        f'<a href="{escape(story.canonical_discussion_url, quote=True)}">'
        f"{escape(story.canonical_discussion_url)}</a></p>"
    )
    if story.external_target_url is not None:
        parts.append(
            "<p>External target: "
            f'<a href="{escape(story.external_target_url, quote=True)}">'
            f"{escape(story.external_target_url)}</a></p>"
        )
    parts.append(
        "<p>Neutral metrics: "
        f"score={story.score}; descendants={story.descendants}; rank={story.rank}</p>"
    )
    if story.text_html is not None:
        parts.append(f"<section>{story.text_html}</section>")
    return f"<article>{''.join(parts)}</article>"


def _required_int(payload: Mapping[str, Any], key: str, *, context: str) -> int:
    value = payload.get(key)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    msg = f"{context} missing required integer field {key}"
    raise ValueError(msg)


def _optional_int(payload: Mapping[str, Any], key: str, *, default: int) -> int:
    value = payload.get(key)
    if value is None:
        return default
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    msg = f"HN item {payload.get('id', '<unknown>')} field {key} must be an integer"
    raise ValueError(msg)


def _required_clean_text(payload: Mapping[str, Any], key: str, *, context: str) -> str:
    value = payload.get(key)
    if value is None:
        msg = f"{context} missing required text field {key}"
        raise ValueError(msg)
    if not isinstance(value, str):
        msg = f"{context} missing required text field {key}"
        raise TypeError(msg)
    cleaned = _clean_html_text(value)
    if cleaned:
        return cleaned
    msg = f"{context} missing required text field {key}"
    raise ValueError(msg)


def _optional_url(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _optional_story_text(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _clean_html_text(value: str) -> str:
    return " ".join(unescape(_HTML_TAG_PATTERN.sub(" ", value)).split())
