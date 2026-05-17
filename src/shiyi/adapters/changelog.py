"""Official news/blog and changelog-style web adapters."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from typing import cast
from urllib.parse import urljoin

from defusedxml import ElementTree
from selectolax.parser import HTMLParser

from shiyi.domain.models import (
    CaptureWindow,
    ContentDepth,
    InternalItem,
    Provenance,
    SourceIdentity,
    TextPayload,
    payload_content_hash,
)
from shiyi.fetchers.http import HttpWebFetcher
from shiyi.ports.fetcher import FetcherError, FetchErrorKind, FetchResult, WebFetcher

DEEPSEEK_UPDATES_URL = "https://api-docs.deepseek.com/updates"
DEEPSEEK_NEWS_BASE_URL = "https://api-docs.deepseek.com"
Z_AI_BLOG_BASE_URL = "https://z.ai/blog/"
Z_AI_RELEASE_NOTES_URL = "https://docs.z.ai/release-notes/new-released.md"
MOONSHOT_KIMI_CHANGELOG_URL = "https://platform.kimi.com/blog/posts/changelog"
GEMINI_API_CHANGELOG_URL = "https://ai.google.dev/gemini-api/docs/changelog.md.txt"
GEMINI_API_CHANGELOG_CANONICAL_URL = "https://ai.google.dev/gemini-api/docs/changelog"
MISTRAL_NEWS_URL = "https://mistral.ai/news"
MISTRAL_NEWS_BASE_URL = "https://mistral.ai"
COHERE_BLOG_URL = "https://cohere.com/blog"
COHERE_BLOG_BASE_URL = "https://cohere.com"
INVISIBLE_TEXT_CHARS = str.maketrans("", "", "\u200b\u200c\u200d\ufeff")
HTTP_NOT_FOUND = 404
MIN_Z_AI_PARAGRAPH_CHARS = 60
MIN_MISTRAL_TITLE_FRAGMENT_CHARS = 10

ChangelogParser = Callable[[str], tuple["ChangelogEntry", ...]]
ArticleIndexParser = Callable[[str], tuple["ArticleIndexEntry", ...]]


@dataclass(frozen=True, slots=True)
class ChangelogEntry:
    """One logical changelog entry extracted from a source page."""

    entry_id: str
    title: str
    occurred_at: datetime
    body: str
    link: str | None = None


@dataclass(frozen=True, slots=True)
class ArticleIndexEntry:
    """One official article discovered from a stable index page."""

    entry_id: str
    title: str
    occurred_at: datetime
    link: str
    fallback_body: str = ""


@dataclass(frozen=True, slots=True)
class ArticleDetail:
    """Normalized official article detail used as adapter payload input."""

    title: str
    body: str
    link: str
    document_link: str | None = None
    content_depth: ContentDepth = "full_page"
    occurred_at: datetime | None = None


class ChangelogPageAdapter:
    """Reads a stable official changelog page and emits internal items."""

    version = "0.1.0"

    def __init__(  # noqa: PLR0913
        self,
        *,
        name: str,
        page_url: str,
        source_kind: str,
        parser: ChangelogParser,
        web_fetcher: WebFetcher | None = None,
        limit: int | None = None,
        window: CaptureWindow | None = None,
    ) -> None:
        """Create a changelog-page adapter."""
        self._name = name
        self._page_url = page_url
        self._source_kind = source_kind
        self._parser = parser
        self._web_fetcher = web_fetcher or HttpWebFetcher()
        self._window = window or CaptureWindow(max_items=limit)

    @property
    def name(self) -> str:
        """Stable adapter name."""
        return self._name

    async def discover(self) -> AsyncIterator[InternalItem]:
        """Fetch and parse the changelog page into internal items."""
        result = await self._web_fetcher.fetch(self._page_url)
        emitted = 0
        for entry in self._parser(result.content):
            if not self._window.includes(entry.occurred_at):
                continue
            link = entry.link or self._page_url
            payload = _entry_payload(entry=entry, link=link)
            item_id = f"{self._source_kind}:{entry.entry_id}"
            yield InternalItem(
                id=item_id,
                source=SourceIdentity(kind=self._source_kind, uri=self._page_url),
                captured_at=result.fetched_at,
                occurred_at=entry.occurred_at,
                payload=payload,
                content_hash=payload_content_hash(payload),
                provenance=Provenance(
                    adapter_name=self.name,
                    adapter_version=self.version,
                    fetched_at=result.fetched_at,
                    source_item_id=entry.entry_id,
                ),
                idempotency_key=item_id,
                metadata={"title": entry.title, "link": link, "content_depth": "feed_full_content"},
            )
            emitted += 1
            if self._window.max_items is not None and emitted >= self._window.max_items:
                break


class OfficialArticleAdapter:
    """Uses an index only for discovery, then emits official article/blog pages."""

    version = "0.1.0"

    def __init__(  # noqa: PLR0913
        self,
        *,
        name: str,
        index_url: str,
        source_kind: str,
        index_parser: ArticleIndexParser,
        detail_parser: Callable[[str, ArticleIndexEntry], ArticleDetail],
        web_fetcher: WebFetcher | None = None,
        limit: int | None = None,
        window: CaptureWindow | None = None,
    ) -> None:
        """Create an official-article adapter."""
        self._name = name
        self._index_url = index_url
        self._source_kind = source_kind
        self._index_parser = index_parser
        self._detail_parser = detail_parser
        self._web_fetcher = web_fetcher or HttpWebFetcher()
        self._window = window or CaptureWindow(max_items=limit)

    @property
    def name(self) -> str:
        """Stable adapter name."""
        return self._name

    async def discover(self) -> AsyncIterator[InternalItem]:
        """Fetch the index, dereference official articles, and emit article items."""
        index_result = await self._web_fetcher.fetch(self._index_url)
        emitted = 0
        for entry in self._index_parser(index_result.content):
            if not self._window.includes(entry.occurred_at):
                continue
            detail_result = await self._fetch_detail(entry)
            if detail_result is None:
                continue
            detail = self._detail_parser(detail_result.content, entry)
            payload = _article_payload(entry=entry, detail=detail)
            item_id = f"{self._source_kind}:{entry.entry_id}"
            occurred_at = detail.occurred_at or entry.occurred_at
            yield InternalItem(
                id=item_id,
                source=SourceIdentity(kind=self._source_kind, uri=detail.link),
                captured_at=detail_result.fetched_at,
                occurred_at=occurred_at,
                payload=payload,
                content_hash=payload_content_hash(payload),
                provenance=Provenance(
                    adapter_name=self.name,
                    adapter_version=self.version,
                    fetched_at=detail_result.fetched_at,
                    source_item_id=entry.entry_id,
                ),
                idempotency_key=item_id,
                metadata=_article_metadata(entry=entry, detail=detail),
            )
            emitted += 1
            if self._window.max_items is not None and emitted >= self._window.max_items:
                break

    async def _fetch_detail(self, entry: ArticleIndexEntry) -> FetchResult | None:
        try:
            detail = await self._web_fetcher.fetch(entry.link)
        except FetcherError as error:
            if error.kind is FetchErrorKind.HTTP_STATUS and error.status_code == HTTP_NOT_FOUND:
                return None
            raise
        if self._source_kind == "z-ai-blog":
            asset_url = _z_ai_blog_asset_url(detail.content, base_url=entry.link)
            if asset_url:
                asset = await self._web_fetcher.fetch(asset_url)
                return detail.model_copy(
                    update={
                        "content": f"{detail.content}\n{asset.content}",
                        "fetched_at": asset.fetched_at,
                    }
                )
        return detail


def deepseek_news_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> OfficialArticleAdapter:
    """Create the default DeepSeek official news adapter."""
    return OfficialArticleAdapter(
        name="deepseek-news-article",
        index_url=DEEPSEEK_UPDATES_URL,
        source_kind="deepseek-news",
        index_parser=parse_deepseek_news_index,
        detail_parser=parse_deepseek_news_detail,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def z_ai_blog_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> OfficialArticleAdapter:
    """Create the default Z.ai official blog adapter."""
    return OfficialArticleAdapter(
        name="z-ai-blog-article",
        index_url=Z_AI_RELEASE_NOTES_URL,
        source_kind="z-ai-blog",
        index_parser=parse_z_ai_blog_index,
        detail_parser=parse_z_ai_blog_detail,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def deepseek_updates_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> OfficialArticleAdapter:
    """Deprecated compatibility wrapper for the DeepSeek official news adapter."""
    return deepseek_news_adapter(limit=limit, window=window, web_fetcher=web_fetcher)


def z_ai_release_notes_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> OfficialArticleAdapter:
    """Deprecated compatibility wrapper for the Z.ai official blog adapter."""
    return z_ai_blog_adapter(limit=limit, window=window, web_fetcher=web_fetcher)


def moonshot_kimi_changelog_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> ChangelogPageAdapter:
    """Create the default Moonshot/Kimi platform changelog adapter."""
    return ChangelogPageAdapter(
        name="moonshot-kimi-changelog-page",
        page_url=MOONSHOT_KIMI_CHANGELOG_URL,
        source_kind="moonshot-kimi-changelog",
        parser=parse_moonshot_kimi_changelog,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def gemini_api_changelog_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> ChangelogPageAdapter:
    """Create the default Gemini API changelog adapter."""
    return ChangelogPageAdapter(
        name="gemini-api-changelog-page",
        page_url=GEMINI_API_CHANGELOG_URL,
        source_kind="gemini-api-changelog",
        parser=parse_gemini_api_changelog,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def mistral_news_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> OfficialArticleAdapter:
    """Create the default Mistral official news adapter."""
    return OfficialArticleAdapter(
        name="mistral-news-article",
        index_url=MISTRAL_NEWS_URL,
        source_kind="mistral-news",
        index_parser=parse_mistral_news_index,
        detail_parser=parse_mistral_news_detail,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def cohere_blog_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> OfficialArticleAdapter:
    """Create the default Cohere official blog adapter."""
    return OfficialArticleAdapter(
        name="cohere-blog-article",
        index_url=COHERE_BLOG_URL,
        source_kind="cohere-blog",
        index_parser=parse_cohere_blog_index,
        detail_parser=parse_cohere_blog_detail,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def parse_gemini_api_changelog(content: str) -> tuple[ChangelogEntry, ...]:
    """Parse Gemini API markdown changelog entries."""
    blocks = _split_by_marker(
        content.splitlines(),
        pattern=re.compile(r"^##\s+([A-Z][a-z]+\s+\d{1,2},\s+\d{4})\s*$"),
    )
    entries: list[ChangelogEntry] = []
    for raw_date, lines in blocks:
        body = _clean_markdown_body("\n".join(lines))
        if not body:
            continue
        occurred_at = _date_utc(_parse_month_day_year(raw_date))
        title = _markdown_title_from_body(body) or f"Gemini API changelog {raw_date}"
        anchor = occurred_at.strftime("%m-%d-%Y")
        entries.append(
            ChangelogEntry(
                entry_id=occurred_at.date().isoformat(),
                title=title,
                occurred_at=occurred_at,
                body=body,
                link=f"{GEMINI_API_CHANGELOG_CANONICAL_URL}#{anchor}",
            )
        )
    return tuple(entries)


def parse_mistral_news_index(content: str) -> tuple[ArticleIndexEntry, ...]:
    """Parse Mistral's static Next.js news index as article discovery."""
    decoded = _rsc_decoded_text(content)
    post_pattern = re.compile(
        r'\{"id":"(?P<id>[^"]+)","slug":"(?P<slug>[^"]+)","author":"[^"]*",'
        r'"isPinned":(?:true|false),"date":"(?P<date>[^"]+)","category":\{.*?\},'
        r'"title":"(?P<title>(?:\\.|[^"\\])*)","description":"(?P<description>(?:\\.|[^"\\])*)",'
        r'"locale":"en"\}',
        re.DOTALL,
    )
    entries: list[ArticleIndexEntry] = []
    seen: set[str] = set()
    for match in post_pattern.finditer(decoded):
        slug = _clean_text(match.group("slug"))
        if not slug or slug in seen:
            continue
        title = _clean_text(_decode_js_string_fragment(match.group("title")))
        raw_date = match.group("date").strip()
        if not title or not raw_date:
            continue
        seen.add(slug)
        entries.append(
            ArticleIndexEntry(
                entry_id=slug,
                title=title,
                occurred_at=_datetime_utc(raw_date),
                link=urljoin(MISTRAL_NEWS_BASE_URL, f"/news/{slug}"),
                fallback_body=_clean_text(_decode_js_string_fragment(match.group("description"))),
            )
        )
    return tuple(entries)


