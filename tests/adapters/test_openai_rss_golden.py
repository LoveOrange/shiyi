import asyncio
import json
from pathlib import Path

from shiyi import Adapter, InternalItem, openai_news_adapter
from shiyi.fetchers.fake import FakeRssFetcher
from shiyi.ports.fetcher import RssFeed

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "openai-news"
OPENAI_RSS_URL = "https://openai.com/news/rss.xml"


def test_openai_rss_fixture_matches_internal_item_golden_output() -> None:
    feed = RssFeed.model_validate_json((FIXTURE_ROOT / "raw" / "feed.json").read_text())
    adapter = openai_news_adapter(rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: feed}))

    items = asyncio.run(_collect_internal_items(adapter))

    assert [_stable_dump(item) for item in items] == [
        _read_json(FIXTURE_ROOT / "internal-item" / "running-codex-safely.json")
    ]


def test_openai_rss_adapter_keeps_idempotency_stable_and_non_colliding() -> None:
    feed = RssFeed.model_validate_json((FIXTURE_ROOT / "raw" / "feed.json").read_text())
    replay_adapter = openai_news_adapter(rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: feed}))
    changed_feed = feed.model_copy(
        update={
            "entries": (feed.entries[0].model_copy(update={"entry_id": "different-logical-event"}),)
        }
    )
    changed_adapter = openai_news_adapter(
        rss_fetcher=FakeRssFetcher({OPENAI_RSS_URL: changed_feed})
    )

    replay_items = asyncio.run(_collect_internal_items(replay_adapter))
    changed_items = asyncio.run(_collect_internal_items(changed_adapter))

    assert replay_items[0].idempotency_key == "openai-news:running-codex-safely"
    assert changed_items[0].idempotency_key == "openai-news:different-logical-event"
    assert replay_items[0].idempotency_key != changed_items[0].idempotency_key


async def _collect_internal_items(adapter: Adapter) -> list[InternalItem]:
    return [item async for item in adapter.discover()]


def _read_json(path: Path) -> object:
    return json.loads(path.read_text())


def _stable_dump(item: InternalItem) -> object:
    dumped = item.model_dump(mode="json")
    return json.loads(json.dumps(dumped, sort_keys=True))
