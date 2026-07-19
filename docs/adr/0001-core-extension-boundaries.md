# ADR 0001: Core Capture Boundaries

- Status: Accepted
- Date: 2026-07-19

## Context

Shiyi is Briefly's information-ingestion service first and an extensible open-source
collector later. The MVP must collect heterogeneous sources without turning source
differences into a generic event system or a large plugin framework.

The core needs clear boundaries for acquisition, canonicalization, persistence, and
optional AI processing while keeping the deterministic path small and idempotent.

## Decision

The execution flow is:

```text
Scheduler / CLI
-> CaptureRunner
-> Source (selected from CaptureConfig)
-> SourceAdapter
-> SourceItem
-> ContentProcessor
-> ContentItem
-> ContentItemStore
```

Shiyi defines five extension boundaries:

1. `SourceAdapter` performs source-specific network acquisition.
2. `ContentProcessor` converts a `SourceItem` into the canonical `ContentItem` format.
3. `ContentItemStore` persists and queries canonical items.
4. `BlobStore` optionally retains raw, oversized, or cold bytes.
5. `AIProcessor` optionally adds neutral language, summary, category, and tag fields.

`CaptureRunner` owns orchestration, isolation between sources, deterministic identity,
idempotent upserts, and failure reporting. `Source` is declarative configuration, not
an active component. Multiple targets can share one adapter; for example, multiple X
accounts are separate `Source` entries resolved to the same `XCaptureAdapter`.

`ContentItem` is the single canonical persisted and public content contract. Creator
attribution remains the optional `creators: string[]` field; there is no separate
`Creator` model in the MVP.

MongoDB is the initial hot `ContentItemStore`. Filesystem is the initial `BlobStore`,
with COS as a future cold-storage implementation. AI processing is optional and must
not be required for capture correctness or overwrite source facts.

Signal extraction, trends, opportunities, ranking, and editorial decisions belong to
downstream consumers such as Briefly.

## Consequences

Positive:

- one canonical model replaces parallel internal, event, artifact, and export models;
- adding collection targets is mainly configuration, while adding protocols requires
  a focused adapter;
- deterministic collection and persistence remain usable when AI is disabled or fails;
- storage can evolve without changing the canonical content contract.

Trade-offs:

- source-specific checkpoints and rate-limit behavior remain adapter concerns;
- ecosystem compatibility is intentionally deferred until the Briefly-first MVP is
  stable;
- production MongoDB validation, backup, and cold-data policies remain deployment
  concerns rather than additional core abstractions.
