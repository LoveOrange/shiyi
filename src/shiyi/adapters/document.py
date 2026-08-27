"""Direct capture for one configured HTML, Markdown, or PDF document."""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from urllib.parse import urljoin, urlsplit, urlunsplit

from pypdf import PdfReader
from selectolax.parser import HTMLParser

from shiyi.domain.models import CaptureWindow, HtmlPayload, Source, SourceItem, TextPayload
from shiyi.fetchers.http import HttpWebFetcher
from shiyi.ports.fetcher import FetchResult, WebFetcher

DIRECT_DOCUMENT_ADAPTER = "direct-document"
DOCUMENT_FORMATS = frozenset({"html", "markdown", "pdf"})
OPENAI_GPT_LIVE_ENGINEERING_URL = (
    "https://openai.com/index/continuous-voice-interaction-with-gpt-live/"
)
OPENAI_GPT_LIVE_LAUNCH_URL = "https://openai.com/index/introducing-gpt-live/"
OPENAI_CONTENT_VERIFICATION_URL = "https://openai.com/research/verify/"
OPENAI_GPT_LIVE_SYSTEM_CARD_URL = "https://deploymentsafety.openai.com/gpt-live/gpt-live.pdf"
OPENAI_CONTENT_PROVENANCE_URL = "https://developers.openai.com/api/docs/guides/content-provenance"
DEEPMIND_SYNTHID_URL = "https://deepmind.google/models/synthid/"


class DirectDocumentAdapter:
    """Fetch exactly one declared public document and preserve its canonical identity."""

    name = DIRECT_DOCUMENT_ADAPTER
    version = "0.1.0"

    def __init__(
        self,
        *,
        web_fetcher: WebFetcher | None = None,
        window: CaptureWindow | None = None,
    ) -> None:
        """Create a direct-document adapter."""
        self._web_fetcher = web_fetcher or HttpWebFetcher()
        self._window = window or CaptureWindow()

    async def capture(self, source: Source) -> AsyncIterator[SourceItem]:
        """Fetch the configured target once and emit one complete source item."""
        result = await self._web_fetcher.fetch(
            source.target,
            source=source.id,
            raw_key=sha256(source.target.encode()).hexdigest(),
        )
        document_format = _document_format(source)
        _validate_content_type(result, document_format=document_format)

        if document_format == "html":
            canonical_url = _configured_canonical_url(source) or _html_canonical_url(
                result.content,
                fallback_url=str(result.url),
            )
            title = _html_title(source, result.content, url=canonical_url)
            published_at = _published_at(source) or _html_published_at(result.content)
            payload: HtmlPayload | TextPayload = HtmlPayload(
                html=result.content,
                url=canonical_url,
            )
            summary = _html_meta_content(result.content, "description")
            metadata = _html_metadata(source, result.content, title=title)
            raw_content = None
            raw_media_type = None
        elif document_format == "markdown":
            canonical_url = _canonicalize_url(str(result.url))
            title = _configured_title(source) or _markdown_title(result.content, url=canonical_url)
            published_at = _published_at(source)
            payload = TextPayload(text=result.content, content_type="text/markdown")
            summary = None
            metadata = _base_metadata(source, title=title)
            raw_content = None
            raw_media_type = None
        else:
            canonical_url = _canonicalize_url(str(result.url))
            published_at = _published_at(source)
            title, markdown = _pdf_markdown(
                result,
                configured_title=_configured_title(source),
                canonical_url=canonical_url,
            )
            payload = TextPayload(text=markdown, content_type="text/markdown")
            summary = None
            metadata = _base_metadata(source, title=title)
            raw_content = _required_body(result, url=canonical_url)
            raw_media_type = "application/pdf"

        if not self._window.includes(published_at):
            return
        yield SourceItem(
            source_id=source.id,
            source_item_id=canonical_url,
            kind=_content_kind(source),
            canonical_url=canonical_url,
            collected_at=result.fetched_at,
            published_at=published_at,
            summary=summary,
            payload=payload,
            raw_content=raw_content,
            raw_media_type=raw_media_type,
            metadata=metadata,
        )


def direct_document_adapter(
    *,
    web_fetcher: WebFetcher | None = None,
    window: CaptureWindow | None = None,
) -> DirectDocumentAdapter:
    """Create the shared direct-document adapter."""
    return DirectDocumentAdapter(web_fetcher=web_fetcher, window=window)


def _document_format(source: Source) -> str:
    value = source.options.get("document_format", "html")
    if not isinstance(value, str) or value not in DOCUMENT_FORMATS:
        msg = f"Source {source.id!r} document_format must be one of {sorted(DOCUMENT_FORMATS)}"
        raise ValueError(msg)
    return value


def _content_kind(source: Source) -> str:
    value = source.options.get("content_kind", "document")
    if not isinstance(value, str) or not value.strip():
        msg = f"Source {source.id!r} content_kind must be a non-empty string"
        raise ValueError(msg)
    return value.strip()


def _configured_title(source: Source) -> str | None:
    return _optional_source_text(source, "title")


def _configured_canonical_url(source: Source) -> str | None:
    value = _optional_source_text(source, "canonical_url")
    return _canonicalize_url(value) if value is not None else None


def _published_at(source: Source) -> datetime | None:
    value = _optional_source_text(source, "published_at")
    if value is None:
        return None
    return _parse_datetime(value, context=f"Source {source.id!r} published_at")


