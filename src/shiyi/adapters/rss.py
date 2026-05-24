"""RSS/Atom discovery adapters, with optional canonical detail capture."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import escape, unescape
from urllib.parse import urljoin, urlparse, urlunparse

from selectolax.parser import HTMLParser, Node

from shiyi.domain.models import (
    CaptureWindow,
    ContentDepth,
    HtmlPayload,
    InternalItem,
    Provenance,
    SourceIdentity,
    TextPayload,
    payload_content_hash,
)
from shiyi.fetchers.http import HttpRssFetcher, HttpWebFetcher
from shiyi.ports.fetcher import RssEntry, RssFetcher, WebFetcher

_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
MICROSOFT_AI_BLOG_FEED_URL = (
    "https://www.microsoft.com/en-us/microsoft-cloud/blog/topic/ai-resources/feed/"
)
_HUGGINGFACE_SKIP_CLASS_FRAGMENTS = (
    "not-prose",
    "overview-card-wrapper",
    "prose-card",
    "SVELTE_HYDRATER",
    "comment",
)


class RssFeedAdapter:
    """Reads RSS/Atom feeds and emits internal items for feed entries."""

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
        content_depth: ContentDepth = "summary_only",
    ) -> None:
        """Create an RSS adapter for one feed URL."""
        self._name = name
        self._feed_url = feed_url
        self._source_kind = source_kind
        self._rss_fetcher = rss_fetcher or HttpRssFetcher(HttpWebFetcher())
        self._window = window or CaptureWindow(max_items=limit)
        self._content_depth = content_depth

    @property
    def name(self) -> str:
        """Stable adapter name."""
        return self._name

    async def discover(self) -> AsyncIterator[InternalItem]:
        """Fetch and parse the feed into Adapter -> Pipeline internal items."""
        feed = await self._rss_fetcher.fetch(self._feed_url)
        emitted = 0
        for entry in feed.entries:
            occurred_at = entry.published_at or feed.fetched_at
            if not self._window.includes(occurred_at):
                continue
            entry_id = _required_entry_field(entry.entry_id, field="entry_id")
            title = _required_entry_field(entry.title, field="title", entry_id=entry_id)
            payload = _rss_payload(title=title, link=entry.link, html=entry.html)
            item_id = f"{self._source_kind}:{entry_id}"
            yield InternalItem(
                id=item_id,
                source=SourceIdentity(kind=self._source_kind, uri=self._feed_url),
                captured_at=feed.fetched_at,
                occurred_at=occurred_at,
                payload=payload,
                content_hash=payload_content_hash(payload),
                provenance=Provenance(
                    adapter_name=self.name,
                    adapter_version=self.version,
                    fetched_at=feed.fetched_at,
                    source_item_id=entry_id,
                ),
                idempotency_key=item_id,
                metadata={"title": title, "link": entry.link, "content_depth": self._content_depth},
            )
            emitted += 1
            if self._window.max_items is not None and emitted >= self._window.max_items:
                break


@dataclass(frozen=True, slots=True)
class RssDetailArticle:
    """Canonical article data after RSS-discovery detail extraction."""

    title: str
    canonical_url: str
    body_html: str
    published_at: datetime | None = None
    authors: tuple[str, ...] = ()


RssDetailParser = Callable[[str, RssEntry], RssDetailArticle]


class RssDetailAdapter:
    """Discovers feed entries, then emits canonical detail pages."""

    version = "0.1.0"

    def __init__(  # noqa: PLR0913
        self,
        *,
        name: str,
        feed_url: str,
        source_kind: str,
        detail_parser: RssDetailParser,
        rss_fetcher: RssFetcher | None = None,
        web_fetcher: WebFetcher | None = None,
        limit: int | None = None,
        window: CaptureWindow | None = None,
    ) -> None:
        """Create an RSS discovery + detail adapter."""
        self._name = name
        self._feed_url = feed_url
        self._source_kind = source_kind
        self._detail_parser = detail_parser
        self._rss_fetcher = rss_fetcher or HttpRssFetcher(HttpWebFetcher())
        self._web_fetcher = web_fetcher or HttpWebFetcher()
        self._window = window or CaptureWindow(max_items=limit)

    @property
    def name(self) -> str:
        """Stable adapter name."""
        return self._name

    async def discover(self) -> AsyncIterator[InternalItem]:
        """Fetch RSS once, filter by window, then dereference canonical detail pages."""
        feed = await self._rss_fetcher.fetch(self._feed_url)
        emitted = 0
        for entry in feed.entries:
            occurred_at = entry.published_at or feed.fetched_at
            if not self._window.includes(occurred_at):
                continue
            entry_id = _required_entry_field(entry.entry_id, field="entry_id")
            detail_url = _require_detail_url(entry)
            detail_result = await self._web_fetcher.fetch(
                detail_url,
                source=self._source_kind,
                raw_key=_entry_metadata_hash(source=self._source_kind, url=detail_url),
            )
            article = self._detail_parser(detail_result.content, entry)
            payload = HtmlPayload(html=_detail_payload(article), url=article.canonical_url)
            item_id = f"{self._source_kind}:{entry_id}"
            yield InternalItem(
                id=item_id,
                source=SourceIdentity(kind=self._source_kind, uri=article.canonical_url),
                captured_at=detail_result.fetched_at,
                occurred_at=article.published_at or occurred_at,
                payload=payload,
                content_hash=payload_content_hash(payload),
                provenance=Provenance(
                    adapter_name=self.name,
                    adapter_version=self.version,
                    fetched_at=detail_result.fetched_at,
                    source_item_id=entry_id,
                ),
                idempotency_key=item_id,
                metadata={
                    "title": article.title,
                    "link": article.canonical_url,
                    "content_depth": "full_page",
                },
            )
            emitted += 1
            if self._window.max_items is not None and emitted >= self._window.max_items:
                break


def _rss_payload(*, title: str, link: str | None, html: str) -> HtmlPayload | TextPayload:
    if not html:
        return _fallback_text_payload(title=title, link=link)

    parts: list[str] = []
    if not _html_contains_text(html, title):
        parts.append(f"<h1>{escape(title)}</h1>")
    parts.append(html)
    if link is not None and link not in html:
        escaped_link = escape(link, quote=True)
        parts.append(f'<p>Canonical link: <a href="{escaped_link}">{escape(link)}</a></p>')
    return HtmlPayload(html=f"<article>{''.join(parts)}</article>", url=link)


def _detail_payload(article: RssDetailArticle) -> str:
    parts = [f"<h1>{escape(article.title)}</h1>"]
    if article.published_at is not None:
        published_value = escape(article.published_at.date().isoformat())
        published_iso = escape(article.published_at.isoformat(), quote=True)
        parts.append(f'<p>Published: <time datetime="{published_iso}">{published_value}</time></p>')
    parts.append(
        f'<p>Canonical link: <a href="{escape(article.canonical_url, quote=True)}">'
        f"{escape(article.canonical_url)}</a></p>"
    )
    if article.authors:
        parts.append(f"<p>Author: {escape(', '.join(article.authors))}</p>")
    parts.append(article.body_html)
    return f"<article>{''.join(parts)}</article>"


def _fallback_text_payload(*, title: str, link: str | None) -> TextPayload:
    if link is None:
        return TextPayload(text=title)
    return TextPayload(text=f"{title}\n\nCanonical link: {link}")


def _html_contains_text(html: str, text: str) -> bool:
    plain_html = unescape(_HTML_TAG_PATTERN.sub(" ", html))
    normalized_haystack = " ".join(plain_html.casefold().split())
    normalized_needle = " ".join(text.casefold().split())
    return normalized_needle in normalized_haystack


def _required_entry_field(value: str, *, field: str, entry_id: str | None = None) -> str:
    stripped = value.strip()
    if stripped:
        return stripped
    context = f" for RSS entry {entry_id}" if entry_id else ""
    msg = f"RSS entry missing required {field}{context}"
    raise ValueError(msg)


def _require_detail_url(entry: RssEntry) -> str:
    if entry.link and entry.link.strip():
        return _canonicalize_url(entry.link)
    if entry.entry_id.strip().startswith("http"):
        return _canonicalize_url(entry.entry_id)
    msg = f"RSS entry missing canonical detail URL: {entry.entry_id!r}"
    raise ValueError(msg)


def _entry_metadata_hash(*, source: str, url: str) -> str:
    return sha256(f"{source}\n{url}".encode()).hexdigest()


def _canonicalize_url(url: str, *, base_url: str | None = None) -> str:
    joined = urljoin(base_url, url) if base_url else url
    parsed = urlparse(joined)
    return urlunparse(parsed._replace(params="", query="", fragment="")).rstrip("/")


def _article_json_ld(parser: HTMLParser) -> Mapping[str, object]:
    for node in parser.css("script[type='application/ld+json']"):
        try:
            decoded = json.loads(node.text(strip=True))
        except json.JSONDecodeError:
            continue
        for candidate in _json_ld_candidates(decoded):
            if candidate.get("@type") in {"Article", "BlogPosting"}:
                return candidate
    return {}


def _json_ld_candidates(value: object) -> Sequence[Mapping[str, object]]:
    if isinstance(value, dict):
        graph = value.get("@graph")
        if isinstance(graph, list):
            return [item for item in graph if isinstance(item, dict)]
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _string_value(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _author_names(value: object) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        name = _string_value(value.get("name"))
        return (name,) if name else ()
    if isinstance(value, list):
        names = [
            name
            for item in value
            if isinstance(item, Mapping) and (name := _string_value(item.get("name"))) is not None
        ]
        return tuple(names)
    return ()


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _first_text(parser: HTMLParser, selector: str) -> str | None:
    node = parser.css_first(selector)
    if node is None:
        return None
    text = _clean_text(node.text(separator=" ", strip=True))
    return text or None


def _extract_canonical_url(parser: HTMLParser, fallback_url: str) -> str:
    for selector in ("link[rel='canonical']", "meta[property='og:url']"):
        node = parser.css_first(selector)
        if node is None:
            continue
        value = node.attributes.get("href") or node.attributes.get("content")
        if value:
            return _canonicalize_url(value, base_url=fallback_url)
    return _canonicalize_url(fallback_url)


def _require_title(title: str | None, *, url: str) -> str:
    if title:
        return title
    msg = f"detail page missing required title: {url}"
    raise ValueError(msg)


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


def _has_skip_ancestor(node: Node, *, class_fragments: tuple[str, ...]) -> bool:
    parent = node.parent
    while parent is not None:
        classes = parent.attributes.get("class") or ""
        if any(fragment in classes for fragment in class_fragments):
            return True
        parent = parent.parent
    return False


def _heading_html(node: Node) -> str:
    text = _clean_text(node.text(separator=" ", strip=True))
    return f"<{node.tag}>{escape(text)}</{node.tag}>"


def _node_html(node: Node) -> str:
    if node.tag in {"h2", "h3", "h4"}:
        return _heading_html(node)
    if node.html is not None:
        return node.html
    text = escape(_clean_text(node.text(separator=" ", strip=True)))
    return f"<{node.tag}>{text}</{node.tag}>"


def _parse_huggingface_detail(html: str, entry: RssEntry) -> RssDetailArticle:
    parser = HTMLParser(html)
    json_ld = _article_json_ld(parser)
    detail_url = _require_detail_url(entry)
    canonical_url = _extract_canonical_url(parser, detail_url)
    title = _require_title(
        _string_value(json_ld.get("headline"))
        or _first_text(parser, "div.blog-content h1")
        or _first_text(parser, "title"),
        url=canonical_url,
    )
    published_at = _parse_datetime(_string_value(json_ld.get("datePublished")))
    body_html = _huggingface_body_html(parser)
    return RssDetailArticle(
        title=title,
        canonical_url=canonical_url,
        body_html=body_html,
        published_at=published_at,
        authors=_author_names(json_ld.get("author")),
    )


def _huggingface_body_html(parser: HTMLParser) -> str:
    container = parser.css_first("div.blog-content")
    if container is None:
        msg = "Hugging Face blog detail page missing content container"
        raise ValueError(msg)
    fragments: list[str] = []
    for node in container.css("p, h2, h3, ul, ol, pre, blockquote"):
        if _has_skip_ancestor(node, class_fragments=_HUGGINGFACE_SKIP_CLASS_FRAGMENTS):
            continue
        text = _clean_text(node.text(separator=" ", strip=True))
        if not text:
            continue
        fragments.append(_node_html(node))
    if not fragments:
        msg = "Hugging Face blog detail page produced no article fragments"
        raise ValueError(msg)
    return "".join(fragments)


def _parse_google_research_detail(html: str, entry: RssEntry) -> RssDetailArticle:
    parser = HTMLParser(html)
    detail_url = _require_detail_url(entry)
    canonical_url = _extract_canonical_url(parser, detail_url)
    title = _require_title(
        _first_text(parser, "main#page-content h1") or _first_text(parser, "title"),
        url=canonical_url,
    )
    published_at, author = _google_research_hero_metadata(parser)
    body_html = _google_research_body_html(parser)
    authors = (author,) if author else ()
    return RssDetailArticle(
        title=title,
        canonical_url=canonical_url,
        body_html=body_html,
        published_at=published_at,
        authors=authors,
    )


def _google_research_hero_metadata(parser: HTMLParser) -> tuple[datetime | None, str | None]:
    hero = parser.css_first("main#page-content section.basic-hero")
    if hero is None:
        return None, None
    texts = [
        _clean_text(node.text(separator=" ", strip=True))
        for node in hero.css("p")
        if _clean_text(node.text(separator=" ", strip=True))
    ]
    published_at: datetime | None = None
    author: str | None = None
    for text in texts:
        if published_at is None and (parsed := _parse_datetime(text)) is not None:
            published_at = parsed
            continue
        if author is None:
            author = text
    return published_at, author


def _google_research_body_html(parser: HTMLParser) -> str:
    fragments: list[str] = []
    summary = parser.css_first("section.blog-summary .blog-summary__summary")
    if summary is not None and summary.html is not None:
        fragments.append(summary.html)
    for node in parser.css("div.rich-text[data-gt-id='rich_text']"):
        text = _clean_text(node.text(separator=" ", strip=True))
        if not text:
            continue
        if node.html is not None:
            fragments.append(node.html)
    if not fragments:
        msg = "Google Research detail page produced no article fragments"
        raise ValueError(msg)
    return "".join(fragments)


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


def huggingface_blog_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    rss_fetcher: RssFetcher | None = None,
    web_fetcher: WebFetcher | None = None,
) -> RssDetailAdapter:
    """Create the default Hugging Face blog adapter."""
    return RssDetailAdapter(
        name="huggingface-blog-detail",
        feed_url="https://huggingface.co/blog/feed.xml",
        source_kind="huggingface-blog",
        limit=limit,
        window=window,
        rss_fetcher=rss_fetcher,
        web_fetcher=web_fetcher,
        detail_parser=_parse_huggingface_detail,
    )


def google_research_blog_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    rss_fetcher: RssFetcher | None = None,
    web_fetcher: WebFetcher | None = None,
) -> RssDetailAdapter:
    """Create the default Google Research blog adapter."""
    return RssDetailAdapter(
        name="google-research-blog-detail",
        feed_url="https://research.google/blog/rss/",
        source_kind="google-research-blog",
        limit=limit,
        window=window,
        rss_fetcher=rss_fetcher,
        web_fetcher=web_fetcher,
        detail_parser=_parse_google_research_detail,
    )


def microsoft_ai_blog_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    rss_fetcher: RssFetcher | None = None,
) -> RssFeedAdapter:
    """Create the default Microsoft AI blog RSS adapter."""
    return RssFeedAdapter(
        name="microsoft-ai-blog-rss",
        feed_url=MICROSOFT_AI_BLOG_FEED_URL,
        source_kind="microsoft-ai-blog",
        limit=limit,
        window=window,
        rss_fetcher=rss_fetcher,
        content_depth="feed_full_content",
    )
