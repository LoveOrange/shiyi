import asyncio
import json
import re
from collections.abc import Callable, Mapping
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
    bytedance_seed_blog_adapter,
    cohere_blog_adapter,
    cursor_changelog_adapter,
    deepmind_blog_adapter,
    deepseek_news_adapter,
    export_items,
    gemini_api_changelog_adapter,
    github_copilot_changelog_adapter,
    google_research_blog_adapter,
    hacker_news_topstories_adapter,
    huggingface_blog_adapter,
    microsoft_ai_blog_adapter,
    mistral_news_adapter,
    moonshot_kimi_changelog_adapter,
    openai_news_adapter,
    z_ai_blog_adapter,
)
from shiyi.adapters.hacker_news import HACKER_NEWS_ITEM_URL_TEMPLATE, HACKER_NEWS_TOP_STORIES_URL
from shiyi.domain.models import EnrichmentResult, EnrichmentTask
from shiyi.fetchers.fake import FakeRssFetcher, FakeWebFetcher
from shiyi.ports.fetcher import RssEntry, RssFeed
from shiyi.stores.filesystem import FileSystemArtifactStore
from shiyi.stores.sqlite import SQLiteEventRecordStore

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"
OPENAI_RSS_URL = "https://openai.com/news/rss.xml"
HUGGINGFACE_RSS_URL = "https://huggingface.co/blog/feed.xml"
GOOGLE_RESEARCH_RSS_URL = "https://research.google/blog/rss/"
DEEPMIND_RSS_URL = "https://deepmind.google/blog/rss.xml"
DEEPMIND_ALPHAEVOLVE_URL = "https://deepmind.google/blog/alphaevolve-impact/"
DEEPSEEK_UPDATES_URL = "https://api-docs.deepseek.com/updates"
DEEPSEEK_NEWS_URL = "https://api-docs.deepseek.com/news/news260424"
Z_AI_RELEASE_NOTES_URL = "https://docs.z.ai/release-notes/new-released.md"
Z_AI_BLOG_URL = "https://z.ai/blog/glm-5.1"
Z_AI_BLOG_ASSET_URL = "https://z.ai/blog/assets/glm-5.1-sEcXPNR5.js"
MOONSHOT_KIMI_CHANGELOG_URL = "https://platform.kimi.com/blog/posts/changelog"
BYTEDANCE_SEED_BLOG_URL = "https://seed.bytedance.com/zh/blog"
BYTEDANCE_SEED_ARTICLE_URL = "https://seed.bytedance.com/zh/blog/seed3d-2-0发布-更高精度-更强可用性"
GEMINI_API_CHANGELOG_URL = "https://ai.google.dev/gemini-api/docs/changelog.md.txt"
MISTRAL_NEWS_URL = "https://mistral.ai/news"
MISTRAL_NEWS_ARTICLE_URL = "https://mistral.ai/news/vibe-remote-agents-mistral-medium-3-5"
MICROSOFT_AI_BLOG_FEED_URL = (
    "https://www.microsoft.com/en-us/microsoft-cloud/blog/topic/ai-resources/feed/"
)
HUGGINGFACE_OPEN_R1_URL = "https://huggingface.co/blog/open-r1"
GOOGLE_RESEARCH_ARTICLE_URL = (
    "https://research.google/blog/"
    "catalyzing-scientific-impact-through-global-partnerships-and-open-resources"
)
COHERE_BLOG_URL = "https://cohere.com/blog"
COHERE_BLOG_ARTICLE_URL = "https://cohere.com/blog/cohere-sovereign-ai-nvidia"
CURSOR_CHANGELOG_URL = "https://cursor.com/changelog"
GITHUB_COPILOT_CHANGELOG_FEED_URL = "https://github.blog/changelog/label/copilot/feed/"
HACKER_NEWS_FIXTURE_ROOT = FIXTURE_ROOT / "hacker-news"
FETCHED_AT = datetime(2026, 5, 14, 8, 30, tzinfo=UTC)


class RssExportCase(NamedTuple):
    source_kind: str
    feed_url: str
    fixture_root: Path
    expected_export_path: Path
    build_adapter: Callable[[RssFeed, FakeWebFetcher | None], Adapter]
    pages: Mapping[str, str] = {}


