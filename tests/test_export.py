import asyncio
from datetime import UTC, datetime
from pathlib import Path

from shiyi.domain.models import (
    ArtifactWrite,
    HtmlPayload,
    InternalItem,
    Provenance,
    SourceIdentity,
    payload_content_hash,
)
from shiyi.export import export_items
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
    assert exported[0].source == {"kind": "blog", "uri": None, "account_id": None}
    assert exported[0].captured_at == "2026-05-12T10:00:00+00:00"
    assert exported[0].normalized_media_type == "text/markdown"
    assert exported[0].normalized_content is not None
    assert "# evt\\_1" in exported[0].normalized_content
    assert "third-party" not in exported[0].model_dump_json()


def test_export_items_returns_empty_when_workspace_has_no_records(tmp_path: Path) -> None:
    assert export_items(workspace=tmp_path) == []


def _html_payload(event: InternalItem) -> HtmlPayload:
    assert isinstance(event.payload, HtmlPayload)
    return event.payload


def _event(event_id: str, source_kind: str, captured_at: datetime) -> InternalItem:
    payload = HtmlPayload(html=f"<article><h1>{event_id}</h1><p>Hello</p></article>")
    return InternalItem(
        id=event_id,
        source=SourceIdentity(kind=source_kind),
        captured_at=captured_at,
        occurred_at=captured_at,
        payload=payload,
        content_hash=payload_content_hash(payload),
        provenance=Provenance(
            adapter_name="test-adapter",
            adapter_version="0.1.0",
            fetched_at=captured_at,
        ),
        idempotency_key=f"{source_kind}:{event_id}",
    )
