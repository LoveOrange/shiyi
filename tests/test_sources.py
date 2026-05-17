import pytest

from shiyi import (
    BUILTIN_SOURCE_NAMES,
    SOURCE_BACKLOG,
    SourceName,
    build_source_adapter,
    iter_builtin_sources,
    source_definition,
    source_summaries,
)
from shiyi.domain.models import CaptureWindow


def test_source_registry_covers_builtin_source_name_enum() -> None:
    assert tuple(source.value for source in SourceName) == BUILTIN_SOURCE_NAMES
    assert tuple(source.name.value for source in iter_builtin_sources()) == BUILTIN_SOURCE_NAMES


def test_source_registry_builds_adapter_without_cli_branching() -> None:
    adapter = build_source_adapter(
        "microsoft-ai-blog",
        window=CaptureWindow(max_items=1),
    )

    assert adapter.name == "microsoft-ai-blog-rss"
    assert source_definition("microsoft-ai-blog").source_kind == "microsoft-ai-blog"


def test_source_registry_summaries_expose_builtin_metadata_without_factories() -> None:
    summaries = source_summaries()

    microsoft = next(summary for summary in summaries if summary.name == "microsoft-ai-blog")
    openai = next(summary for summary in summaries if summary.name == "openai")
    assert microsoft.status == "built-in"
    assert microsoft.default_content_depth == "feed_full_content"
    assert microsoft.source_ready is True
    assert openai.source_ready is False
    assert all(not hasattr(summary, "factory") for summary in summaries)


def test_source_registry_handoff_backlog_separates_deferred_sources() -> None:
    summaries = source_summaries(include_backlog=True)

    assert {item.name for item in SOURCE_BACKLOG} <= {summary.name for summary in summaries}
    qwen = next(summary for summary in summaries if summary.name == "qwen-research")
    community = next(
        summary for summary in summaries if summary.name == "github-trending-or-community-feeds"
    )
    assert qwen.status == "deferred"
    assert qwen.bucket == "p3-json-api-fetcher"
    assert community.bucket == "later-high-noise"


def test_source_registry_rejects_unknown_source() -> None:
    with pytest.raises(ValueError, match="unknown source"):
        source_definition("not-a-source")
