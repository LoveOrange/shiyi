# Shiyi Testing Boundary

This document is the source of truth for Shiyi's P2/P2.5 test boundary. It defines what must stay true across Fetchers, Adapters, `InternalItem`, the capture pipeline, persistence, and export/read surfaces before Shiyi adds more sources. P2.5 extends the gate with full article/detail content readiness.

Notion tasks can track progress, but this repository document owns the engineering contract.

## 1. Goals

P2 is test-boundary-first. Before adding more adapters or sources, Shiyi must have deterministic tests that protect the core capture contract:

- Source-specific DTOs stay outside Shiyi core.
- `InternalItem` is the only domain boundary object entering the pipeline.
- `idempotency_key` stays stable across replay and rerun.
- Pipeline writes are replay-safe and do not duplicate durable records.
- Export/read surfaces expose Shiyi schema, not third-party raw payloads.
- Source-ready built-in adapters expose full article/detail content when available, not merely RSS/index summaries.
- Downstream consumers can rely on stable normalized content and trace fields.

## 2. Non-goals

P2 should not create a large slow end-to-end suite or force every source to hit the network in CI.

- No live third-party API dependency in default CI.
- No broad compatibility shim layer for old MVP names.
- No product-specific ranking, editorial scoring, or downstream insight tests inside Shiyi core.
- No requirement that every future storage backend is implemented before the current local stores are covered.

## 3. Test layers

Default CI should make failures easy to localize by layer.

### Unit tests

Unit tests cover pure functions and local model behavior. They should not use real network calls or real third-party credentials.

Required coverage:

- domain model validation
- date/window boundary behavior
- normalization helpers
- idempotency-key construction helpers, when present
- export formatting helpers

### Contract tests

Contract tests protect ports and source boundaries. They use fixtures, fake clients, or mocked HTTP responses.

Required coverage:

- Fetcher input/output behavior
- Adapter raw payload to `InternalItem` mapping
- `InternalItem` schema and semantic invariants
- full article/detail fixture coverage or explicit no-detail exemption for built-in sources
- source fixture conversion snapshots or golden outputs

### Integration tests

Integration tests exercise Shiyi core against local fake sources and local persistence backends.

Required coverage:

- Fetcher/Adapter or fake source into pipeline
- artifact store writes
- event-record store writes
- idempotent reruns
- partial failure handling
- checkpoint/progress commit behavior when implemented

### E2E smoke tests

E2E smoke tests prove the smallest useful full path still works. They should be few, deterministic, and fast.

Required coverage:

- fixture-backed ingest
- persist raw and normalized artifacts
- read/export by time range and source kind
- empty-result behavior

Live public-source smoke tests may exist, but they must remain opt-in and excluded from default CI.

## 4. Core invariants

These invariants are test gates. A change that violates them should fail CI unless the repository explicitly updates the contract and tests in the same PR.

### 4.1 `InternalItem` is the core boundary

Adapters may know third-party source shapes. Pipeline, persistence, and export/read code must not depend on third-party DTOs.

Tests should catch:

- third-party raw fields leaking into pipeline-only code
- Adapter output that is not a valid `InternalItem`
- persistence accepting raw-only source payloads without normalized boundary fields
- export exposing raw source DTOs instead of Shiyi fields

### 4.2 Idempotency is mandatory

`idempotency_key` is the stable logical replay identity. It is not a generic dedupe label and should not be renamed to `dedupe_key`.

Tests should catch:

- the same logical source item producing different `idempotency_key` values across runs
- different logical source items colliding under the same `idempotency_key`
- rerunning the same batch creating duplicate durable event records
- retrying after a partial failure advancing durable state too early

### 4.3 Time-window semantics are explicit

Capture and export windows should be deterministic. The current CLI semantics are half-open: `since` is inclusive and `until` is exclusive.

Tests should catch:

- off-by-one inclusion at `since` and `until`
- timezone-naive timestamps crossing boundaries unexpectedly
- second/millisecond conversion bugs
- invalid timestamps silently becoming valid records

### 4.4 Raw provenance is preserved but contained

Shiyi should preserve enough raw provenance for audit/debug, while keeping raw DTOs away from public normalized/export surfaces.

Tests should catch:

- raw artifacts not being written for successfully captured records
- normalized records losing trace fields needed to find raw provenance
- raw source-only fields leaking into export output

### 4.5 Content depth is part of source readiness

RSS/index/changelog snippets are discovery metadata by default. A built-in source should be source-ready only when Shiyi captures the canonical article/detail page or official structured detail payload when one exists.

Tests should catch:

- adapter fixtures that only exercise teaser/summary/listing content while a detail page exists
- normalized content that is materially shorter or less informative than the source detail payload
- records lacking source-neutral `content_depth` metadata when they are summary-only, partial, or blocked
- AI Weekly readiness checks counting `summary_only`, `partial`, or `blocked` records as full source coverage

### 4.6 Export/read is a consumer contract

Export/read output is what downstream consumers depend on. It must be stable, typed, and source-neutral.

Tests should catch:

- missing `idempotency_key`, source, captured time, or normalized content fields
- unstable default ordering
- source-kind or time-range filters returning incorrect records
- empty exports crashing or returning non-contract output

## 5. Required P2 test areas

### P2-01 Test Boundary Constitution and CI gate

Acceptance criteria:

- This document exists and is linked from relevant P2 work.
- Test layers are discoverable from paths, names, or CI commands.
- Default CI runs unit, contract, and integration smoke coverage without live credentials.
- Live tests are opt-in.
- New Adapter/source work is blocked unless its contract tests and fixtures exist.

Cases:

1. Test paths or markers make the layer clear enough for a maintainer to locate failures.
2. CI does not require third-party tokens or live network calls.
3. Live tests remain gated by an explicit environment variable.
4. Each built-in source has fixtures or mocked source data for default CI.
5. Contract failures identify the broken boundary instead of failing only through a broad E2E test.

### P2-02 Fetcher contract tests

Fetcher tests prove raw/source retrieval behavior without silently doing business normalization.

Current built-in fetchers do not expose pagination cursors, durable checkpoints, `since`, or `until` parameters. Their P2-02 contract therefore proves that they return complete parsed collections, preserve timestamps/provenance for adapters, classify retryable/permanent failures, and do not advance business progress. If a future fetcher adds cursor/checkpoint or time-window parameters, the same task must add explicit contract tests for those semantics.

Must cover:

1. Happy path with one page of source data.
2. Pagination or multiple discovered items without duplicates or missing records; for current RSS/sitemap fetchers, this means all parsed entries are returned exactly once from the fetched document.
3. Empty source result returns an empty collection, not a business failure.
4. Retryable source error is classified or retried according to the current policy.
5. Permanent source error is not swallowed and includes source/context.
6. Cursor/checkpoint input is honored when the implementation supports it.
7. Progress state advances only after the successful boundary, when checkpointing exists.
8. Time window filtering follows inclusive `since` and exclusive `until` semantics where applicable; current fetchers preserve source timestamps and leave filtering to adapter/domain tests.
9. Raw payload keeps enough fields for Adapter conversion and provenance.

### P2-03 Adapter and `InternalItem` contract tests

Adapter tests prove source-specific raw payloads become valid Shiyi domain items.

Must cover:

1. Minimal valid raw payload maps to a valid `InternalItem`.
2. Representative real-structure fixture maps to the expected `InternalItem` golden output.
3. Missing required source fields fail clearly or produce an explicit invalid-item path, not silent dirty data.
4. Optional fields follow stable null/default behavior.
5. Time parsing covers timezone, seconds/milliseconds, and invalid timestamps.
6. Same logical event always generates the same `idempotency_key`.
7. Different logical events do not collide under the same `idempotency_key`.
8. Core fields such as source, source kind, external id, captured time, title/content URL, and normalized input remain stable.
9. Adapter output passes `InternalItem` schema validation.
10. Source-specific raw DTOs do not pass into pipeline tests as substitutes for `InternalItem`.
11. For built-in source-ready adapters, representative fixtures prove the emitted item is based on full article/detail content or an official structured detail payload, not only listing/feed summary text.

### P2-04 Pipeline to persistence integration tests

Pipeline tests prove full local writes are safe, replayable, and observable.

Must cover:

1. Happy path writes raw artifact, normalized artifact, and event record.
2. Rerunning the same batch does not duplicate durable records.
3. Duplicate items inside one batch are handled according to the current idempotency policy.
4. One invalid item does not corrupt successfully processable items.
5. Partial failure records enough error context to diagnose source/item failure.
6. Durable event status reflects success/failure accurately.
7. Persistence conflict handling matches the product semantics of `idempotency_key`.
8. Checkpoint/progress commits only after successful persistence when checkpointing exists.
9. Run summary reports source, processed count, skipped/idempotent count, artifact count, and error summary where supported.

### P2-05 Export/read and E2E smoke tests

Export/read tests prove captured data is usable by downstream projects without source-specific DTO knowledge.

Must cover:

1. Read/export by time range returns the correct half-open window.
2. Read/export by source kind filters correctly.
3. Default ordering is stable and documented by test expectation.
4. Output schema includes Shiyi trace fields and `normalized_content`.
5. Output schema excludes third-party raw DTO fields.
6. Empty result returns a stable empty output, not a crash.
7. Fixture-backed E2E smoke runs ingest to persist to read/export.
8. Golden export output changes only when the contract intentionally changes.
9. Export/read output includes source-neutral `content_depth` metadata so consumers can exclude `summary_only`, `partial`, and `blocked` degraded records from decision-grade workflows.

## 6. Fixture and golden-output policy

Fixtures are part of the contract. They should be small, readable, and safe to commit.

Required fixture types:

- raw source fixture: a representative source payload, sanitized if derived from a real source
- expected `InternalItem`: the normalized domain object expected from the raw fixture
- expected export output: the consumer-facing output expected after persistence/export

Rules:

1. Fixtures must not include secrets, private tokens, cookies, internal account IDs, or personal data that is not intentionally public.
2. Prefer one high-signal fixture over many noisy fixtures.
3. Preserve enough real structure to catch source parsing regressions.
4. Golden output updates must be reviewed as contract changes, not mechanical snapshots.
5. If a source changes shape, update the raw fixture and expected output together.

Suggested layout:

```text
tests/
  fixtures/
    README.md
    openai/
      raw/
      internal-item/
      export/
    anthropic/
      raw/
      internal-item/
      export/
```

Existing tests may keep their current names while moving toward this layout incrementally.

## 7. New Adapter/source readiness gate

A new Adapter/source should not be merged until it has:

- at least one sanitized raw fixture
- sanitized raw detail/full-article fixture when the source exposes canonical detail content
- Adapter contract tests from raw fixture to `InternalItem`
- content-depth assertion proving the normalized/exported content is full article/detail content, or an explicit no-detail exemption
- `idempotency_key` stability and non-collision tests
- invalid/missing-required-field tests
- time-window or captured-time boundary tests, if the source carries time fields
- fake-source or mocked Fetcher contract coverage
- fixture-backed pipeline integration smoke, when the source is part of built-in capture
- export/read smoke proving downstream output does not expose third-party DTOs
- export/read smoke proving `summary_only`, `partial`, and `blocked` degraded records are marked source-neutrally with `content_depth` and do not count as AI Weekly source-ready

If a source cannot satisfy this gate yet, merge it behind an explicit experimental path and keep it out of default source lists.

The `shiyi sources --include-backlog` review contract must also stay covered by
regression tests. The JSON rows should distinguish ready, degraded, and deferred
readiness states; listing-only, summary-only, canonical-detail, and structured-API capture
modes; source class; defer reason; traceability refs; and whether the row counts as
official source-ready coverage. High-noise/community backlog rows must be explicit and
must never count as official source-ready coverage.

## 8. CI expectations

Default CI should run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

The default `uv run pytest` suite should be deterministic, credential-free, and safe to run offline except for package installation.

Live smoke tests should require explicit opt-in, for example:

```bash
SHIYI_RUN_LIVE_TESTS=1 uv run pytest tests/live/test_public_sources.py
```

## 9. Review checklist

Before accepting P2 test work, review:

- Does the test fail for a meaningful contract violation, or only for implementation details?
- Does it protect `InternalItem` as the core boundary?
- Does it protect `idempotency_key` semantics?
- Does it keep live network dependencies out of default CI?
- Does it prevent raw/third-party DTO leakage into export/read surfaces?
- Does it make adding the next Adapter/source safer rather than slower for no reason?

Keep the suite small enough to run often. The goal is a sharp safety rail, not a museum of brittle snapshots.