def _optional_source_text(source: Source, key: str) -> str | None:
    value = source.options.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        msg = f"Source {source.id!r} option {key!r} must be a non-empty string"
        raise ValueError(msg)
    return value.strip()


def _base_metadata(source: Source, *, title: str) -> dict[str, object]:
    metadata: dict[str, object] = {"title": title, "is_complete": True}
    if language := _optional_source_text(source, "language"):
        metadata["language"] = language
    return metadata


def _html_metadata(source: Source, html: str, *, title: str) -> dict[str, object]:
    metadata = _base_metadata(source, title=title)
    if language := _html_language(html):
        metadata.setdefault("language", language)
    if author := _html_meta_content(html, "author"):
        metadata["author"] = author
    return metadata


def _html_title(source: Source, html: str, *, url: str) -> str:
    if configured := _configured_title(source):
        return configured
    parser = HTMLParser(html)
    for selector, attribute in (
        ("meta[property='og:title']", "content"),
        ("meta[name='twitter:title']", "content"),
    ):
        node = parser.css_first(selector)
        if node is not None and (title := _clean_text(node.attributes.get(attribute))):
            return title
    for selector in ("main h1", "article h1", "h1", "title"):
        node = parser.css_first(selector)
        if node is not None and (title := _clean_text(node.text(separator=" ", strip=True))):
            return title
    msg = f"direct HTML document has no usable title: {url}"
    raise ValueError(msg)


def _markdown_title(markdown: str, *, url: str) -> str:
    for line in markdown.splitlines():
        title = line.lstrip("# ").strip()
        if title:
            return title[:200]
    msg = f"direct Markdown document has no usable title: {url}"
    raise ValueError(msg)


def _html_canonical_url(html: str, *, fallback_url: str) -> str:
    parser = HTMLParser(html)
    node = parser.css_first("link[rel='canonical']")
    href = node.attributes.get("href") if node is not None else None
    return _canonicalize_url(urljoin(fallback_url, href) if href else fallback_url)


def _html_published_at(html: str) -> datetime | None:
    parser = HTMLParser(html)
    for selector, attribute in (
        ("meta[property='article:published_time']", "content"),
        ("meta[name='date']", "content"),
        ("time[datetime]", "datetime"),
    ):
        node = parser.css_first(selector)
        if node is None:
            continue
        value = _clean_text(node.attributes.get(attribute))
        if value is not None:
            return _parse_datetime(value, context="HTML published time")
    return None


def _html_meta_content(html: str, name: str) -> str | None:
    parser = HTMLParser(html)
    for selector in (f"meta[name='{name}']", f"meta[property='og:{name}']"):
        node = parser.css_first(selector)
        if node is not None and (value := _clean_text(node.attributes.get("content"))):
            return value
    return None


def _html_language(html: str) -> str | None:
    parser = HTMLParser(html)
    node = parser.css_first("html[lang]")
    return _clean_text(node.attributes.get("lang")) if node is not None else None


def _pdf_markdown(
    result: FetchResult,
    *,
    configured_title: str | None,
    canonical_url: str,
) -> tuple[str, str]:
    body = _required_body(result, url=canonical_url)
    reader = PdfReader(BytesIO(body))
    if reader.is_encrypted and reader.decrypt("") == 0:
        msg = f"direct PDF document is encrypted: {canonical_url}"
        raise ValueError(msg)
    page_text = tuple(
        text for page in reader.pages if (text := (page.extract_text() or "").strip())
    )
    if not page_text:
        msg = f"direct PDF document has no extractable text: {canonical_url}"
        raise ValueError(msg)
    metadata_title = reader.metadata.title if reader.metadata is not None else None
    title = configured_title or _clean_text(metadata_title) or _first_text_line(page_text[0])
    if title is None:
        msg = f"direct PDF document has no usable title: {canonical_url}"
        raise ValueError(msg)
    content = "\n\n---\n\n".join(page_text)
    markdown = f"# {title}\n\nSource: [{canonical_url}]({canonical_url})\n\n{content}\n"
    return title, markdown


def _required_body(result: FetchResult, *, url: str) -> bytes:
    if result.body:
        return result.body
    msg = f"direct PDF fetch did not preserve response bytes: {url}"
    raise ValueError(msg)


def _validate_content_type(result: FetchResult, *, document_format: str) -> None:
    if result.content_type is None:
        return
    media_type = result.content_type.partition(";")[0].strip().casefold()
    allowed = {
        "html": {"text/html", "application/xhtml+xml"},
        "markdown": {"text/markdown", "text/plain"},
        "pdf": {"application/pdf"},
    }[document_format]
    if media_type not in allowed:
        msg = f"expected {document_format} document, received {media_type or '<missing>'}"
        raise ValueError(msg)


def _parse_datetime(value: str, *, context: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        msg = f"{context} must be an ISO date/time"
        raise ValueError(msg) from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _canonicalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme.casefold() not in {"http", "https"} or not parsed.netloc:
        msg = f"direct document canonical URL must be absolute HTTP(S): {value!r}"
        raise ValueError(msg)
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((parsed.scheme.casefold(), parsed.netloc.casefold(), path, parsed.query, ""))


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def _first_text_line(value: str) -> str | None:
    for line in value.splitlines():
        if cleaned := _clean_text(line):
            return cleaned[:200]
    return None
