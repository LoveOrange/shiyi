import asyncio
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from shiyi.domain.models import (
    ArtifactWrite,
    HtmlPayload,
    InternalItem,
    Provenance,
    SourceIdentity,
    payload_content_hash,
)
from shiyi.export import ExportedItem, export_items
from shiyi.normalizers.html import HtmlMarkdownNormalizer
from shiyi.stores.filesystem import FileSystemArtifactStore
from shiyi.stores.sqlite import SQLiteEventRecordStore


def test_export_items_reads_normalized_content_by_time_and_source(tmp_path: Path) -> None:
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    records = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    blog_event = _event("evt_1", "blog", datetime(2026, 5, 12, 10, tzinfo=UTC))
    rss_event = _event("evt_2", "rss", datetime(2026, 5, 11, 10, tzinfo=UTC))
    normalizer = HtmlMarkdownNormalizer()

    async def arrange() -> None:
        for event in (blog_event, rss_event):
            raw_ref = await artifacts.put(
                ArtifactWrite(
                    kind="raw",
                    media_type="text/html",
                    content=_html_payload(event).html.encode(),
                )
            )
            normalized = await normalizer.normalize(event)
            assert normalized is not None
            normalized_ref = await artifacts.put(normalized)
            await records.save_event(
                event,
                raw_artifact=raw_ref,
                normalized_artifact=normalized_ref,
            )

    asyncio.run(arrange())

    exported = export_items(
        workspace=tmp_path,
        since=datetime(2026, 5, 12, tzinfo=UTC),
        until=datetime(2026, 5, 13, tzinfo=UTC),
        sources=("blog",),
        limit=10,
    )

    assert len(exported) == 1
    assert exported[0].event_id == "evt_1"
    assert exported[0].source == SourceIdentity(kind="blog")
    assert exported[0].captured_at == "2026-05-12T10:00:00+00:00"
    assert exported[0].occurred_at == "2026-05-12T10:00:00+00:00"
    assert exported[0].published_at == "2026-05-12T10:00:00+00:00"
    assert exported[0].source_category is None
    assert exported[0].source_type == "unknown"
    assert exported[0].source_metrics == {}
    assert exported[0].normalized_media_type == "text/markdown"
    assert exported[0].normalized_content is not None
    assert "# evt\\_1" in exported[0].normalized_content
    payload = exported[0].model_dump(mode="json")
    assert set(payload) == {
        "adapter_name",
        "adapter_version",
        "captured_at",
        "content_completeness",
        "content_depth",
        "content_hash",
        "event_id",
        "idempotency_key",
        "occurred_at",
        "published_at",
        "canonical_discussion_url",
        "external_target_url",
        "normalized_artifact_uri",
        "normalized_content",
        "normalized_media_type",
        "schema_version",
        "source",
        "source_category",
        "source_metrics",
        "source_type",
        "source_ready",
        "status",
        "upstream_id",
        "upstream_parent_id",
    }
    assert "third-party" not in exported[0].model_dump_json()
    assert "raw_payload" not in exported[0].model_dump_json()
    assert "rss_guid" not in exported[0].model_dump_json()


def test_export_items_exposes_occurred_at_separately_from_captured_at(tmp_path: Path) -> None:
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    records = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    event = _event(
        "evt_article_date",
        "blog",
        datetime(2026, 5, 14, 8, 30, tzinfo=UTC),
        occurred_at=datetime(2026, 4, 29, 12, tzinfo=UTC),
    )
    asyncio.run(_save_event(artifacts=artifacts, records=records, event=event, normalized=True))

    exported = export_items(workspace=tmp_path, sources=("blog",), limit=10)

    assert exported[0].captured_at == "2026-05-14T08:30:00+00:00"
    assert exported[0].occurred_at == "2026-04-29T12:00:00+00:00"
    assert exported[0].published_at == "2026-04-29T12:00:00+00:00"


