# Shiyi Test Boundary

- Status: Accepted
- Last updated: 2026-07-19

## Purpose

Tests protect the Briefly-facing source-to-content contract without coupling core behavior to third-party payload shapes.

## Required layers

### Fetcher tests

- timeout, retry, response size, and error classification;
- fake and real HTTP boundary parity;
- raw cache behavior where enabled.

### SourceAdapter contract tests

- receives the requested `Source` target;
- emits valid `SourceItem` only;
- stable `source_id` and `source_item_id`;
- canonical detail content where the source provides it;
- HTML, Markdown, and text-extractable PDF direct documents stay inside one
  adapter boundary, and mismatched media types fail closed;
- source DTO fields do not leak across the boundary;
- date window and item limits are deterministic.

### ContentProcessor tests

- HTML/text becomes non-empty Markdown;
- title, creators, language, metrics, and source-specific `extra` are mapped correctly;
- missing creators remain valid;
- deterministic global id and content hash remain stable;
- incomplete source material does not become ready.

### CaptureRunner tests

- Scheduler/CLI-facing config is the entry and multiple sources can share one adapter;
- disabled sources do not run;
- one source failure does not block another;
- repeated content upserts one id;
- identical raw bytes produce one content-addressed Blob;
- binary-to-Markdown capture retains the acquired binary bytes, not the derived
  text, behind the resulting `BlobRef`;
- capture performs no AI call.

### AI Provider ACL tests

- only ready records with an empty summary are selected;
- a batch uses one provider-neutral structured request;
- existing source summaries never call a provider;
- duplicate, missing, or unexpected provider result ids are rejected;
- allowed fields are bounded and merged without replacing source-owned fields;
- provider failure leaves deterministic content unchanged and naturally retryable;
- Codex CLI refuses non-ChatGPT login and receives no MongoDB configuration.

### Store tests

- MongoDB `_id` equals `ContentItem.id`;
- replace/upsert is idempotent;
- ready queries filter and order deterministically;
- categories and tags use separate multikey indexes;
- filesystem Blob paths cannot escape the configured root;
- Blob keys and hashes are content-addressed.

### Briefly boundary test

A final integration test runs a configured source through adapter, Blob storage, processor, and canonical store, then reads a ready `ContentItem` without inspecting `SourceItem`, runner state, or adapter DTOs.

## Forbidden test shortcuts

- passing source DTOs directly to the processor;
- asserting a second export/event schema instead of `ContentItem`;
- depending on a compatibility alias for a removed MVP boundary;
- treating AI output as required for capture correctness;
- putting Signal, Trend, Opportunity, or editorial fields in Shiyi fixtures.

## Commands

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest
```
