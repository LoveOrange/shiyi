"""ByteDance Seed official blog adapter."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from html import escape
from typing import cast

from selectolax.parser import HTMLParser

from shiyi.domain.models import (
    CaptureWindow,
    HtmlPayload,
    Source,
    SourceItem,
    TextPayload,
)
from shiyi.fetchers.http import HttpWebFetcher
from shiyi.ports.fetcher import WebFetcher

BYTEDANCE_SEED_BLOG_URL = "https://seed.bytedance.com/zh/blog"
BYTEDANCE_SEED_BLOG_BASE_URL = "https://seed.bytedance.com/zh/blog/"
BYTEDANCE_SEED_EN_BLOG_BASE_URL = "https://seed.bytedance.com/en/blog/"


class ByteDanceSeedBlogAdapter:
    """Reads ByteDance Seed's official SSR blog payload and emits internal items."""

    name = "bytedance-seed-blog-ssr"
    version = "0.1.0"

    def __init__(
        self,
        *,
        limit: int | None = 10,
        web_fetcher: WebFetcher | None = None,
        window: CaptureWindow | None = None,
    ) -> None:
        """Create a ByteDance Seed blog adapter."""
        self._web_fetcher = web_fetcher or HttpWebFetcher()
        self._window = window or CaptureWindow(max_items=limit)

    async def capture(self, source: Source) -> AsyncIterator[SourceItem]:
        """Fetch the blog index and article detail payloads."""
        index_result = await self._web_fetcher.fetch(source.target)
        emitted = 0
        for index_item in _extract_index_items(index_result.content):
            if not self._window.includes(index_item.occurred_at):
                continue
            detail_result = await self._web_fetcher.fetch(
                index_item.link,
                source="bytedance-seed-blog",
                raw_key=_entry_metadata_hash(source="bytedance-seed-blog", url=index_item.link),
            )
            detail = _extract_detail(detail_result.content)
            payload = _entry_payload(index_item=index_item, detail=detail)
            yield SourceItem(
                source_id=source.id,
                source_item_id=index_item.entry_id,
                kind=_content_kind(source),
                canonical_url=index_item.link,
                collected_at=detail_result.fetched_at,
                published_at=index_item.occurred_at,
                summary=index_item.abstract or None,
                payload=payload,
                metadata={
                    "title": index_item.title,
                    "link": index_item.link,
                    "language": "zh",
                    "english_link": index_item.english_link,
                    "is_complete": detail.complete,
                },
            )
            emitted += 1
            if self._window.max_items is not None and emitted >= self._window.max_items:
                break


def _content_kind(source: Source) -> str:
    value = source.options.get("content_kind", "article")
    return value if isinstance(value, str) and value else "article"


