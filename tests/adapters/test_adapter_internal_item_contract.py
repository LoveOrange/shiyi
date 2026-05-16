import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple, get_args

import pytest

from shiyi import (
    Adapter,
    InternalItem,
    anthropic_news_adapter,
    bytedance_seed_blog_adapter,
    deepseek_news_adapter,
    google_research_blog_adapter,
    huggingface_blog_adapter,
    moonshot_kimi_changelog_adapter,
    openai_news_adapter,
    z_ai_blog_adapter,
)
from shiyi.adapters.anthropic import ANTHROPIC_NEWS_URL
from shiyi.cli import SourceName
from shiyi.domain.models import CaptureWindow, HtmlPayload, TextPayload
from shiyi.fetchers.fake import FakeRssFetcher, FakeWebFetcher
from shiyi.ports.fetcher import RssEntry, RssFeed

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"
OPENAI_FIXTURE_ROOT = FIXTURE_ROOT / "openai-news"
HUGGINGFACE_FIXTURE_ROOT = FIXTURE_ROOT / "huggingface-blog"
GOOGLE_RESEARCH_FIXTURE_ROOT = FIXTURE_ROOT / "google-research-blog"
DEEPSEEK_FIXTURE_ROOT = FIXTURE_ROOT / "deepseek-news"
Z_AI_FIXTURE_ROOT = FIXTURE_ROOT / "z-ai-blog"
MOONSHOT_KIMI_FIXTURE_ROOT = FIXTURE_ROOT / "moonshot-kimi-changelog"
BYTEDANCE_SEED_FIXTURE_ROOT = FIXTURE_ROOT / "bytedance-seed-blog"
ANTHROPIC_FIXTURE_ROOT = FIXTURE_ROOT / "anthropic-news"
OPENAI_RSS_URL = "https://openai.com/news/rss.xml"
HUGGINGFACE_RSS_URL = "https://huggingface.co/blog/feed.xml"
GOOGLE_RESEARCH_RSS_URL = "https://research.google/blog/rss/"
DEEPSEEK_UPDATES_URL = "https://api-docs.deepseek.com/updates"
DEEPSEEK_NEWS_URL = "https://api-docs.deepseek.com/news/news260424"
Z_AI_RELEASE_NOTES_URL = "https://docs.z.ai/release-notes/new-released.md"
Z_AI_BLOG_URL = "https://z.ai/blog/glm-5.1"
Z_AI_BLOG_ASSET_URL = "https://z.ai/blog/assets/glm-5.1-sEcXPNR5.js"
MOONSHOT_KIMI_CHANGELOG_URL = "https://platform.kimi.com/blog/posts/changelog"
BYTEDANCE_SEED_BLOG_URL = "https://seed.bytedance.com/zh/blog"
BYTEDANCE_SEED_ARTICLE_URL = "https://seed.bytedance.com/zh/blog/seed3d-2-0发布-更高精度-更强可用性"
CLAUDE_DESIGN_URL = "https://www.anthropic.com/news/claude-design-anthropic-labs"
ANTHROPIC_MINIMAL_URL = "https://www.anthropic.com/news/minimal-contract"
ANTHROPIC_SECOND_URL = "https://www.anthropic.com/news/second-contract"
ANTHROPIC_MILLISECOND_URL = "https://www.anthropic.com/news/millisecond-contract"
FETCHED_AT = datetime(2026, 5, 14, 8, 30, tzinfo=UTC)


class ContractCase(NamedTuple):
    source_name: SourceName
    build_adapter: Callable[[], Adapter]
    expected_paths: tuple[Path, ...]


class RssBuiltinCase(NamedTuple):
    source_name: SourceName
    feed_url: str
    source_kind: str
    adapter_name: str
    build_adapter: Callable[[RssFeed, CaptureWindow | None], Adapter]


