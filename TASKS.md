# Shiyi MVP Tasks

Target: run Anthropic and OpenAI blog adapters by Wednesday, 2026-05-13.

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

- [x] Investigate Anthropic blog/news source shape: no official `https://www.anthropic.com/news/rss.xml`; news index HTML is usable, may need source-specific index parser or sitemap check.
- [x] Investigate OpenAI blog/news source shape: RSS available at `https://openai.com/news/rss.xml`; index HTML also usable.
- [ ] Implement Anthropic blog adapter.
- [x] Implement OpenAI blog adapter. (RSS-based)
- [ ] Add adapter contract tests with recorded/minimal fixtures.

## Milestone 4 — End-to-end run

- [ ] Add CLI or script for one-shot capture run.
- [ ] Run Anthropic adapter into local `.shiyi/` workspace.
- [ ] Run OpenAI adapter into local `.shiyi/` workspace.
- [ ] Verify raw artifacts, normalized artifacts, metadata rows, and idempotent re-run behavior.

## Review decisions

- Metadata default: SQLite.
- Artifact default: filesystem.
- Checkpointing: deferred; scheduled capture re-runs use idempotency and metadata status.
- Classification: multi-label tags, not single exclusive category.
- First sources: Anthropic and OpenAI blogs/news.
