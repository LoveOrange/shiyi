from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from shiyi.domain.models import (
    HtmlPayload,
    InternalItem,
    Provenance,
    SourceIdentity,
    payload_content_hash,
)
from shiyi.export import ExportedItem


def test_internal_item_rejects_source_dto_fields_at_boundary() -> None:
    payload = HtmlPayload(html="<article><h1>Hello</h1></article>")
    item_data = {
        "id": "openai-news:item-1",
        "source": {"kind": "openai-news"},
        "captured_at": datetime(2026, 5, 13, tzinfo=UTC),
        "occurred_at": datetime(2026, 5, 12, tzinfo=UTC),
        "payload": payload,
        "content_hash": payload_content_hash(payload),
        "provenance": Provenance(
            adapter_name="openai-news-rss",
            adapter_version="0.2.0",
            fetched_at=datetime(2026, 5, 13, tzinfo=UTC),
            source_item_id="item-1",
        ),
        "idempotency_key": "openai-news:item-1",
        "rss_guid": "source DTO field must not cross the InternalItem boundary",
    }

    with pytest.raises(ValidationError):
        InternalItem.model_validate(item_data)


def test_idempotency_key_is_stable_replay_identity_not_dedupe_alias() -> None:
    first = _item(entry_id="running-codex-safely", title="Running Codex safely")
    replay = _item(entry_id="running-codex-safely", title="Running Codex safely")
    different = _item(entry_id="announcing-gpt-5", title="Announcing GPT-5")

    assert first.idempotency_key == replay.idempotency_key
    assert first.content_hash == replay.content_hash
    assert first.idempotency_key != different.idempotency_key
    assert "dedupe_key" not in first.model_dump(mode="json")


def test_internal_item_requires_trace_fields_for_pipeline_and_export_contract() -> None:
    with pytest.raises(ValidationError) as error_info:
        InternalItem.model_validate(
            {
                "id": "openai-news:item-1",
                "source": {"kind": "openai-news"},
                "captured_at": datetime(2026, 5, 13, tzinfo=UTC),
                "occurred_at": datetime(2026, 5, 12, tzinfo=UTC),
                "payload": {"type": "html", "html": "<p>Hello</p>"},
                "content_hash": "hash",
                "idempotency_key": "openai-news:item-1",
            }
        )

    assert "provenance" in str(error_info.value)


def test_internal_item_rejects_missing_required_source_fields_and_invalid_timestamps() -> None:
    valid = _item(entry_id="item-1", title="Hello").model_dump(mode="json")

    missing_source_kind = valid | {"source": {"uri": "https://openai.com/news/rss.xml"}}
    with pytest.raises(ValidationError) as missing_source_error:
        InternalItem.model_validate(missing_source_kind)

    invalid_timestamp = valid | {"captured_at": "not-a-timestamp"}
    with pytest.raises(ValidationError) as invalid_time_error:
        InternalItem.model_validate(invalid_timestamp)

    assert "source.kind" in str(missing_source_error.value)
    assert "captured_at" in str(invalid_time_error.value)


def test_export_contract_rejects_raw_or_source_specific_dto_fields() -> None:
    valid_export = {
        "event_id": "openai-news:item-1",
        "idempotency_key": "openai-news:item-1",
        "status": "persisted",
        "source": {"kind": "openai-news", "uri": "https://openai.com/news/rss.xml"},
        "captured_at": "2026-05-13T01:30:00+00:00",
        "content_hash": "hash",
        "adapter_name": "openai-news-rss",
        "adapter_version": "0.2.0",
        "normalized_content": "# Hello\n",
    }

    ExportedItem.model_validate(valid_export)

    with pytest.raises(ValidationError):
        ExportedItem.model_validate(valid_export | {"schema_version": "third-party-rss.v1"})

    with pytest.raises(ValidationError):
        ExportedItem.model_validate(valid_export | {"raw_payload": {"rss_guid": "item-1"}})

    with pytest.raises(ValidationError):
        ExportedItem.model_validate(
            valid_export
            | {
                "source": {
                    "kind": "openai-news",
                    "uri": "https://openai.com/news/rss.xml",
                    "rss_guid": "item-1",
                }
            }
        )


def _item(*, entry_id: str, title: str) -> InternalItem:
    payload = HtmlPayload(html=f"<article><h1>{title}</h1></article>")
    return InternalItem(
        id=f"openai-news:{entry_id}",
        source=SourceIdentity(kind="openai-news", uri="https://openai.com/news/rss.xml"),
        captured_at=datetime(2026, 5, 13, 1, 30, tzinfo=UTC),
        occurred_at=datetime(2026, 5, 8, 10, tzinfo=UTC),
        payload=payload,
        content_hash=payload_content_hash(payload),
        provenance=Provenance(
            adapter_name="openai-news-rss",
            adapter_version="0.2.0",
            fetched_at=datetime(2026, 5, 13, 1, 30, tzinfo=UTC),
            source_item_id=entry_id,
        ),
        idempotency_key=f"openai-news:{entry_id}",
        metadata={"title": title},
    )