def parse_mistral_news_detail(content: str, entry: ArticleIndexEntry) -> ArticleDetail:
    """Parse a Mistral official news detail page."""
    title = _clean_text(
        _meta_content(content, "og:title") or _first_heading_text(content, "h1") or entry.title
    )
    title = re.sub(r"\s*\|\s*Mistral AI\s*$", "", title).strip()
    body_lines = _article_text_lines(content, selector="article")
    body = _mistral_article_body(title=title, lines=body_lines)
    return ArticleDetail(
        title=title,
        body=body or entry.fallback_body,
        link=entry.link,
        content_depth=_article_content_depth(body=body, fallback_body=entry.fallback_body),
    )


def parse_cohere_blog_index(content: str) -> tuple[ArticleIndexEntry, ...]:
    """Parse Cohere's official sitemap or static blog index as article discovery."""
    if content.lstrip().startswith("<?xml"):
        sitemap_entries = _cohere_blog_sitemap_entries(content)
        if sitemap_entries:
            return sitemap_entries
    decoded = _rsc_decoded_text(content)
    entries: list[ArticleIndexEntry] = []
    seen: set[str] = set()
    ghost_pattern = re.compile(
        r'"published_at":"(?P<date>[^"]+)","slug":"(?P<slug>[^"]+)","title":"(?P<title>[^"]+)","id":"(?P<id>[^"]+)"'
    )
    sanity_pattern = re.compile(
        r'"_id":"(?P<id>[^"]+)"(?:(?!"_id":).){0,6000}?"date":"(?P<date>\d{4}-\d{2}-\d{2})"'
        r'(?:(?!"_id":).){0,6000}?"slug":\{"_type":"slug","current":"(?P<slug>[^"]+)"\}'
        r'(?:(?!"_id":).){0,6000}?"title":"(?P<title>[^"]+)"',
        re.DOTALL,
    )
    for pattern in (sanity_pattern, ghost_pattern):
        for match in pattern.finditer(decoded):
            slug = _clean_text(match.group("slug"))
            if not slug or slug in seen:
                continue
            title = _clean_text(match.group("title"))
            raw_date = match.group("date")
            if not title or not raw_date:
                continue
            seen.add(slug)
            entries.append(
                ArticleIndexEntry(
                    entry_id=slug,
                    title=title,
                    occurred_at=_datetime_utc(raw_date),
                    link=urljoin(COHERE_BLOG_BASE_URL, f"/blog/{slug}"),
                )
            )
    entries.sort(key=lambda entry: entry.occurred_at, reverse=True)
    return tuple(entries)


