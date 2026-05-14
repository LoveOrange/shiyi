import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import NamedTuple, get_args

import pytest

from shiyi import Adapter, InternalItem, anthropic_news_adapter, openai_news_adapter
from shiyi.adapters.anthropic import ANTHROPIC_NEWS_URL
from shiyi.cli import SourceName
from shiyi.domain.models import CaptureWindow, HtmlPayload, TextPayload
from shiyi.fetchers.fake import FakeRssFetcher, FakeWebFetcher
from shiyi.ports.fetcher import RssEntry, RssFeed

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"
OPENAI_FIXTURE_ROOT = FIXTURE_ROOT / "openai-news"
ANTHROPIC_FIXTURE_ROOT = FIXTURE_ROOT / "anthropic-news"
OPENAI_RSS_URL = "https://openai.com/news/rss.xml"
CLAUDE_DESIGN_URL = "https://www.anthropic.com/news/claude-design-anthropic-labs"
ANTHROPIC_MINIMAL_URL = "https://www.anthropic.com/news/minimal-contract"
ANTHROPIC_SECOND_URL = "https://www.anthropic.com/news/second-contract"
ANTHROPIC_MILLISECOND_URL = "https://www.anthropic.com/news/millisecond-contract"
FETCHED_AT = datetime(2026, 5, 14, 8, 30, tzinfo=UTC)


class ContractCase(NamedTuple):
    source_name: SourceName
    build_adapter: Callable[[], Adapter]
    expected_paths: tuple[Path, ...]


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


def test_openai_rss_minimal_raw_payload_maps_to_valid_internal_item() -> None:
    feed = _rss_feed(
        entries=(
            RssEntry(
                entry_id="minimal-rss-entry",
                title="Minimal RSS Entry",
                link=None,
                html="",
                published_at=None,
            ),
        )
    )
    adapter = openai_news_adapter(rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: feed}))

    items = asyncio.run(_collect_items(adapter.discover()))

    assert len(items) == 1
    item = InternalItem.model_validate(items[0].model_dump(mode="json"))
    assert item.id == "openai-news:minimal-rss-entry"
    assert item.source.kind == "openai-news"
    assert item.source.uri is not None
    assert item.source.account_id is None
    assert item.captured_at == FETCHED_AT
    assert item.occurred_at == FETCHED_AT
    assert item.provenance.source_item_id == "minimal-rss-entry"
    assert item.provenance.adapter_name == "openai-news-rss"
    assert item.metadata == {"title": "Minimal RSS Entry", "link": None}
    assert item.payload == TextPayload(text="Minimal RSS Entry")
    assert _dump_for_leak_check(item).isdisjoint({"raw_payload", "rss_guid", "feedparser"})


@pytest.mark.parametrize(
    ("entry", "message"),
    [
        (
            RssEntry(
                entry_id="",
                title="Missing external id",
                link="https://openai.com/missing-id",
                html="<p>body</p>",
                published_at=FETCHED_AT,
            ),
            "RSS entry missing required entry_id",
        ),
        (
            RssEntry(
                entry_id="missing-title",
                title="",
                link="https://openai.com/missing-title",
                html="<p>body</p>",
                published_at=FETCHED_AT,
            ),
            "RSS entry missing required title for RSS entry missing-title",
        ),
    ],
)
def test_openai_rss_missing_required_fields_fail_clearly(
    entry: RssEntry,
    message: str,
) -> None:
    feed = _rss_feed(entries=(entry,))
    adapter = openai_news_adapter(rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: feed}))

    with pytest.raises(ValueError, match=message):
        asyncio.run(_collect_items(adapter.discover()))


def test_openai_rss_filters_out_of_window_entries_before_required_field_validation() -> None:
    feed = _rss_feed(
        entries=(
            RssEntry(
                entry_id="old-invalid-entry",
                title="",
                link="https://openai.com/old-invalid-entry",
                html="<article>old invalid body</article>",
                published_at=datetime(2026, 5, 11, tzinfo=UTC),
            ),
            RssEntry(
                entry_id="valid-in-window",
                title="Valid In Window",
                link="https://openai.com/valid-in-window",
                html="<article>valid body</article>",
                published_at=datetime(2026, 5, 12, 12, tzinfo=UTC),
            ),
        )
    )
    adapter = openai_news_adapter(
        rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: feed}),
        window=CaptureWindow(
            since=datetime(2026, 5, 12, tzinfo=UTC),
            until=datetime(2026, 5, 13, tzinfo=UTC),
        ),
    )

    items = asyncio.run(_collect_items(adapter.discover()))

    assert [item.idempotency_key for item in items] == ["openai-news:valid-in-window"]


def test_openai_rss_timestamp_and_idempotency_contract_is_stable() -> None:
    occurred_at = datetime(2026, 5, 12, 18, 45, 0, 123000, tzinfo=timezone(timedelta(hours=8)))
    first = RssEntry(
        entry_id="timezone-entry",
        title="Timezone Entry",
        link="https://openai.com/timezone-entry",
        html="<article>timezone body</article>",
        published_at=occurred_at,
    )
    second = first.model_copy(
        update={
            "entry_id": "distinct-entry",
            "title": "Distinct Entry",
            "link": "https://openai.com/distinct-entry",
            "html": "<article>distinct body</article>",
        }
    )
    feed = _rss_feed(entries=(first, second))
    adapter = openai_news_adapter(rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: feed}))

    items = asyncio.run(_collect_items(adapter.discover()))

    expected_count = 2
    assert len(items) == expected_count
    assert items[0].occurred_at == occurred_at
    assert items[0].idempotency_key == "openai-news:timezone-entry"
    assert items[1].idempotency_key == "openai-news:distinct-entry"
    assert items[0].idempotency_key != items[1].idempotency_key
    assert items[0].content_hash != items[1].content_hash
    assert isinstance(items[0].payload, HtmlPayload)
    assert str(items[0].payload.url) == "https://openai.com/timezone-entry"


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
    assert item.metadata == {"title": "Minimal Anthropic Item", "link": ANTHROPIC_MINIMAL_URL}
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


def _rss_feed(*, entries: tuple[RssEntry, ...]) -> RssFeed:
    return RssFeed(url=OPENAI_RSS_URL, fetched_at=FETCHED_AT, entries=entries)


async def _collect_items(events: AsyncIterator[InternalItem]) -> list[InternalItem]:
    return [event async for event in events]


def _read_json(path: Path) -> object:
    return json.loads(path.read_text())


def _stable_dump(item: InternalItem) -> object:
    dumped = item.model_dump(mode="json")
    return json.loads(json.dumps(dumped, sort_keys=True))


def _dump_for_leak_check(item: InternalItem) -> set[str]:
    return set(json.dumps(item.model_dump(mode="json"), sort_keys=True).split('"'))
