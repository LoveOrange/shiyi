# Test Fixtures

Fixtures protect Shiyi's source-boundary contracts. They should make Adapter, `InternalItem`, pipeline, persistence, and export/read behavior reproducible without live third-party services.

See [`../../docs/testing-boundary.md`](../../docs/testing-boundary.md) for the full P2 testing boundary.

## Fixture types

Use three fixture classes for each built-in source when practical:

```text
<source>/
  raw/              # sanitized source payloads or mocked HTTP responses
  internal-item/    # expected InternalItem-shaped output
  export/           # expected consumer-facing export/read output
```

Existing tests may keep source-specific layouts while migrating toward this convention.

## Rules

1. Do not commit secrets, tokens, cookies, private account IDs, or unnecessary personal data.
2. Prefer small fixtures that preserve real source structure over large copied payloads.
3. Raw fixtures should contain enough provenance fields to validate Adapter behavior.
4. Expected `InternalItem` fixtures should include stable identity, source, type/kind, captured time, provenance, and normalized content inputs where applicable.
5. Expected export fixtures should include only Shiyi consumer-facing fields; raw third-party DTO fields should not leak into export output.
6. Golden output changes are contract changes. Update them intentionally and review the diff.
7. If a source payload shape changes, update the raw fixture and expected outputs together.

## Minimum gate for a new source

Before a new built-in Adapter/source is considered ready, add:

- one sanitized raw fixture
- a raw fixture to `InternalItem` contract test
- `idempotency_key` stability and non-collision tests
- invalid/missing-required-field coverage
- time parsing or time-window boundary tests when the source has time fields
- a fixture-backed pipeline or export/read smoke test when the source is part of the default capture flow

Experimental sources that do not meet this gate should stay clearly marked experimental and should not be required by default CI.
