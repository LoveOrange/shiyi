# Shiyi Capture Pipeline SDD

- Status: Review
- Owner: Shiyi contributors
- Last updated: 2026-05-12
- Scope: capture pipeline orchestration from adapter events to durable artifacts, event records, and enrichment artifacts

## 1. Purpose

This document specifies the Capture Pipeline behavior for Shiyi. It is the single pipeline-level SDD for now.

We intentionally keep the pipeline stages in one document because the hard part is not an individual stage; it is the ordering, boundary, and state transition between stages. Split stage-specific SDDs only when a stage develops enough independent complexity to justify it.

The pipeline coordinates these responsibilities:

1. Consume `CaptureEvent` objects from an adapter.
2. Use idempotency to skip already-complete logical events.
3. Persist raw source payloads as artifacts.
4. Normalize event payloads into canonical artifacts when a normalizer is configured.
5. Persist processing state in an `EventRecordStore`.
6. Run configured enrichment tasks through an `AIProvider`.
7. Persist validated enrichment results as artifacts.
8. Update event records with status and artifact references.

## 2. Non-goals

The pipeline must not own these responsibilities:

- Fetching HTTP pages, RSS feeds, sitemaps, pagination, timeout, retry, or raw fetch cache. These belong to fetchers.
- Source-specific parsing, source identity, source timestamps, source metadata, or adapter-defined raw keys. These belong to adapters.
- Artifact layout details beyond calling `ArtifactStore.put` and using returned `ArtifactRef` values.
- Database schema details beyond the `EventRecordStore` contract.
- Real model vendor configuration, prompt management, or provider retries. These belong to AI provider implementations.
- Scheduling or daemon behavior. Scheduled runs call the pipeline repeatedly with overlapping capture windows.
- Search, vector indexing, export, or Notion sync.

## 3. Core terms

### 3.1 CaptureEvent

`CaptureEvent` is the normalized input boundary emitted by adapters and consumed by the pipeline.

Required semantics:

- `id`: stable event ID inside Shiyi.
- `source`: source identity.
- `occurred_at`: source event timestamp when available, otherwise discovery/fetch time.
- `payload`: typed raw-ish event payload (`html`, `text`, or `binary`).
- `provenance`: adapter name/version, source item ID, and fetch timestamp.
- `idempotency_key`: stable logical identity for replay safety.
- `metadata`: source/event descriptive metadata. This is not pipeline processing state.

### 3.2 Artifact

An artifact is durable content stored outside event-record storage.

Pipeline-created artifact kinds:

- `raw`: original payload material from the event.
- `normalized`: canonical Markdown/text or other normalized form.
- `enrichment`: validated AI enrichment JSON.

### 3.3 EventRecord

`EventRecord` is the pipeline processing ledger for one logical capture event.

It tracks:

- event ID;
- idempotency key;
- processing status;
- raw artifact reference;
- normalized artifact reference;
- last error when applicable;
- enrichment artifact references through the store implementation.

`EventRecord` is deliberately not called metadata because `CaptureEvent.metadata` already means source/event descriptive metadata.

### 3.4 EnrichmentResult

`EnrichmentResult` is a structured AI-provider result for a configured task such as `summarize`, `classify`, or `extract`.

The pipeline treats provider output as untrusted until it has been parsed into the domain model and persisted as an enrichment artifact.

## 4. Ports used by the pipeline

The pipeline depends on explicit ports only:

```python
class Adapter(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    def discover(self) -> AsyncIterator[CaptureEvent]: ...

class Normalizer(Protocol):
    async def normalize(self, event: CaptureEvent) -> ArtifactWrite | None: ...

class ArtifactStore(Protocol):
    async def put(self, artifact: ArtifactWrite) -> ArtifactRef: ...
    async def get(self, ref: ArtifactRef) -> ArtifactRead: ...
    async def exists(self, ref: ArtifactRef) -> bool: ...

class EventRecordStore(Protocol):
    async def find_by_idempotency_key(self, idempotency_key: str) -> EventRecord | None: ...
    async def save_event(
        self,
        event: CaptureEvent,
        *,
        raw_artifact: ArtifactRef | None,
        normalized_artifact: ArtifactRef | None,
    ) -> EventRecord: ...
    async def save_enrichment(
        self,
        event: CaptureEvent,
        result: EnrichmentResult,
        artifact: ArtifactRef,
    ) -> EventRecord: ...

class AIProvider(Protocol):
    @property
    def name(self) -> str: ...
    async def run(self, task: EnrichmentTask, event: CaptureEvent) -> EnrichmentResult: ...
```

