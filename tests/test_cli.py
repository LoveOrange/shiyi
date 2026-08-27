import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from shiyi import MemoryContentItemStore, Source, SourceItem, TextPayload
from shiyi.cli import _build_parser, run_capture

NOW = datetime(2026, 7, 19, tzinfo=UTC)
DEFAULT_ENRICH_LIMIT = 5


class OpenAIFakeAdapter:
    name = "openai-news-rss"
    version = "test"

    async def capture(self, source: Source) -> AsyncIterator[SourceItem]:
        yield SourceItem(
            source_id=source.id,
            source_item_id="post-1",
            kind="article",
            canonical_url="https://openai.com/news/post-1",
            collected_at=NOW,
            published_at=NOW,
            payload=TextPayload(text="Post title\n\nPost body"),
            metadata={"title": "Post title", "is_complete": True},
        )


def test_capture_parser_accepts_multiple_sources() -> None:
    args = _build_parser().parse_args(
        [
            "capture",
            "--source",
            "openai",
            "--source",
            "anthropic",
            "--operator-snapshot-manifest",
            "snapshots/manifest.json",
        ]
    )

    assert args.source == ["openai", "anthropic"]
    assert args.operator_snapshot_manifest == Path("snapshots/manifest.json")


def test_enrich_parser_requires_an_explicit_provider() -> None:
    args = _build_parser().parse_args(
        ["enrich", "--provider", "codex-cli", "--summary-language", "zh"]
    )

    assert args.provider == "codex-cli"
    assert args.limit == DEFAULT_ENRICH_LIMIT
    assert args.summary_language == "zh"


def test_run_capture_uses_configured_source_and_injected_canonical_store(tmp_path: Path) -> None:
    store = MemoryContentItemStore()

    summary = asyncio.run(
        run_capture(
            sources=("openai",),
            workspace=tmp_path,
            content_store=store,
            adapters=(OpenAIFakeAdapter(),),
        )
    )

    assert summary.processed == 1
    assert summary.sources == ("openai",)
    [item] = store.items.values()
    assert item.source_id == "openai-news"
    assert item.title == "Post title"
    assert json.loads(item.model_dump_json())["creators"] == []