def parse_cohere_blog_detail(content: str, entry: ArticleIndexEntry) -> ArticleDetail:
    """Parse a Cohere official blog detail page from embedded Ghost/RSC data."""
    title = _clean_text(
        _ghost_blog_field(content, "title") or _first_heading_text(content, "h1") or entry.title
    )
    body_html = _cohere_ghost_html(content)
    body = "\n".join(
        _meaningful_lines(HTMLParser(body_html).text(separator="\n", strip=True).splitlines())
    )
    published_at = _ghost_blog_field(content, "published_at")
    return ArticleDetail(
        title=title,
        body=body,
        link=entry.link,
        content_depth=_article_content_depth(body=body, fallback_body=entry.fallback_body),
        occurred_at=_datetime_utc(published_at) if published_at else None,
    )


def parse_deepseek_news_index(content: str) -> tuple[ArticleIndexEntry, ...]:
    """Parse DeepSeek changelog as a discovery index for official news pages."""
    blocks = _deepseek_update_blocks(content)
    entries: list[ArticleIndexEntry] = []
    for date_value, block_html in blocks:
        title = _first_heading_text(block_html, "h3") or f"DeepSeek news {date_value}"
        body = "\n".join(_meaningful_lines(_html_main_text(block_html).splitlines()))
        link = _first_href(block_html, contains="/news/")
        if not link:
            continue
        entries.append(
            ArticleIndexEntry(
                entry_id=_slug_or_value(date_value, title),
                title=title,
                occurred_at=_date_utc(date_value),
                link=urljoin(DEEPSEEK_NEWS_BASE_URL, link),
                fallback_body=body,
            )
        )
    return tuple(entries)


