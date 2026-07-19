# Shiyi Agent Guide

Shiyi is still in MVP. Optimize for simple, direct progress over long-lived compatibility layers.

## Product Positioning

Shiyi is information collection and canonicalization infrastructure. It collects content from heterogeneous sources and turns it into stable, source-neutral `ContentItem` records for downstream consumers.

The current product objective is to provide a stable data input for Briefly. Briefly launches only after Shiyi can supply data reliably. Open-source breadth, third-party extension ergonomics, and a large adapter ecosystem are later goals and must not slow the Briefly-first MVP.

Shiyi may eventually collect news, blogs, videos, social posts, forum threads, repositories, and other public information. It does not interpret those records as business or editorial insights.

## Scope

The canonical execution flow is:

`Scheduler / CLI -> CaptureRunner -> Source (from CaptureConfig) -> SourceAdapter -> SourceItem -> ContentProcessor -> ContentItem -> ContentItemStore`

The domain terms mean:

- `CaptureRunner`: the execution entry point invoked by a scheduler or CLI. It loads enabled sources, resolves their adapters, and orchestrates processing and persistence.
- `CaptureConfig`: the declarative definition of what to collect. It owns the enabled `Source` list and target-specific options; it does not perform collection.
- `Source`: one independently identifiable collection target with a stable id, adapter kind, target, and checkpoint boundary. Multiple X accounts are separate `Source` entries in one `CaptureConfig` and share the same X adapter implementation.
- `SourceAdapter`: the component that performs source-specific network acquisition. It isolates authentication, pagination, rate limits, checkpoints, and source payload shapes. Implementations may be named `XCaptureAdapter`, `RedditCaptureAdapter`, or `RssCaptureAdapter`.
- `SourceItem`: a transient, source-facing item emitted by an adapter. It preserves source identity, acquired raw content, and an optional source-provided summary needed for processing.
- `ContentProcessor`: deterministic normalization plus optional reusable AI preprocessing.
- `ContentItem`: the canonical, persisted, source-neutral contract consumed by Briefly and future downstream products.
- `ContentItemStore`: the durable query boundary for canonical items.
- `BlobRef` / `BlobStore`: optional storage for raw, oversized, or cold content outside the canonical document.

Use the `Item` suffix only for the two core data units, `SourceItem` and `ContentItem`. Do not add it to supporting concepts such as `Source`, `SourceAdapter`, `ContentProcessor`, `ContentItemStore`, or `BlobRef`.

Shiyi is responsible for:

- collecting original content and source metadata;
- mapping heterogeneous source data into a stable source-neutral schema;
- preserving provenance, canonical URL, source-native identity, timestamps, content kind, and original language;
- retaining source-provided attribution as an optional `creators: string[]` field; `Creator` is not a separate MVP model and missing creators must not block readiness;
- normalizing textual content into a consistent format, Markdown by default;
- optionally detecting language and producing a neutral summary, simple categories/tags, or a configured-language summary/translated title;
- persisting canonical content idempotently and retaining raw or large payloads by reference when needed;
- exposing a stable read contract for Briefly.

Shiyi is not responsible for:

- signals, trends, opportunities, recommendations, or business judgments;
- topic importance, credibility scoring, ranking, clustering, or editorial selection;
- Briefly-specific presentation or product decisions;
- a generic agent workflow or open-ended AI task system;
- production-grade plugin ecosystems or compatibility layers during the Briefly-first MVP.

Those interpretations belong to downstream consumers:

`ContentItem -> Signal / Trend / Opportunity / Editorial Decision`

## MVP Outcome

The MVP is successful when configured sources repeatedly produce complete, deduplicated `ContentItem` records that Briefly can consume without reading source-specific payloads or Shiyi's internal pipeline state.

For the MVP:

- use a deterministic global `ContentItem.id` and idempotent upserts;
- preserve original-language content; do not require full-content translation;
- treat AI as optional preprocessing, limited to neutral reusable fields;
- persist usable deterministic output even when AI is unavailable or fails;
- prefer MongoDB as the canonical hot/query store for Briefly;
- use the filesystem initially, and COS later, for raw, oversized, or cold blobs referenced from MongoDB;
- keep one canonical truth for queryable `ContentItem` data rather than parallel SQLite, filesystem, and MongoDB representations.

## Processing Boundaries

Deterministic code owns configuration loading, source selection, adapter resolution, collection, validation, identity, canonical URL handling, field mapping, content conversion, hashing, deduplication, persistence, retries, and checkpoints.

AI may own only optional language normalization, summarization, and simple semantic labels. An adapter-provided non-empty summary is authoritative: AI must not summarize that item again or replace it. AI failure must not prevent capture or overwrite source facts. AI output must remain neutral and reusable by consumers other than Briefly.

## Design Principles

- Lightweight: add the smallest code and spec surface that proves the current product need.
- Simple: prefer one clear model/function/path over adapter layers, aliases, or migration shims.
- Elegant: keep names aligned with the domain language used in specs and tests.
- Declarative: make behavior explicit in typed contracts, tests, and specs instead of hidden conventions.
- Idempotent: repeated pipeline runs should be safe and should not duplicate durable records/artifacts.

## MVP Compatibility Policy

Do not add backward-compatibility aliases, compatibility names, migration branches, or compatibility-style fixes unless Lin explicitly asks for them.

When a boundary name changes during MVP, rename it directly across code, tests, and docs. Broken old imports are acceptable because there are no supported external consumers yet.

## Overdesign Guardrail

Before adding an abstraction, ask:

1. Is it required by the current MVP acceptance criteria?
2. Can the same product behavior be expressed with fewer moving parts?
3. Does it improve idempotency, clarity, or source-boundary isolation now?

If not, do not add it.
