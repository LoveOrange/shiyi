# Fetcher and SourceAdapter SDD

- Status: Accepted
- Last updated: 2026-07-19
- Scope: network acquisition inside `SourceAdapter`

## Decision

`CaptureRunner` selects a configured `Source` and resolves its `SourceAdapter`. The adapter then uses fetchers to perform network I/O and emits `SourceItem` records.

```text
CaptureConfig -> CaptureRunner -> Source -> SourceAdapter -> Fetcher -> SourceItem
```

Fetchers do not know about `ContentItem`, MongoDB, AI, readiness, or downstream consumers.

## Fetcher responsibility

- execute HTTP/API requests;
- enforce timeout and response-size limits;
- classify transient and permanent network failures;
- apply bounded retries and rate-limit behavior;
- return response content and collection time;
- optionally maintain a content-addressed raw request cache.

## SourceAdapter responsibility

- interpret `Source.target` and options;
- own authentication, pagination, API shapes, and source-specific parsing;
- use indexes/feeds only for discovery when canonical detail content exists;
- emit source-neutral identity, kind, URL, times, payload, and objective metadata;
- keep third-party DTO fields private;
- maintain checkpoint progress per `Source.id` when checkpointing is added.

## Complete content

Built-in Briefly sources should fetch the canonical article/detail surface when a feed or index contains only a preview. An adapter may emit incomplete fallback material with `metadata.is_complete = false`; the default processor persists it but leaves `ready_at` unset.

A simple boolean is sufficient for MVP. Do not recreate parallel content-depth and completeness taxonomies.

## Raw cache

Raw fetch caching is a network optimization, not canonical persistence. Cache keys must be stable and cannot replace `ContentItem.id` or MongoDB upsert checks.

## Errors

Source I/O retries are bounded inside the adapter/fetcher boundary. After exhaustion, the adapter raises a diagnosable error and `CaptureRunner` continues with the next configured source.

## Acceptance

1. The adapter receives the exact configured source.
2. Multiple source targets may share one adapter implementation.
3. A valid `SourceItem` is the only output boundary.
4. Source-specific response objects do not leak into core tests.
5. Repeated network results lead to stable source-native identity.