def parse_deepseek_news_detail(content: str, entry: ArticleIndexEntry) -> ArticleDetail:
    """Parse an official DeepSeek news article page."""
    title = _clean_text(_first_heading_text(content, "h1") or entry.title)
    body_lines = [
        line
        for line in _meaningful_lines(_html_main_text(content).splitlines())
        if not _looks_like_duplicate_title(line, (title, entry.title))
    ]
    body = _body_without_duplicate_title(title=title, body="\n".join(body_lines))
    return ArticleDetail(
        title=title,
        body=body or entry.fallback_body,
        link=entry.link,
        content_depth=_article_content_depth(body=body, fallback_body=entry.fallback_body),
    )


def parse_z_ai_blog_index(content: str) -> tuple[ArticleIndexEntry, ...]:
    """Parse Z.ai release notes only as a blog discovery index.

    Z.ai exposes individual official blog pages such as /blog/glm-5.1 but does not list
    them in sitemap.xml. Release notes are therefore used only to derive candidate blog
    URLs; entries without a reachable blog page are skipped by the adapter.
    """
    entries: list[ArticleIndexEntry] = []
    for note in parse_z_ai_release_notes(content):
        slug = _z_ai_blog_slug(note.title)
        if not slug:
            continue
        entries.append(
            ArticleIndexEntry(
                entry_id=note.entry_id,
                title=note.title,
                occurred_at=note.occurred_at,
                link=urljoin(Z_AI_BLOG_BASE_URL, slug),
                fallback_body=note.body,
            )
        )
    return tuple(entries)


