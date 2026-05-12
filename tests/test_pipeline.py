import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from shiyi import (
    AIProvider,
    CaptureEvent,
    CapturePipeline,
    EnrichmentResult,
    ModelIdentity,
    Persistence,
    Provenance,
    SourceIdentity,
    SummarizeTask,
    TextPayload,
)
from shiyi.domain.models import Checkpoint, EnrichmentTask
from shiyi.ports.persistence import PersistenceResult


class FakeAdapter:
    name = "fake"
    version = "0.1.0"

    async def discover(self, checkpoint: Checkpoint | None = None) -> AsyncIterator[CaptureEvent]:
        del checkpoint
        yield CaptureEvent(
            id="evt_1",
            source=SourceIdentity(kind="test"),
            occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
            payload=TextPayload(text="hello"),
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


class FakePersistence:
    name = "fake-store"

    def __init__(self) -> None:
        self.raw_count = 0
        self.enriched_count = 0

    async def save_raw(self, event: CaptureEvent) -> PersistenceResult:
        del event
        self.raw_count += 1
        return PersistenceResult(status="committed", record_id="raw_1")

    async def save_enriched(
        self,
        event: CaptureEvent,
        result: EnrichmentResult,
    ) -> PersistenceResult:
        del event, result
        self.enriched_count += 1
        return PersistenceResult(status="committed", record_id="enriched_1")

    async def commit_checkpoint(self, checkpoint: Checkpoint) -> None:
        del checkpoint


def test_pipeline_runs_adapter_ai_and_persistence() -> None:
    persistence = FakePersistence()
    pipeline = CapturePipeline(
        adapter=FakeAdapter(),
        ai_provider=FakeAIProvider(),
        persistence=persistence,
        enrichment_tasks=[SummarizeTask(max_tokens=100)],
    )

    processed = asyncio.run(pipeline.run_once())

    assert processed == 1
    assert persistence.raw_count == 1
    assert persistence.enriched_count == 1


def test_fake_implementations_match_ports() -> None:
    adapter_name = FakeAdapter().name
    ai_provider: AIProvider = FakeAIProvider()
    persistence: Persistence = FakePersistence()

    assert adapter_name == "fake"
    assert ai_provider.name == "fake-ai"
    assert persistence.name == "fake-store"
