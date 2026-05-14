import asyncio
import json
from pathlib import Path

from shiyi import (
    Adapter,
    CapturePipeline,
    HtmlMarkdownNormalizer,
    InternalItem,
    export_items,
    openai_news_adapter,
)
from shiyi.domain.models import EnrichmentResult, EnrichmentTask
from shiyi.fetchers.fake import FakeRssFetcher
from shiyi.ports.fetcher import RssFeed
from shiyi.stores.filesystem import FileSystemArtifactStore
from shiyi.stores.sqlite import SQLiteEventRecordStore

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "openai-news"
OPENAI_RSS_URL = "https://openai.com/news/rss.xml"


class NoopAIProvider:
    name = "noop-ai"

    async def run(self, _task: EnrichmentTask, _event: InternalItem) -> EnrichmentResult:
        msg = "golden export smoke should not run enrichment tasks"
        raise AssertionError(msg)


def test_fixture_backed_ingest_persist_export_matches_golden(tmp_path: Path) -> None:
    feed = RssFeed.model_validate_json((FIXTURE_ROOT / "raw" / "feed.json").read_text())
    adapter = openai_news_adapter(rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: feed}))
    pipeline = _pipeline(adapter=adapter, workspace=tmp_path)

    summary = asyncio.run(pipeline.run_once())
    exported = [item.model_dump(mode="json") for item in export_items(workspace=tmp_path, limit=10)]

    assert summary.processed == 1
    assert _stable_dump(exported) == _read_json(
        FIXTURE_ROOT / "export" / "running-codex-safely.json"
    )
    assert "rss_guid" not in json.dumps(exported)
    assert "raw_payload" not in json.dumps(exported)


def test_pipeline_rerun_and_duplicate_batch_do_not_duplicate_durable_events(tmp_path: Path) -> None:
    feed = RssFeed.model_validate_json((FIXTURE_ROOT / "raw" / "feed.json").read_text())
    duplicate_feed = feed.model_copy(update={"entries": (feed.entries[0], feed.entries[0])})
    pipeline = _pipeline(
        adapter=openai_news_adapter(rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: duplicate_feed})),
        workspace=tmp_path,
    )

    first_summary = asyncio.run(pipeline.run_once())
    second_summary = asyncio.run(pipeline.run_once())
    exported = export_items(workspace=tmp_path, limit=10)

    duplicate_item_count = 2

    assert first_summary.processed == 1
    assert first_summary.skipped == 1
    assert second_summary.processed == 0
    assert second_summary.skipped == duplicate_item_count
    assert [item.idempotency_key for item in exported] == ["openai-news:running-codex-safely"]


def _pipeline(*, adapter: Adapter, workspace: Path) -> CapturePipeline:
    return CapturePipeline(
        adapter=adapter,
        ai_provider=NoopAIProvider(),
        artifact_store=FileSystemArtifactStore(workspace / "artifacts"),
        event_record_store=SQLiteEventRecordStore(workspace / "event-records.sqlite"),
        normalizer=HtmlMarkdownNormalizer(),
        enrichment_tasks=[],
    )


def _read_json(path: Path) -> object:
    return json.loads(path.read_text())


def _stable_dump(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True))
