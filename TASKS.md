# Shiyi MVP Tasks

Target: run Anthropic and OpenAI blog adapters by Wednesday, 2026-05-13.

## Milestone 1 — Local storage foundation

- [x] Define local storage contracts in code and docs.
- [x] Implement `FileSystemArtifactStore`.
- [x] Implement `SQLiteMetadataStore`.
- [x] Add contract tests for artifact and metadata stores.
- [ ] Update pipeline tests to use real local stores. (fake stores still used; real-store integration test next)

## Milestone 2 — Article capture foundation

- [ ] Add normalizer contract for HTML to canonical Markdown/text.
- [ ] Add minimal HTML article normalizer.
- [ ] Preserve raw HTML artifact before normalization.
- [ ] Store normalized Markdown/text artifact separately.

## Milestone 3 — Blog adapters

- [ ] Investigate Anthropic blog/news source shape: RSS, sitemap, index HTML, article HTML.
- [ ] Investigate OpenAI blog/news source shape: RSS, sitemap, index HTML, article HTML.
- [ ] Implement Anthropic blog adapter.
- [ ] Implement OpenAI blog adapter.
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
