# Shiyi MVP Definition

## MVP promise

The MVP proves that Shiyi can capture article-like information from real public sources into a local, inspectable, replay-safe workspace.

A successful MVP run must:

1. Capture OpenAI news content.
2. Capture Anthropic news content.
3. Preserve raw source HTML or feed content as filesystem artifacts.
4. Normalize HTML into Markdown artifacts.
5. Store metadata and enrichment references in SQLite.
6. Produce deterministic CLI summaries.
7. Skip already-enriched records on re-run using idempotency keys.
8. List captured metadata from the CLI.
9. Pass local and CI quality gates.

## Included in MVP

- Python package with strict typing and tests.
- Filesystem artifact store.
- SQLite metadata store.
- HTML-to-Markdown normalizer.
- OpenAI RSS adapter.
- Anthropic news index adapter.
- Local heuristic enrichment provider.
- One-shot CLI capture command.
- README quickstart.
- Metadata listing CLI.

## Not included in MVP

- Real LLM provider integration.
- Hosted service or web UI.
- Scheduler/daemon mode.
- Checkpoint store.
- Search or vector index.
- Notion/PARA sync.
- Broad web crawler.

## Exit criteria

The MVP is ready when these commands work on a clean checkout:

```bash
uv sync
uv run shiyi capture --source openai --workspace .shiyi/openai --max-items 2
uv run shiyi capture --source anthropic --workspace .shiyi/anthropic --max-items 2
uv run shiyi list --workspace .shiyi/openai
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

A second capture run for the same source and workspace should report `"processed": 0`.

## Live source smoke tests

Public-source smoke tests are opt-in so normal CI remains deterministic:

```bash
SHIYI_RUN_LIVE_TESTS=1 uv run pytest tests/live/test_public_sources.py
```

These tests verify that the current Anthropic news index still exposes article links and that the OpenAI RSS feed is reachable.


## Post-MVP v0.2 hardening

Shiyi now supports explicit capture windows for daily/backfill workflows:

```bash
uv run shiyi capture --source openai --workspace .shiyi/openai --since 2026-05-10 --until 2026-05-13 --max-items 100
```

`--since` is inclusive and `--until` is exclusive. Daily jobs should use a 2-3 day overlap window and rely on idempotency to avoid duplicate processing.

Fetching/crawling concerns now live behind shared fetchers (`WebFetcher`, `RssFetcher`, `SitemapFetcher`) so adapters focus on source-specific parsing and mapping.
