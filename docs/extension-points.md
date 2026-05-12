# Extension Points

Shiyi is designed so users can customize major extension points without changing core.

Shiyi's scope is shared capture infrastructure:

```text
Shiyi = Capture + Normalize + Neutral Preprocess + Distribution
Briefly / AI Insight / Demand Radar = Domain Enrichment + Ranking + Product Output
```

## Adapter

Adapters connect external sources to Shiyi.

Responsibilities:

- Authenticate with the source.
- Discover new or updated source items.
- Convert source-specific data into `CaptureEvent`.
- Provide checkpoint metadata for reliable resume.
- Respect source rate limits and terms.

Adapters should not decide final storage schema or silently mutate provider results.

## Normalizer

Normalizers convert source payloads into canonical content.

Responsibilities:

- Convert HTML/feed/API payloads into Markdown, text, or structured canonical artifacts.
- Preserve source provenance and artifact traceability.
- Avoid product-specific interpretation.
- Return artifact writes rather than persisting final records directly.

Normalizers should not call model providers or decide business ranking.

## Neutral Preprocessor / AI Provider

Neutral preprocessors expose optional model-backed or heuristic capabilities behind stable contracts.

Responsibilities:

- Execute domain-neutral preprocessing tasks.
- Return structured, schema-validatable annotations.
- Surface usage, latency, model identity, and safety metadata when model-backed.
- Support retries only when safe and explicit.

Allowed examples:

- neutral summaries;
- language detection;
- entity extraction;
- coarse topics;
- quality/spam/near-duplicate signals;
- chunking and embeddings.

Out of scope:

- business insight generation;
- opportunity scoring;
- ranking or editorial selection;
- downstream-product-specific prompts.

Current code still uses `AIProvider` / `EnrichmentTask` naming as a transitional MVP artifact. Future public contracts should prefer `PreprocessTask`, `AnnotationTask`, or `ExtractionTask` where appropriate.

Neutral preprocessors should not persist final records directly.

## Artifact Store

Artifact Store implementations store raw and generated content such as HTML, markdown, extracted text, attachments, screenshots, neutral annotation JSON, and future provider response JSON when policy allows it.

Responsibilities:

- Store artifacts durably.
- Return stable artifact references.
- Preserve media type, size, checksum, and creation time.
- Support local filesystem storage as the MVP default.

## Event Record Store

Event Record Store implementations track pipeline control data and artifact references.

Responsibilities:

- Enforce idempotency keys and optimistic concurrency where possible.
- Track event status, fingerprints, artifact references, annotation references, failures, and retry counts.
- Use SQLite as the MVP default implementation.
- Allow future implementations backed by Postgres, document databases, or other stores.

## Checkpointing

A dedicated Checkpoint Store is deferred for the MVP. Scheduled capture runs should rely on idempotency and event record status to skip completed records and retry incomplete work.

## Contract testing

Each extension point should eventually ship with a shared contract test suite. A third-party implementation should be able to run the suite and verify compatibility before publishing.
