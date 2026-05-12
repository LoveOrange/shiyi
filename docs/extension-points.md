# Extension Points

Shiyi is designed so users can customize three major extension points without changing core.

## Adapter

Adapters connect external sources to Shiyi.

Responsibilities:

- Authenticate with the source.
- Discover new or updated source items.
- Convert source-specific data into `CaptureEvent`.
- Provide checkpoint metadata for reliable resume.
- Respect source rate limits and terms.

Adapters should not decide final storage schema or silently mutate AI results.

## AI Provider

AI Providers expose model-backed capabilities behind stable contracts.

Responsibilities:

- Execute typed enrichment tasks.
- Return structured, schema-validatable results.
- Surface usage, latency, model identity, and safety metadata.
- Support retries only when safe and explicit.

AI Providers should not persist final records directly.

## Persistence

Persistence implementations store Shiyi data in user-selected backends.

Responsibilities:

- Store raw capture events and enriched records.
- Enforce idempotency keys and optimistic concurrency where possible.
- Store checkpoints only after successful pipeline processing.
- Preserve provenance and audit trail.

Persistence should make failure semantics clear: committed, rejected, conflict, or unknown.

## Contract testing

Each extension point should eventually ship with a shared contract test suite. A third-party implementation should be able to run the suite and verify compatibility before publishing.