CONTRACT_CASES = (
    ContractCase(
        source_name="openai",
        build_adapter=lambda: openai_news_adapter(
            rss_fetcher=FakeRssFetcher(
                {
                    OPENAI_RSS_URL: RssFeed.model_validate_json(
                        (OPENAI_FIXTURE_ROOT / "raw" / "feed.json").read_text()
                    )
                }
            )
        ),
        expected_paths=(OPENAI_FIXTURE_ROOT / "internal-item" / "running-codex-safely.json",),
    ),
    ContractCase(
        source_name="huggingface-blog",
        build_adapter=lambda: huggingface_blog_adapter(
            rss_fetcher=FakeRssFetcher(
                {
                    HUGGINGFACE_RSS_URL: RssFeed.model_validate_json(
                        (HUGGINGFACE_FIXTURE_ROOT / "raw" / "feed.json").read_text()
                    )
                }
            )
        ),
        expected_paths=(HUGGINGFACE_FIXTURE_ROOT / "internal-item" / "open-r1.json",),
    ),
    ContractCase(
        source_name="google-research-blog",
        build_adapter=lambda: google_research_blog_adapter(
            rss_fetcher=FakeRssFetcher(
                {
                    GOOGLE_RESEARCH_RSS_URL: RssFeed.model_validate_json(
                        (GOOGLE_RESEARCH_FIXTURE_ROOT / "raw" / "feed.json").read_text()
                    )
                }
            )
        ),
        expected_paths=(
            GOOGLE_RESEARCH_FIXTURE_ROOT / "internal-item" / "catalyzing-scientific-impact.json",
        ),
    ),
    ContractCase(
        source_name="deepseek-news",
        build_adapter=lambda: deepseek_news_adapter(
            limit=1,
            web_fetcher=FakeWebFetcher(
                {
                    DEEPSEEK_UPDATES_URL: (
                        DEEPSEEK_FIXTURE_ROOT / "raw" / "updates.html"
                    ).read_text(),
                    DEEPSEEK_NEWS_URL: (
                        DEEPSEEK_FIXTURE_ROOT / "raw" / "news260424.html"
                    ).read_text(),
                },
                fetched_at=FETCHED_AT,
            ),
        ),
        expected_paths=(DEEPSEEK_FIXTURE_ROOT / "internal-item" / "deepseek-v4.json",),
    ),
    ContractCase(
        source_name="z-ai-blog",
        build_adapter=lambda: z_ai_blog_adapter(
            limit=1,
            web_fetcher=FakeWebFetcher(
                {
                    Z_AI_RELEASE_NOTES_URL: (
                        Z_AI_FIXTURE_ROOT / "raw" / "new-released.md"
                    ).read_text(),
                    Z_AI_BLOG_URL: (Z_AI_FIXTURE_ROOT / "raw" / "glm-5-1.html").read_text(),
                    Z_AI_BLOG_ASSET_URL: (Z_AI_FIXTURE_ROOT / "raw" / "glm-5-1.js").read_text(),
                },
                fetched_at=FETCHED_AT,
            ),
        ),
        expected_paths=(Z_AI_FIXTURE_ROOT / "internal-item" / "glm-5-1.json",),
    ),
    ContractCase(
        source_name="moonshot-kimi-changelog",
        build_adapter=lambda: moonshot_kimi_changelog_adapter(
            web_fetcher=FakeWebFetcher(
                {
                    MOONSHOT_KIMI_CHANGELOG_URL: (
                        MOONSHOT_KIMI_FIXTURE_ROOT / "raw" / "changelog.html"
                    ).read_text()
                },
                fetched_at=FETCHED_AT,
            )
        ),
        expected_paths=(MOONSHOT_KIMI_FIXTURE_ROOT / "internal-item" / "kimi-k2-think.json",),
    ),
    ContractCase(
        source_name="bytedance-seed-blog",
        build_adapter=lambda: bytedance_seed_blog_adapter(
            web_fetcher=FakeWebFetcher(
                {
                    BYTEDANCE_SEED_BLOG_URL: (
                        BYTEDANCE_SEED_FIXTURE_ROOT / "raw" / "index.html"
                    ).read_text(),
                    BYTEDANCE_SEED_ARTICLE_URL: (
                        BYTEDANCE_SEED_FIXTURE_ROOT / "raw" / "seed3d-2-0-released.html"
                    ).read_text(),
                },
                fetched_at=FETCHED_AT,
            )
        ),
        expected_paths=(BYTEDANCE_SEED_FIXTURE_ROOT / "internal-item" / "seed3d-2-0.json",),
    ),
    ContractCase(
        source_name="anthropic",
        build_adapter=lambda: anthropic_news_adapter(
            limit=1,
            web_fetcher=FakeWebFetcher(
                {
                    ANTHROPIC_NEWS_URL: (ANTHROPIC_FIXTURE_ROOT / "raw" / "index.html").read_text(),
                    CLAUDE_DESIGN_URL: (
                        ANTHROPIC_FIXTURE_ROOT / "raw" / "claude-design-anthropic-labs.html"
                    ).read_text(),
                },
                fetched_at=datetime(2026, 5, 14, tzinfo=UTC),
            ),
        ),
        expected_paths=(
            ANTHROPIC_FIXTURE_ROOT / "internal-item" / "claude-design-anthropic-labs.json",
        ),
    ),
)

