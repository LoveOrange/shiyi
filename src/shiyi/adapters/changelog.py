"""Official news/blog and changelog-style web adapters."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urljoin

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
INVISIBLE_TEXT_CHARS = str.maketrans("", "", "\u200b\u200c\u200d\ufeff")
HTTP_NOT_FOUND = 404
MIN_Z_AI_PARAGRAPH_CHARS = 60

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
            yield InternalItem(
                id=item_id,
                source=SourceIdentity(kind=self._source_kind, uri=detail.link),
                captured_at=detail_result.fetched_at,
                occurred_at=entry.occurred_at,
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


def _entry_payload(*, entry: ChangelogEntry, link: str) -> TextPayload:
    published = entry.occurred_at.date().isoformat()
    body = _body_without_duplicate_title(title=entry.title, body=entry.body)
    return TextPayload(
        text=(f"{entry.title}\n\nPublished: {published}\nCanonical link: {link}\n\n{body}")
    )


def _article_payload(*, entry: ArticleIndexEntry, detail: ArticleDetail) -> TextPayload:
    published = entry.occurred_at.date().isoformat()
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
