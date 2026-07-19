# Shiyi Milestones

- Last updated: 2026-07-19
- Priority: Briefly-first

## M0: Canonical architecture

Goal: replace the event/artifact/enrichment model with the accepted source-to-content boundary.

- `CaptureConfig`, `Source`, `SourceItem`, `ContentItem`, and `BlobRef` contracts;
- `CaptureRunner`, `SourceAdapter`, `ContentProcessor`, `ContentItemStore`, and `BlobStore` ports;
- deterministic identity and idempotent upsert behavior;
- MongoDB canonical store and filesystem Blob store;
- architecture, scope, storage, AI, and test specifications aligned.

## M1: Briefly launch data gate

Goal: prove stable production data delivery for the selected initial sources.

- select the minimum Briefly source set;
- run scheduled capture and backfill repeatedly;
- verify complete Markdown, timestamps, provenance, language, and readiness;
- install MongoDB schema validation and indexes;
- verify backups, restore, and read-only Briefly access;
- measure source success, latency, duplicates, and failure recovery.

## M2: Neutral AI preprocessing

Goal: add value without making AI part of capture correctness.

- one structured summary/language/categories/tags request;
- configured summary language;
- deterministic validation and field limits;
- retry and failure telemetry;
- no full-content translation unless Briefly proves the need.

## M3: Open-source breadth

Goal: improve Shiyi as a reusable public project after Briefly is stable.

- additional social, forum, video, repository, and document sources;
- documented adapter authoring examples and contract tests;
- configuration ergonomics and secrets guidance;
- COS Blob implementation and volume-driven hot/cold policy;
- public API stabilization only after real external usage.