RSS_BUILTIN_CASES = (
    RssBuiltinCase(
        source_name="openai",
        feed_url=OPENAI_RSS_URL,
        source_kind="openai-news",
        adapter_name="openai-news-rss",
        build_adapter=lambda feed, window: openai_news_adapter(
            rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: feed}), window=window
        ),
    ),
    RssBuiltinCase(
        source_name="huggingface-blog",
        feed_url=HUGGINGFACE_RSS_URL,
        source_kind="huggingface-blog",
        adapter_name="huggingface-blog-rss",
        build_adapter=lambda feed, window: huggingface_blog_adapter(
            rss_fetcher=FakeRssFetcher({HUGGINGFACE_RSS_URL: feed}), window=window
        ),
    ),
    RssBuiltinCase(
        source_name="google-research-blog",
        feed_url=GOOGLE_RESEARCH_RSS_URL,
        source_kind="google-research-blog",
        adapter_name="google-research-blog-rss",
        build_adapter=lambda feed, window: google_research_blog_adapter(
            rss_fetcher=FakeRssFetcher({GOOGLE_RESEARCH_RSS_URL: feed}), window=window
        ),
    ),
)


def test_every_builtin_source_has_executable_contract_case() -> None:
    assert {case.source_name for case in CONTRACT_CASES} == set(get_args(SourceName))


@pytest.mark.parametrize("case", CONTRACT_CASES, ids=lambda case: case.source_name)
def test_builtin_source_raw_fixture_matches_internal_item_golden(case: ContractCase) -> None:
    items = asyncio.run(_collect_items(case.build_adapter().discover()))

    assert [_stable_dump(item) for item in items] == [
        _read_json(path) for path in case.expected_paths
    ]
    for item in items:
        InternalItem.model_validate(item.model_dump(mode="json"))


@pytest.mark.parametrize("case", RSS_BUILTIN_CASES, ids=lambda case: case.source_name)
def test_rss_builtin_minimal_raw_payload_maps_to_valid_internal_item(
    case: RssBuiltinCase,
) -> None:
    feed = _rss_feed(
        feed_url=case.feed_url,
        entries=(
            RssEntry(
                entry_id="minimal-rss-entry",
                title="Minimal RSS Entry",
                link=None,
                html="",
                published_at=None,
            ),
        ),
    )

    items = asyncio.run(_collect_items(case.build_adapter(feed, None).discover()))

    assert len(items) == 1
    item = InternalItem.model_validate(items[0].model_dump(mode="json"))
    assert item.id == f"{case.source_kind}:minimal-rss-entry"
    assert item.source.kind == case.source_kind
    assert str(item.source.uri) == case.feed_url
    assert item.source.account_id is None
    assert item.captured_at == FETCHED_AT
    assert item.occurred_at == FETCHED_AT
    assert item.provenance.source_item_id == "minimal-rss-entry"
    assert item.provenance.adapter_name == case.adapter_name
    assert item.metadata == {
        "title": "Minimal RSS Entry",
        "link": None,
        "content_depth": "summary_only",
    }
    assert item.payload == TextPayload(text="Minimal RSS Entry")
    assert _dump_for_leak_check(item).isdisjoint({"raw_payload", "rss_guid", "feedparser"})


