# Shiyi Local Storage SDD

- Status: Draft
- Last updated: 2026-05-12
- Scope: MVP filesystem artifact store and SQLite metadata store

## 1. Purpose

The MVP local storage implementation must support deterministic local capture runs without requiring external services. Artifacts are stored as files. Pipeline metadata is stored in SQLite.

## 2. Filesystem Artifact Store

### Responsibilities

- Store raw, normalized, and enrichment artifacts under a local root directory.
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
    └── enrichment/
        └── <sha256-prefix>/<sha256>
```

## 3. SQLite Metadata Store

### Responsibilities

- Enforce idempotency by `idempotency_key`.
- Track event status.
- Store raw and normalized artifact references as JSON.
- Store enrichment artifact references as JSON rows.
- Support idempotent re-runs by returning existing complete records.

### Minimal schema

```sql
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id TEXT NOT NULL,
  idempotency_key TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL,
  raw_artifact_json TEXT,
  normalized_artifact_json TEXT,
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

## 4. MVP constraints

- No checkpoint tables yet.
- No external database server.
- No vector/full-text index.
- No concurrent writer guarantees beyond SQLite's normal local behavior.
