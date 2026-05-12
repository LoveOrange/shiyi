import asyncio
import hashlib
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from shiyi import (
    AIProvider,
    ArtifactRead,
    ArtifactRef,
    ArtifactStore,
    ArtifactWrite,
    CaptureEvent,
    CapturePipeline,
    EnrichmentResult,
    EventRecord,
    EventRecordStore,
    HtmlPayload,
    ModelIdentity,
    Provenance,
    SourceIdentity,
    SummarizeTask,
)
from shiyi.domain.models import EnrichmentTask


class FakeAdapter:
    name = "fake"
    version = "0.1.0"

    async def discover(self) -> AsyncIterator[CaptureEvent]:
        yield CaptureEvent(
            id="evt_1",
            source=SourceIdentity(kind="test"),
            occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
            payload=HtmlPayload(html="<article>hello</article>"),
            provenance=Provenance(
                adapter_name=self.name,
                adapter_version=self.version,
                fetched_at=datetime(2026, 5, 12, tzinfo=UTC),
            ),
            idempotency_key="test:evt_1",
        )


class FakeAIProvider:
    name = "fake-ai"

    async def run(self, task: EnrichmentTask, event: CaptureEvent) -> EnrichmentResult:
        return EnrichmentResult(
            task_type=task.type,
            output={"event_id": event.id},
            model=ModelIdentity(provider=self.name, name="fake-model"),
        )


class FakeArtifactStore:
    name = "fake-artifacts"

    def __init__(self) -> None:
        self.artifacts: dict[str, ArtifactRead] = {}

    async def put(self, artifact: ArtifactWrite) -> ArtifactRef:
        digest = hashlib.sha256(artifact.content).hexdigest()
        ref = ArtifactRef(
            uri=f"memory://{artifact.kind}/{digest}",
            kind=artifact.kind,
            media_type=artifact.media_type,
            size_bytes=len(artifact.content),
            sha256=digest,
        )
        self.artifacts[ref.uri] = ArtifactRead(ref=ref, content=artifact.content)
        return ref

    async def get(self, ref: ArtifactRef) -> ArtifactRead:
        return self.artifacts[ref.uri]

    async def exists(self, ref: ArtifactRef) -> bool:
        return ref.uri in self.artifacts


class FakeEventRecordStore:
    name = "fake-event-records"

    def __init__(self) -> None:
        self.records: dict[str, EventRecord] = {}
        self.enrichment_count = 0

    async def find_by_idempotency_key(self, idempotency_key: str) -> EventRecord | None:
        return self.records.get(idempotency_key)

    async def save_event(
        self,
        event: CaptureEvent,
        *,
        raw_artifact: ArtifactRef | None,
        normalized_artifact: ArtifactRef | None,
    ) -> EventRecord:
        record = EventRecord(
            event_id=event.id,
            idempotency_key=event.idempotency_key,
            status="persisted",
            raw_artifact=raw_artifact,
            normalized_artifact=normalized_artifact,
        )
        self.records[event.idempotency_key] = record
        return record

    async def save_enrichment(
        self,
        event: CaptureEvent,
        result: EnrichmentResult,
        artifact: ArtifactRef,
    ) -> EventRecord:
        del result, artifact
        self.enrichment_count += 1
        record = EventRecord(
            event_id=event.id,
            idempotency_key=event.idempotency_key,
            status="enriched",
        )
        self.records[event.idempotency_key] = record
        return record


def test_pipeline_runs_adapter_ai_and_stores() -> None:
    artifact_store = FakeArtifactStore()
    event_record_store = FakeEventRecordStore()
    pipeline = CapturePipeline(
        adapter=FakeAdapter(),
        ai_provider=FakeAIProvider(),
        artifact_store=artifact_store,
        event_record_store=event_record_store,
        enrichment_tasks=[SummarizeTask(max_tokens=100)],
    )

    processed = asyncio.run(pipeline.run_once())

    assert processed == 1
    expected_artifact_count = 2
    assert len(artifact_store.artifacts) == expected_artifact_count
    assert event_record_store.enrichment_count == 1


def test_pipeline_skips_already_enriched_event() -> None:
    artifact_store = FakeArtifactStore()
    event_record_store = FakeEventRecordStore()
    event_record_store.records["test:evt_1"] = EventRecord(
        event_id="evt_1",
        idempotency_key="test:evt_1",
        status="enriched",
    )
    pipeline = CapturePipeline(
        adapter=FakeAdapter(),
        ai_provider=FakeAIProvider(),
        artifact_store=artifact_store,
        event_record_store=event_record_store,
        enrichment_tasks=[SummarizeTask(max_tokens=100)],
    )

    processed = asyncio.run(pipeline.run_once())

    assert processed == 0
    assert artifact_store.artifacts == {}


def test_fake_implementations_match_ports() -> None:
    adapter_name = FakeAdapter().name
    ai_provider: AIProvider = FakeAIProvider()
    artifact_store: ArtifactStore = FakeArtifactStore()
    event_record_store: EventRecordStore = FakeEventRecordStore()

    assert adapter_name == "fake"
    assert ai_provider.name == "fake-ai"
    assert artifact_store.name == "fake-artifacts"
    assert event_record_store.name == "fake-event-records"
