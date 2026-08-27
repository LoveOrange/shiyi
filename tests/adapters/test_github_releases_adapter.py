import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from shiyi.adapters.github_releases import (
    github_releases_adapter,
    github_releases_api_url,
    parse_github_releases,
)
from shiyi.domain.models import CaptureWindow, Source, SourceItem, TextPayload
from shiyi.fetchers.fake import FakeWebFetcher

FIXTURE_PATH = (
    Path(__file__).parents[1] / "fixtures" / "deepseek-harness-releases" / "raw" / "releases.json"
)
TARGET = github_releases_api_url("deepseek-ai/deepseek-harness")
FETCHED_AT = datetime(2026, 8, 22, tzinfo=UTC)


def test_github_release_parser_keeps_prereleases_and_excludes_drafts() -> None:
    releases = parse_github_releases(FIXTURE_PATH.read_text())

    assert [release.release_id for release in releases] == ["101", "100"]
    assert all(release.prerelease for release in releases)
    assert releases[0].tag_name == "dsh-v0.1.1-rc.2"
    assert releases[0].published_at == datetime(2026, 8, 21, 12, 35, 8, tzinfo=UTC)


def test_github_release_adapter_emits_complete_body_without_fake_summary() -> None:
    adapter = github_releases_adapter(
        web_fetcher=FakeWebFetcher({TARGET: FIXTURE_PATH.read_text()}, fetched_at=FETCHED_AT),
        window=CaptureWindow(
            since=datetime(2026, 8, 21, tzinfo=UTC),
            until=datetime(2026, 8, 22, tzinfo=UTC),
        ),
    )

    [item] = asyncio.run(_collect_items(adapter.capture(_source())))

    assert item.source_item_id == "101"
    assert item.kind == "release_note"
    assert item.summary is None
    assert item.metadata["prerelease"] is True
    assert item.metadata["tag_name"] == "dsh-v0.1.1-rc.2"
    assert isinstance(item.payload, TextPayload)
    assert "Files API for image uploads" in item.payload.text
    assert str(item.canonical_url).endswith("/releases/tag/dsh-v0.1.1-rc.2")


def test_github_release_parser_rejects_non_array_response() -> None:
    with pytest.raises(TypeError, match="JSON array"):
        parse_github_releases('{"message": "rate limited"}')


def test_github_release_url_requires_owner_and_repository() -> None:
    with pytest.raises(ValueError, match="owner/name"):
        github_releases_api_url("openai")


async def _collect_items(iterator: AsyncIterator[SourceItem]) -> list[SourceItem]:
    return [item async for item in iterator]


def _source() -> Source:
    return Source(
        id="deepseek-harness-releases",
        adapter="github-releases-api",
        target=TARGET,
        options={"content_kind": "release_note"},
    )