RSS_EXPORT_CASES = (
    RssExportCase(
        source_kind="openai-news",
        feed_url=OPENAI_RSS_URL,
        fixture_root=FIXTURE_ROOT / "openai-news",
        expected_export_path=FIXTURE_ROOT / "openai-news" / "export" / "running-codex-safely.json",
        build_adapter=lambda feed, _fetcher: openai_news_adapter(
            rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: feed})
        ),
    ),
    RssExportCase(
        source_kind="huggingface-blog",
        feed_url=HUGGINGFACE_RSS_URL,
        fixture_root=FIXTURE_ROOT / "huggingface-blog",
        expected_export_path=FIXTURE_ROOT / "huggingface-blog" / "export" / "open-r1.json",
        build_adapter=lambda feed, fetcher: huggingface_blog_adapter(
            rss_fetcher=FakeRssFetcher({HUGGINGFACE_RSS_URL: feed}),
            web_fetcher=fetcher,
        ),
        pages={
            HUGGINGFACE_OPEN_R1_URL: (
                FIXTURE_ROOT / "huggingface-blog" / "raw" / "open-r1.html"
            ).read_text(),
        },
    ),
    RssExportCase(
        source_kind="google-research-blog",
        feed_url=GOOGLE_RESEARCH_RSS_URL,
        fixture_root=FIXTURE_ROOT / "google-research-blog",
        expected_export_path=(
            FIXTURE_ROOT / "google-research-blog" / "export" / "catalyzing-scientific-impact.json"
        ),
        build_adapter=lambda feed, fetcher: google_research_blog_adapter(
            rss_fetcher=FakeRssFetcher({GOOGLE_RESEARCH_RSS_URL: feed}),
            web_fetcher=fetcher,
        ),
        pages={
            GOOGLE_RESEARCH_ARTICLE_URL: (
                FIXTURE_ROOT / "google-research-blog" / "raw" / "catalyzing-scientific-impact.html"
            ).read_text(),
        },
    ),
    RssExportCase(
        source_kind="microsoft-ai-blog",
        feed_url=MICROSOFT_AI_BLOG_FEED_URL,
        fixture_root=FIXTURE_ROOT / "microsoft-ai-blog",
        expected_export_path=(
            FIXTURE_ROOT / "microsoft-ai-blog" / "export" / "frontier-transformation-readiness.json"
        ),
        build_adapter=lambda feed, _fetcher: microsoft_ai_blog_adapter(
            rss_fetcher=FakeRssFetcher({MICROSOFT_AI_BLOG_FEED_URL: feed})
        ),
    ),
    RssExportCase(
        source_kind="github-copilot-changelog",
        feed_url=GITHUB_COPILOT_CHANGELOG_FEED_URL,
        fixture_root=FIXTURE_ROOT / "github-copilot-changelog",
        expected_export_path=(
            FIXTURE_ROOT
            / "github-copilot-changelog"
            / "export"
            / "github-copilot-for-eclipse-is-open-source.json"
        ),
        build_adapter=lambda feed, _fetcher: github_copilot_changelog_adapter(
            limit=1,
            rss_fetcher=FakeRssFetcher({GITHUB_COPILOT_CHANGELOG_FEED_URL: feed}),
        ),
    ),
)


class WebExportCase(NamedTuple):
    source_kind: str
    pages: Mapping[str, str]
    expected_export_path: Path
    build_adapter: Callable[[FakeWebFetcher], Adapter]
    expected_excerpt: str | None = None
    excluded_excerpts: tuple[str, ...] = ()


