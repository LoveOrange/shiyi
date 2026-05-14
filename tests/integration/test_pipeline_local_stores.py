import asyncio
import sqlite3
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from shiyi import (
    CapturePipeline,
    EnrichmentResult,
    HtmlPayload,
    InternalItem,
    ModelIdentity,
    Provenance,
    SourceIdentity,
    SummarizeTask,
    payload_content_hash,
)
from shiyi.domain.models import EnrichmentTask
from shiyi.normalizers.html import HtmlMarkdownNormalizer
from shiyi.stores.filesystem import FileSystemArtifactStore
from shiyi.stores.sqlite import SQLiteEventRecordStore


class SingleEventAdapter:
    name = "single-event"
    version = "0.1.0"

    async def discover(self) -> AsyncIterator[InternalItem]:
        payload = HtmlPayload(html="<article><h1>Hello</h1><p>World</p></article>")
        yield InternalItem(
            id="evt_1",
            source=SourceIdentity(kind="blog"),
            captured_at=datetime(2026, 5, 12, tzinfo=UTC),
            occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
            payload=payload,
            content_hash=payload_content_hash(payload),
            provenance=Provenance(
                adapter_name=self.name,
                adapter_version=self.version,
                fetched_at=datetime(2026, 5, 12, tzinfo=UTC),
            ),
            idempotency_key="blog:evt_1",
        )


class FakeAIProvider:
    name = "fake-ai"

    async def run(self, task: EnrichmentTask, event: InternalItem) -> EnrichmentResult:
        return EnrichmentResult(
            task_type=task.type,
            output={"event_id": event.id},
            model=ModelIdentity(provider=self.name, name="fake-model"),
        )


def test_pipeline_writes_raw_normalized_enrichment_and_sqlite_metadata(tmp_path: Path) -> None:
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    metadata = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    pipeline = CapturePipeline(
        adapter=SingleEventAdapter(),
        ai_provider=FakeAIProvider(),
        artifact_store=artifacts,
        event_record_store=metadata,
        normalizer=HtmlMarkdownNormalizer(),
        enrichment_tasks=[SummarizeTask(max_tokens=100)],
    )

    summary = asyncio.run(pipeline.run_once())

    assert summary.processed == 1
    assert summary.skipped == 0
    assert summary.failed == 0
    with sqlite3.connect(tmp_path / "event-records.sqlite") as connection:
        event_count = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        enrichment_count = connection.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0]
        row = connection.execute(
            """
            SELECT raw_artifact_json, normalized_artifact_json, status,
                   source_json, captured_at, content_hash, adapter_name, adapter_version,
                   idempotency_key
            FROM events
            """
        ).fetchone()

    assert event_count == 1
    assert enrichment_count == 1
    assert row[0] is not None
    assert row[1] is not None
    assert row[2] == "enriched"
    assert row[3] is not None
    assert row[4] == "2026-05-12T00:00:00+00:00"
    assert row[5] == payload_content_hash(
        HtmlPayload(html="<article><h1>Hello</h1><p>World</p></article>")
    )
    assert row[6] == "single-event"
    assert row[7] == "0.1.0"
    assert row[8] == "blog:evt_1"

    summary_again = asyncio.run(pipeline.run_once())

    assert summary_again.processed == 0
    assert summary_again.skipped == 1
