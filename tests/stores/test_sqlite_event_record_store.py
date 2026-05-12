import asyncio
from datetime import UTC, datetime
from pathlib import Path

from shiyi.domain.models import (
    ArtifactRef,
    CaptureEvent,
    EnrichmentResult,
    HtmlPayload,
    ModelIdentity,
    Provenance,
    SourceIdentity,
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

    enriched = asyncio.run(
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

    assert enriched.status == "enriched"


def _event() -> CaptureEvent:
    return CaptureEvent(
        id="evt_1",
        source=SourceIdentity(kind="blog"),
        occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
        payload=HtmlPayload(html="<article>hello</article>"),
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
