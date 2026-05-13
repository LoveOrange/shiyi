from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from shiyi import InternalItem, Provenance, SourceIdentity, TextPayload


def test_internal_item_accepts_text_payload() -> None:
    event = InternalItem(
        id="evt_1",
        source=SourceIdentity(kind="rss"),
        occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
        payload=TextPayload(text="hello"),
        provenance=Provenance(
            adapter_name="rss-adapter",
            adapter_version="0.1.0",
            fetched_at=datetime(2026, 5, 12, tzinfo=UTC),
        ),
        idempotency_key="rss:evt_1",
    )

    assert event.payload.type == "text"
    assert event.idempotency_key == "rss:evt_1"


def test_internal_item_rejects_unknown_fields() -> None:
    payload: dict[str, Any] = {
        "id": "evt_1",
        "source": SourceIdentity(kind="rss"),
        "occurred_at": datetime(2026, 5, 12, tzinfo=UTC),
        "payload": TextPayload(text="hello"),
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
