# Shiyi Local Storage SDD

- Status: Draft
- Last updated: 2026-05-16
- Scope: MVP filesystem artifact store and SQLite event record store

## 1. Purpose

The MVP local storage implementation must support deterministic local capture runs without requiring external services. Artifacts are stored as files. Pipeline event records are stored in SQLite.

## 2. Filesystem Artifact Store

### Responsibilities

- Store raw, normalized, and optional annotation/preprocess artifacts under a local root directory.
- For P2.5 built-in adapters, raw artifacts must preserve the canonical article/detail payload used for normalization, not only the RSS/index/listing snippet.
- Use content-addressed paths based on SHA-256.
- Return stable `ArtifactRef` objects.
- Prevent path traversal by never trusting user-provided names as final paths.
- Preserve media type, artifact kind, size, and digest.

### Layout

```text
.shiyi/
└── artifacts/
    ├── raw/
    │   └── <sha256-prefix>/<sha256>
    ├── normalized/
    │   └── <sha256-prefix>/<sha256>
    └── enrichment/  # neutral annotation artifacts
        └── <sha256-prefix>/<sha256>
```

## 3. SQLite Event Record Store

### Responsibilities

- Enforce idempotency by `idempotency_key`.
- Track event status.
- Store raw and normalized artifact references as JSON.
- Store minimal trace fields needed to audit pipeline writes: source, captured_at, content_hash, idempotency_key, adapter_name, and adapter_version.
- Persist `captured_at` as canonical UTC ISO-8601 text (`+00:00`) before any export filtering or ordering.
- Store item failure context in `last_error` when the pipeline can record a failed attempt.
- Store optional annotation/preprocess artifact references as JSON rows.
- Support idempotent re-runs by returning existing complete records.
- Support MVP upstream export by reading event records with normalized artifact content filtered by `captured_at` and source kind.

### Minimal schema

```sql
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  raw_artifact_json TEXT,
  normalized_artifact_json TEXT,
  source_json TEXT,
  captured_at TEXT,
  content_hash TEXT,
  adapter_name TEXT,
  adapter_version TEXT,
  last_error TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE enrichments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL,
  task_type TEXT NOT NULL,
  artifact_json TEXT NOT NULL,
  model_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

## 4. Upstream export

The MVP exposes local export as a pull-based read over the SQLite event ledger and filesystem artifacts:

```bash
shiyi export --since 2026-05-12 --until 2026-05-13 --source blog --limit 20
```

Output is a JSON array of `shiyi-export-item.v1` objects containing Shiyi trace fields plus `normalized_content`. It deliberately does not expose third-party adapter DTOs to consumers.

For P2.5 source-readiness review, export/read consumers must be able to distinguish complete records from summary-only or partial degraded records. Export/read should expose Shiyi-native `content_depth` plus derived `content_completeness`; both are limited to the MVP states `complete`, `partial`, and `summary_only`. Capture mechanics such as canonical detail pages, structured APIs, RSS/feed paths, and fetch blocker state must not leak into `content_depth`. Only `content_completeness=complete` is source-ready by default. Do not leak adapter-specific raw DTO fields.

Export filters use a half-open `captured_at` window: `--since` is inclusive and `--until` is exclusive. Both stored `captured_at` values and filter bounds are compared as canonical UTC instants, so source timestamps with non-UTC offsets are first normalized to UTC.
Repeated `--source` filters match canonical Shiyi `source.kind` values with OR semantics.
Default ordering is stable and consumer-visible: newest `captured_at` first, with `event_id` ascending as the deterministic tie-breaker.
Empty matches return `[]`.

## 5. MVP constraints

- No checkpoint tables yet.
- No external database server.
- No vector/full-text index.
- No concurrent writer guarantees beyond SQLite's normal local behavior.
