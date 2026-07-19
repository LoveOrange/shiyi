import asyncio
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import pytest

from shiyi import (
    CaptureConfig,
    CaptureRunner,
    CaptureRunSummary,
    ContentItem,
    FileSystemBlobStore,
    MarkdownContentProcessor,
    MemoryContentItemStore,
    Source,
    SourceAdapter,
)
from shiyi.adapters.bytedance_seed import bytedance_seed_blog_adapter
from shiyi.adapters.changelog import (
    cohere_blog_adapter,
    cursor_changelog_adapter,
    deepseek_news_adapter,
    gemini_api_changelog_adapter,
    mistral_news_adapter,
    moonshot_kimi_changelog_adapter,
    z_ai_blog_adapter,
)
from shiyi.adapters.rss import (
    github_copilot_changelog_adapter,
    google_research_blog_adapter,
    huggingface_blog_adapter,
    microsoft_ai_blog_adapter,
)
from shiyi.fetchers.fake import FakeRssFetcher, FakeWebFetcher
from shiyi.ports.fetcher import RssFeed

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"
FETCHED_AT = datetime(2026, 5, 14, 8, 30, tzinfo=UTC)


class RssCase(NamedTuple):
    source_id: str
    target: str
    feed_path: Path
    pages: Mapping[str, str]
    build: Callable[[RssFeed, FakeWebFetcher | None], SourceAdapter]
    expected_excerpt: str


class WebCase(NamedTuple):
    source_id: str
    target: str
    pages: Mapping[str, str]
    build: Callable[[FakeWebFetcher], SourceAdapter]
    expected_excerpt: str
    content_kind: str = "article"


RSS_CASES = (
    RssCase(
        source_id="huggingface-blog",
        target="https://huggingface.co/blog/feed.xml",
        feed_path=FIXTURE_ROOT / "huggingface-blog" / "raw" / "feed.json",
        pages={
            "https://huggingface.co/blog/open-r1": (
                FIXTURE_ROOT / "huggingface-blog" / "raw" / "open-r1.html"
            ).read_text()
        },
        build=lambda feed, fetcher: huggingface_blog_adapter(
            rss_fetcher=FakeRssFetcher({str(feed.url): feed}),
            web_fetcher=fetcher,
        ),
        expected_excerpt="reinforcement learning",
    ),
    RssCase(
        source_id="google-research-blog",
        target="https://research.google/blog/rss/",
        feed_path=FIXTURE_ROOT / "google-research-blog" / "raw" / "feed.json",
        pages={
            "https://research.google/blog/"
            "catalyzing-scientific-impact-through-global-partnerships-and-open-resources": (
                FIXTURE_ROOT / "google-research-blog" / "raw" / "catalyzing-scientific-impact.html"
            ).read_text()
        },
        build=lambda feed, fetcher: google_research_blog_adapter(
            rss_fetcher=FakeRssFetcher({str(feed.url): feed}),
            web_fetcher=fetcher,
        ),
        expected_excerpt="scientific impact",
    ),
    RssCase(
        source_id="microsoft-ai-blog",
        target="https://www.microsoft.com/en-us/microsoft-cloud/blog/topic/ai-resources/feed/",
        feed_path=FIXTURE_ROOT / "microsoft-ai-blog" / "raw" / "feed.json",
        pages={},
        build=lambda feed, _fetcher: microsoft_ai_blog_adapter(
            rss_fetcher=FakeRssFetcher({str(feed.url): feed})
        ),
        expected_excerpt="Frontier",
    ),
    RssCase(
        source_id="github-copilot-changelog",
        target="https://github.blog/changelog/label/copilot/feed/",
        feed_path=FIXTURE_ROOT / "github-copilot-changelog" / "raw" / "feed.json",
        pages={},
        build=lambda feed, _fetcher: github_copilot_changelog_adapter(
            limit=1,
            rss_fetcher=FakeRssFetcher({str(feed.url): feed}),
        ),
        expected_excerpt="Eclipse",
    ),
)


