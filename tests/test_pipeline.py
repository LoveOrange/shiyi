import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from shiyi import (
    CaptureConfig,
    CaptureRunner,
    CaptureRunSummary,
    HtmlPayload,
    MarkdownContentProcessor,
    MemoryContentItemStore,
    Source,
    SourceItem,
)

NOW = datetime(2026, 7, 19, tzinfo=UTC)
EXPECTED_SOURCE_COUNT = 2


class SharedXAdapter:
    name = "x"
    version = "1"

    def __init__(
        self,
        *,
        fail_source: str | None = None,
        source_summary: str | None = None,
    ) -> None:
        self.sources: list[str] = []
        self._fail_source = fail_source
        self.source_summary = source_summary

    async def capture(self, source: Source) -> AsyncIterator[SourceItem]:
        self.sources.append(source.id)
        if source.id == self._fail_source:
            message = "source unavailable"
            raise RuntimeError(message)
        yield _source_item(source, summary=self.source_summary)


def test_runner_starts_from_config_and_shares_one_adapter_across_sources() -> None:
    adapter = SharedXAdapter()
    store = MemoryContentItemStore()
    runner = _runner(
        sources=(_source("x:openai", "openai"), _source("x:sama", "sama")),
        adapter=adapter,
        store=store,
    )

    result = _run(runner)

    assert result.processed == EXPECTED_SOURCE_COUNT
    assert result.failed == 0
    assert adapter.sources == ["x:openai", "x:sama"]
    assert {item.source_id for item in store.items.values()} == {"x:openai", "x:sama"}


def test_repeated_run_upserts_one_id_and_skips_unchanged_content() -> None:
    adapter = SharedXAdapter()
    store = MemoryContentItemStore()
    runner = _runner(sources=(_source("x:openai", "openai"),), adapter=adapter, store=store)

    first = _run(runner)
    second = _run(runner)

    assert first.processed == 1
    assert second.skipped == 1
    assert len(store.items) == 1


def test_source_summary_is_promoted_without_ai() -> None:
    store = MemoryContentItemStore()
    runner = _runner(
        sources=(_source("x:openai", "openai"),),
        adapter=SharedXAdapter(source_summary="Official source summary"),
        store=store,
    )

    _run(runner)
    [item] = store.items.values()

    assert item.summary == "Official source summary"
    assert item.summary_language is None


def test_new_source_summary_updates_unchanged_content() -> None:
    adapter = SharedXAdapter()
    store = MemoryContentItemStore()
    runner = _runner(
        sources=(_source("x:openai", "openai"),),
        adapter=adapter,
        store=store,
    )

    first = _run(runner)
    adapter.source_summary = "New official summary"
    second = _run(runner)
    [item] = store.items.values()

    assert first.processed == 1
    assert second.processed == 1
    assert item.summary == "New official summary"


def test_new_source_summary_drops_language_from_old_ai_summary() -> None:
    adapter = SharedXAdapter()
    store = MemoryContentItemStore()
    source = _source("x:openai", "openai")
    _run(_runner(sources=(source,), adapter=adapter, store=store))
    [captured] = store.items.values()
    asyncio.run(
        store.upsert(
            captured.model_copy(
                update={"summary": "AI summary", "summary_language": "zh"},
            )
        )
    )
    adapter.source_summary = "Official source summary"

    _run(_runner(sources=(source,), adapter=adapter, store=store))
    [item] = store.items.values()

    assert item.summary == "Official source summary"
    assert item.summary_language is None


def test_one_source_failure_does_not_block_later_sources() -> None:
    adapter = SharedXAdapter(fail_source="x:bad")
    store = MemoryContentItemStore()
    runner = _runner(
        sources=(_source("x:bad", "bad"), _source("x:openai", "openai")),
        adapter=adapter,
        store=store,
    )

    result = _run(runner)

    assert result.failed == 1
    assert result.processed == 1
    assert [item.source_id for item in store.items.values()] == ["x:openai"]


def _runner(
    *,
    sources: tuple[Source, ...],
    adapter: SharedXAdapter,
    store: MemoryContentItemStore,
) -> CaptureRunner:
    return CaptureRunner(
        config=CaptureConfig(sources=sources),
        adapters=(adapter,),
        processor=MarkdownContentProcessor(clock=lambda: NOW),
        content_store=store,
        clock=lambda: NOW,
    )


def _source(source_id: str, target: str) -> Source:
    return Source(
        id=source_id,
        adapter="x",
        target=target,
        options={"content_kind": "social_post"},
    )


def _source_item(source: Source, *, summary: str | None = None) -> SourceItem:
    return SourceItem(
        source_id=source.id,
        source_item_id="42",
        kind="social_post",
        canonical_url=f"https://x.com/{source.target}/status/42",
        collected_at=NOW,
        published_at=NOW,
        summary=summary,
        payload=HtmlPayload(
            html=f"<article><h1>{source.target} update</h1></article>",
        ),
        metadata={"title": f"{source.target} update", "language": "en"},
    )


def _run(runner: CaptureRunner) -> CaptureRunSummary:
    return asyncio.run(runner.run_once())
