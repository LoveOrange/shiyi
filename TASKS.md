# Shiyi MVP Tasks

Target: ship a usable local MVP that captures Anthropic and OpenAI blog/news content into filesystem artifacts plus SQLite metadata.

## Status summary

- Current state: Anthropic and OpenAI capture both run locally end-to-end.
- MVP completion estimate: ~70%.
- Biggest remaining gap: productization and robustness, not core pipeline feasibility.

## Milestone 1 — Local storage foundation

- [x] Define local storage contracts in code and docs.
- [x] Implement `FileSystemArtifactStore`.
- [x] Implement `SQLiteMetadataStore`.
- [x] Add contract tests for artifact and metadata stores.
- [x] Update pipeline tests to use real local stores.

## Milestone 2 — Article capture foundation

- [x] Add normalizer contract for HTML to canonical Markdown/text.
- [x] Add minimal HTML article normalizer.
- [x] Preserve raw HTML artifact before normalization.
- [x] Store normalized Markdown/text artifact separately.

## Milestone 3 — Blog adapters

- [x] Investigate Anthropic blog/news source shape: no official `https://www.anthropic.com/news/rss.xml`; news index HTML is usable.
- [x] Investigate OpenAI blog/news source shape: RSS available at `https://openai.com/news/rss.xml`; index HTML also usable.
- [x] Implement Anthropic blog adapter. (news index parser)
- [x] Implement OpenAI blog adapter. (RSS-based)
- [ ] Add adapter contract tests with recorded/minimal fixtures.
- [ ] Add source-level smoke tests that assert current public source pages still parse enough items.

## Milestone 4 — End-to-end run

- [x] Add CLI or script for one-shot capture run.
- [x] Run Anthropic adapter into local `.shiyi/` workspace.
- [x] Run OpenAI adapter into local `.shiyi/` workspace.
- [x] Verify raw artifacts, normalized artifacts, metadata rows, and idempotent re-run behavior.

## Milestone 5 — MVP closing work

- [x] Add README quickstart for `uv run shiyi capture`.
- [x] Add CLI tests for `capture --source openai|anthropic`.
- [x] Improve CLI output: JSON summary with processed/events/enrichments/artifacts counts.
- [x] Add metadata query/list command or documented SQLite inspection snippet. (README SQLite snippet)
- [ ] Add source configuration docs: source name, URL, adapter type, limit, workspace.
- [ ] Add minimal real AI provider design spec before implementing provider integrations.
- [ ] Decide whether MVP includes a real LLM provider or ships with local heuristic enrichment only.
- [ ] Add release notes / MVP definition in docs.

## Nice-to-have after MVP

- [ ] Sync tasks to Notion PARA/Product Tasks DB once DB/project mapping is confirmed.
- [ ] Add JSONL export for metadata/debugging.
- [ ] Add retry policy and richer failure status.
- [ ] Add pagination/backfill controls for source adapters.
- [ ] Add stronger article extraction quality tests.

## Review decisions

- Metadata default: SQLite.
- Artifact default: filesystem.
- Checkpointing: deferred; scheduled capture re-runs use idempotency and metadata status.
- Classification: multi-label tags, not single exclusive category.
- First sources: Anthropic and OpenAI blogs/news.
