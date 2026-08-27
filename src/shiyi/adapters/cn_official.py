"""Official Chinese AI vendor release and article adapters."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urljoin, urlparse

from selectolax.parser import HTMLParser, Node

from shiyi.adapters.changelog import (
    ArticleDetail,
    ArticleIndexEntry,
    ChangelogEntry,
    ChangelogPageAdapter,
    OfficialArticleAdapter,
)
from shiyi.domain.models import CaptureWindow
from shiyi.ports.fetcher import WebFetcher

KIMI_RESEARCH_URL = "https://www.kimi.com/en/blog/"
KIMI_BASE_URL = "https://www.kimi.com"
KIMI_CODE_CHANGELOG_URL = "https://www.kimi.com/code/docs/kimi-code/whats-new.html"
QWEN_MODEL_RELEASES_URL = "https://docs.qwencloud.com/changelog/models.md"
QWEN_MODEL_RELEASES_CANONICAL_URL = "https://docs.qwencloud.com/changelog/models"
QWEN_CODE_BLOG_URL = "https://qwenlm.github.io/qwen-code-docs/en/blog/"
QWEN_CODE_BASE_URL = "https://qwenlm.github.io/qwen-code-docs"
BIGMODEL_RELEASES_URL = "https://docs.bigmodel.cn/cn/update/new-releases.md"
BIGMODEL_RELEASES_CANONICAL_URL = "https://docs.bigmodel.cn/cn/update/new-releases"
MINIMAX_MODEL_RELEASES_URL = "https://platform.minimaxi.com/docs/release-notes/models.md"
MINIMAX_MODEL_RELEASES_CANONICAL_URL = "https://platform.minimaxi.com/docs/release-notes/models"
MINIMAX_API_UPDATES_URL = "https://platform.minimaxi.com/docs/release-notes/apis.md"
MINIMAX_API_UPDATES_CANONICAL_URL = "https://platform.minimaxi.com/docs/release-notes/apis"

_INVISIBLE_TEXT_CHARS = str.maketrans("", "", "\u200b\u200c\u200d\ufeff")
_UPDATE_PATTERN = re.compile(
    r'<Update\s+label="(?P<label>[^"]+)"(?P<attrs>[^>]*)>\s*'
    r"(?P<body>.*?)\s*</Update>",
    re.DOTALL,
)
_CHINESE_DATE_PATTERN = re.compile(
    r"(?P<year>\d{4})\s*年\s*(?P<month>\d{1,2})\s*月\s*(?P<day>\d{1,2})\s*日"
)


def kimi_research_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> OfficialArticleAdapter:
    """Create the Kimi official research article adapter."""
    return OfficialArticleAdapter(
        name="kimi-research-article",
        index_parser=parse_kimi_research_index,
        detail_parser=parse_kimi_research_detail,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def kimi_code_changelog_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> ChangelogPageAdapter:
    """Create the Kimi Code dated changelog adapter."""
    return ChangelogPageAdapter(
        name="kimi-code-changelog-page",
        parser=parse_kimi_code_changelog,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def qwen_model_releases_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> ChangelogPageAdapter:
    """Create the Qwen model release-note adapter."""
    return ChangelogPageAdapter(
        name="qwen-model-releases-page",
        parser=parse_qwen_model_releases,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def qwen_code_blog_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> OfficialArticleAdapter:
    """Create the Qwen Code official article adapter."""
    return OfficialArticleAdapter(
        name="qwen-code-blog-article",
        index_parser=parse_qwen_code_blog_index,
        detail_parser=parse_qwen_code_blog_detail,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def bigmodel_releases_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> ChangelogPageAdapter:
    """Create the Zhipu BigModel release-note adapter."""
    return ChangelogPageAdapter(
        name="zhipu-bigmodel-releases-page",
        parser=parse_bigmodel_releases,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def minimax_model_releases_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> ChangelogPageAdapter:
    """Create the MiniMax model release-note adapter."""
    return ChangelogPageAdapter(
        name="minimax-model-releases-page",
        parser=parse_minimax_model_releases,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def minimax_api_updates_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> ChangelogPageAdapter:
    """Create the MiniMax API update adapter."""
    return ChangelogPageAdapter(
        name="minimax-api-updates-page",
        parser=parse_minimax_api_updates,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def parse_kimi_research_index(content: str) -> tuple[ArticleIndexEntry, ...]:
    """Parse Kimi's rendered research cards as article discovery."""
    parser = HTMLParser(content)
    entries: list[ArticleIndexEntry] = []
    seen: set[str] = set()
    for card in parser.css(".menu-card"):
        link_node = card.css_first("a[href]")
        title_node = card.css_first(".card-title")
        date_node = card.css_first(".card-date")
        if link_node is None or title_node is None or date_node is None:
            continue
        href = str(link_node.attributes.get("href") or "")
        if not href.startswith("/blog/"):
            continue
        entry_id = urlparse(href).path.rstrip("/").rsplit("/", 1)[-1]
        if not entry_id or entry_id in seen:
            continue
        title = _clean_text(title_node.text(separator=" ", strip=True))
        raw_date = _clean_text(date_node.text(separator=" ", strip=True))
        if not title or not raw_date:
            continue
        seen.add(entry_id)
        entries.append(
            ArticleIndexEntry(
                entry_id=entry_id,
                title=title,
                occurred_at=datetime.strptime(raw_date, "%Y/%m/%d").replace(tzinfo=UTC),
                link=urljoin(KIMI_BASE_URL, href),
            )
        )
    entries.sort(key=lambda entry: entry.occurred_at, reverse=True)
    return tuple(entries)


