import asyncio
import sqlite3
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from shiyi import (
    ArtifactRef,
    ArtifactWrite,
    CapturePipeline,
    HtmlMarkdownNormalizer,
    HtmlPayload,
    InternalItem,
    Provenance,
    SourceIdentity,
    payload_content_hash,
)
from shiyi.cli import _capture_summary
from shiyi.domain.models import EnrichmentResult, EnrichmentTask
from shiyi.ports.normalizer import Normalizer
from shiyi.stores.filesystem import FileSystemArtifactStore
from shiyi.stores.sqlite import SQLiteEventRecordStore


class StaticAdapter:
    name = "static-contract-adapter"
    version = "0.1.0"

    def __init__(self, events: Sequence[InternalItem]) -> None:
        self._events = tuple(events)

    async def discover(self) -> AsyncIterator[InternalItem]:
        for event in self._events:
            yield event


class NoopAIProvider:
    name = "noop-ai"

    async def run(self, _task: EnrichmentTask, _event: InternalItem) -> EnrichmentResult:
        msg = "P2-04 persistence contract tests do not configure enrichment tasks"
        raise AssertionError(msg)


class FailingNormalizer:
    name = "failing-normalizer"

    def __init__(self, failed_event_id: str) -> None:
        self._failed_event_id = failed_event_id
        self._delegate = HtmlMarkdownNormalizer()

    async def normalize(self, event: InternalItem) -> ArtifactWrite | None:
        if event.id == self._failed_event_id:
            msg = "invalid item payload for normalization"
            raise ValueError(msg)
        return await self._delegate.normalize(event)


def test_p2_04_writes_raw_normalized_event_record_and_skips_rerun(tmp_path: Path) -> None:
    event = _event("evt_1")
    pipeline = _pipeline(events=(event,), workspace=tmp_path)

    summary = asyncio.run(pipeline.run_once())
    row = _event_row(tmp_path, event.idempotency_key)
    raw_ref = ArtifactRef.model_validate_json(row["raw_artifact_json"])
    normalized_ref = ArtifactRef.model_validate_json(row["normalized_artifact_json"])

    expected_artifacts = 2

    assert summary.processed == 1
    assert summary.skipped == 0
    assert summary.failed == 0
    assert summary.artifacts == expected_artifacts
    assert row["status"] == "persisted"
    assert row["last_error"] is None
    assert row["source_json"] is not None
    assert row["content_hash"] == event.content_hash
    assert row["adapter_name"] == event.provenance.adapter_name
    assert isinstance(event.payload, HtmlPayload)
    assert (tmp_path / "artifacts" / raw_ref.uri).read_bytes() == event.payload.html.encode()
    normalized_content = (tmp_path / "artifacts" / normalized_ref.uri).read_text()

    assert normalized_ref.kind == "normalized"
    assert "contract body" in normalized_content

    rerun_summary = asyncio.run(pipeline.run_once())

    assert rerun_summary.processed == 0
    assert rerun_summary.skipped == 1
    assert _event_count(tmp_path) == 1


def test_p2_04_duplicate_items_inside_one_batch_are_skipped_by_idempotency_key(
    tmp_path: Path,
) -> None:
    event = _event("evt_1", idempotency_key="contract:duplicate")
    duplicate = _event(
        "evt_1_duplicate",
        idempotency_key="contract:duplicate",
        html="<article><h1>duplicate should not overwrite</h1></article>",
    )
    pipeline = _pipeline(events=(event, duplicate), workspace=tmp_path)

    summary = asyncio.run(pipeline.run_once())
    row = _event_row(tmp_path, event.idempotency_key)

    assert summary.processed == 1
    assert summary.skipped == 1
    assert summary.failed == 0
    assert _event_count(tmp_path) == 1
    assert row["event_id"] == "evt_1"
    assert row["content_hash"] == event.content_hash


def test_p2_04_invalid_item_failure_does_not_corrupt_processable_items(
    tmp_path: Path,
) -> None:
    good_before = _event("good_before")
    invalid = _event("invalid")
    good_after = _event("good_after")
    pipeline = _pipeline(
        events=(good_before, invalid, good_after),
        workspace=tmp_path,
        normalizer=FailingNormalizer(failed_event_id="invalid"),
    )

    summary = asyncio.run(pipeline.run_once())
    invalid_row = _event_row(tmp_path, invalid.idempotency_key)
    before_row = _event_row(tmp_path, good_before.idempotency_key)
    after_row = _event_row(tmp_path, good_after.idempotency_key)

    expected_processed = 2

    assert summary.processed == expected_processed
    assert summary.failed == 1
    assert len(summary.errors) == 1
    assert summary.errors[0].event_id == "invalid"
    assert summary.errors[0].stage == "normalization"
    assert before_row["status"] == "persisted"
    assert after_row["status"] == "persisted"
    assert invalid_row["status"] == "failed"
    assert invalid_row["raw_artifact_json"] is not None
    assert invalid_row["normalized_artifact_json"] is None
    assert "normalization failed" in invalid_row["last_error"]
    assert "contract/contract:invalid" in invalid_row["last_error"]
    assert "ValueError: invalid item payload" in invalid_row["last_error"]


