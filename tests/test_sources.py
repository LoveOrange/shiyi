from datetime import UTC, datetime

from shiyi import (
    BUILTIN_SOURCES,
    CaptureWindow,
    build_capture_config,
    build_source_adapters,
    source_summaries,
)


def test_builtin_capture_config_is_declarative_and_unique() -> None:
    config = build_capture_config(("openai", "anthropic"))

    assert [source.id for source in config.sources] == ["openai-news", "anthropic-news"]
    assert [source.target for source in config.sources] == [
        "https://openai.com/news/rss.xml",
        "https://www.anthropic.com/news",
    ]


def test_adapter_factories_match_the_adapter_selected_by_source() -> None:
    config = build_capture_config(tuple(source.name for source in BUILTIN_SOURCES))
    adapters = build_source_adapters(
        config,
        window=CaptureWindow(
            since=datetime(2026, 7, 18, tzinfo=UTC),
            until=datetime(2026, 7, 19, tzinfo=UTC),
        ),
    )

    assert {adapter.name for adapter in adapters} == {
        source.source.adapter for source in BUILTIN_SOURCES
    }


def test_source_summaries_do_not_expose_planning_or_downstream_models() -> None:
    [first, *rest] = source_summaries()

    assert first.id == "openai-news"
    assert rest
    dumped = repr(source_summaries()).lower()
    assert "opportunity" not in dumped
    assert "admission" not in dumped
    assert "backlog" not in dumped


def test_harness_release_sources_are_registered_as_release_notes() -> None:
    names = (
        "openclaw-releases",
        "hermes-agent-releases",
        "deepseek-harness-releases",
        "codex-releases",
        "claude-code-releases",
        "google-antigravity-changelog",
    )

    config = build_capture_config(names)

    assert [source.id for source in config.sources] == list(names)
    assert all(source.options["content_kind"] == "release_note" for source in config.sources)
