import asyncio
from datetime import UTC, datetime
from pathlib import Path

from shiyi.domain.models import (
    ArtifactRef,
    EnrichmentResult,
    HtmlPayload,
    InternalItem,
    ModelIdentity,
    Provenance,
    SourceIdentity,
    payload_content_hash,
)
from shiyi.stores.sqlite import SQLiteEventRecordStore


def test_sqlite_event_record_store_saves_event_and_enrichment(tmp_path: Path) -> None:
    store = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    event = _event()
    artifact = _artifact()

    record = asyncio.run(
        store.save_event(
            event,
            raw_artifact=artifact,
            normalized_artifact=None,
        )
    )
    found = asyncio.run(store.find_by_idempotency_key(event.idempotency_key))

    assert record.status == "persisted"
    assert found is not None
    assert found.raw_artifact == artifact

    still_persisted = asyncio.run(
        store.save_enrichment(
            event,
            EnrichmentResult(
                task_type="summarize",
                output={"summary": "hello"},
                model=ModelIdentity(provider="fake", name="fake-model"),
            ),
            artifact,
        )
    )

    assert still_persisted.status == "persisted"

    enriched = asyncio.run(store.mark_enriched(event))

    assert enriched.status == "enriched"


def _event() -> InternalItem:
    payload = HtmlPayload(html="<article>hello</article>")
    return InternalItem(
        id="evt_1",
        source=SourceIdentity(kind="blog"),
        captured_at=datetime(2026, 5, 12, tzinfo=UTC),
        occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
        payload=payload,
        content_hash=payload_content_hash(payload),
        provenance=Provenance(
            adapter_name="test",
            adapter_version="0.1.0",
            fetched_at=datetime(2026, 5, 12, tzinfo=UTC),
        ),
        idempotency_key="blog:evt_1",
    )


def _artifact() -> ArtifactRef:
    return ArtifactRef(
        uri="raw/ab/abc",
        kind="raw",
        media_type="text/html",
        size_bytes=10,
        sha256="abc",
    )
