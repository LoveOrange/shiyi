"""Deterministic source payload to canonical Markdown processing."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from markdownify import markdownify as markdownify_html
from selectolax.parser import HTMLParser

from shiyi.domain.models import BlobRef, ContentItem, SourceItem, content_item_id

_PROMOTED_METADATA_FIELDS = frozenset(
    {
        "author",
        "authors",
        "creators",
        "is_complete",
        "language",
        "link",
        "source_metrics",
        "title",
    }
)


class MarkdownContentProcessor:
    """Builds one source-neutral ContentItem from a text-like SourceItem."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        """Create a processor with an injectable UTC clock for deterministic tests."""
        self._clock = clock or (lambda: datetime.now(UTC))

    async def process(
        self,
        item: SourceItem,
        *,
        raw_ref: BlobRef | None,
    ) -> ContentItem:
        """Normalize the payload and promote stable source-neutral fields."""
        content = _normalized_markdown(item)
        title = _title(item.metadata, content=content)
        now = self._clock()
        return ContentItem(
            id=content_item_id(source_id=item.source_id, source_item_id=item.source_item_id),
            source_id=item.source_id,
            source_item_id=item.source_item_id,
            kind=item.kind,
            canonical_url=item.canonical_url,
            title=title,
            creators=_creators(item.metadata),
            published_at=item.published_at,
            collected_at=item.collected_at,
            language=_optional_string(item.metadata.get("language")),
            content=content,
            summary=_optional_string(item.summary),
            categories=(),
            tags=(),
            metrics=_metrics(item.metadata.get("source_metrics")),
            raw_ref=raw_ref,
            content_hash=sha256(content.encode()).hexdigest(),
            extra={
                key: value
                for key, value in item.metadata.items()
                if key not in _PROMOTED_METADATA_FIELDS
            },
            ready_at=now if item.metadata.get("is_complete", True) is True else None,
            updated_at=now,
        )


def _normalized_markdown(item: SourceItem) -> str:
    if item.payload.type == "text":
        content = item.payload.text.strip()
    elif item.payload.type == "html":
        cleaned_html = _extract_main_html(item.payload.html)
        content = markdownify_html(cleaned_html, heading_style="ATX").strip()
        if not content:
            content = markdownify_html(item.payload.html, heading_style="ATX").strip()
    else:
        msg = f"binary SourceItem requires a dedicated ContentProcessor: {item.source_item_id}"
        raise ValueError(msg)
    if not content:
        msg = f"SourceItem produced empty canonical content: {item.source_item_id}"
        raise ValueError(msg)
    return f"{content}\n"


def _title(metadata: Mapping[str, Any], *, content: str) -> str:
    if title := _optional_string(metadata.get("title")):
        return title
    for line in content.splitlines():
        candidate = line.lstrip("# ").strip()
        if candidate:
            return candidate[:200]
    msg = "canonical content requires a title or non-empty first line"
    raise ValueError(msg)


def _creators(metadata: Mapping[str, Any]) -> tuple[str, ...]:
    values: list[str] = []
    for key in ("creators", "authors"):
        candidate = metadata.get(key)
        if isinstance(candidate, Iterable) and not isinstance(candidate, (str, bytes, Mapping)):
            values.extend(value.strip() for value in candidate if isinstance(value, str))
    if author := _optional_string(metadata.get("author")):
        values.append(author)
    return tuple(dict.fromkeys(value for value in values if value))


def _metrics(value: object) -> dict[str, int | float]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): metric
        for key, metric in value.items()
        if isinstance(metric, (int, float)) and not isinstance(metric, bool)
    }


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _extract_main_html(html: str) -> str:
    parser = HTMLParser(html)
    content_nodes = [*parser.css("article"), *parser.css("main")]
    if content_nodes:
        node = max(content_nodes, key=lambda candidate: len(candidate.text(strip=True)))
        if node.html is not None:
            return node.html
    body = parser.css_first("body")
    if body is not None and body.html is not None:
        return body.html
    return html