def parse_z_ai_blog_detail(content: str, entry: ArticleIndexEntry) -> ArticleDetail:
    """Parse a Z.ai official blog article shell and bundled article module."""
    title = _clean_text(_regex_last_group(content, r"title:`([^`]+)`") or entry.title)
    date_text = _regex_last_group(content, r"date:`([^`]+)`")
    document_link = _regex_last_group(content, r"document:`([^`]+)`")
    article_body = _z_ai_blog_body(content)
    body = article_body
    if date_text and date_text != entry.occurred_at.date().isoformat():
        body = f"Article date: {date_text}\n{body}" if body else f"Article date: {date_text}"
    return ArticleDetail(
        title=title,
        body=body or entry.fallback_body,
        link=entry.link,
        document_link=document_link,
        content_depth=_article_content_depth(body=article_body, fallback_body=entry.fallback_body),
    )


def parse_deepseek_updates(content: str) -> tuple[ChangelogEntry, ...]:
    """Parse DeepSeek Docusaurus changelog HTML into dated entries."""
    text = _html_main_text(content)
    blocks = _split_by_marker(
        text.splitlines(), pattern=re.compile(r"^Date:\s*(\d{4}-\d{2}-\d{2})$")
    )
    entries: list[ChangelogEntry] = []
    for date_value, lines in blocks:
        body_lines = _meaningful_lines(lines)
        if not body_lines:
            continue
        title = body_lines[0]
        entry_id = _slug_or_value(date_value, title)
        entries.append(
            ChangelogEntry(
                entry_id=entry_id,
                title=title,
                occurred_at=_date_utc(date_value),
                body="\n".join(body_lines),
                link=f"{DEEPSEEK_UPDATES_URL}#date-{date_value}",
            )
        )
    return tuple(entries)


def parse_z_ai_release_notes(content: str) -> tuple[ChangelogEntry, ...]:
    """Parse Z.ai Mintlify markdown release notes into entries."""
    pattern = re.compile(
        r'<Update\s+label="(?P<date>\d{4}-\d{2}-\d{2})"\s+description="(?P<title>[^"]*)"\s*>\s*(?P<body>.*?)\s*</Update>',
        re.DOTALL,
    )
    entries: list[ChangelogEntry] = []
    for match in pattern.finditer(content):
        date_value = match.group("date")
        title = _clean_text(match.group("title"))
        body = _clean_markdown_body(match.group("body"))
        if not title or not body:
            continue
        entries.append(
            ChangelogEntry(
                entry_id=_slug_or_value(date_value, title),
                title=title,
                occurred_at=_date_utc(date_value),
                body=body,
                link=Z_AI_RELEASE_NOTES_URL.removesuffix(".md"),
            )
        )
    return tuple(entries)


