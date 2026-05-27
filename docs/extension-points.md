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
- Resolve canonical article/detail content when a feed/index/changelog entry is only a teaser or summary.
- Convert source-specific data into `InternalItem`.
- Provide checkpoint metadata for reliable resume.
- Respect source rate limits and terms.

Adapters should not decide final storage schema or silently mutate provider results. If only partial or summary content is available, adapters should mark that source-neutrally instead of presenting it as full article content.

### Adapter admission and package placement

Built-in core adapters are the narrowest class: public official sources with no
credentials, no private data, no browser state, no heavy default dependency, bounded
fixtures, repeatable tests, stable replay identity, stable timestamps/URLs when ready,
and source-neutral complete content.

Adapters that fail one of those gates do not automatically create a new package system:

- public official adapters with complete evidence but non-default runtime needs stay
  `optional_official` until a real optional packaging requirement is approved;
- credentialed, browser-state, private-workspace, or account-bound adapters stay
  `private_closed`;
- official sources without complete payload/readiness evidence stay `deferred_official`;
- community/social/high-noise sources that need aggregation or ranking stay
  `bfl_m3_future`.

The Shiyi -> downstream boundary remains the neutral normalized/export contract. Adapter
placement must not add AI Weekly projections, topic links, ranked candidates, report
entries, renderer fields, or editorial decisions to Shiyi.

## Normalizer

Normalizers convert source payloads into canonical content.

Responsibilities:

- Convert HTML/feed/API payloads into Markdown, text, or structured canonical artifacts.
- Preserve source provenance and artifact traceability.
- Avoid product-specific interpretation.
- Return artifact writes rather than persisting final records directly.

Normalizers should not call model providers or decide business ranking.

## Neutral AI Provider

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

`AIProvider`, `EnrichmentTask`, and `EnrichmentResult` are the MVP neutral annotation boundary. Keep them neutral and reusable; do not turn them into product-specific insight generation.

AI providers should not persist final records directly.

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

Each extension point should eventually ship with a shared contract test suite. A third-party implementation should be able to run the suite and verify contract conformance before publishing.