@pytest.mark.parametrize("case", RSS_BUILTIN_CASES, ids=lambda case: case.source_name)
@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (
            RssEntry(
                entry_id="",
                title="Missing external id",
                link="https://example.com/missing-id",
                html="<p>body</p>",
                published_at=FETCHED_AT,
            ),
            "RSS entry missing required entry_id",
        ),
        (
            RssEntry(
                entry_id="missing-title",
                title="",
                link="https://example.com/missing-title",
                html="<p>body</p>",
                published_at=FETCHED_AT,
            ),
            "RSS entry missing required title for RSS entry missing-title",
        ),
    ],
)
def test_rss_builtin_missing_required_fields_fail_clearly(
    case: RssBuiltinCase,
    entry: RssEntry,
    message: str,
) -> None:
    feed = _rss_feed(feed_url=case.feed_url, entries=(entry,))

    with pytest.raises(ValueError, match=message):
        asyncio.run(_collect_items(case.build_adapter(feed, None).discover()))


@pytest.mark.parametrize("case", RSS_BUILTIN_CASES, ids=lambda case: case.source_name)
def test_rss_builtin_timestamp_and_idempotency_contract_is_stable(
    case: RssBuiltinCase,
) -> None:
    occurred_at = datetime(2026, 5, 12, 18, 45, 0, 123000, tzinfo=timezone(timedelta(hours=8)))
    first = RssEntry(
        entry_id="timezone-entry",
        title="Timezone Entry",
        link="https://example.com/timezone-entry",
        html="<article>timezone body</article>",
        published_at=occurred_at,
    )
    second = first.model_copy(
        update={
            "entry_id": "distinct-entry",
            "title": "Distinct Entry",
            "link": "https://example.com/distinct-entry",
            "html": "<article>distinct body</article>",
        }
    )
    feed = _rss_feed(feed_url=case.feed_url, entries=(first, second))

    items = asyncio.run(_collect_items(case.build_adapter(feed, None).discover()))

    expected_count = 2
    assert len(items) == expected_count
    assert items[0].occurred_at == occurred_at
    assert items[0].idempotency_key == f"{case.source_kind}:timezone-entry"
    assert items[1].idempotency_key == f"{case.source_kind}:distinct-entry"
    assert items[0].idempotency_key != items[1].idempotency_key
    assert items[0].content_hash != items[1].content_hash
    assert isinstance(items[0].payload, HtmlPayload)
    assert str(items[0].payload.url) == "https://example.com/timezone-entry"


@pytest.mark.parametrize("case", RSS_BUILTIN_CASES, ids=lambda case: case.source_name)
def test_rss_builtin_filters_out_of_window_entries_before_required_field_validation(
    case: RssBuiltinCase,
) -> None:
    feed = _rss_feed(
        feed_url=case.feed_url,
        entries=(
            RssEntry(
                entry_id="old-invalid-entry",
                title="",
                link="https://example.com/old-invalid-entry",
                html="<article>old invalid body</article>",
                published_at=datetime(2026, 5, 11, tzinfo=UTC),
            ),
            RssEntry(
                entry_id="valid-in-window",
                title="Valid In Window",
                link="https://example.com/valid-in-window",
                html="<article>valid body</article>",
                published_at=datetime(2026, 5, 12, 12, tzinfo=UTC),
            ),
        ),
    )
    adapter = case.build_adapter(
        feed,
        CaptureWindow(
            since=datetime(2026, 5, 12, tzinfo=UTC),
            until=datetime(2026, 5, 13, tzinfo=UTC),
        ),
    )

    items = asyncio.run(_collect_items(adapter.discover()))

    assert [item.idempotency_key for item in items] == [f"{case.source_kind}:valid-in-window"]


def test_anthropic_minimal_raw_payload_maps_to_valid_internal_item() -> None:
    fetcher = FakeWebFetcher(
        {
            ANTHROPIC_NEWS_URL: f'<a href="{ANTHROPIC_MINIMAL_URL}">Minimal</a>',
            ANTHROPIC_MINIMAL_URL: """
            <html><body>
              <main><h1>Minimal Anthropic Item</h1><p>Body</p></main>
            </body></html>
            """,
        },
        fetched_at=FETCHED_AT,
    )
    adapter = anthropic_news_adapter(limit=1, web_fetcher=fetcher)

    items = asyncio.run(_collect_items(adapter.discover()))

    assert len(items) == 1
    item = InternalItem.model_validate(items[0].model_dump(mode="json"))
    assert item.id == "anthropic-news:minimal-contract"
    assert item.source.kind == "anthropic-news"
    assert str(item.source.uri) == ANTHROPIC_MINIMAL_URL
    assert item.source.account_id is None
    assert item.captured_at == FETCHED_AT
    assert item.occurred_at == FETCHED_AT
    assert item.provenance.source_item_id == "minimal-contract"
    assert item.provenance.adapter_name == "anthropic-news-index"
    assert item.metadata == {
        "title": "Minimal Anthropic Item",
        "link": ANTHROPIC_MINIMAL_URL,
        "content_depth": "full_page",
    }
    assert isinstance(item.payload, HtmlPayload)
    assert str(item.payload.url) == ANTHROPIC_MINIMAL_URL
    assert _dump_for_leak_check(item).isdisjoint({"raw_payload", "dom_node", "selectolax"})


