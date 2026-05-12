# Shiyi Tasks

Target: ship and evolve a usable local information-capture pipeline for Anthropic and OpenAI blog/news content.

## Status summary

- Current state: local MVP is complete for the defined scope.
- MVP completion estimate: 100% for local MVP.
- Next focus: post-MVP architecture hardening for production-like daily capture.
- Current priority theme: pipeline SDD review, daily capture operations, and adapter robustness.

## Milestone 1 — Local storage foundation

- [x] Define local storage contracts in code and docs.
- [x] Implement `FileSystemArtifactStore`.
- [x] Implement `SQLiteEventRecordStore`.
- [x] Add contract tests for artifact and event record stores.
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
- [x] Add adapter contract tests with recorded/minimal fixtures.
- [x] Add source-level smoke tests that assert current public source pages still parse enough items. (opt-in live tests)

## Milestone 4 — End-to-end run

- [x] Add CLI or script for one-shot capture run.
- [x] Run Anthropic adapter into local `.shiyi/` workspace.
- [x] Run OpenAI adapter into local `.shiyi/` workspace.
- [x] Verify raw artifacts, normalized artifacts, event record rows, and idempotent re-run behavior.

## Milestone 5 — MVP closing work

- [x] Add README quickstart for `uv run shiyi capture`.
- [x] Add CLI tests for `capture --source openai|anthropic`.
- [x] Improve CLI output: JSON summary with processed/events/enrichments/artifacts counts.
- [x] Add event record query/list command or documented SQLite inspection snippet. (README SQLite snippet)
- [x] Add event record listing CLI.
- [x] Add source configuration docs: source name, URL, adapter type, limit, workspace. (README quickstart + built-in sources)
- [x] Add minimal real AI provider design spec before implementing provider integrations.
- [x] Decide whether MVP includes a real LLM provider or ships with local heuristic enrichment only. (MVP ships local heuristic only)
- [x] Add release notes / MVP definition in docs.

## Priority plan — Post-MVP v0.2

### P0 — Capture window semantics

Goal: make daily and backfill capture safe without relying on arbitrary `limit`.

- [x] Add `CaptureWindow` domain model with `since`, `until`, and optional `max_items`.
- [x] Add CLI flags: `--since`, `--until`, `--max-items`.
- [x] Keep `--limit` only as a debug/smoke alias or deprecate it in favor of `--max-items`.
- [x] Define default daily window behavior: overlap last 2-3 days and rely on idempotency to skip already-enriched items.
- [x] Define initial backfill behavior: explicit `--since` plus optional `--max-items` safety cap.
- [x] Update OpenAI RSS adapter to filter by feed item `published` / `updated` date.
- [x] Update Anthropic adapter to derive dates from article page, sitemap `lastmod`, or index metadata.
- [x] Add tests for date-window filtering, inclusive/exclusive boundaries, and idempotent overlap reruns.

### P0 — Shared fetcher infrastructure

Goal: move crawling/fetching concerns below adapters so rate limiting, retry, timeout, and user-agent policy are centralized.

- [x] Add fetcher SDD: WebFetcher, RSSFetcher, SitemapFetcher, FetchResult, rate-limit policy, retry policy.
- [x] Add `ports/fetcher.py` contracts.
- [x] Implement `HttpWebFetcher` with shared `httpx.AsyncClient`, timeout, user-agent, and minimal retry.
- [x] Implement `RssFetcher` on top of WebFetcher + feed parsing.
- [x] Implement `SitemapFetcher` for sitemap URL discovery and `lastmod` extraction.
- [x] Move direct `httpx` calls out of OpenAI and Anthropic adapters.
- [x] Refactor adapters to do only source-specific parsing, mapping, idempotency keys, and metadata construction.
- [x] Add fetcher contract tests and adapter tests using fake fetchers.

### P1 — Pipeline specification review

Goal: make pipeline stage boundaries, status transitions, and replay semantics reviewable before adding more operational behavior.

- [x] Rewrite `docs/specs/capture-pipeline-sdd.md` as one pipeline-level SDD instead of splitting stages prematurely.
- [x] Specify stage contracts from discovery through enrichment persistence.
- [x] Specify current and target event status transitions.
- [x] Clarify ArtifactStore vs EventRecordStore responsibilities.
- [ ] Review with Lin and revise accepted scope.

### P1 — Daily capture operation

Goal: prepare for scheduled capture without introducing a daemon yet.

- [x] Add documented daily command examples using `--since` / `--until`.
- [x] Add overlap-window recommendation to README and `docs/mvp.md`.
- [ ] Add CLI summary fields for skipped/duplicates if pipeline exposes them.
- [ ] Add failure status and retry metadata for fetch or parse failures.
- [ ] Add one local script/example for daily capture of both sources.
- [x] Add adapter-defined raw-key cache for full-page fetches.

### P1 — Adapter robustness

Goal: reduce breakage from public website structure changes.

- [ ] Add recorded fixtures for representative Anthropic index/article pages.
- [ ] Add recorded fixtures for representative OpenAI RSS entries.
- [ ] Add live smoke tests for date extraction where available.
- [ ] Add parser fallback behavior and explicit parse errors.
- [ ] Add source-specific notes documenting assumptions and known fragility.

### P2 — Provider and export extensions

Goal: expand capabilities after capture semantics are stable.

- [ ] Implement real AI provider v1 after provider config is reviewed.
- [ ] Add JSONL export for event records/debugging.
- [ ] Sync tasks to Notion PARA/Product Tasks DB once DB/project mapping is confirmed.
- [ ] Add stronger article extraction quality tests.

## Review decisions

- Metadata default: SQLite.
- Artifact default: filesystem.
- Checkpointing: deferred; scheduled capture re-runs use idempotency and event record status.
- Daily capture should use date windows, not item count limits.
- Daily jobs should use a 2-3 day overlap window and rely on idempotency.
- Classification: multi-label tags, not single exclusive category.
- First sources: Anthropic and OpenAI blogs/news.
- Fetching/crawling belongs in lower-level fetchers; adapters should focus on source-specific parsing and mapping.
- Event-level raw cache keys are adapter-defined metadata hashes; fetchers only use `{source}/{raw_key}` to skip repeated full-page fetches.
- Pipeline stages should stay in one SDD until a stage has independent design pressure; split only for failure/retry, enrichment orchestration, event versioning, or observability when needed.
