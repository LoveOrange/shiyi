# Shiyi Scope SDD

- Status: Accepted
- Owner: Shiyi contributors
- Last updated: 2026-07-19
- Priority: Briefly-first MVP
- Architecture: [`../architecture.md`](../architecture.md)

## 1. Decision

Shiyi is information collection and canonicalization infrastructure. Its stable product boundary is:

```text
Shiyi = Configure + Capture + Normalize + Optional Neutral AI + Persist ContentItem
Downstream = Signal + Trend + Opportunity + Ranking + Editorial Output
```

Shiyi may ingest many content kinds, but it ends at a source-neutral `ContentItem`. It must not turn that content into product-specific insight.

## 2. Current goal

Briefly launches after Shiyi can supply data reliably. Therefore the MVP optimizes for:

1. stable configured sources needed by Briefly;
2. complete original content when available;
3. deterministic normalization and idempotent MongoDB upserts;
4. a simple readiness contract for Briefly;
5. optional neutral summary and language processing that cannot break capture.

Open-source adapter breadth and third-party extension ergonomics are later goals.

## 3. In scope

### 3.1 Configuration and collection

- `CaptureConfig` declares enabled `Source` targets.
- Scheduler or CLI invokes `CaptureRunner`.
- Runner resolves a `SourceAdapter` for each enabled source.
- Adapters own authentication, HTTP/API access, pagination, rate limits, checkpoints, and source-specific parsing.
- Multiple targets may share one adapter; for example, multiple X account sources share `XCaptureAdapter`.

### 3.2 SourceItem

`SourceItem` is the transient Adapter -> Processor boundary. It retains source identity, source-native item identity, collection time, canonical URL when known, raw payload, an optional source-provided summary, and source metadata.

It is not persisted as the public consumer contract.

### 3.3 ContentItem

`ContentItem` is the only canonical persisted and consumer-facing document. It owns:

- deterministic Shiyi id;
- source and source-native identity;
- content kind and canonical URL;
- title and optional `creators: string[]` attribution;
- published and collected timestamps;
- original language and normalized Markdown content;
- optional summary and summary language;
- optional categories, tags, and objective metrics;
- content hash, source-specific `extra`, and optional `BlobRef`;
- readiness and update timestamps.

Missing creators must not block readiness. `Creator` is not a separate MVP model.

### 3.4 Optional neutral AI

AI may produce only reusable neutral fields:

- language normalization;
- a configured-language title when needed;
- neutral summary;
- simple categories or tags.

AI output is untrusted until deterministically validated and merged. A non-empty source-provided summary is promoted directly and prevents AI summarization. AI failure must not lose deterministic output.

### 3.5 Persistence and distribution

- MongoDB is the canonical hot/query store for `ContentItem`.
- Filesystem initially, and COS later, stores raw, oversized, or cold bytes referenced by `BlobRef`.
- Briefly reads canonical items from MongoDB.
- JSON or CLI export is derived output, not a second authority.

## 4. Out of scope

Shiyi does not own:

- signals, trends, opportunities, recommendations, or business conclusions;
- credibility, importance, ranking, clustering, or editorial selection;
- Briefly-specific presentation logic;
- generic extraction tasks, agent workflows, or arbitrary AI jobs;
- parallel canonical SQLite, filesystem, and MongoDB representations;
- compatibility layers or a production plugin ecosystem during MVP.

## 5. Acceptance criteria

The MVP boundary is satisfied when:

1. configured sources repeatedly produce complete, validated `ContentItem` documents;
2. the same logical source item upserts the same deterministic `ContentItem.id`;
3. source-specific DTOs do not cross the `SourceItem` boundary;
4. Briefly needs no adapter, raw payload, runner, or checkpoint knowledge;
5. AI can be disabled or fail without losing captured deterministic content;
6. downstream insight concepts do not appear in Shiyi domain contracts.

## 6. Naming

Use `Item` only for `SourceItem` and `ContentItem`.

Use:

- `CaptureRunner`, not a generic pipeline/event orchestrator;
- `SourceAdapter`, with implementations such as `XCaptureAdapter`;
- `ContentProcessor`, not a generic enrichment task graph;
- `ContentItemStore`, not `EventRecordStore`;
- `BlobStore` and `BlobRef`, not artifact/event families.

During MVP, rename these boundaries directly across code, tests, and docs without compatibility aliases.