## 5. End-to-end flow

The current pipeline flow is:

```text
Adapter.discover()
  -> CaptureEvent
  -> find existing EventRecord by idempotency_key
  -> skip if existing.status == enriched
  -> convert CaptureEvent.payload to raw ArtifactWrite
  -> ArtifactStore.put(raw)
  -> Normalizer.normalize(event) when configured
  -> ArtifactStore.put(normalized) when normalizer returns content
  -> EventRecordStore.save_event(..., status=persisted)
  -> for each EnrichmentTask:
       AIProvider.run(task, event)
       serialize EnrichmentResult as enrichment ArtifactWrite
       ArtifactStore.put(enrichment)
       EventRecordStore.save_enrichment(..., status=enriched)
  -> return processed event count
```

Target flow adds explicit failure status and retry metadata without changing the boundary shape:

```text
for event in adapter.discover():
  validate event
  existing = event_record_store.find_by_idempotency_key(event.idempotency_key)
  decision = decide_skip_or_resume(existing)
  if decision == skip:
    record skipped summary
    continue

  try:
    raw_ref = persist_raw(event)
    normalized_ref = normalize_and_persist(event)
    event_record_store.save_event(event, raw_ref, normalized_ref)
    for task in enrichment_tasks:
      result = ai_provider.run(task, event)
      enrichment_ref = persist_enrichment(event, task, result)
      event_record_store.save_enrichment(event, result, enrichment_ref)
  except retryable_error as error:
    event_record_store.save_failure(event, error, retryable=True)
  except fatal_error as error:
    event_record_store.save_failure(event, error, retryable=False)
```

## 6. Stage specifications

### 6.1 Discover stage

Input: `Adapter`.

Output: async stream of `CaptureEvent` objects.

Rules:

- The adapter owns source-specific discovery, parsing, source metadata, and idempotency key construction.
- The pipeline must not know source-specific HTML/RSS/API structure.
- Adapter failures should be surfaced as typed errors in future work; the pipeline should not silently drop items.

### 6.2 Validate stage

Input: `CaptureEvent`.

Output: valid event or failure.

Rules:

- Pydantic model construction validates structural fields.
- The pipeline may add semantic validation later: payload size, required provenance, supported content type.
- Invalid events must not produce durable artifacts unless explicitly stored for debugging under policy.

Current status: model validation exists; explicit pipeline semantic validation is still minimal.

### 6.3 Dedupe/resume stage

Input: `event.idempotency_key`.

Output: process, skip, or resume decision.

Rules:

- `EventRecordStore.find_by_idempotency_key` is the only pipeline-level idempotency lookup.
- If an existing record is `enriched`, the event is complete and should be skipped.
- If an existing record is incomplete or failed, the pipeline may resume/retry using the same idempotency key.
- The pipeline must not consult fetch raw cache for processing idempotency. Fetch cache only avoids repeated full-page downloads.

Current status: records with status `enriched` are skipped; other statuses are reprocessed.

### 6.4 Raw artifact stage

Input: `CaptureEvent.payload`.

Output: raw `ArtifactRef`.

Rules:

- `html` payload becomes `text/html` raw artifact.
- `text` payload uses its declared content type.
- `binary` payload records a reference payload as raw content until real binary handling is introduced.
- The pipeline persists event-level raw artifacts even if fetcher-level raw cache was hit. Fetch cache and durable pipeline artifacts are separate concerns.

### 6.5 Normalize stage

Input: `CaptureEvent` and optional `Normalizer`.

Output: normalized `ArtifactRef | None`.

Rules:

