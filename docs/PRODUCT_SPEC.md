# Shiyi Product Specification

- Status: Accepted
- Last updated: 2026-07-19
- Priority: Briefly-first MVP

## Product goal

Shiyi provides Briefly with stable, source-neutral information records. It collects configured external targets, acquires original content, normalizes it into a common document shape, optionally adds neutral AI fields, and persists canonical `ContentItem` documents.

Briefly launches after Shiyi can provide this data reliably.

## Long-term direction

Shiyi may eventually collect news, blogs, videos, social posts, forum threads, repositories, and other public information. It is intended to become an open-source information collection foundation with multiple adapters.

That long-term breadth does not expand the current scope into insight generation. Signal, Trend, Opportunity, ranking, and editorial decisions always belong to downstream consumers.

## MVP flow

```text
Scheduler / CLI
-> CaptureRunner
-> Source from CaptureConfig
-> SourceAdapter
-> SourceItem
-> ContentProcessor
-> ContentItem
-> MongoDB
-> Briefly
```

Raw, oversized, or cold bytes are retained in filesystem storage initially and COS later through `BlobRef`.

## Functional requirements

### Configuration

- A configuration declares one or more enabled `Source` records.
- A source owns a stable id, adapter key, target, options, and checkpoint boundary.
- Multiple sources may share one adapter implementation.

### Capture

- Adapters isolate authentication, network access, pagination, rate limits, and source DTOs.
- Adapters emit valid `SourceItem` records.
- One source failure does not block other configured sources.

### Canonicalization

- Textual content is normalized to Markdown.
- Identity is deterministic from source id and source-native item id.
- Original language content is preserved.
- `creators` is an optional string array; it is not a separate entity model.
- Missing creators or AI fields do not invalidate the base document.

### AI

- AI is optional and neutral.
- Allowed fields are language, summary, summary language, categories, and tags.
- AI cannot overwrite ids, provenance, source facts, URL, timestamps, content, metrics, or Blob references.
- AI failure leaves deterministic output durable.

### Persistence

- MongoDB is the canonical hot/query store.
- `ContentItem.id` maps to MongoDB `_id` and is the only upsert identity.
- Filesystem/COS Blob storage is content-addressed and idempotent.
- Briefly reads `ready_at != null` documents without pipeline knowledge.

## Non-functional requirements

- Repeated runs are idempotent.
- Source-specific DTOs stop at the adapter boundary.
- Schemas are typed and reject unknown fields.
- Retries are bounded and observable.
- MongoDB production deployment has replication, backups, restore verification, and read-only Briefly credentials.

## Non-goals

- business or editorial insight;
- product-specific ranking or clustering;
- a generic agent/AI task system;
- an event-record status machine;
- multiple competing canonical stores;
- compatibility shims or a plugin marketplace during MVP.

## Acceptance

The MVP is ready for Briefly when selected sources repeatedly produce complete, deduplicated `ContentItem` documents, AI outages do not lose captured data, and Briefly can incrementally read canonical records using only MongoDB fields.
