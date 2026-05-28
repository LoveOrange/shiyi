import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Never

from shiyi.adapters.hacker_news import (
    HACKER_NEWS_ITEM_URL_TEMPLATE,
    HACKER_NEWS_TOP_STORIES_URL,
    hacker_news_topstories_adapter,
)
from shiyi.cli import LocalHeuristicAIProvider
from shiyi.enrichments.hacker_news_external import enrich_hacker_news_external_targets
from shiyi.export import export_items
from shiyi.fetchers.fake import FakeWebFetcher
from shiyi.normalizers.html import HtmlMarkdownNormalizer
from shiyi.pipeline.runner import CapturePipeline
from shiyi.ports.fetcher import FetcherError, FetchErrorKind
from shiyi.stores.filesystem import FileSystemArtifactStore
from shiyi.stores.sqlite import SQLiteEventRecordStore

FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "hacker-news"
FETCHED_AT = datetime(2026, 5, 14, 8, 30, tzinfo=UTC)
TARGET_URL = "https://example.com/agentic-code-review-traces"
EXPECTED_ARTIFACT_COUNT = 2
ROBOTS_DISALLOWED_HTTP_STATUS = 403


def test_hn_external_target_enrichment_exports_success_metadata(tmp_path: Path) -> None:
    asyncio.run(_persist_hn_item(tmp_path))
    external_fetcher = FakeWebFetcher(
        {
            TARGET_URL: (
                FIXTURE_ROOT / "external-target" / "agentic-code-review-traces.html"
            ).read_text(),
        },
        fetched_at=datetime(2026, 5, 14, 9, 0, tzinfo=UTC),
    )

    summary = asyncio.run(
        enrich_hacker_news_external_targets(workspace=tmp_path, web_fetcher=external_fetcher)
    )
    [item] = export_items(workspace=tmp_path, sources=("hacker-news",), limit=10)

    assert summary.processed == 1
    assert summary.enriched == 1
    assert summary.failed == 0
    assert summary.artifacts == EXPECTED_ARTIFACT_COUNT
    assert item.external_target_url == TARGET_URL
    enrichment = item.external_target_enrichment
    assert enrichment is not None
    assert enrichment["schema_version"] == "external_target_enrichment.v1"
    assert enrichment["target_url"] == TARGET_URL
    assert enrichment["final_url"] == TARGET_URL
    assert enrichment["external_title"] == "Agentic code review traces"
    assert enrichment["fetch_status"] == "fetched"
    assert enrichment["source_type"] == "unknown"
    assert "deterministic approval checkpoints" in enrichment["factual_summary"]
    assert enrichment["content_hash"]
    assert enrichment["provenance"]["fetcher"] == "hacker-news-external-target"
    assert enrichment["provenance"]["raw_artifact_ref"]["kind"] == "raw"
    assert enrichment["provenance"]["normalized_artifact_ref"]["kind"] == "normalized"
    assert external_fetcher.calls[0].source == "hacker-news-external-target"


def test_hn_external_target_enrichment_exports_failure_status(tmp_path: Path) -> None:
    asyncio.run(_persist_hn_item(tmp_path))

    summary = asyncio.run(
        enrich_hacker_news_external_targets(
            workspace=tmp_path,
            web_fetcher=RobotsDisallowedFetcher(),
        )
    )
    [item] = export_items(workspace=tmp_path, sources=("hacker-news",), limit=10)

    assert summary.processed == 1
    assert summary.enriched == 0
    assert summary.failed == 1
    enrichment = item.external_target_enrichment
    assert enrichment is not None
    assert enrichment["fetch_status"] == "robots_disallowed"
    assert enrichment["target_url"] == TARGET_URL
    assert "raw_artifact_ref" not in enrichment["provenance"]
    assert enrichment["provenance"]["http_status"] == ROBOTS_DISALLOWED_HTTP_STATUS
    assert "robots" in enrichment["provenance"]["failure_reason"]


async def _persist_hn_item(workspace: Path) -> None:
    adapter = hacker_news_topstories_adapter(
        limit=1,
        web_fetcher=FakeWebFetcher(
            {
                HACKER_NEWS_TOP_STORIES_URL: (FIXTURE_ROOT / "raw" / "topstories.json").read_text(),
                HACKER_NEWS_ITEM_URL_TEMPLATE.format(item_id=44123456): (
                    FIXTURE_ROOT / "raw" / "44123456.json"
                ).read_text(),
            },
            fetched_at=FETCHED_AT,
        ),
    )
    pipeline = CapturePipeline(
        adapter=adapter,
        ai_provider=LocalHeuristicAIProvider(),
        artifact_store=FileSystemArtifactStore(workspace / "artifacts"),
        event_record_store=SQLiteEventRecordStore(workspace / "event-records.sqlite"),
        normalizer=HtmlMarkdownNormalizer(),
        enrichment_tasks=(),
    )
    summary = await pipeline.run_once()
    assert summary.processed == 1


class RobotsDisallowedFetcher:
    async def fetch(
        self,
        url: str,
        *,
        source: str | None = None,
        raw_key: str | None = None,
    ) -> Never:
        _ = raw_key
        raise FetcherError(
            url=url,
            kind=FetchErrorKind.HTTP_STATUS,
            status_code=ROBOTS_DISALLOWED_HTTP_STATUS,
            source=source,
            message="robots disallowed by external target",
        )