- Normalization is optional.
- If no normalizer is configured, the pipeline still persists raw and event record state.
- If the normalizer returns `None`, no normalized artifact is written.
- Normalizers must not write event records directly.

Current MVP normalizer: HTML to Markdown/text artifact.

### 6.6 Save event record stage

Input: event, raw artifact ref, normalized artifact ref.

Output: `EventRecord`.

Rules:

- Saving an event record records that the event payload and available normalized artifact have been persisted.
- MVP status after this stage is `persisted`.
- This stage must not embed artifact blobs; it stores references.
- `CaptureEvent.metadata` may be stored in a future schema if needed, but it remains source/event descriptive metadata, not pipeline state.

### 6.7 Enrichment stage

Input: configured `EnrichmentTask` list and `CaptureEvent`.

Output: one `EnrichmentResult` per task.

Rules:

- Enrichment tasks are explicit pipeline configuration.
- The pipeline calls `AIProvider.run(task, event)` and expects a typed result.
- AI providers must not persist final records directly.
- The pipeline should eventually prefer normalized artifacts as enrichment input when provider contracts support artifact references; current provider contract receives the event.

Current MVP tasks: summarize and multi-label classify.

### 6.8 Persist enrichment stage

Input: `EnrichmentResult`.

Output: enrichment `ArtifactRef` and updated `EventRecord`.

Rules:

- Enrichment results are serialized as JSON artifacts.
- The event record store records enrichment references and transitions status.
- MVP status after successful enrichment save is `enriched`.
- Future multi-task behavior should distinguish `partially_enriched` from fully `enriched`.

### 6.9 Observe stage

Input: run results and stage outcomes.

Output: CLI summary, logs, and future metrics/traces.

Rules:

- The pipeline should expose enough counts for daily operation: discovered, processed, skipped, duplicate/already-complete, failed, enriched.
- Current `run_once` returns only processed count. CLI derives additional counts from the local store.
- P1 should add explicit skipped/duplicate/failure summary fields when pipeline exposes them.

## 7. State model

Allowed domain statuses:

```text
persisted
  raw and optional normalized artifacts have been persisted;
  enrichment is not guaranteed complete.

enriched
  configured enrichment work has completed successfully for the event.

partially_enriched
  some enrichment work completed, but at least one task remains missing or failed.

failed
  processing failed and should be inspected or retried according to retry metadata.

skipped
  event was intentionally skipped by policy.
```

MVP implemented transitions:

```text
new -> persisted -> enriched
existing enriched -> skipped by pipeline without writing a new record
```

Target near-term transitions:

```text
new -> persisted -> enriched
new -> failed
persisted -> partially_enriched
partially_enriched -> enriched
failed -> persisted -> enriched
existing enriched -> skipped summary
```

Rules:

- Status transitions belong to `EventRecordStore`; adapters do not set pipeline processing status.
- Fetch raw cache hits do not imply `persisted` or `enriched`.
- Event records are the source of truth for pipeline resume behavior in MVP.

## 8. Idempotency and replay

### 8.1 Idempotency key

Adapters provide `idempotency_key`. Recommended shape:

```text
<source-kind>:<source-item-id-or-canonical-url>
```

Rules:

- The same logical source item must produce the same idempotency key across overlapping runs.
- The pipeline must not create duplicate logical event records for the same key.
- SQLite enforces uniqueness for MVP local storage.

### 8.2 Overlapping capture windows

Daily capture should use 2-3 days of overlap and rely on idempotency:

```bash
uv run shiyi capture --source openai --workspace .shiyi/openai --since 2026-05-10 --until 2026-05-13 --max-items 100
```

Rules:

- Overlap is expected and safe.
- Complete records are skipped.
- Incomplete/failed records are candidates for retry/resume.

### 8.3 Content changes

A source item may change under the same idempotency key.

Target rule:

- The pipeline should compute a canonical content fingerprint after normalization.
- If the same idempotency key appears with a different fingerprint, record a version or conflict explicitly.
- Do not silently overwrite prior artifacts without traceability.

Current status: content fingerprint/version semantics are not implemented yet.

