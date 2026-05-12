# Extension Points

Shiyi is designed so users can customize major extension points without changing core.

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

## Artifact Store

Artifact Store implementations store raw and generated content such as HTML, markdown, extracted text, attachments, screenshots, and AI response JSON.

Responsibilities:

- Store artifacts durably.
- Return stable artifact references.
- Preserve media type, size, checksum, and creation time.
- Support local filesystem storage as the MVP default.

## Metadata Store

Metadata Store implementations track pipeline control data and artifact references.

Responsibilities:

- Enforce idempotency keys and optimistic concurrency where possible.
- Track event status, fingerprints, artifact references, enrichment references, failures, and retry counts.
- Use SQLite as the MVP default implementation.
- Allow future implementations backed by Postgres, document databases, or other stores.

## Checkpointing

A dedicated Checkpoint Store is deferred for the MVP. Scheduled capture runs should rely on idempotency and metadata status to skip completed records and retry incomplete work.

## Contract testing

Each extension point should eventually ship with a shared contract test suite. A third-party implementation should be able to run the suite and verify compatibility before publishing.
