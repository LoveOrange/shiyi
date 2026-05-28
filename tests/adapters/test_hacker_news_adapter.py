import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from shiyi.adapters.hacker_news import (
    HACKER_NEWS_ITEM_URL_TEMPLATE,
    HACKER_NEWS_TOP_STORIES_URL,
    hacker_news_topstories_adapter,
)
from shiyi.domain.models import CaptureWindow, HtmlPayload, InternalItem
from shiyi.fetchers.fake import FakeWebFetcher

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "hacker-news"
FETCHED_AT = datetime(2026, 5, 14, 8, 30, tzinfo=UTC)


def test_hacker_news_topstory_raw_payload_maps_to_valid_internal_item() -> None:
    adapter = hacker_news_topstories_adapter(
        limit=1,
        web_fetcher=_fixture_fetcher(),
    )

    [item] = asyncio.run(_collect_items(adapter.discover()))

    assert InternalItem.model_validate(item.model_dump(mode="json")) == item
    assert item.id == "hacker-news:44123456"
    assert item.source.kind == "hacker-news"
    assert str(item.source.uri) == "https://news.ycombinator.com/item?id=44123456"
    assert item.captured_at == FETCHED_AT
    assert item.occurred_at == datetime(2026, 5, 13, 15, 20, tzinfo=UTC)
    assert item.provenance.adapter_name == "hacker-news-topstories-api"
    assert item.provenance.source_item_id == "44123456"
    assert item.idempotency_key == "hacker-news:44123456"
    assert item.metadata == {
        "title": "Show HN: Agentic code review traces for AI teams",
        "link": "https://example.com/agentic-code-review-traces",
        "content_depth": "complete",
        "upstream_id": "44123456",
        "canonical_discussion_url": "https://news.ycombinator.com/item?id=44123456",
        "external_target_url": "https://example.com/agentic-code-review-traces",
        "source_metrics": {"score": 512, "descendants": 128, "rank": 1},
    }
    assert isinstance(item.payload, HtmlPayload)
    assert str(item.payload.url) == "https://news.ycombinator.com/item?id=44123456"
    assert "Hacker News discussion" in item.payload.html
    assert "score=512; descendants=128; rank=1" in item.payload.html
    assert _dump_for_leak_check(item).isdisjoint({"kids", "by", "raw_payload"})


def test_hacker_news_window_filter_runs_after_required_time_and_before_emit() -> None:
    topstories = json.dumps([44123456, 44123457])
    pages = {
        HACKER_NEWS_TOP_STORIES_URL: topstories,
        HACKER_NEWS_ITEM_URL_TEMPLATE.format(item_id=44123456): _fixture_item(),
        HACKER_NEWS_ITEM_URL_TEMPLATE.format(item_id=44123457): json.dumps(
            {
                "id": 44123457,
                "type": "story",
                "time": 1778578200,
                "title": "Older HN story",
                "url": "https://example.com/older",
                "score": 12,
                "descendants": 3,
            }
        ),
    }
    adapter = hacker_news_topstories_adapter(
        web_fetcher=FakeWebFetcher(pages, fetched_at=FETCHED_AT),
        window=CaptureWindow(
            since=datetime(2026, 5, 13, tzinfo=UTC),
            until=datetime(2026, 5, 14, tzinfo=UTC),
        ),
    )

    items = asyncio.run(_collect_items(adapter.discover()))

    assert [item.idempotency_key for item in items] == ["hacker-news:44123456"]


def test_hacker_news_dead_deleted_or_non_story_items_fail_closed_without_emit() -> None:
    pages = {
        HACKER_NEWS_TOP_STORIES_URL: json.dumps([1, 2, 3]),
        HACKER_NEWS_ITEM_URL_TEMPLATE.format(item_id=1): json.dumps(
            {"id": 1, "type": "story", "time": 1778685600, "title": "Dead", "dead": True}
        ),
        HACKER_NEWS_ITEM_URL_TEMPLATE.format(item_id=2): json.dumps(
            {"id": 2, "type": "story", "time": 1778685600, "title": "Deleted", "deleted": True}
        ),
        HACKER_NEWS_ITEM_URL_TEMPLATE.format(item_id=3): json.dumps(
            {"id": 3, "type": "comment", "time": 1778685600, "text": "Comment"}
        ),
    }
    adapter = hacker_news_topstories_adapter(
        web_fetcher=FakeWebFetcher(pages, fetched_at=FETCHED_AT),
    )

    assert asyncio.run(_collect_items(adapter.discover())) == []


def test_hacker_news_missing_required_fields_fail_clearly() -> None:
    pages = {
        HACKER_NEWS_TOP_STORIES_URL: json.dumps([44123456]),
        HACKER_NEWS_ITEM_URL_TEMPLATE.format(item_id=44123456): json.dumps(
            {"id": 44123456, "type": "story", "time": 1778685600}
        ),
    }
    adapter = hacker_news_topstories_adapter(
        web_fetcher=FakeWebFetcher(pages, fetched_at=FETCHED_AT),
    )

    with pytest.raises(ValueError, match="HN item 44123456 missing required text field title"):
        asyncio.run(_collect_items(adapter.discover()))


def test_hacker_news_topstories_shape_fails_closed() -> None:
    adapter = hacker_news_topstories_adapter(
        web_fetcher=FakeWebFetcher(
            {HACKER_NEWS_TOP_STORIES_URL: json.dumps({"not": "a list"})},
            fetched_at=FETCHED_AT,
        ),
    )

    with pytest.raises(ValueError, match="topstories response"):
        asyncio.run(_collect_items(adapter.discover()))


def _fixture_fetcher() -> FakeWebFetcher:
    return FakeWebFetcher(
        {
            HACKER_NEWS_TOP_STORIES_URL: (FIXTURE_ROOT / "raw" / "topstories.json").read_text(),
            HACKER_NEWS_ITEM_URL_TEMPLATE.format(item_id=44123456): _fixture_item(),
        },
        fetched_at=FETCHED_AT,
    )


def _fixture_item() -> str:
    return (FIXTURE_ROOT / "raw" / "44123456.json").read_text()


async def _collect_items(iterator: AsyncIterator[InternalItem]) -> list[InternalItem]:
    return [item async for item in iterator]


def _dump_for_leak_check(item: InternalItem) -> set[str]:
    return set(json.dumps(item.model_dump(mode="json"), sort_keys=True).split('"'))
