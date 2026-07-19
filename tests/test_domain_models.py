from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shiyi import (
    CaptureConfig,
    ContentItem,
    Source,
    content_item_id,
)

NOW = datetime(2026, 7, 19, tzinfo=UTC)


def test_capture_config_requires_unique_source_ids() -> None:
    source = Source(id="x:openai", adapter="x", target="openai")

    with pytest.raises(ValidationError, match="source ids must be unique"):
        CaptureConfig(sources=(source, source))


def test_content_item_uses_optional_string_creators_without_creator_model() -> None:
    item = _content_item(creators=("OpenAI", "Sam Altman"))

    assert item.creators == ("OpenAI", "Sam Altman")
    assert ContentItem.model_validate(item.model_dump(mode="json")) == item


def test_missing_creators_do_not_block_readiness() -> None:
    item = _content_item(creators=())

    assert item.creators == ()
    assert item.ready_at == NOW


def test_content_item_id_is_stable_and_separates_sources() -> None:
    first = content_item_id(source_id="x:openai", source_item_id="42")

    assert first == content_item_id(source_id="x:openai", source_item_id="42")
    assert first != content_item_id(source_id="reddit:ai", source_item_id="42")


def _content_item(*, creators: tuple[str, ...]) -> ContentItem:
    return ContentItem(
        id=content_item_id(source_id="x:openai", source_item_id="42"),
        source_id="x:openai",
        source_item_id="42",
        kind="social_post",
        canonical_url="https://x.com/openai/status/42",
        title="A new model",
        creators=creators,
        published_at=NOW,
        collected_at=NOW,
        language="en",
        content="A new model\n",
        content_hash="a" * 64,
        ready_at=NOW,
        updated_at=NOW,
    )
