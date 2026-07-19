"""Google DeepMind blog RSS + detail-page adapter."""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from hashlib import sha256
from html import escape
from urllib.parse import urljoin, urlparse, urlunparse

from selectolax.parser import HTMLParser, Node

from shiyi.domain.models import (
    CaptureWindow,
    HtmlPayload,
    Source,
    SourceItem,
)
from shiyi.fetchers.http import HttpRssFetcher, HttpWebFetcher
from shiyi.ports.fetcher import RssEntry, RssFetcher, WebFetcher

DEEPMIND_BLOG_RSS_URL = "https://deepmind.google/blog/rss.xml"
DEEPMIND_SOURCE_KIND = "deepmind-blog"
MIN_REDIRECTED_ARTICLE_CHARS = 500


@dataclass(frozen=True, slots=True)
class DeepMindArticle:
    """Canonical DeepMind article data after detail-page extraction."""

    slug: str
    title: str
    canonical_url: str
    html: str
    published_at: datetime | None = None
    modified_at: datetime | None = None
    author: str | None = None
    complete: bool = True


class DeepMindBlogAdapter:
    """Discovers DeepMind blog RSS entries, then emits canonical detail pages."""

    name = "deepmind-blog-detail"
    version = "0.1.0"

    def __init__(
        self,
        *,
        rss_fetcher: RssFetcher | None = None,
        web_fetcher: WebFetcher | None = None,
        limit: int | None = None,
        window: CaptureWindow | None = None,
    ) -> None:
        """Create a DeepMind blog adapter."""
        self._rss_fetcher = rss_fetcher or HttpRssFetcher(HttpWebFetcher())
        self._web_fetcher = web_fetcher or HttpWebFetcher()
        self._window = window or CaptureWindow(max_items=limit)

    async def capture(self, source: Source) -> AsyncIterator[SourceItem]:
        """Fetch RSS once, filter by capture window, then fetch matching article details."""
        feed = await self._rss_fetcher.fetch(source.target)
        emitted = 0
        for entry in feed.entries:
            if self._window.max_items is not None and emitted >= self._window.max_items:
                break
            occurred_at = entry.published_at or feed.fetched_at
            if not self._window.includes(occurred_at):
                continue
            detail_url = _require_detail_url(entry)
            detail_result = await self._web_fetcher.fetch(
                detail_url,
                source=DEEPMIND_SOURCE_KIND,
                raw_key=_entry_metadata_hash(source=DEEPMIND_SOURCE_KIND, url=detail_url),
            )
            article = _parse_article(
                detail_result.content,
                fallback_title=entry.title,
                fallback_url=detail_url,
            )
            payload = HtmlPayload(html=article.html, url=article.canonical_url)
            yield SourceItem(
                source_id=source.id,
                source_item_id=_article_id(article.canonical_url, fallback_url=detail_url),
                kind=_content_kind(source),
                canonical_url=article.canonical_url,
                collected_at=detail_result.fetched_at,
                published_at=article.published_at or occurred_at,
                summary=_rss_summary(entry),
                payload=payload,
                metadata=_metadata(article),
            )
            emitted += 1


def deepmind_blog_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    rss_fetcher: RssFetcher | None = None,
    web_fetcher: WebFetcher | None = None,
) -> DeepMindBlogAdapter:
    """Create the default Google DeepMind blog adapter."""
    return DeepMindBlogAdapter(
        limit=limit,
        window=window,
        rss_fetcher=rss_fetcher,
        web_fetcher=web_fetcher,
    )


def _require_detail_url(entry: RssEntry) -> str:
    if entry.link and entry.link.strip():
        return _canonicalize_url(entry.link)
    if entry.entry_id.strip().startswith("http"):
        return _canonicalize_url(entry.entry_id)
    msg = f"DeepMind RSS entry missing canonical detail URL: {entry.entry_id!r}"
    raise ValueError(msg)


def _parse_article(html: str, *, fallback_title: str, fallback_url: str) -> DeepMindArticle:
    parser = HTMLParser(html)
    json_ld = _blog_posting_json_ld(parser)
    canonical_url = _extract_canonical_url(
        parser=parser, json_ld=json_ld, fallback_url=fallback_url
    )
    extracted_title = _require_title(
        _string_value(json_ld.get("headline"))
        or _first_text(parser, "h1")
        or _title_without_suffix(_first_text(parser, "title"))
        or fallback_title,
        url=canonical_url,
    )
    main = parser.css_first("main#page-content") or parser.css_first("main")
    body_length = len(_clean_text(main.text(separator=" ", strip=True))) if main is not None else 0
    complete = (
        urlparse(canonical_url).netloc.casefold().endswith("deepmind.google")
        or body_length >= MIN_REDIRECTED_ARTICLE_CHARS
    )
    title = extracted_title if complete else _require_title(fallback_title, url=fallback_url)
    published_at = _parse_datetime(_string_value(json_ld.get("datePublished")))
    modified_at = _parse_datetime(_string_value(json_ld.get("dateModified")))
    author = _author_name(json_ld.get("author"))
    article_html = _article_scoped_html(
        parser=parser,
        title=title,
        canonical_url=canonical_url,
        published_at=published_at,
        author=author,
    )
    return DeepMindArticle(
        slug=_article_id(canonical_url),
        title=title,
        canonical_url=canonical_url,
        html=article_html,
        published_at=published_at,
        modified_at=modified_at,
        author=author,
        complete=complete,
    )


def _blog_posting_json_ld(parser: HTMLParser) -> Mapping[str, object]:
    for node in parser.css("script[type='application/ld+json']"):
        try:
            decoded = json.loads(node.text(strip=True))
        except json.JSONDecodeError:
            continue
        for candidate in _json_ld_candidates(decoded):
            if candidate.get("@type") == "BlogPosting":
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