def parse_kimi_research_detail(content: str, entry: ArticleIndexEntry) -> ArticleDetail:
    """Parse one Kimi research detail page without navigation chrome."""
    parser = HTMLParser(content)
    title_node = parser.css_first("h1")
    body_node = parser.css_first(".blog-v2-main .markdown") or parser.css_first("main")
    title = (
        _clean_text(title_node.text(separator=" ", strip=True))
        if title_node is not None
        else entry.title
    )
    body = _node_text(body_node)
    return ArticleDetail(
        title=title,
        body=body,
        link=entry.link,
        complete=bool(body),
        summary=_meta_content(parser, "description"),
    )


def parse_kimi_code_changelog(content: str) -> tuple[ChangelogEntry, ...]:
    """Parse one SourceItem per dated Kimi Code release."""
    parser = HTMLParser(content)
    entries: list[ChangelogEntry] = []
    for release in parser.css(".wn-entry"):
        heading = release.css_first("h2[id]")
        version_node = release.css_first(".ignore-header")
        date_node = release.css_first(".wn-date")
        product_node = release.css_first(".wn-product")
        body_node = release.css_first(".wn-content")
        if heading is None or version_node is None or date_node is None or body_node is None:
            continue
        anchor = str(heading.attributes.get("id") or "")
        version = _clean_text(version_node.text(separator=" ", strip=True))
        product = (
            _clean_text(product_node.text(separator=" ", strip=True))
            if product_node is not None
            else "Kimi Code"
        )
        occurred_at = _chinese_date_utc(date_node.text(separator=" ", strip=True))
        body = _node_text(body_node)
        if not anchor or not version or occurred_at is None or not body:
            continue
        entries.append(
            ChangelogEntry(
                entry_id=anchor,
                title=f"{product} {version}",
                occurred_at=occurred_at,
                body=body,
                link=f"{KIMI_CODE_CHANGELOG_URL}#{anchor}",
            )
        )
    return tuple(entries)


def parse_qwen_model_releases(content: str) -> tuple[ChangelogEntry, ...]:
    """Parse Qwen's Mintlify model release blocks."""
    entries: list[ChangelogEntry] = []
    for match in _UPDATE_PATTERN.finditer(content):
        occurred_at = _english_or_iso_date_utc(match.group("label"))
        body = _clean_mdx_body(match.group("body"))
        title = _first_markdown_heading(match.group("body"))
        if occurred_at is None or not title or not body:
            continue
        entries.append(
            ChangelogEntry(
                entry_id=_entry_id(occurred_at, title),
                title=title,
                occurred_at=occurred_at,
                body=body,
                link=QWEN_MODEL_RELEASES_CANONICAL_URL,
            )
        )
    return tuple(entries)


