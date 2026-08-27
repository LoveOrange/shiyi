import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from shiyi.adapters.antigravity import (
    ANTIGRAVITY_CHANGELOG_URL,
    antigravity_changelog_adapter,
    parse_antigravity_changelog,
)
from shiyi.domain.models import CaptureWindow, Source, SourceItem, TextPayload
from shiyi.fetchers.fake import FakeWebFetcher

FIXTURE_PATH = (
    Path(__file__).parents[1]
    / "fixtures"
    / "google-antigravity-changelog"
    / "raw"
    / "changelog.html"
)
FETCHED_AT = datetime(2026, 8, 22, tzinfo=UTC)


def test_antigravity_parser_covers_product_and_cli_panels() -> None:
    entries = parse_antigravity_changelog(FIXTURE_PATH.read_text())

    assert [entry.entry_id for entry in entries] == ["hub:2.9.1", "cli:1.1.16"]
    assert entries[0].title.startswith("Antigravity 2.0 2.9.1")
    assert entries[0].occurred_at == datetime(2026, 8, 20, tzinfo=UTC)
    assert entries[0].link == ("https://www.antigravity.google/releases?tab=hub&version=2.9.1")
    assert "browser-based Remote Control" in entries[0].body


def test_antigravity_adapter_honors_window_across_product_panels() -> None:
    adapter = antigravity_changelog_adapter(
        web_fetcher=FakeWebFetcher(
            {ANTIGRAVITY_CHANGELOG_URL: FIXTURE_PATH.read_text()},
            fetched_at=FETCHED_AT,
        ),
        window=CaptureWindow(
            since=datetime(2026, 8, 20, tzinfo=UTC),
            until=datetime(2026, 8, 21, tzinfo=UTC),
        ),
    )

    [item] = asyncio.run(_collect_items(adapter.capture(_source())))

    assert item.source_item_id == "hub:2.9.1"
    assert item.summary is None
    assert item.metadata["is_complete"] is True
    assert isinstance(item.payload, TextPayload)
    assert "Remote Control for local agent sessions" in item.payload.text


async def _collect_items(iterator: AsyncIterator[SourceItem]) -> list[SourceItem]:
    return [item async for item in iterator]


def _source() -> Source:
    return Source(
        id="google-antigravity-changelog",
        adapter="google-antigravity-changelog-page",
        target=ANTIGRAVITY_CHANGELOG_URL,
        options={"content_kind": "release_note"},
    )
