# Shiyi Briefly-first MVP

## Outcome

Provide a reliable canonical information feed for Briefly before expanding Shiyi's open-source adapter surface.

## Included

- declarative `CaptureConfig` with enabled `Source` targets;
- `CaptureRunner` as the Scheduler/CLI execution entry;
- source-specific `SourceAdapter` acquisition;
- transient `SourceItem` and canonical `ContentItem` contracts;
- deterministic Markdown normalization, identity, hashing, and idempotent upserts;
- MongoDB canonical storage;
- filesystem Blob storage with a future COS implementation boundary;
- optional neutral language, summary, categories, and tags.

## Excluded

- Signal, Trend, Opportunity, ranking, clustering, or editorial output;
- generic enrichment/extraction task models;
- event ledgers and artifact families;
- runtime plugin discovery;
- broad third-party compatibility guarantees.

## Launch gate

1. Selected Briefly sources run repeatedly without duplicate documents.
2. Complete source content is normalized into queryable Markdown.
3. MongoDB indexes and schema validation are installed.
4. AI can be disabled or unavailable without capture data loss.
5. Briefly reads only ready canonical documents.
6. Backups and restore procedures are exercised before production.

See [`architecture.md`](architecture.md) and [`specs/scope-sdd.md`](specs/scope-sdd.md).
