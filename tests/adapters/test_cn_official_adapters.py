import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from shiyi.adapters.cn_official import (
    KIMI_CODE_CHANGELOG_URL,
    KIMI_RESEARCH_URL,
    kimi_code_changelog_adapter,
    parse_bigmodel_releases,
    parse_kimi_code_changelog,
    parse_kimi_research_index,
    parse_minimax_api_updates,
    parse_minimax_model_releases,
    parse_qwen_code_blog_index,
    parse_qwen_model_releases,
)
from shiyi.domain.models import CaptureWindow, Source
from shiyi.fetchers.fake import FakeWebFetcher

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures"


def _fixture(source_id: str, name: str) -> str:
    return (FIXTURE_ROOT / source_id / "raw" / name).read_text()


def test_kimi_research_index_uses_canonical_article_identity() -> None:
    entries = parse_kimi_research_index(_fixture("kimi-research", "index.html"))

    assert [(entry.entry_id, entry.link, entry.occurred_at) for entry in entries] == [
        (
            "kimi-k3",
            "https://www.kimi.com/blog/kimi-k3",
            datetime(2026, 7, 16, tzinfo=UTC),
        )
    ]


def test_kimi_code_emits_one_stable_item_per_release() -> None:
    entries = parse_kimi_code_changelog(_fixture("kimi-code-changelog", "changelog.html"))

    assert [entry.entry_id for entry in entries] == [
        "v0-31-0-2026-年-7-月-30-日",
        "v0-30-0-2026-年-7-月-29-日",
    ]
    assert entries[0].occurred_at == datetime(2026, 7, 30, tzinfo=UTC)
    assert entries[0].link == (f"{KIMI_CODE_CHANGELOG_URL}#v0-31-0-2026-年-7-月-30-日")


@pytest.mark.parametrize(
    ("parser", "source_id", "fixture_name", "expected_title", "expected_date"),
    (
        (
            parse_qwen_model_releases,
            "qwen-model-releases",
            "models.md",
            "qwen3.8-max",
            datetime(2026, 8, 3, tzinfo=UTC),
        ),
        (
            parse_qwen_code_blog_index,
            "qwen-code-blog",
            "index.html",
            "Qwen Code Weekly: Agent Skills",
            datetime(2026, 7, 30, tzinfo=UTC),
        ),
        (
            parse_bigmodel_releases,
            "zhipu-bigmodel-releases",
            "new-releases.md",
            "GLM-5.2 新一代旗舰模型上线",
            datetime(2026, 6, 16, tzinfo=UTC),
        ),
        (
            parse_minimax_model_releases,
            "minimax-model-releases",
            "models.md",
            "MiniMax H3",
            datetime(2026, 7, 31, tzinfo=UTC),
        ),
        (
            parse_minimax_api_updates,
            "minimax-api-updates",
            "apis.md",
            "MiniMax API 更新 — 2026-07-28",
            datetime(2026, 7, 28, tzinfo=UTC),
        ),
    ),
)
def test_cn_release_parsers_preserve_title_and_objective_date(
    parser: object,
    source_id: str,
    fixture_name: str,
    expected_title: str,
    expected_date: datetime,
) -> None:
    entries = parser(_fixture(source_id, fixture_name))  # type: ignore[operator]

    assert entries[0].title == expected_title
    assert entries[0].occurred_at == expected_date
    assert entries[0].link.startswith("https://")


def test_cn_changelog_adapter_honors_capture_window() -> None:
    fetcher = FakeWebFetcher(
        {KIMI_CODE_CHANGELOG_URL: _fixture("kimi-code-changelog", "changelog.html")}
    )
    adapter = kimi_code_changelog_adapter(
        window=CaptureWindow(
            since=datetime(2026, 7, 30, tzinfo=UTC),
            until=datetime(2026, 7, 31, tzinfo=UTC),
        ),
        web_fetcher=fetcher,
    )
    source = Source(
        id="kimi-code-changelog",
        adapter=adapter.name,
        target=KIMI_CODE_CHANGELOG_URL,
        options={"content_kind": "release_note"},
    )

    async def capture_ids() -> list[str]:
        return [item.source_item_id async for item in adapter.capture(source)]

    assert asyncio.run(capture_ids()) == ["v0-31-0-2026-年-7-月-30-日"]
    assert KIMI_RESEARCH_URL == "https://www.kimi.com/en/blog/"