def parse_moonshot_kimi_changelog(content: str) -> tuple[ChangelogEntry, ...]:
    """Parse the Kimi Open Platform static changelog page into dated entries."""
    text = _html_main_text(content)
    blocks = _split_by_marker(
        text.splitlines(), pattern=re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$")
    )
    entries: list[ChangelogEntry] = []
    for raw_date, lines in blocks:
        date_value = _normalize_chinese_date(raw_date)
        body_lines = _meaningful_lines(lines)
        if not body_lines:
            continue
        title = body_lines[0]
        entries.append(
            ChangelogEntry(
                entry_id=date_value,
                title=title,
                occurred_at=_date_utc(date_value),
                body="\n".join(body_lines),
                link=f"{MOONSHOT_KIMI_CHANGELOG_URL}#{date_value}",
            )
        )
    return tuple(entries)


def _cohere_blog_sitemap_entries(content: str) -> tuple[ArticleIndexEntry, ...]:
    root = ElementTree.fromstring(content)
    namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
    entries: list[ArticleIndexEntry] = []
    for url_node in root.findall(f"{namespace}url"):
        link = (url_node.findtext(f"{namespace}loc") or "").strip()
        lastmod = (url_node.findtext(f"{namespace}lastmod") or "").strip()
        if not link.startswith(f"{COHERE_BLOG_BASE_URL}/blog/"):
            continue
        slug = link.rstrip("/").rsplit("/", 1)[-1]
        if not slug or not lastmod:
            continue
        title = slug.replace("-", " ").strip().title()
        entries.append(
            ArticleIndexEntry(
                entry_id=slug,
                title=title,
                occurred_at=_datetime_utc(lastmod),
                link=link,
            )
        )
    entries.sort(key=lambda entry: entry.occurred_at, reverse=True)
    return tuple(entries)


def _parse_month_day_year(value: str) -> str:
    parsed = datetime.strptime(value, "%B %d, %Y").replace(tzinfo=UTC)
    return parsed.date().isoformat()


def _markdown_title_from_body(body: str) -> str | None:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("-"):
            candidate = stripped.lstrip("- ").strip()
            candidate = re.sub(r"[`*_]+", "", candidate).strip()
            return candidate.rstrip(".") or None
        if stripped:
            return stripped
    return None


def _datetime_utc(value: str) -> datetime:
    normalized = value.strip()
    if not normalized:
        msg = "empty datetime value"
        raise ValueError(msg)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
        return _date_utc(normalized)
    normalized = normalized.replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", normalized):
        normalized = f"{normalized}+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _meta_content(html: str, name: str) -> str | None:
    parser = HTMLParser(html)
    selector = f'meta[property="{name}"]'
    node = parser.css_first(selector)
    if node is None:
        node = parser.css_first(f'meta[name="{name}"]')
    if node is None:
        return None
    content = node.attributes.get("content")
    if not content:
        return None
    text = _clean_text(content)
    return text or None


def _article_text_lines(content: str, *, selector: str) -> list[str]:
    parser = HTMLParser(content)
    node = parser.css_first(selector)
    if node is None:
        node = parser.css_first("main") or parser.css_first("body")
    if node is None:
        return _meaningful_lines(content.splitlines())
    return _meaningful_lines(node.text(separator="\n", strip=True).splitlines())


def _mistral_article_body(*, title: str, lines: Sequence[str]) -> str:
    body_lines: list[str] = []
    stop_at = {"share this article", "more from mistral ai", "the next chapter of ai is yours."}
    title_key = _title_compare_key(title)
    start = 0
    for index, line in enumerate(lines):
        if line.casefold().startswith("press enter or space to select"):
            continue
        line_key = _title_compare_key(line)
        if (
            line_key
            and len(line_key) >= MIN_MISTRAL_TITLE_FRAGMENT_CHARS
            and (line_key in title_key or title_key in line_key)
        ):
            start = index
            break
    for line in lines[start:]:
        lower = line.casefold()
        if lower in stop_at:
            break
        if lower.startswith("press enter or space to select"):
            continue
        body_lines.append(line)
    return "\n".join(body_lines).strip()


def _rsc_decoded_text(content: str) -> str:
    decoded = content.replace('\\"', '"')
    replacements = {
        r"\u003c": "<",
        r"\u003e": ">",
        r"\u0026": "&",
        r"\u0027": "'",
        r"\u0022": '"',
        r"\u002F": "/",
        r"\n": "\n",
        r"\t": "\t",
    }
    for escaped, visible in replacements.items():
        decoded = decoded.replace(escaped, visible)
    return decoded


