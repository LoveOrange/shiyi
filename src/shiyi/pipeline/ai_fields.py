"""Deterministic validation and merging of optional AI content fields."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from shiyi.domain.models import AIContentFields, ContentItem

MAX_LABELS = 32
MAX_LABEL_LENGTH = 100


def merge_ai_content_fields(
    *,
    item: ContentItem,
    fields: AIContentFields,
    updated_at: datetime,
) -> ContentItem:
    """Merge only allowed neutral fields without replacing source facts."""
    source_summary = _clean_optional(item.summary)
    update: dict[str, Any] = {
        "language": item.language or _clean_optional(fields.language),
        "summary": source_summary or _clean_optional(fields.summary),
        "summary_language": (
            item.summary_language
            if source_summary is not None
            else _clean_optional(fields.summary_language) or item.summary_language
        ),
        "categories": _labels(fields.categories) or item.categories,
        "tags": _labels(fields.tags) or item.tags,
        "updated_at": updated_at,
    }
    return ContentItem.model_validate({**item.model_dump(mode="python"), **update})


def _labels(values: Sequence[str]) -> tuple[str, ...]:
    cleaned = (
        value.strip()
        for value in values[:MAX_LABELS]
        if value.strip() and len(value.strip()) <= MAX_LABEL_LENGTH
    )
    return tuple(dict.fromkeys(cleaned))


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