def test_p2_04_failed_record_can_be_retried_by_same_idempotency_key(tmp_path: Path) -> None:
    failed_event = _event("old_failure", idempotency_key="contract:retry")
    recovered_event = _event("recovered", idempotency_key="contract:retry")
    records = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    asyncio.run(
        records.save_failure(
            failed_event,
            raw_artifact=None,
            normalized_artifact=None,
            error="previous normalization failure",
        )
    )
    pipeline = _pipeline(events=(recovered_event,), workspace=tmp_path)

    summary = asyncio.run(pipeline.run_once())
    row = _event_row(tmp_path, recovered_event.idempotency_key)

    assert summary.processed == 1
    assert summary.skipped == 0
    assert summary.failed == 0
    assert _event_count(tmp_path) == 1
    assert row["event_id"] == "recovered"
    assert row["status"] == "persisted"
    assert row["last_error"] is None
    assert row["content_hash"] == recovered_event.content_hash


def test_p2_04_capture_summary_exposes_counts_artifacts_and_errors(tmp_path: Path) -> None:
    good = _event("good")
    invalid = _event("invalid")
    pipeline = _pipeline(
        events=(good, good, invalid),
        workspace=tmp_path,
        normalizer=FailingNormalizer(failed_event_id="invalid"),
    )
    run_summary = asyncio.run(pipeline.run_once())

    capture_summary = _capture_summary(
        source="openai",
        workspace=tmp_path,
        run_summary=run_summary,
    )

    expected_artifacts = 3

    assert capture_summary.source == "openai"
    assert capture_summary.processed == 1
    assert capture_summary.skipped == 1
    assert capture_summary.failed == 1
    assert capture_summary.artifacts == expected_artifacts
    assert capture_summary.errors
    assert "normalization failed" in capture_summary.errors[0]


def _pipeline(
    *,
    events: Sequence[InternalItem],
    workspace: Path,
    normalizer: Normalizer | None = None,
) -> CapturePipeline:
    return CapturePipeline(
        adapter=StaticAdapter(events),
        ai_provider=NoopAIProvider(),
        artifact_store=FileSystemArtifactStore(workspace / "artifacts"),
        event_record_store=SQLiteEventRecordStore(workspace / "event-records.sqlite"),
        normalizer=normalizer or HtmlMarkdownNormalizer(),
        enrichment_tasks=[],
    )


def _event(
    event_id: str,
    *,
    idempotency_key: str | None = None,
    html: str | None = None,
) -> InternalItem:
    payload = HtmlPayload(
        html=html or f"<article><h1>{event_id}</h1><p>contract body</p></article>"
    )
    captured_at = datetime(2026, 5, 14, tzinfo=UTC) + timedelta(minutes=len(event_id))
    return InternalItem(
        id=event_id,
        source=SourceIdentity(kind="contract"),
        captured_at=captured_at,
        occurred_at=captured_at,
        payload=payload,
        content_hash=payload_content_hash(payload),
        provenance=Provenance(
            adapter_name="static-contract-adapter",
            adapter_version="0.1.0",
            fetched_at=captured_at,
            source_item_id=event_id,
        ),
        idempotency_key=idempotency_key or f"contract:{event_id}",
    )


def _event_row(tmp_path: Path, idempotency_key: str) -> sqlite3.Row:
    with sqlite3.connect(tmp_path / "event-records.sqlite") as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT event_id, idempotency_key, status, raw_artifact_json,
                   normalized_artifact_json, source_json, captured_at, content_hash,
                   adapter_name, adapter_version, last_error
            FROM events
            WHERE idempotency_key = ?
            """,
            (idempotency_key,),
        ).fetchone()
    assert row is not None
    return cast(sqlite3.Row, row)


def _event_count(tmp_path: Path) -> int:
    with sqlite3.connect(tmp_path / "event-records.sqlite") as connection:
        return int(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])