def bytedance_seed_blog_adapter(
    *,
    limit: int | None = 10,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> ByteDanceSeedBlogAdapter:
    """Create the default ByteDance Seed official blog adapter."""
    return ByteDanceSeedBlogAdapter(limit=limit, window=window, web_fetcher=web_fetcher)


@dataclass(frozen=True, slots=True)
class _IndexItem:
    entry_id: str
    title: str
    abstract: str
    link: str
    english_link: str
    occurred_at: datetime
    categories: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Detail:
    content_html: str
    complete: bool


def _extract_index_items(html: str) -> tuple[_IndexItem, ...]:
    router_data = _router_data(html)
    page_data = _mapping_path(router_data, "loaderData", "(locale$)/blog/page")
    article_list = _object_sequence(page_data.get("article_list"))
    entries: list[_IndexItem] = []
    for raw_item in article_list:
        meta = _mapping(raw_item.get("ArticleMeta"))
        content = _mapping(raw_item.get("ArticleSubContentZh"))
        english_content = _mapping(raw_item.get("ArticleSubContentEn"))
        entry_id = _string_or_int(meta.get("ArticleID")) or _string_or_int(meta.get("ID"))
        title_key = _required_string(content.get("TitleKey"), field="TitleKey")
        english_title_key = _required_string(
            english_content.get("TitleKey"), field="English TitleKey"
        )
        title = _required_string(content.get("Title"), field="Title")
        publish_ms = _required_number(meta.get("PublishDate"), field="PublishDate")
        if not entry_id:
            entry_id = title_key
        entries.append(
            _IndexItem(
                entry_id=entry_id,
                title=title,
                abstract=_string_value(content.get("Abstract")),
                link=f"{BYTEDANCE_SEED_BLOG_BASE_URL}{title_key}",
                english_link=f"{BYTEDANCE_SEED_EN_BLOG_BASE_URL}{english_title_key}",
                occurred_at=_epoch_ms_utc(publish_ms),
                categories=_research_area_names(meta.get("ResearchArea")),
            )
        )
    return tuple(entries)


def _extract_detail(html: str) -> _Detail:
    router_data = _router_data(html)
    page_data = _mapping_path(
        router_data, "loaderData", "(locale$)/blog/(id)/page", "data", "article"
    )
    content = _string_value(page_data.get("ContentZh")) or _string_value(page_data.get("ContentEn"))
    return _Detail(content_html=content, complete=bool(content))


def _entry_payload(*, index_item: _IndexItem, detail: _Detail) -> HtmlPayload | TextPayload:
    if detail.content_html:
        category_text = ", ".join(index_item.categories)
        category_html = f"<p>Categories: {escape(category_text)}</p>" if category_text else ""
        abstract_html = f"<p>{escape(index_item.abstract)}</p>" if index_item.abstract else ""
        english_link_html = (
            f'<p>English link: <a href="{escape(index_item.english_link, quote=True)}">'
            f"{escape(index_item.english_link)}</a></p>"
        )
        link_html = (
            f'<p>Canonical link: <a href="{escape(index_item.link, quote=True)}">'
            f"{escape(index_item.link)}</a></p>"
        )
        return HtmlPayload(
            html=(
                "<article>"
                f"<h1>{escape(index_item.title)}</h1>"
                f"{link_html}"
                f"{english_link_html}"
                f"{category_html}"
                f"{abstract_html}"
                f"{detail.content_html}"
                "</article>"
            ),
            url=index_item.link,
        )
    text_parts = [
        index_item.title,
        f"Canonical link: {index_item.link}",
        f"English link: {index_item.english_link}",
    ]
    if index_item.categories:
        text_parts.append(f"Categories: {', '.join(index_item.categories)}")
    if index_item.abstract:
        text_parts.append(index_item.abstract)
    return TextPayload(text="\n\n".join(text_parts))


def _router_data(html: str) -> Mapping[str, object]:
    parser = HTMLParser(html)
    for script in parser.css("script"):
        content = script.text()
        if "window._ROUTER_DATA" not in content:
            continue
        match = re.search(r"window\._ROUTER_DATA\s*=\s*(\{.*\})\s*;?\s*$", content, re.DOTALL)
        if match is None:
            break
        value = json.loads(match.group(1))
        if isinstance(value, Mapping):
            return cast(Mapping[str, object], value)
    msg = "ByteDance Seed page missing window._ROUTER_DATA payload"
    raise ValueError(msg)


def _mapping_path(root: Mapping[str, object], *path: str) -> Mapping[str, object]:
    current: object = root
    for key in path:
        current = _mapping(current).get(key)
    return _mapping(current)


def _mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return cast(Mapping[str, object], value)
    return {}


def _object_sequence(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(_mapping(item) for item in value)


def _research_area_names(value: object) -> tuple[str, ...]:
    names: list[str] = []
    for area in _object_sequence(value):
        name = _string_value(area.get("ResearchAreaName"))
        if name:
            names.append(name)
    return tuple(names)


def _entry_metadata_hash(*, source: str, url: str) -> str:
    return sha256(f"{source}\n{url}".encode()).hexdigest()


def _string_or_int(value: object) -> str:
    if isinstance(value, int):
        return str(value)
    return _string_value(value)


def _string_value(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _required_string(value: object, *, field: str) -> str:
    result = _string_value(value)
    if result:
        return result
    msg = f"ByteDance Seed article missing required {field}"
    raise ValueError(msg)


def _required_number(value: object, *, field: str) -> int | float:
    if isinstance(value, (int, float)):
        return value
    msg = f"ByteDance Seed article missing required {field}"
    raise ValueError(msg)


def _epoch_ms_utc(value: int | float) -> datetime:
    return datetime.fromtimestamp(value / 1000, tz=UTC)