def _extract_canonical_url(
    *, parser: HTMLParser, json_ld: Mapping[str, object], fallback_url: str
) -> str:
    main_entity = json_ld.get("mainEntityOfPage")
    if isinstance(main_entity, Mapping) and (url := _string_value(main_entity.get("url"))):
        return _canonicalize_url(url, base_url=fallback_url)
    for selector in ("link[rel='canonical']", "meta[property='og:url']"):
        node = parser.css_first(selector)
        if node is None:
            continue
        value = node.attributes.get("href") or node.attributes.get("content")
        if value:
            return _canonicalize_url(value, base_url=fallback_url)
    return _canonicalize_url(fallback_url)


def _article_scoped_html(
    *,
    parser: HTMLParser,
    title: str,
    canonical_url: str,
    published_at: datetime | None,
    author: str | None,
) -> str:
    fragments = _article_body_fragments(parser)
    if not fragments:
        fragments = [_main_fallback_html(parser)]
    header = [f"<h1>{escape(title)}</h1>"]
    if published_at is not None:
        published_value = published_at.date().isoformat()
        published_iso = escape(published_at.isoformat())
        header.append(
            f'<p>Published: <time datetime="{published_iso}">{published_value}</time></p>'
        )
    header.append(
        f'<p>Canonical link: <a href="{escape(canonical_url, quote=True)}">'
        f"{escape(canonical_url)}</a></p>"
    )
    if author:
        header.append(f"<p>Author: {escape(author)}</p>")
    return f"<article>{''.join(header)}{''.join(fragments)}</article>"


def _article_body_fragments(parser: HTMLParser) -> list[str]:
    main = parser.css_first("main#page-content") or parser.css_first("main")
    if main is None:
        return []
    fragments: list[str] = []
    for section in main.css("section"):
        class_name = section.attributes.get("class") or ""
        text = _clean_text(section.text(separator=" ", strip=True))
        if _is_skippable_section(class_name=class_name, text=text):
            continue
        _remove_noise_nodes(section)
        html = section.html
        if html and _clean_text(section.text(separator=" ", strip=True)):
            fragments.append(html)
    return fragments


def _main_fallback_html(parser: HTMLParser) -> str:
    main = (
        parser.css_first("main#page-content")
        or parser.css_first("main")
        or parser.css_first("body")
    )
    if main is None or main.html is None:
        return ""
    _remove_noise_nodes(main)
    return main.html


def _is_skippable_section(*, class_name: str, text: str) -> bool:
    normalized = text.casefold()
    return (
        "section-cover" in class_name
        or "related posts" in normalized
        or "card-blog" in class_name
        or normalized.startswith("explore our next generation ai systems")
    )


def _remove_noise_nodes(node: Node) -> None:
    for selector in (
        "script",
        "style",
        "noscript",
        "svg",
        "picture",
        "source",
        "img",
        "video",
        "button",
        "form",
        "nav",
        "aside",
        "[aria-label='Share']",
        ".share",
        ".social",
    ):
        for child in node.css(selector):
            child.decompose()


def _metadata(article: DeepMindArticle) -> dict[str, object]:
    metadata = {
        "title": article.title,
        "link": article.canonical_url,
        "is_complete": article.complete,
    }
    if article.author:
        metadata["author"] = article.author
    if article.modified_at:
        metadata["modified_at"] = article.modified_at.isoformat()
    return metadata


def _content_kind(source: Source) -> str:
    value = source.options.get("content_kind", "article")
    return value if isinstance(value, str) and value else "article"


def _first_text(parser: HTMLParser, selector: str) -> str:
    node = parser.css_first(selector)
    if node is None:
        return ""
    return _clean_text(node.text(separator=" ", strip=True))


def _title_without_suffix(value: str) -> str:
    return re.sub(r"\s+—\s+Google DeepMind\s*$", "", value).strip()


def _require_title(title: str, *, url: str) -> str:
    if title.strip():
        return _clean_text(title)
    msg = f"DeepMind article missing required title: {url}"
    raise ValueError(msg)


def _author_name(value: object) -> str | None:
    if isinstance(value, list):
        names = [_author_name(item) for item in value]
        return ", ".join(name for name in names if name) or None
    if isinstance(value, Mapping):
        return _string_value(value.get("name"))
    return _string_value(value)


def _string_value(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return _clean_text(value)
    return None


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            for fmt in ("%B %d, %Y", "%b %d, %Y"):
                try:
                    parsed = datetime.strptime(value, fmt).replace(tzinfo=UTC)
                except ValueError:
                    continue
                break
            else:
                return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _canonicalize_url(url: str, *, base_url: str | None = None) -> str:
    parsed = urlparse(urljoin(base_url or url, url))
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _article_id(url: str, *, fallback_url: str | None = None) -> str:
    path = urlparse(url).path.strip("/")
    slug = path.removeprefix("blog/").rstrip("/").split("/")[-1]
    if slug:
        return slug
    if fallback_url is not None:
        return _article_id(fallback_url)
    return sha256(url.encode()).hexdigest()[:16]


def _rss_summary(entry: RssEntry) -> str | None:
    if not entry.summary_html.strip():
        return None
    summary = _clean_text(HTMLParser(entry.summary_html).text(separator=" ", strip=True))
    if not summary or summary.casefold() == _clean_text(entry.title).casefold():
        return None
    return summary


def _entry_metadata_hash(*, source: str, url: str) -> str:
    """Adapter-defined raw cache key from entry-level metadata."""
    return sha256(f"{source}\n{url}".encode()).hexdigest()


def _clean_text(value: str) -> str:
    return " ".join(value.strip().split())