def test_export_items_uses_half_open_window_source_filter_and_stable_ordering(
    tmp_path: Path,
) -> None:
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    records = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    events = (
        _event("evt_until_boundary", "blog", datetime(2026, 5, 13, tzinfo=UTC)),
        _event("evt_same_time_b", "blog", datetime(2026, 5, 12, 12, tzinfo=UTC)),
        _event("evt_other_source", "rss", datetime(2026, 5, 12, 13, tzinfo=UTC)),
        _event("evt_same_time_a", "blog", datetime(2026, 5, 12, 12, tzinfo=UTC)),
        _event("evt_since_boundary", "blog", datetime(2026, 5, 12, tzinfo=UTC)),
        _event("evt_before_window", "blog", datetime(2026, 5, 11, 23, 59, tzinfo=UTC)),
    )

    async def arrange() -> None:
        for event in events:
            await _save_event(
                artifacts=artifacts,
                records=records,
                event=event,
                normalized=True,
            )

    asyncio.run(arrange())

    exported = export_items(
        workspace=tmp_path,
        since=datetime(2026, 5, 12, tzinfo=UTC),
        until=datetime(2026, 5, 13, tzinfo=UTC),
        sources=("blog",),
        limit=10,
    )

    assert [item.event_id for item in exported] == [
        "evt_same_time_a",
        "evt_same_time_b",
        "evt_since_boundary",
    ]


def test_export_items_normalizes_non_utc_captured_at_before_window_filtering(
    tmp_path: Path,
) -> None:
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    records = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    utc_plus_8 = timezone(timedelta(hours=8))
    outside_window = _event(
        "evt_offset_before_utc_window",
        "blog",
        datetime(2026, 5, 12, 0, 30, tzinfo=utc_plus_8),
    )
    inside_window = _event(
        "evt_offset_inside_utc_window",
        "blog",
        datetime(2026, 5, 12, 8, 15, tzinfo=utc_plus_8),
    )

    async def arrange() -> None:
        for event in (outside_window, inside_window):
            await _save_event(
                artifacts=artifacts,
                records=records,
                event=event,
                normalized=True,
            )

    asyncio.run(arrange())

    exported = export_items(
        workspace=tmp_path,
        since=datetime(2026, 5, 12, tzinfo=UTC),
        until=datetime(2026, 5, 13, tzinfo=UTC),
        sources=("blog",),
        limit=10,
    )

    assert [item.event_id for item in exported] == ["evt_offset_inside_utc_window"]
    assert exported[0].captured_at == "2026-05-12T00:15:00+00:00"


def test_export_items_exposes_content_depth_and_can_filter_source_ready_records(
    tmp_path: Path,
) -> None:
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    records = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    events = (
        _event(
            "evt_complete",
            "blog",
            datetime(2026, 5, 12, 12, tzinfo=UTC),
            content_depth="complete",
        ),
        _event(
            "evt_summary",
            "blog",
            datetime(2026, 5, 12, 10, tzinfo=UTC),
            content_depth="summary_only",
        ),
        _event(
            "evt_partial",
            "blog",
            datetime(2026, 5, 12, 9, tzinfo=UTC),
            content_depth="partial",
        ),
    )

    async def arrange() -> None:
        for event in events:
            await _save_event(
                artifacts=artifacts,
                records=records,
                event=event,
                normalized=True,
            )

    asyncio.run(arrange())

    exported = export_items(workspace=tmp_path, sources=("blog",), limit=10)
    depth_by_id = {item.event_id: item.content_depth for item in exported}
    completeness_by_id = {item.event_id: item.content_completeness for item in exported}
    source_ready_by_id = {item.event_id: item.source_ready for item in exported}
    source_ready_only = export_items(
        workspace=tmp_path,
        sources=("blog",),
        limit=10,
        source_ready_only=True,
    )

    assert depth_by_id == {
        "evt_complete": "complete",
        "evt_summary": "summary_only",
        "evt_partial": "partial",
    }
    assert completeness_by_id == {
        "evt_complete": "complete",
        "evt_summary": "summary_only",
        "evt_partial": "partial",
    }
    assert source_ready_by_id == {
        "evt_complete": True,
        "evt_summary": False,
        "evt_partial": False,
    }
    assert [item.event_id for item in source_ready_only] == ["evt_complete"]


