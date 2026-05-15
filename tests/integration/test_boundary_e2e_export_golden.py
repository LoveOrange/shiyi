import asyncio
import json
import re
from collections.abc import Callable
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from typing import NamedTuple

import pytest

from shiyi import (
    Adapter,
    CapturePipeline,
    HtmlMarkdownNormalizer,
    InternalItem,
    export_items,
    google_research_blog_adapter,
    huggingface_blog_adapter,
    openai_news_adapter,
)
from shiyi.domain.models import EnrichmentResult, EnrichmentTask
from shiyi.fetchers.fake import FakeRssFetcher
from shiyi.ports.fetcher import RssEntry, RssFeed
from shiyi.stores.filesystem import FileSystemArtifactStore
from shiyi.stores.sqlite import SQLiteEventRecordStore

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"
OPENAI_RSS_URL = "https://openai.com/news/rss.xml"
HUGGINGFACE_RSS_URL = "https://huggingface.co/blog/feed.xml"
GOOGLE_RESEARCH_RSS_URL = "https://research.google/blog/rss/"


class RssExportCase(NamedTuple):
    source_kind: str
    feed_url: str
    fixture_root: Path
    expected_export_path: Path
    build_adapter: Callable[..., Adapter]


RSS_EXPORT_CASES = (
    RssExportCase(
        source_kind="openai-news",
        feed_url=OPENAI_RSS_URL,
        fixture_root=FIXTURE_ROOT / "openai-news",
        expected_export_path=FIXTURE_ROOT / "openai-news" / "export" / "running-codex-safely.json",
        build_adapter=openai_news_adapter,
    ),
    RssExportCase(
        source_kind="huggingface-blog",
        feed_url=HUGGINGFACE_RSS_URL,
        fixture_root=FIXTURE_ROOT / "huggingface-blog",
        expected_export_path=FIXTURE_ROOT / "huggingface-blog" / "export" / "open-r1.json",
        build_adapter=huggingface_blog_adapter,
    ),
    RssExportCase(
        source_kind="google-research-blog",
        feed_url=GOOGLE_RESEARCH_RSS_URL,
        fixture_root=FIXTURE_ROOT / "google-research-blog",
        expected_export_path=(
            FIXTURE_ROOT / "google-research-blog" / "export" / "catalyzing-scientific-impact.json"
        ),
        build_adapter=google_research_blog_adapter,
    ),
)


class NoopAIProvider:
    name = "noop-ai"

    async def run(self, _task: EnrichmentTask, _event: InternalItem) -> EnrichmentResult:
        msg = "golden export smoke should not run enrichment tasks"
        raise AssertionError(msg)


@pytest.mark.parametrize("case", RSS_EXPORT_CASES, ids=lambda case: case.source_kind)
def test_fixture_backed_rss_ingest_persist_export_matches_golden(
    tmp_path: Path,
    case: RssExportCase,
) -> None:
    feed = RssFeed.model_validate_json((case.fixture_root / "raw" / "feed.json").read_text())
    adapter = case.build_adapter(rss_fetcher=FakeRssFetcher({case.feed_url: feed}))
    pipeline = _pipeline(adapter=adapter, workspace=tmp_path)

    summary = asyncio.run(pipeline.run_once())
    exported = [
        item.model_dump(mode="json")
        for item in export_items(
            workspace=tmp_path,
            since=datetime(2026, 5, 1, tzinfo=UTC),
            until=datetime(2026, 5, 14, tzinfo=UTC),
            sources=(case.source_kind,),
            limit=10,
        )
    ]

    entry = feed.entries[0]
    normalized_content = exported[0]["normalized_content"] or ""

    assert summary.processed == 1
    assert _stable_dump(exported) == _read_json(case.expected_export_path)
    assert "rss_guid" not in json.dumps(exported)
    assert "raw_payload" not in json.dumps(exported)
    assert entry.title in normalized_content
    if entry.link is not None:
        assert entry.link in normalized_content
    if entry.html and entry.html == _plain_text(entry.html):
        assert entry.html in normalized_content


def test_summary_only_rss_exports_are_disambiguated_by_title_and_link(tmp_path: Path) -> None:
    first_link = "https://research.google/blog/first-summary-only/"
    second_link = "https://research.google/blog/second-summary-only/"
    feed = RssFeed(
        url=GOOGLE_RESEARCH_RSS_URL,
        fetched_at=datetime(2026, 5, 13, 1, 30, tzinfo=UTC),
        entries=(
            RssEntry(
                entry_id=first_link,
                title="First summary-only research item",
                link=first_link,
                html="Data Mining & Modeling",
                published_at=datetime(2026, 5, 12, 10, tzinfo=UTC),
            ),
            RssEntry(
                entry_id=second_link,
                title="Second summary-only research item",
                link=second_link,
                html="Data Mining & Modeling",
                published_at=datetime(2026, 5, 12, 11, tzinfo=UTC),
            ),
        ),
    )
    pipeline = _pipeline(
        adapter=google_research_blog_adapter(
            rss_fetcher=FakeRssFetcher({GOOGLE_RESEARCH_RSS_URL: feed})
        ),
        workspace=tmp_path,
    )

    summary = asyncio.run(pipeline.run_once())
    exported = export_items(
        workspace=tmp_path,
        sources=("google-research-blog",),
        limit=10,
    )
    normalized_by_event_id = {item.event_id: item.normalized_content or "" for item in exported}
    expected_count = 2

    assert summary.processed == expected_count
    assert len(exported) == expected_count
    assert len(set(normalized_by_event_id.values())) == expected_count
    assert len({item.content_hash for item in exported}) == expected_count
    assert (
        "First summary-only research item"
        in normalized_by_event_id[f"google-research-blog:{first_link}"]
    )
    assert first_link in normalized_by_event_id[f"google-research-blog:{first_link}"]
    assert (
        "Second summary-only research item"
        in normalized_by_event_id[f"google-research-blog:{second_link}"]
    )
    assert second_link in normalized_by_event_id[f"google-research-blog:{second_link}"]


def test_pipeline_rerun_and_duplicate_batch_do_not_duplicate_durable_events(tmp_path: Path) -> None:
    fixture_root = FIXTURE_ROOT / "openai-news"
    feed = RssFeed.model_validate_json((fixture_root / "raw" / "feed.json").read_text())
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


def _plain_text(html: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", html)).split())


def _read_json(path: Path) -> object:
    return json.loads(path.read_text())


def _stable_dump(value: object) -> object:
    return json.loads(json.dumps(value, sort_keys=True))