## 9. Artifact and event-record boundaries

### 9.1 ArtifactStore owns content bytes

Artifact store owns:

- raw HTML/text/reference payloads;
- normalized Markdown/text;
- enrichment JSON;
- content digest and size;
- backend-specific URI layout.

### 9.2 EventRecordStore owns processing ledger

Event record store owns:

- idempotency key lookup;
- status transitions;
- artifact references;
- enrichment references;
- last error and retry metadata in target behavior.

### 9.3 CaptureEvent.metadata remains descriptive

`CaptureEvent.metadata` may include source-level facts such as title, author, URL, tags from the source, feed fields, or adapter-specific hints.

It must not become the pipeline status ledger. That belongs to `EventRecord`.

## 10. Failure behavior

Current MVP behavior is intentionally simple: unhandled exceptions fail the run. This is acceptable for local MVP but not enough for daily operation.

Target behavior:

- Raw persistence failure: mark event failed if possible; do not continue to normalization/enrichment.
- Normalization failure: keep raw artifact, mark failed or persisted-with-error depending on policy.
- Event record write failure: fail fast; do not continue because resume state is unreliable.
- AI provider failure: preserve already-written raw/normalized artifacts; mark failed or partially enriched.
- Enrichment artifact failure: do not mark the enrichment task successful.
- Parse/fetch failures inside adapters should become explicit failures in adapter results or typed exceptions in a future adapter contract revision.

Retry metadata target fields:

- `last_error`;
- `retry_count`;
- `last_attempt_at`;
- `next_retry_at | None`;
- `retryable`.

These are P1 and should be added only when needed by daily capture operations. Do not add unused fields just to make the schema look complete.

## 11. Observability and summaries

Pipeline/run summaries should eventually include:

- source;
- workspace;
- discovered count;
- processed count;
- skipped/already-complete count;
- failed count;
- enriched event count;
- enrichment row count;
- artifact count;
- raw-cache hit count when fetchers expose it;
- run duration.

Current CLI summary includes:

- source;
- workspace;
- processed;
- total events;
- enriched events;
- enrichments;
- artifact count.

P1 should add skipped/duplicates/failure fields after pipeline exposes those outcomes directly.

## 12. Testing requirements

### 12.1 Existing required coverage

The MVP must keep tests for:

- domain model validation;
- fake adapter + fake AI provider pipeline behavior;
- duplicate enriched record skip;
- raw artifact persistence;
- normalized artifact persistence;
- enrichment artifact persistence;
- filesystem artifact store;
- SQLite event record store;
- CLI capture/list behavior;
- OpenAI and Anthropic adapter behavior with fake fetchers.

### 12.2 Required next tests

P1 should add tests for:

- skipped/duplicate summary counts;
- failure status persistence;
- retry metadata updates;
- partial enrichment behavior;
- normalizer failure behavior;
- AI provider failure behavior;
- overlapping daily capture window idempotency at pipeline summary level.

## 13. Acceptance criteria

A pipeline change is acceptable only if:

1. The main flow remains simple: adapter -> pipeline -> artifact store + event record store -> AI provider.
2. Fetcher concerns do not leak into pipeline state decisions.
3. Source metadata and pipeline event records remain distinct.
4. Replaying the same completed event does not duplicate logical records.
5. Raw and normalized artifacts are inspectable and referenced by event records.
6. Enrichment results are persisted as artifacts before being recorded as successful.
7. Failure behavior is explicit when introduced; no hidden infinite retries.
8. Tests pass locally and in CI.

## 14. Split policy for future specs

Keep this document as the single pipeline SDD until one stage has independent design pressure.

Split a stage into its own SDD only when at least one is true:

- It has its own public port and multiple implementations.
- It needs a separate state machine.
- It has provider/backend-specific policy.
- It has enough tests and acceptance criteria to review independently.

Likely future split candidates:

- failure/retry SDD;
- enrichment orchestration SDD;
- event versioning/fingerprint SDD;
- pipeline observability/run-summary SDD.

Do not split specs just to make the docs look more enterprise. Split only when review and implementation benefit from the separation.
