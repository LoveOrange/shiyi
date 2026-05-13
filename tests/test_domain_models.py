from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from shiyi import (
    BinaryPayload,
    InternalItem,
    Provenance,
    SourceIdentity,
    TextPayload,
    payload_content_hash,
)


def test_internal_item_accepts_text_payload() -> None:
    payload = TextPayload(text="hello")
    event = InternalItem(
        id="evt_1",
        source=SourceIdentity(kind="rss"),
        captured_at=datetime(2026, 5, 12, tzinfo=UTC),
        occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
        payload=payload,
        content_hash=payload_content_hash(payload),
        provenance=Provenance(
            adapter_name="rss-adapter",
            adapter_version="0.1.0",
            fetched_at=datetime(2026, 5, 12, tzinfo=UTC),
        ),
        idempotency_key="rss:evt_1",
    )

    assert event.schema_version == "internal-item.v1"
    assert event.payload.type == "text"
    assert event.content_hash == payload_content_hash(payload)
    assert event.idempotency_key == "rss:evt_1"


def test_payload_content_hash_covers_binary_references() -> None:
    payload = BinaryPayload(media_type="application/pdf", bytes_ref="artifact://doc.pdf")

    assert payload_content_hash(payload) == payload_content_hash(payload)


def test_internal_item_rejects_unknown_fields() -> None:
    payload: dict[str, Any] = {
        "id": "evt_1",
        "source": SourceIdentity(kind="rss"),
        "captured_at": datetime(2026, 5, 12, tzinfo=UTC),
        "occurred_at": datetime(2026, 5, 12, tzinfo=UTC),
        "payload": TextPayload(text="hello"),
        "content_hash": payload_content_hash(TextPayload(text="hello")),
        "provenance": Provenance(
            adapter_name="rss-adapter",
            adapter_version="0.1.0",
            fetched_at=datetime(2026, 5, 12, tzinfo=UTC),
        ),
        "idempotency_key": "rss:evt_1",
        "unexpected": True,
    }

    with pytest.raises(ValidationError):
        InternalItem.model_validate(payload)