WEB_CASES = (
    WebCase(
        source_id="deepseek-news",
        target="https://api-docs.deepseek.com/updates",
        pages={
            "https://api-docs.deepseek.com/updates": (
                FIXTURE_ROOT / "deepseek-news" / "raw" / "updates.html"
            ).read_text(),
            "https://api-docs.deepseek.com/news/news260424": (
                FIXTURE_ROOT / "deepseek-news" / "raw" / "news260424.html"
            ).read_text(),
        },
        build=lambda fetcher: deepseek_news_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="DeepSeek",
    ),
    WebCase(
        source_id="z-ai-blog",
        target="https://docs.z.ai/release-notes/new-released.md",
        pages={
            "https://docs.z.ai/release-notes/new-released.md": (
                FIXTURE_ROOT / "z-ai-blog" / "raw" / "new-released.md"
            ).read_text(),
            "https://z.ai/blog/glm-5.1": (
                FIXTURE_ROOT / "z-ai-blog" / "raw" / "glm-5-1.html"
            ).read_text(),
            "https://z.ai/blog/assets/glm-5.1-sEcXPNR5.js": (
                FIXTURE_ROOT / "z-ai-blog" / "raw" / "glm-5-1.js"
            ).read_text(),
        },
        build=lambda fetcher: z_ai_blog_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="key variable",
    ),
    WebCase(
        source_id="moonshot-kimi-changelog",
        target="https://platform.kimi.com/blog/posts/changelog",
        pages={
            "https://platform.kimi.com/blog/posts/changelog": (
                FIXTURE_ROOT / "moonshot-kimi-changelog" / "raw" / "changelog.html"
            ).read_text()
        },
        build=lambda fetcher: moonshot_kimi_changelog_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="Kimi",
        content_kind="release_note",
    ),
    WebCase(
        source_id="bytedance-seed-blog",
        target="https://seed.bytedance.com/zh/blog",
        pages={
            "https://seed.bytedance.com/zh/blog": (
                FIXTURE_ROOT / "bytedance-seed-blog" / "raw" / "index.html"
            ).read_text(),
            "https://seed.bytedance.com/zh/blog/seed3d-2-0发布-更高精度-更强可用性": (
                FIXTURE_ROOT / "bytedance-seed-blog" / "raw" / "seed3d-2-0-released.html"
            ).read_text(),
        },
        build=lambda fetcher: bytedance_seed_blog_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="Seed3D",
    ),
    WebCase(
        source_id="gemini-api-changelog",
        target="https://ai.google.dev/gemini-api/docs/changelog.md.txt",
        pages={
            "https://ai.google.dev/gemini-api/docs/changelog.md.txt": (
                FIXTURE_ROOT / "gemini-api-changelog" / "raw" / "changelog.md"
            ).read_text()
        },
        build=lambda fetcher: gemini_api_changelog_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="gemini-3.1-flash-lite",
        content_kind="release_note",
    ),
    WebCase(
        source_id="mistral-news",
        target="https://mistral.ai/news",
        pages={
            "https://mistral.ai/news": (
                FIXTURE_ROOT / "mistral-news" / "raw" / "index.html"
            ).read_text(),
            "https://mistral.ai/news/vibe-remote-agents-mistral-medium-3-5": (
                FIXTURE_ROOT / "mistral-news" / "raw" / "vibe-remote-agents-mistral-medium-3-5.html"
            ).read_text(),
        },
        build=lambda fetcher: mistral_news_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="Remote coding sessions",
    ),
    WebCase(
        source_id="cohere-blog",
        target="https://cohere.com/blog",
        pages={
            "https://cohere.com/blog": (
                FIXTURE_ROOT / "cohere-blog" / "raw" / "index.html"
            ).read_text(),
            "https://cohere.com/blog/cohere-sovereign-ai-nvidia": (
                FIXTURE_ROOT / "cohere-blog" / "raw" / "cohere-sovereign-ai-nvidia.html"
            ).read_text(),
        },
        build=lambda fetcher: cohere_blog_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="NVIDIA",
    ),
    WebCase(
        source_id="cursor-changelog",
        target="https://cursor.com/changelog",
        pages={
            "https://cursor.com/changelog": (
                FIXTURE_ROOT / "cursor-changelog" / "raw" / "changelog.html"
            ).read_text()
        },
        build=lambda fetcher: cursor_changelog_adapter(limit=1, web_fetcher=fetcher),
        expected_excerpt="Cursor Automations",
        content_kind="release_note",
    ),
)


@pytest.mark.parametrize("case", RSS_CASES, ids=lambda case: case.source_id)
def test_rss_source_fixture_reaches_canonical_content(tmp_path: Path, case: RssCase) -> None:
    feed = RssFeed.model_validate_json(case.feed_path.read_text())
    fetcher = FakeWebFetcher(case.pages, fetched_at=FETCHED_AT) if case.pages else None
    adapter = case.build(feed, fetcher)

    result, item = _run_case(
        tmp_path=tmp_path,
        source=Source(
            id=case.source_id,
            adapter=adapter.name,
            target=case.target,
            options={"content_kind": "article"},
        ),
        adapter=adapter,
    )

    assert result.processed == 1
    assert case.expected_excerpt.casefold() in item.content.casefold()
    assert item.ready_at is not None


@pytest.mark.parametrize("case", WEB_CASES, ids=lambda case: case.source_id)
def test_web_source_fixture_reaches_canonical_content(tmp_path: Path, case: WebCase) -> None:
    adapter = case.build(FakeWebFetcher(case.pages, fetched_at=FETCHED_AT))

    result, item = _run_case(
        tmp_path=tmp_path,
        source=Source(
            id=case.source_id,
            adapter=adapter.name,
            target=case.target,
            options={"content_kind": case.content_kind},
        ),
        adapter=adapter,
    )

    assert result.processed == 1
    assert case.expected_excerpt.casefold() in item.content.casefold()
    assert item.kind == case.content_kind
    assert item.ready_at is not None


def _run_case(
    *,
    tmp_path: Path,
    source: Source,
    adapter: SourceAdapter,
) -> tuple[CaptureRunSummary, ContentItem]:
    store = MemoryContentItemStore()
    runner = CaptureRunner(
        config=CaptureConfig(sources=(source,)),
        adapters=(adapter,),
        processor=MarkdownContentProcessor(clock=lambda: FETCHED_AT),
        content_store=store,
        blob_store=FileSystemBlobStore(tmp_path / "blobs"),
    )
    result = asyncio.run(runner.run_once())
    assert store.items, result.errors
    [item] = store.items.values()
    return result, item