def test_export_items_adds_source_taxonomy_from_builtin_registry(tmp_path: Path) -> None:
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    records = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    event = _event(
        "evt_copilot",
        "github-copilot-changelog",
        datetime(2026, 5, 12, 10, tzinfo=UTC),
        content_depth="complete",
    )
    asyncio.run(_save_event(artifacts=artifacts, records=records, event=event, normalized=True))

    [item] = export_items(workspace=tmp_path, sources=("github-copilot-changelog",), limit=10)

    assert item.source_category == "official"
    assert item.source_type == "changelog"
    assert item.model_dump(mode="json")["source_category"] == "official"
    assert item.model_dump(mode="json")["source_type"] == "changelog"


def test_export_items_exposes_high_noise_source_metadata(tmp_path: Path) -> None:
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    records = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    event = _event(
        "hacker-news:44123456",
        "hacker-news",
        datetime(2026, 5, 14, 8, 30, tzinfo=UTC),
        content_depth="complete",
        occurred_at=datetime(2026, 5, 13, 15, 20, tzinfo=UTC),
        metadata={
            "upstream_id": "44123456",
            "canonical_discussion_url": "https://news.ycombinator.com/item?id=44123456",
            "external_target_url": "https://example.com/agentic-code-review-traces",
            "source_metrics": {"score": 512, "descendants": 128, "rank": 1},
        },
    )
    asyncio.run(_save_event(artifacts=artifacts, records=records, event=event, normalized=True))

    [item] = export_items(workspace=tmp_path, sources=("hacker-news",), limit=10)

    assert item.source_category == "community"
    assert item.source_type == "unknown"
    assert item.upstream_id == "44123456"
    assert item.canonical_discussion_url == "https://news.ycombinator.com/item?id=44123456"
    assert item.external_target_url == "https://example.com/agentic-code-review-traces"
    assert item.source_metrics == {"score": 512, "descendants": 128, "rank": 1}
    assert item.source_ready is True


def test_exported_item_derives_readiness_from_content_depth() -> None:
    item = ExportedItem(
        event_id="evt_1",
        idempotency_key="blog:evt_1",
        status="persisted",
        source=SourceIdentity(kind="blog"),
        captured_at="2026-05-12T00:00:00+00:00",
        content_hash="abc",
        adapter_name="test",
        adapter_version="0.1.0",
        content_depth="complete",
        normalized_content="# Hello\n",
    )

    assert item.content_completeness == "complete"
    assert item.source_ready is True
    with pytest.raises(ValidationError, match="content_completeness must be derived"):
        ExportedItem(
            event_id="evt_bad_completeness",
            idempotency_key="blog:evt_bad_completeness",
            status="persisted",
            source=SourceIdentity(kind="blog"),
            captured_at="2026-05-12T00:00:00+00:00",
            content_hash="abc",
            adapter_name="test",
            adapter_version="0.1.0",
            content_depth="complete",
            content_completeness="summary_only",
            normalized_content="# Hello\n",
        )
    with pytest.raises(ValidationError, match="source_ready must be derived"):
        ExportedItem(
            event_id="evt_bad_ready",
            idempotency_key="blog:evt_bad_ready",
            status="persisted",
            source=SourceIdentity(kind="blog"),
            captured_at="2026-05-12T00:00:00+00:00",
            content_hash="abc",
            adapter_name="test",
            adapter_version="0.1.0",
            content_depth="summary_only",
            source_ready=True,
            normalized_content="# Hello\n",
        )


