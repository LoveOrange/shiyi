import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from shiyi import Adapter, InternalItem, anthropic_news_adapter
from shiyi.adapters.anthropic import ANTHROPIC_NEWS_URL
from shiyi.ports.fetcher import FetchResult

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "anthropic-news"
CLAUDE_DESIGN_URL = "https://www.anthropic.com/news/claude-design-anthropic-labs"
PROJECT_GLASSWING_URL = "https://www.anthropic.com/news/project-glasswing"


@dataclass(frozen=True)
class FetchCall:
    url: str
    source: str | None
    raw_key: str | None


class FixtureWebFetcher:
    def __init__(self) -> None:
        self.calls: list[FetchCall] = []
        self.pages = {
            ANTHROPIC_NEWS_URL: (FIXTURE_ROOT / "raw" / "index.html").read_text(),
            CLAUDE_DESIGN_URL: (
                FIXTURE_ROOT / "raw" / "claude-design-anthropic-labs.html"
            ).read_text(),
            PROJECT_GLASSWING_URL: """
            <html><head>
              <title>Project Glasswing</title>
              <meta property="article:published_time" content="2026-05-13T10:00:00Z">
            </head><body><h1>Project Glasswing</h1></body></html>
            """,
        }

    async def fetch(
        self,
        url: str,
        *,
        source: str | None = None,
        raw_key: str | None = None,
    ) -> FetchResult:
        self.calls.append(FetchCall(url=url, source=source, raw_key=raw_key))
        return FetchResult(
            url=url,
            status_code=200,
            content=self.pages[url],
            fetched_at=datetime(2026, 5, 14, tzinfo=UTC),
        )


def test_anthropic_fixture_matches_internal_item_golden_output() -> None:
    fetcher = FixtureWebFetcher()
    adapter = anthropic_news_adapter(limit=1, web_fetcher=fetcher)

    items = asyncio.run(_collect_internal_items(adapter))

    assert [_stable_dump(item) for item in items] == [
        _read_json(FIXTURE_ROOT / "internal-item" / "claude-design-anthropic-labs.json")
    ]
    assert [call.url for call in fetcher.calls] == [ANTHROPIC_NEWS_URL, CLAUDE_DESIGN_URL]
    assert fetcher.calls[1].source == "anthropic-news"
    assert fetcher.calls[1].raw_key is not None


def test_anthropic_adapter_deduplicates_index_links_and_keeps_idempotency_stable() -> None:
    first_fetcher = FixtureWebFetcher()
    second_fetcher = FixtureWebFetcher()

    first_items = asyncio.run(
        _collect_internal_items(anthropic_news_adapter(limit=1, web_fetcher=first_fetcher))
    )
    second_items = asyncio.run(
        _collect_internal_items(anthropic_news_adapter(limit=1, web_fetcher=second_fetcher))
    )

    assert first_items[0].idempotency_key == second_items[0].idempotency_key
    assert first_items[0].content_hash == second_items[0].content_hash
    assert [call.url for call in first_fetcher.calls] == [ANTHROPIC_NEWS_URL, CLAUDE_DESIGN_URL]


async def _collect_internal_items(adapter: Adapter) -> list[InternalItem]:
    return [item async for item in adapter.discover()]


def _read_json(path: Path) -> object:
    return json.loads(path.read_text())


def _stable_dump(item: InternalItem) -> object:
    dumped = item.model_dump(mode="json")
    return json.loads(json.dumps(dumped, sort_keys=True))