WEB_EXPORT_CASES = (
    WebExportCase(
        source_kind="deepmind-blog",
        pages={
            DEEPMIND_ALPHAEVOLVE_URL: (
                FIXTURE_ROOT / "deepmind-blog" / "raw" / "alphaevolve-impact.html"
            ).read_text()
        },
        expected_export_path=FIXTURE_ROOT / "deepmind-blog" / "export" / "alphaevolve-impact.json",
        build_adapter=lambda fetcher: deepmind_blog_adapter(
            limit=1,
            rss_fetcher=FakeRssFetcher(
                {
                    DEEPMIND_RSS_URL: RssFeed.model_validate_json(
                        (FIXTURE_ROOT / "deepmind-blog" / "raw" / "feed.json").read_text()
                    )
                }
            ),
            web_fetcher=fetcher,
        ),
        expected_excerpt="Improving AI infrastructure",
        excluded_excerpts=("Related posts", "Explore our next generation AI systems"),
    ),
    WebExportCase(
        source_kind="deepseek-news",
        pages={
            DEEPSEEK_UPDATES_URL: (
                FIXTURE_ROOT / "deepseek-news" / "raw" / "updates.html"
            ).read_text(),
            DEEPSEEK_NEWS_URL: (
                FIXTURE_ROOT / "deepseek-news" / "raw" / "news260424.html"
            ).read_text(),
        },
        expected_export_path=FIXTURE_ROOT / "deepseek-news" / "export" / "deepseek-v4.json",
        build_adapter=lambda fetcher: deepseek_news_adapter(limit=1, web_fetcher=fetcher),
    ),
    WebExportCase(
        source_kind="z-ai-blog",
        pages={
            Z_AI_RELEASE_NOTES_URL: (
                FIXTURE_ROOT / "z-ai-blog" / "raw" / "new-released.md"
            ).read_text(),
            Z_AI_BLOG_URL: (FIXTURE_ROOT / "z-ai-blog" / "raw" / "glm-5-1.html").read_text(),
            Z_AI_BLOG_ASSET_URL: (FIXTURE_ROOT / "z-ai-blog" / "raw" / "glm-5-1.js").read_text(),
        },
        expected_export_path=FIXTURE_ROOT / "z-ai-blog" / "export" / "glm-5-1.json",
        build_adapter=lambda fetcher: z_ai_blog_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="Across all three settings, the key variable is not runtime alone",
    ),
    WebExportCase(
        source_kind="moonshot-kimi-changelog",
        pages={
            MOONSHOT_KIMI_CHANGELOG_URL: (
                FIXTURE_ROOT / "moonshot-kimi-changelog" / "raw" / "changelog.html"
            ).read_text()
        },
        expected_export_path=(
            FIXTURE_ROOT / "moonshot-kimi-changelog" / "export" / "kimi-k2-think.json"
        ),
        build_adapter=lambda fetcher: moonshot_kimi_changelog_adapter(web_fetcher=fetcher),
    ),
    WebExportCase(
        source_kind="bytedance-seed-blog",
        pages={
            BYTEDANCE_SEED_BLOG_URL: (
                FIXTURE_ROOT / "bytedance-seed-blog" / "raw" / "index.html"
            ).read_text(),
            BYTEDANCE_SEED_ARTICLE_URL: (
                FIXTURE_ROOT / "bytedance-seed-blog" / "raw" / "seed3d-2-0-released.html"
            ).read_text(),
        },
        expected_export_path=FIXTURE_ROOT / "bytedance-seed-blog" / "export" / "seed3d-2-0.json",
        build_adapter=lambda fetcher: bytedance_seed_blog_adapter(web_fetcher=fetcher),
    ),
    WebExportCase(
        source_kind="gemini-api-changelog",
        pages={
            GEMINI_API_CHANGELOG_URL: (
                FIXTURE_ROOT / "gemini-api-changelog" / "raw" / "changelog.md"
            ).read_text()
        },
        expected_export_path=(FIXTURE_ROOT / "gemini-api-changelog" / "export" / "2026-05-07.json"),
        build_adapter=lambda fetcher: gemini_api_changelog_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="gemini-3.1-flash-lite",
    ),
    WebExportCase(
        source_kind="mistral-news",
        pages={
            MISTRAL_NEWS_URL: (FIXTURE_ROOT / "mistral-news" / "raw" / "index.html").read_text(),
            MISTRAL_NEWS_ARTICLE_URL: (
                FIXTURE_ROOT / "mistral-news" / "raw" / "vibe-remote-agents-mistral-medium-3-5.html"
            ).read_text(),
        },
        expected_export_path=FIXTURE_ROOT / "mistral-news" / "export" / "vibe-remote-agents.json",
        build_adapter=lambda fetcher: mistral_news_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="Remote coding sessions run in the cloud",
        excluded_excerpts=("Footer noise",),
    ),
    WebExportCase(
        source_kind="cohere-blog",
        pages={
            COHERE_BLOG_URL: (FIXTURE_ROOT / "cohere-blog" / "raw" / "index.html").read_text(),
            COHERE_BLOG_ARTICLE_URL: (
                FIXTURE_ROOT / "cohere-blog" / "raw" / "cohere-sovereign-ai-nvidia.html"
            ).read_text(),
        },
        expected_export_path=FIXTURE_ROOT
        / "cohere-blog"
        / "export"
        / "cohere-sovereign-ai-nvidia.json",
        build_adapter=lambda fetcher: cohere_blog_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="Together with NVIDIA",
    ),
    WebExportCase(
        source_kind="cursor-changelog",
        pages={
            CURSOR_CHANGELOG_URL: (
                FIXTURE_ROOT / "cursor-changelog" / "raw" / "changelog.html"
            ).read_text(),
        },
        expected_export_path=(
            FIXTURE_ROOT / "cursor-changelog" / "export" / "improvements-to-cursor-automations.json"
        ),
        build_adapter=lambda fetcher: cursor_changelog_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="Cursor Automations are now available in the Agents Window",
    ),
    WebExportCase(
        source_kind="hacker-news",
        pages={
            HACKER_NEWS_TOP_STORIES_URL: (
                HACKER_NEWS_FIXTURE_ROOT / "raw" / "topstories.json"
            ).read_text(),
            HACKER_NEWS_ITEM_URL_TEMPLATE.format(item_id=44123456): (
                HACKER_NEWS_FIXTURE_ROOT / "raw" / "44123456.json"
            ).read_text(),
        },
        expected_export_path=HACKER_NEWS_FIXTURE_ROOT / "export" / "hn-44123456.json",
        build_adapter=lambda fetcher: hacker_news_topstories_adapter(
            limit=1,
            web_fetcher=fetcher,
        ),
        expected_excerpt="Neutral metrics: score=512; descendants=128; rank=1",
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
    web_fetcher = FakeWebFetcher(case.pages, fetched_at=FETCHED_AT) if case.pages else None
    adapter = case.build_adapter(feed, web_fetcher)
    pipeline = _pipeline(adapter=adapter, workspace=tmp_path)

    summary = asyncio.run(pipeline.run_once())
    exported = [
        item.model_dump(mode="json")
        for item in export_items(
            workspace=tmp_path,
            since=datetime(2026, 5, 1, tzinfo=UTC),
            until=datetime(2026, 5, 26, tzinfo=UTC),
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
    if case.pages:
        assert normalized_content.startswith("# ")
        assert "Canonical link:" in normalized_content
        source = exported[0]["source"] or {}
        source_uri = source.get("uri")
        if isinstance(source_uri, str):
            assert source_uri in normalized_content
        if case.source_kind == "huggingface-blog":
            assert exported[0]["content_depth"] == "complete"
            assert exported[0]["content_completeness"] == "complete"
            assert exported[0]["source_ready"] is True
            assert exported[0]["published_at"] == "2026-05-09T09:00:00+00:00"
            assert source_uri == HUGGINGFACE_OPEN_R1_URL
    else:
        assert entry.title in normalized_content
        if entry.link is not None:
            assert entry.link in normalized_content
        if entry.html and entry.html == _plain_text(entry.html):
            assert entry.html in normalized_content


@pytest.mark.parametrize("case", WEB_EXPORT_CASES, ids=lambda case: case.source_kind)
def test_fixture_backed_web_ingest_persist_export_matches_golden(
    tmp_path: Path,
    case: WebExportCase,
) -> None:
    adapter = case.build_adapter(FakeWebFetcher(case.pages, fetched_at=FETCHED_AT))
    pipeline = _pipeline(adapter=adapter, workspace=tmp_path)

    summary = asyncio.run(pipeline.run_once())
    exported = [
        item.model_dump(mode="json")
        for item in export_items(
            workspace=tmp_path,
            since=datetime(2026, 5, 1, tzinfo=UTC),
            until=datetime(2026, 5, 15, tzinfo=UTC),
            sources=(case.source_kind,),
            limit=10,
        )
    ]
    normalized_content = exported[0]["normalized_content"] or ""

    assert summary.processed == 1
    assert _stable_dump(exported) == _read_json(case.expected_export_path)
    assert "raw_payload" not in json.dumps(exported)
    if case.source_kind == "hacker-news":
        assert "Hacker News discussion:" in normalized_content
    else:
        assert "Canonical link:" in normalized_content
    if case.expected_excerpt is not None:
        assert case.expected_excerpt in normalized_content
    for excluded_excerpt in case.excluded_excerpts:
        assert excluded_excerpt not in normalized_content


def test_summary_only_rss_exports_are_disambiguated_by_title_and_link(tmp_path: Path) -> None:
    first_link = "https://openai.com/index/first-summary-only/"
    second_link = "https://openai.com/index/second-summary-only/"
    feed = RssFeed(
        url=OPENAI_RSS_URL,
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
        adapter=openai_news_adapter(rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: feed})),
        workspace=tmp_path,
    )

    summary = asyncio.run(pipeline.run_once())
    exported = export_items(
        workspace=tmp_path,
        sources=("openai-news",),
        limit=10,
    )
    normalized_by_event_id = {item.event_id: item.normalized_content or "" for item in exported}
    expected_count = 2

    assert summary.processed == expected_count
    assert len(exported) == expected_count
    assert {item.content_depth for item in exported} == {"summary_only"}
    assert {item.content_completeness for item in exported} == {"summary_only"}
    assert {item.source_ready for item in exported} == {False}
    assert len(set(normalized_by_event_id.values())) == expected_count
    assert len({item.content_hash for item in exported}) == expected_count
    assert "First summary-only research item" in normalized_by_event_id[f"openai-news:{first_link}"]
    assert first_link in normalized_by_event_id[f"openai-news:{first_link}"]
    assert (
        "Second summary-only research item" in normalized_by_event_id[f"openai-news:{second_link}"]
    )
    assert second_link in normalized_by_event_id[f"openai-news:{second_link}"]


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