def _rsc_json_array_after(content: str, marker: str) -> list[object]:
    decoded = _rsc_decoded_text(content)
    marker_index = decoded.find(marker)
    if marker_index < 0:
        return []
    start = decoded.find("[", marker_index + len(marker))
    if start < 0:
        return []
    end = _balanced_json_end(decoded, start)
    if end is None:
        return []
    return cast(list[object], json.loads(decoded[start:end]))


def _balanced_json_end(text: str, start: int) -> int | None:
    stack: list[str] = []
    in_string = False
    escaped = False
    pairs = {"[": "]", "{": "}"}
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
            if not stack:
                return index + 1
    return None


def _ghost_blog_field(content: str, field: str) -> str | None:
    decoded = _rsc_decoded_text(content)
    start = decoded.find('"ghostBlogData"')
    search_area = decoded[start:] if start >= 0 else decoded
    match = re.search(rf'"{re.escape(field)}":"(?P<value>(?:\\.|[^"\\])*)"', search_area)
    if match is None:
        return None
    return _decode_js_string_fragment(match.group("value"))


def _cohere_ghost_html(content: str) -> str:
    html_ref = _ghost_blog_field(content, "html")
    if not html_ref or not html_ref.startswith("$"):
        return ""
    ref = re.escape(html_ref[1:])
    match = re.search(
        rf'{ref}:T(?P<length>[0-9a-f]+),(?P<html>.*?)(?="\]\)</script>)',
        content,
        re.DOTALL,
    )
    if match is None:
        return ""
    expected_length = int(match.group("length"), 16)
    decoded_parts = [_decode_js_string_fragment(match.group("html"))]
    decoded = "".join(decoded_parts)
    if len(decoded) >= expected_length - 32:
        return _truncate_cohere_rsc_tail(decoded)
    tail = content[match.end() :]
    chunk_pattern = re.compile(
        r'self\.__next_f\.push\(\[1,"(?P<chunk>.*?)(?="\]\)</script>)', re.DOTALL
    )
    for chunk_match in chunk_pattern.finditer(tail):
        decoded_parts.append(_decode_js_string_fragment(chunk_match.group("chunk")))
        decoded = "".join(decoded_parts)
        if len(decoded) >= expected_length - 32:
            return _truncate_cohere_rsc_tail(decoded)
    return _truncate_cohere_rsc_tail(decoded)


def _truncate_cohere_rsc_tail(value: str) -> str:
    for marker in ('5:["$"', '\n5:["$"'):
        index = value.find(marker)
        if index >= 0:
            return value[:index]
    return value


def _decode_js_string_fragment(value: str) -> str:
    try:
        return cast(str, json.loads(f'"{value}"'))
    except json.JSONDecodeError:
        return _rsc_decoded_text(value)


def _entry_payload(*, entry: ChangelogEntry, link: str) -> TextPayload:
    published = entry.occurred_at.date().isoformat()
    body = _body_without_duplicate_title(title=entry.title, body=entry.body)
    return TextPayload(
        text=(f"{entry.title}\n\nPublished: {published}\nCanonical link: {link}\n\n{body}")
    )


def _article_payload(*, entry: ArticleIndexEntry, detail: ArticleDetail) -> TextPayload:
    published_at = detail.occurred_at or entry.occurred_at
    published = published_at.date().isoformat()
    body = _body_without_duplicate_title(title=detail.title, body=detail.body)
    metadata_lines = [
        detail.title,
        "",
        f"Published: {published}",
        f"Canonical link: {detail.link}",
    ]
    if detail.document_link:
        metadata_lines.append(f"Documentation: {detail.document_link}")
    metadata_lines.extend(["", body])
    return TextPayload(text="\n".join(metadata_lines).strip())


def _article_metadata(*, entry: ArticleIndexEntry, detail: ArticleDetail) -> dict[str, str]:
    metadata = {
        "title": detail.title,
        "link": detail.link,
        "index_title": entry.title,
        "content_depth": detail.content_depth,
    }
    if detail.document_link:
        metadata["document_link"] = detail.document_link
    return metadata


def _article_content_depth(*, body: str, fallback_body: str) -> ContentDepth:
    if body.strip():
        return "full_page"
    if fallback_body.strip():
        return "summary_only"
    return "blocked"