def test_export_items_returns_stable_empty_result_when_filters_match_no_rows(
    tmp_path: Path,
) -> None:
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    records = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    event = _event("evt_1", "blog", datetime(2026, 5, 12, 10, tzinfo=UTC))
    asyncio.run(_save_event(artifacts=artifacts, records=records, event=event, normalized=True))

    assert (
        export_items(
            workspace=tmp_path,
            since=datetime(2026, 5, 13, tzinfo=UTC),
            until=datetime(2026, 5, 14, tzinfo=UTC),
            sources=("blog",),
            limit=10,
        )
        == []
    )
    assert export_items(workspace=tmp_path, sources=("rss",), limit=10) == []


def test_export_items_returns_empty_when_workspace_has_no_records(tmp_path: Path) -> None:
    assert export_items(workspace=tmp_path) == []


def test_export_items_returns_empty_for_non_positive_limit(tmp_path: Path) -> None:
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    records = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    event = _event("evt_1", "blog", datetime(2026, 5, 12, 10, tzinfo=UTC))
    asyncio.run(_save_event(artifacts=artifacts, records=records, event=event, normalized=True))

    assert export_items(workspace=tmp_path, limit=0) == []
    assert export_items(workspace=tmp_path, limit=-1) == []


def test_export_items_skips_events_without_normalized_artifact(tmp_path: Path) -> None:
    artifacts = FileSystemArtifactStore(tmp_path / "artifacts")
    records = SQLiteEventRecordStore(tmp_path / "event-records.sqlite")
    normalized_event = _event("evt_1", "blog", datetime(2026, 5, 12, 10, tzinfo=UTC))
    raw_only_event = _event("evt_2", "blog", datetime(2026, 5, 12, 11, tzinfo=UTC))

    async def arrange() -> None:
        await _save_event(
            artifacts=artifacts,
            records=records,
            event=normalized_event,
            normalized=True,
        )
        await _save_event(
            artifacts=artifacts,
            records=records,
            event=raw_only_event,
            normalized=False,
        )

    asyncio.run(arrange())

    exported = export_items(workspace=tmp_path, limit=10)

    assert [item.event_id for item in exported] == ["evt_1"]
    assert exported[0].normalized_content is not None


async def _save_event(
    *,
    artifacts: FileSystemArtifactStore,
    records: SQLiteEventRecordStore,
    event: InternalItem,
    normalized: bool,
) -> None:
    raw_ref = await artifacts.put(
        ArtifactWrite(
            kind="raw",
            media_type="text/html",
            content=_html_payload(event).html.encode(),
        )
    )
    normalized_ref = None
    if normalized:
        normalized_artifact = await HtmlMarkdownNormalizer().normalize(event)
        assert normalized_artifact is not None
        normalized_ref = await artifacts.put(normalized_artifact)
    await records.save_event(
        event,
        raw_artifact=raw_ref,
        normalized_artifact=normalized_ref,
    )


def _html_payload(event: InternalItem) -> HtmlPayload:
    assert isinstance(event.payload, HtmlPayload)
    return event.payload


def _event(  # noqa: PLR0913
    event_id: str,
    source_kind: str,
    captured_at: datetime,
    *,
    content_depth: str | None = None,
    occurred_at: datetime | None = None,
    metadata: dict[str, object] | None = None,
) -> InternalItem:
    payload = HtmlPayload(html=f"<article><h1>{event_id}</h1><p>Hello</p></article>")
    event_metadata = dict(metadata or {})
    if content_depth is not None:
        event_metadata["content_depth"] = content_depth
    return InternalItem(
        id=event_id,
        source=SourceIdentity(kind=source_kind),
        captured_at=captured_at,
        occurred_at=occurred_at or captured_at,
        payload=payload,
        content_hash=payload_content_hash(payload),
        provenance=Provenance(
            adapter_name="test-adapter",
            adapter_version="0.1.0",
            fetched_at=captured_at,
        ),
        idempotency_key=f"{source_kind}:{event_id}",
        metadata=event_metadata,
    )