def parse_qwen_code_blog_index(content: str) -> tuple[ArticleIndexEntry, ...]:
    """Parse Qwen Code's embedded, server-rendered article index."""
    decoded = _decode_next_data(content)
    pattern = re.compile(
        r'\{"title":"(?P<title>(?:\\.|[^"\\])*)","date":"(?P<date>\d{4}-\d{2}-\d{2})",'
        r'"description":"(?P<description>(?:\\.|[^"\\])*)","author":"(?P<author>(?:\\.|[^"\\])*)",'
        r'"route":"(?P<route>/en/blog/[^"\\]+)"'
    )
    entries: list[ArticleIndexEntry] = []
    seen: set[str] = set()
    for match in pattern.finditer(decoded):
        route = match.group("route").rstrip("/")
        entry_id = route.removeprefix("/en/blog/")
        if not entry_id or entry_id in seen:
            continue
        seen.add(entry_id)
        entries.append(
            ArticleIndexEntry(
                entry_id=entry_id,
                title=_decode_json_fragment(match.group("title")),
                occurred_at=_date_utc(match.group("date")),
                link=f"{QWEN_CODE_BASE_URL}{route}/",
                fallback_body=_decode_json_fragment(match.group("description")),
                summary=_decode_json_fragment(match.group("description")) or None,
            )
        )
    entries.sort(key=lambda entry: entry.occurred_at, reverse=True)
    return tuple(entries)


def parse_qwen_code_blog_detail(content: str, entry: ArticleIndexEntry) -> ArticleDetail:
    """Parse a complete Qwen Code article body."""
    parser = HTMLParser(content)
    title_node = parser.css_first("main h1") or parser.css_first("h1")
    body_node = parser.css_first("main")
    title = (
        _clean_text(title_node.text(separator=" ", strip=True))
        if title_node is not None
        else entry.title
    )
    header_node = title_node.parent if title_node is not None else None
    author_node = header_node.css_first(".font-medium") if header_node is not None else None
    author = _node_text(author_node)
    body = _node_text(body_node)
    return ArticleDetail(
        title=title,
        body=body or entry.fallback_body,
        link=entry.link,
        complete=bool(body),
        summary=_meta_content(parser, "description") or entry.summary,
        authors=(author,) if author else (),
    )


def parse_bigmodel_releases(content: str) -> tuple[ChangelogEntry, ...]:
    """Parse Zhipu BigModel's dated Mintlify release blocks."""
    entries: list[ChangelogEntry] = []
    for match in _UPDATE_PATTERN.finditer(content):
        occurred_at = _english_or_iso_date_utc(match.group("label"))
        description_match = re.search(r'description="([^"]+)"', match.group("attrs"))
        title = _clean_text(description_match.group(1)) if description_match else ""
        body = _clean_mdx_body(match.group("body"))
        if occurred_at is None or not title or not body:
            continue
        entries.append(
            ChangelogEntry(
                entry_id=_entry_id(occurred_at, title),
                title=title,
                occurred_at=occurred_at,
                body=body,
                link=BIGMODEL_RELEASES_CANONICAL_URL,
            )
        )
    return tuple(entries)


def parse_minimax_model_releases(content: str) -> tuple[ChangelogEntry, ...]:
    """Parse each dated MiniMax model card as one release item."""
    blocks = _split_chinese_markdown_dates(content, heading_level=2)
    card_pattern = re.compile(r"<Card\b(?P<attrs>[^>]*)>(?P<body>.*?)</Card>", re.DOTALL)
    entries: list[ChangelogEntry] = []
    for occurred_at, block in blocks:
        for card in card_pattern.finditer(block):
            title_match = re.search(r'title="([^"]+)"', card.group("attrs"))
            href_match = re.search(r'href="([^"]+)"', card.group("attrs"))
            title = _clean_text(title_match.group(1)) if title_match else ""
            body = _clean_mdx_body(card.group("body"))
            if not title or not body:
                continue
            link = (
                urljoin(MINIMAX_MODEL_RELEASES_CANONICAL_URL, href_match.group(1))
                if href_match
                else MINIMAX_MODEL_RELEASES_CANONICAL_URL
            )
            entries.append(
                ChangelogEntry(
                    entry_id=_entry_id(occurred_at, title),
                    title=title,
                    occurred_at=occurred_at,
                    body=body,
                    link=link,
                )
            )
    return tuple(entries)