def _body_without_duplicate_title(*, title: str, body: str) -> str:
    body_lines = body.strip().splitlines()
    if body_lines and _clean_text(body_lines[0]).casefold() == title.casefold():
        return "\n".join(body_lines[1:]).strip()
    return body.strip()


def _deepseek_update_blocks(content: str) -> list[tuple[str, str]]:
    matches = list(
        re.finditer(
            r"<h2[^>]*>\s*Date:\s*(\d{4}-\d{2}-\d{2}).*?</h2>",
            content,
            flags=re.DOTALL,
        )
    )
    blocks: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        blocks.append((match.group(1), content[match.start() : end]))
    return blocks


def _first_heading_text(html: str, selector: str) -> str | None:
    node = HTMLParser(html).css_first(selector)
    if node is None:
        return None
    text = _clean_text(node.text(separator=" ", strip=True))
    return text or None


def _first_href(html: str, *, contains: str) -> str | None:
    for node in HTMLParser(html).css("a"):
        href = node.attributes.get("href")
        if href and contains in href:
            return href
    return None


def _z_ai_blog_asset_url(html: str, *, base_url: str) -> str | None:
    for script in HTMLParser(html).css("script"):
        src = script.attributes.get("src")
        if src and "/blog/assets/" in src:
            return urljoin(base_url, src)
    return None


def _z_ai_blog_slug(title: str) -> str:
    return re.sub(r"[^a-z0-9.]+", "-", title.casefold()).strip("-")


def _regex_last_group(content: str, pattern: str) -> str | None:
    matches = list(re.finditer(pattern, content))
    return matches[-1].group(1) if matches else None


def _looks_like_duplicate_title(line: str, titles: Sequence[str]) -> bool:
    normalized_line = _title_compare_key(line)
    return any(normalized_line == _title_compare_key(title) for title in titles if title)


def _title_compare_key(value: str) -> str:
    without_date = re.sub(r"\b\d{4}/\d{2}/\d{2}\b", "", value)
    return re.sub(r"[^a-z0-9]+", "", without_date.casefold())


def _z_ai_blog_body(content: str) -> str:
    paragraphs: list[str] = []
    for raw_value in re.findall(r"children:`((?:\\`|[^`])*)`", content):
        value = raw_value.replace("\\`", "`")
        value = value.replace("\\n", " ").replace("\\t", " ")
        text = _clean_text(value)
        if len(text) >= MIN_Z_AI_PARAGRAPH_CHARS:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def _split_by_marker(
    lines: Sequence[str], *, pattern: re.Pattern[str]
) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    current_marker: str | None = None
    current_lines: list[str] = []
    for raw_line in lines:
        line = _clean_text(raw_line)
        match = pattern.match(line)
        if match is not None:
            if current_marker is not None:
                blocks.append((current_marker, current_lines))
            current_marker = match.group(1) if match.lastindex == 1 else line
            current_lines = []
            continue
        if current_marker is not None:
            current_lines.append(line)
    if current_marker is not None:
        blocks.append((current_marker, current_lines))
    return blocks


def _html_main_text(html: str) -> str:
    parser = HTMLParser(html)
    for selector in ("article", "main", "body"):
        node = parser.css_first(selector)
        if node is not None:
            text = node.text(separator="\n", strip=True)
            if text:
                return text
    return html


def _meaningful_lines(lines: Sequence[str]) -> list[str]:
    ignored = {"", "on this page", "change log", "news", "返回", "platform"}
    return [
        line
        for raw_line in lines
        if (line := _clean_text(raw_line)) and line.casefold() not in ignored
    ]


def _clean_markdown_body(value: str) -> str:
    normalized = value.replace("\\*", "*")
    lines = _meaningful_lines(normalized.splitlines())
    return "\n".join(lines)


def _clean_text(value: str) -> str:
    visible = unescape(value).translate(INVISIBLE_TEXT_CHARS)
    return " ".join(visible.strip().split())


def _date_utc(value: str) -> datetime:
    date_parts = datetime.fromisoformat(value).date()
    return datetime(date_parts.year, date_parts.month, date_parts.day, tzinfo=UTC)


def _normalize_chinese_date(value: str) -> str:
    match = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", value)
    if match is None:
        return value
    year, month, day = (int(part) for part in match.groups())
    return f"{year:04d}-{month:02d}-{day:02d}"


def _slug_or_value(value: str, title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.casefold()).strip("-")
    if not slug:
        return value
    return f"{value}-{slug}"