def test_anthropic_missing_required_title_fails_clearly() -> None:
    fetcher = FakeWebFetcher(
        {
            ANTHROPIC_NEWS_URL: f'<a href="{ANTHROPIC_MINIMAL_URL}">Missing title</a>',
            ANTHROPIC_MINIMAL_URL: "<html><body><main><p>No title here.</p></main></body></html>",
        },
        fetched_at=FETCHED_AT,
    )
    adapter = anthropic_news_adapter(limit=1, web_fetcher=fetcher)

    with pytest.raises(ValueError, match="Anthropic article missing required title"):
        asyncio.run(_collect_items(adapter.discover()))


def test_anthropic_timestamp_parsing_handles_timezone_milliseconds_and_invalid_values() -> None:
    fetcher = FakeWebFetcher(
        {
            ANTHROPIC_NEWS_URL: """
            <a href="/news/minimal-contract">Minimal</a>
            <a href="/news/second-contract">Second</a>
            <a href="/news/millisecond-contract">Millisecond</a>
            """,
            ANTHROPIC_MINIMAL_URL: """
            <html><head>
              <title>Timezone Anthropic Item</title>
              <meta property="article:published_time" content="2026-05-12T10:15:00-07:00">
            </head><body><h1>Timezone Anthropic Item</h1></body></html>
            """,
            ANTHROPIC_SECOND_URL: """
            <html><head>
              <title>Invalid Date Anthropic Item</title>
              <time datetime="not-a-date">not-a-date</time>
            </head><body><h1>Invalid Date Anthropic Item</h1></body></html>
            """,
            ANTHROPIC_MILLISECOND_URL: """
            <html><head>
              <title>Millisecond Anthropic Item</title>
              <meta property="article:published_time" content="2026-05-12T10:15:00.123-07:00">
            </head><body><h1>Millisecond Anthropic Item</h1></body></html>
            """,
        },
        fetched_at=FETCHED_AT,
    )
    adapter = anthropic_news_adapter(limit=3, web_fetcher=fetcher)

    items = asyncio.run(_collect_items(adapter.discover()))

    expected_count = 3
    assert len(items) == expected_count
    assert items[0].occurred_at == datetime(2026, 5, 12, 17, 15, tzinfo=UTC)
    assert items[1].occurred_at == FETCHED_AT
    assert items[2].occurred_at == datetime(2026, 5, 12, 17, 15, 0, 123000, tzinfo=UTC)
    assert [item.idempotency_key for item in items] == [
        "anthropic-news:minimal-contract",
        "anthropic-news:second-contract",
        "anthropic-news:millisecond-contract",
    ]
    assert items[0].idempotency_key != items[1].idempotency_key
    assert len({item.idempotency_key for item in items}) == expected_count


def _rss_feed(*, entries: tuple[RssEntry, ...], feed_url: str = OPENAI_RSS_URL) -> RssFeed:
    return RssFeed(url=feed_url, fetched_at=FETCHED_AT, entries=entries)


async def _collect_items(events: AsyncIterator[InternalItem]) -> list[InternalItem]:
    return [event async for event in events]


def _read_json(path: Path) -> object:
    return json.loads(path.read_text())


def _stable_dump(item: InternalItem) -> object:
    dumped = item.model_dump(mode="json")
    return json.loads(json.dumps(dumped, sort_keys=True))


def _dump_for_leak_check(item: InternalItem) -> set[str]:
    return set(json.dumps(item.model_dump(mode="json"), sort_keys=True).split('"'))