def parse_minimax_api_updates(content: str) -> tuple[ChangelogEntry, ...]:
    """Parse one MiniMax API update item per complete date heading."""
    entries: list[ChangelogEntry] = []
    for occurred_at, body_value in _split_chinese_markdown_dates(content, heading_level=3):
        body = _clean_mdx_body(body_value)
        if not body:
            continue
        title = f"MiniMax API 更新 — {occurred_at.date().isoformat()}"
        entries.append(
            ChangelogEntry(
                entry_id=occurred_at.date().isoformat(),
                title=title,
                occurred_at=occurred_at,
                body=body,
                link=MINIMAX_API_UPDATES_CANONICAL_URL,
            )
        )
    return tuple(entries)


def _split_chinese_markdown_dates(
    content: str, *, heading_level: int
) -> tuple[tuple[datetime, str], ...]:
    marker = "#" * heading_level
    pattern = re.compile(
        rf"^{marker}\s+(?P<date>\d{{4}}\s*年\s*\d{{1,2}}\s*月\s*\d{{1,2}}\s*日)\s*$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(content))
    blocks: list[tuple[datetime, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        occurred_at = _chinese_date_utc(match.group("date"))
        if occurred_at is not None:
            blocks.append((occurred_at, content[match.end() : end]))
    return tuple(blocks)


def _node_text(node: Node | None) -> str:
    if node is None:
        return ""
    return "\n".join(
        line
        for raw_line in node.text(separator="\n", strip=True).splitlines()
        if (line := _clean_text(raw_line))
    )


def _meta_content(parser: HTMLParser, name: str) -> str | None:
    for node in parser.css("meta"):
        key = node.attributes.get("name") or node.attributes.get("property")
        value = node.attributes.get("content")
        if key in {name, f"og:{name}"} and value:
            return _clean_text(value)
    return None


def _clean_mdx_body(value: str) -> str:
    without_tags = re.sub(r"</?[A-Z][^>]*>", "", value)
    return "\n".join(
        line for raw_line in without_tags.splitlines() if (line := _clean_text(raw_line))
    )


def _first_markdown_heading(value: str) -> str:
    match = re.search(r"^#{2,6}\s+(.+?)\s*$", value, re.MULTILINE)
    return _clean_text(match.group(1)) if match else ""


def _chinese_date_utc(value: str) -> datetime | None:
    match = _CHINESE_DATE_PATTERN.search(_clean_text(value))
    if match is None:
        return None
    return datetime(
        int(match.group("year")),
        int(match.group("month")),
        int(match.group("day")),
        tzinfo=UTC,
    )


def _english_or_iso_date_utc(value: str) -> datetime | None:
    cleaned = _clean_text(value)
    for pattern in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(cleaned, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
        return parsed
    return None


def _date_utc(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _entry_id(occurred_at: datetime, title: str) -> str:
    slug = re.sub(r"[^a-z0-9.]+", "-", title.casefold()).strip("-")
    return f"{occurred_at.date().isoformat()}-{slug}" if slug else occurred_at.date().isoformat()


def _decode_next_data(content: str) -> str:
    decoded = content.replace('\\"', '"')
    for escaped, visible in {
        r"\u003c": "<",
        r"\u003e": ">",
        r"\u0026": "&",
        r"\u0027": "'",
    }.items():
        decoded = decoded.replace(escaped, visible)
    return decoded


def _decode_json_fragment(value: str) -> str:
    try:
        return _clean_text(json.loads(f'"{value}"'))
    except json.JSONDecodeError:
        return _clean_text(value)


def _clean_text(value: str) -> str:
    visible = unescape(value).translate(_INVISIBLE_TEXT_CHARS)
    return " ".join(visible.strip().split())
