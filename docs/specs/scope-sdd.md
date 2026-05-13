# Shiyi Scope SDD

- Status: Review
- Owner: Shiyi contributors
- Last updated: 2026-05-12
- Scope: product and architectural boundary for Shiyi as shared information capture infrastructure

## 1. Decision

Shiyi is a shared information capture and normalization infrastructure, not a general AI insight product.

The scope boundary is:

```text
Shiyi = Capture + Normalize + Neutral Preprocess + Distribution
Briefly / AI Insight / Demand Radar = Domain Enrichment + Ranking + Product Output
```

Shiyi produces facts, provenance, canonical content, and optional neutral annotations. It must not produce business opinions.

## 2. Why this boundary exists

Shiyi is intended to support multiple top-level products and workflows:

- Briefly and other vertical information insight products;
- AI R&D industry monitoring;
- demand radar and opportunity discovery;
- future capture consumers that need reliable source ingestion.

If Shiyi starts owning product-specific analysis, prompts, scoring, ranking, or editorial decisions, every consumer will push its own business logic into the infrastructure layer. That would turn Shiyi into a mixed insight application instead of a reusable capture substrate.

## 3. In scope

### 3.1 Source integration

Shiyi owns reusable source ingestion boundaries:

- RSS, web, sitemap, API, social/source adapters;
- source windows for daily/backfill capture;
- idempotency keys;
- source metadata and provenance;
- source-specific parsing behind adapters;
- shared fetchers for network policy, timeout, retry, user-agent, and event-level raw cache.

### 3.2 Raw capture

Shiyi owns durable raw capture:

- raw HTML/feed/API payload artifacts;
- fetch/source provenance;
- adapter name/version;
- fetched time;
- source item ID or canonical URL;
- replay/audit-friendly storage.

### 3.3 Normalize

Shiyi owns canonical source-independent representations:

- normalized Markdown/text artifacts;
- basic article/body extraction;
- title/author/published time/link/content-type where available;
- language and content metadata when source-neutral;
- stable references from event records to raw and normalized artifacts.

### 3.4 Event ledger

Shiyi owns pipeline bookkeeping:

- event records;
- status transitions;
- idempotency and replay safety;
- artifact references;
- retry/failure metadata when implemented;
- run summaries and operational counters.

### 3.5 Neutral preprocess, optional

Shiyi may provide optional neutral preprocessing when it is reusable across consumers and does not encode product-specific judgment.

Allowed examples:

- language detection;
- translation helper fields;
- neutral short summary for preview/indexing;
- entity extraction: company, product, person, paper, model, organization;
- coarse topic/category tags;
- content quality/spam/near-duplicate signals;
- chunking and embeddings for retrieval.

Neutral preprocess must be configurable and disableable. P0 should not require it.

### 3.6 Distribution

Shiyi should eventually expose captured material to consumers through simple distribution mechanisms:

- CLI list/export;
- JSONL export;
- local API;
- event stream or queue;
- stable artifact/event-record query interfaces.

## 4. Out of scope

Shiyi must not own domain/product decisions such as:

- Briefly vertical insight judgment;
- AI R&D industry trend analysis;
- demand radar pain-point or opportunity scoring;
- whether an item deserves inclusion in a weekly report;
- product-specific ranking, prioritization, or editorial selection;
- business conclusion generation;
- domain-specific prompts that only one top-level product understands.

Those belong to consumers that subscribe to Shiyi's normalized artifacts and event records.

## 5. Milestone scope

### P0: Capture + normalize infrastructure

P0 should prove:

- source adapters work for first real sources;
- raw artifacts are persisted;
- normalized/canonical artifacts are persisted;
- event records provide idempotency and replay safety;
- daily/backfill windows are safe;
- CLI can capture and list results.

P0 does not require AI preprocessing.

### P1: Neutral preprocessing

P1 may add optional neutral preprocessing only after capture semantics are stable.

P1 candidates:

- neutral summary;
- entity extraction;
- coarse topics;
- language detection;
- chunking/embedding;
- quality/duplicate signals.

The public API should prefer names such as `PreprocessTask`, `AnnotationTask`, or `ExtractionTask` over `EnrichmentTask`.

### P2: Consumer distribution

P2 should make it easy for product consumers to use Shiyi output:

- JSONL export;
- API/query layer;
- event stream;
- integration examples for Briefly, AI Insight, and Demand Radar.

## 6. Naming guidance

`Enrichment` is a dangerous name for Shiyi core because it suggests business insight.

`EnrichmentTask` and `EnrichmentResult` are the MVP names for neutral, reusable annotation work. Specs must not expand their meaning into product-specific insight generation.

## 7. Pipeline implication

The pipeline MVP uses one direct mode:

1. Raw + normalized artifacts are persisted first.
2. Configured neutral annotation tasks run next.
3. The item reaches terminal `enriched` state only after every configured annotation task succeeds.

MVP status semantics stay direct: `persisted` means raw/normalized artifacts were written, `enriched` means all configured neutral annotation tasks completed, and `failed` means the run needs inspection or retry. Rename status concepts directly only when a task explicitly changes the implemented state model.

## 8. Acceptance criteria

A scope or architecture change is acceptable only if:

1. Shiyi remains reusable infrastructure for multiple consumers.
2. Product-specific ranking, scoring, and insight generation stay outside Shiyi.
3. Raw and normalized artifacts remain first-class outputs.
4. Optional AI work is neutral, configurable, and not required for P0 capture correctness.
5. Names do not imply that Shiyi owns business enrichment.
6. Consumer products can build their own domain pipelines on top of Shiyi outputs.
