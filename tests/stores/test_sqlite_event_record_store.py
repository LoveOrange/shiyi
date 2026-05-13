import asyncio
import sqlite3
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
    assert found.source == event.source
    assert found.captured_at == event.captured_at
    assert found.content_hash == event.content_hash
    assert found.adapter_name == event.provenance.adapter_name
    assert found.adapter_version == event.provenance.adapter_version

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


def test_sqlite_event_record_store_adds_trace_columns_to_existing_events_table(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "event-records.sqlite"
    _create_legacy_events_table(database_path)

    store = SQLiteEventRecordStore(database_path)
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

    assert record.source == event.source
    assert found is not None
    assert found.source == event.source
    assert found.captured_at == event.captured_at
    assert found.content_hash == event.content_hash
    assert found.adapter_name == event.provenance.adapter_name
    assert found.adapter_version == event.provenance.adapter_version

    with sqlite3.connect(database_path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(events)")}

    assert {
        "source_json",
        "captured_at",
        "content_hash",
        "adapter_name",
        "adapter_version",
    }.issubset(columns)


def _create_legacy_events_table(database_path: Path) -> None:
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              event_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL UNIQUE,
              status TEXT NOT NULL,
              raw_artifact_json TEXT,
              normalized_artifact_json TEXT,
              last_error TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            """
        )


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
