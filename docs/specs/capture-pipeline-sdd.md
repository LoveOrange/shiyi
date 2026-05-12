# Shiyi Capture Pipeline SDD

- Status: Review
- Owner: Shiyi contributors
- Last updated: 2026-05-12
- Scope: capture pipeline orchestration from adapter events to durable raw/normalized artifacts, event records, and optional neutral preprocessing artifacts

## 1. Purpose

This document specifies the Capture Pipeline behavior for Shiyi. It is the single pipeline-level SDD for now.

We intentionally keep the pipeline stages in one document because the hard part is not an individual stage; it is the ordering, boundary, and state transition between stages. Split stage-specific SDDs only when a stage develops enough independent complexity to justify it.

The pipeline coordinates these responsibilities:

1. Consume `CaptureEvent` objects from an adapter.
2. Use idempotency to skip already-complete logical events.
3. Persist raw source payloads as artifacts.
4. Normalize event payloads into canonical artifacts when a normalizer is configured.
5. Persist processing state in an `EventRecordStore`.
6. Optionally run configured neutral preprocessing tasks through a transitional `AIProvider`.
7. Persist validated neutral annotation/preprocess results as artifacts.
8. Update event records with status and artifact references.

## 2. Non-goals

The pipeline must not own these responsibilities:

- Fetching HTTP pages, RSS feeds, sitemaps, pagination, timeout, retry, or raw fetch cache. These belong to fetchers.
- Source-specific parsing, source identity, source timestamps, source metadata, or adapter-defined raw keys. These belong to adapters.
- Artifact layout details beyond calling `ArtifactStore.put` and using returned `ArtifactRef` values.
- Database schema details beyond the `EventRecordStore` contract.
- Real model vendor configuration, prompt management, or provider retries. These belong to provider implementations.
- Scheduling or daemon behavior. Scheduled runs call the pipeline repeatedly with overlapping capture windows.
- Product-specific insight generation, ranking, scoring, weekly-report selection, search, export, or Notion sync.

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
- `enrichment`: transitional artifact kind for validated neutral annotation/preprocess JSON.

### 3.3 EventRecord

`EventRecord` is the pipeline processing ledger for one logical capture event.

It tracks:

- event ID;
- idempotency key;
- processing status;
- raw artifact reference;
- normalized artifact reference;
- last error when applicable;
- annotation/preprocess artifact references through the store implementation.

`EventRecord` is deliberately not called metadata because `CaptureEvent.metadata` already means source/event descriptive metadata.

### 3.4 Neutral annotation / transitional EnrichmentResult

`EnrichmentResult` is the current transitional implementation name for a neutral preprocessing/annotation result. It may represent reusable facts such as neutral summaries, entities, coarse topics, language, quality signals, chunks, or embeddings.

The pipeline treats provider output as untrusted until it has been parsed into the domain model and persisted as an annotation artifact. Product-specific insight output is out of scope.

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
    async def mark_enriched(self, event: CaptureEvent) -> EventRecord: ...

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
  -> count already-complete and skip if existing.status == enriched
  -> convert CaptureEvent.payload to raw ArtifactWrite
  -> ArtifactStore.put(raw)
  -> Normalizer.normalize(event) when configured
  -> ArtifactStore.put(normalized) when normalizer returns content
  -> EventRecordStore.save_event(..., status=persisted)
  -> if neutral preprocess tasks are configured:
       for each transitional EnrichmentTask / future PreprocessTask:
         AIProvider.run(task, event)  # MVP temporary input shape
         serialize result as annotation ArtifactWrite
         ArtifactStore.put(annotation)
         EventRecordStore.save_enrichment(...)  # append annotation ref only
       EventRecordStore.mark_enriched(...) after all configured tasks succeed
  -> if no neutral preprocess tasks are configured:
       target behavior should mark the event captured/complete after raw + normalized persistence
  -> return processed event count
```

Target flow adds explicit failure status and retry metadata without changing the boundary shape:

```text
for event in adapter.discover():
  validate event
  existing = event_record_store.find_by_idempotency_key(event.idempotency_key)
  decision = decide_skip_or_resume(existing)
  if decision == skip:
    record already_complete/skipped run outcome
    continue

  try:
    raw_ref = persist_raw(event)
    normalized_ref = normalize_and_persist(event)
    event_record_store.save_event(event, raw_ref, normalized_ref)
    if preprocess_tasks:
      for task in preprocess_tasks:
        canonical_input = load_normalized_or_raw_content(event, normalized_ref, raw_ref)
        result = preprocess_provider.run(task, canonical_input)
        annotation_ref = persist_annotation(event, task, result)
        event_record_store.save_annotation(event, result, annotation_ref)
      event_record_store.mark_preprocessed(event)
    else:
      event_record_store.mark_captured(event)
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
- MVP status after this stage is `persisted`. `persisted` means raw and optional normalized artifacts are durable and referenced; it does not mean optional preprocessing or semantic annotation is complete.
- This stage must not embed artifact blobs; it stores references.
- `CaptureEvent.metadata` may be stored in a future schema if needed, but it remains source/event descriptive metadata, not pipeline state.

### 6.7 Optional neutral preprocessing stage

Input: optional configured neutral preprocessing task list plus canonical content from the normalized artifact when available.

Output: one neutral annotation/preprocess result per task.

Rules:

- Neutral preprocessing tasks are explicit pipeline configuration and must be disableable.
- Target behavior: preprocessing should operate on normalized/canonical content, with the event used only for provenance and source/event descriptive metadata.
- Current MVP behavior: the provider contract is still `AIProvider.run(task, event)` and task classes are still named `EnrichmentTask`. This is a temporary compatibility shape, not the long-term semantic target.
- Providers must not persist final records directly.
- The pipeline must not let preprocessing bypass normalization indefinitely; otherwise normalized artifacts become decorative instead of canonical.
- Product-specific insight prompts, ranking, or business opinions are out of scope.

Current MVP tasks are local heuristic annotations only. Future specs should rename them toward `PreprocessTask`, `AnnotationTask`, or `ExtractionTask`.

### 6.8 Persist annotation/preprocess stage

Input: neutral annotation/preprocess result.

Output: annotation `ArtifactRef` and updated `EventRecord`.

Rules:

- Neutral annotation results are serialized as JSON artifacts.
- Current `save_enrichment` naming is transitional; semantically it records an annotation/preprocess artifact reference only.
- The pipeline should mark a preprocess-complete terminal state only after every configured required preprocess task succeeds.
- If task 1 succeeds and task 2 fails, the event must not be marked complete for that mode; otherwise replay would incorrectly skip an incomplete event.
- If no preprocess tasks are configured, target behavior should mark the event captured/complete after raw and normalized artifacts are persisted. The current implementation still needs a follow-up completion state/name cleanup for this mode.

### 6.9 Observe stage

Input: run results and stage outcomes.

Output: CLI summary, logs, and future metrics/traces.

Rules:

- The pipeline should expose enough counts for daily operation: discovered, processed, already_complete, duplicate, skipped, failed, enriched.
- Current `run_once` returns only processed count. CLI derives additional counts from the local store.
- P1 should add explicit outcome fields when pipeline exposes them.
- Outcome definitions: `already_complete` means an existing event record is `enriched`; `duplicate` means the same idempotency key appeared more than once in a single run; `skipped` means a policy decision intentionally skipped an event.

## 7. State model

Allowed persisted `EventRecord.status` values:

```text
persisted
  raw and optional normalized artifacts have been persisted;
  optional preprocessing is not guaranteed complete.

enriched / preprocessed (transitional naming)
  configured neutral preprocessing work has completed successfully for the event. The name `enriched` is transitional and should not imply business insight.

partially_enriched
  some preprocessing work completed, but at least one task remains missing or failed.

failed
  processing failed and should be inspected or retried according to retry metadata.
```

MVP implemented transitions:

```text
new -> persisted
persisted -> enriched/preprocessed only after all configured neutral preprocessing tasks succeed
existing enriched -> already_complete run outcome without writing a new record
```

Target near-term transitions:

```text
new -> persisted -> enriched
new -> failed
persisted -> partially_enriched when at least one required task succeeds and another remains missing/failed
partially_enriched -> enriched only after all required tasks complete
failed -> persisted -> enriched
existing enriched -> already_complete/skipped run summary outcome
```

Rules:

- Status transitions belong to `EventRecordStore`; adapters do not set pipeline processing status.
- Fetch raw cache hits do not imply `persisted` or `enriched`.
- Event records are the source of truth for pipeline resume behavior in MVP.
- `enriched` currently means all configured required neutral preprocessing tasks completed successfully, not merely that one annotation artifact exists. The name is transitional.
- `skipped` is a run outcome or summary counter, not a persisted event-record status for replaying an already-complete event.

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

Target rule for a later dedicated versioning/fingerprint spec:

- The pipeline should compute a canonical content fingerprint after normalization.
- If the same idempotency key appears with a different fingerprint, record a version or conflict explicitly.
- Do not silently overwrite prior artifacts without traceability.

Current status: content fingerprint/version semantics are not implemented yet and must not affect the v0.2 replay/cache/pipeline main flow.

## 9. Artifact and event-record boundaries

### 9.1 ArtifactStore owns content bytes

Artifact store owns:

- raw HTML/text/reference payloads;
- normalized Markdown/text;
- annotation/preprocess JSON;
- content digest and size;
- backend-specific URI layout.

### 9.2 EventRecordStore owns processing ledger

Event record store owns:

- idempotency key lookup;
- status transitions;
- artifact references;
- annotation/preprocess references;
- last error and retry metadata in target behavior.

### 9.3 CaptureEvent.metadata remains descriptive

`CaptureEvent.metadata` may include source-level facts such as title, author, URL, tags from the source, feed fields, or adapter-specific hints.

It must not become the pipeline status ledger. That belongs to `EventRecord`.

## 10. Failure behavior

Current MVP behavior is intentionally simple: unhandled exceptions fail the run. This is acceptable for local MVP but not enough for daily operation.

Target behavior:

- Raw persistence failure: mark event failed if possible; do not continue to normalization/preprocessing.
- Normalization failure: keep raw artifact, mark failed with the raw artifact reference when possible.
- Event record write failure: fail fast; do not continue because resume state is unreliable.
- Preprocess provider failure: preserve already-written raw/normalized artifacts; mark failed or partially preprocessed when that state exists.
- Annotation artifact failure: do not mark the preprocess task successful.
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
- complete/preprocessed event count;
- annotation/preprocess row count;
- artifact count;
- raw-cache hit count when fetchers expose it;
- run duration.

Current CLI summary includes:

- source;
- workspace;
- processed;
- total events;
- enriched/preprocessed events;
- enrichment/annotation rows;
- artifact count.

P1 should add already_complete/duplicate/skipped/failure fields after pipeline exposes those outcomes directly.

## 12. Testing requirements

### 12.1 Existing required coverage

The MVP must keep tests for:

- domain model validation;
- fake adapter + fake AI provider pipeline behavior;
- duplicate enriched record skip;
- raw artifact persistence;
- normalized artifact persistence;
- annotation/preprocess artifact persistence;
- filesystem artifact store;
- SQLite event record store;
- CLI capture/list behavior;
- OpenAI and Anthropic adapter behavior with fake fetchers.

### 12.2 Required next tests

P1 should add tests for:

- already_complete/duplicate/skipped summary counts;
- multi-task preprocessing does not mark the event complete until all configured required tasks succeed;
- failure status persistence;
- retry metadata updates;
- partial preprocessing behavior;
- normalizer failure behavior;
- AI provider failure behavior;
- overlapping daily capture window idempotency at pipeline summary level.

## 13. Acceptance criteria

A pipeline change is acceptable only if:

1. The main flow remains simple: adapter -> pipeline -> artifact store + event record store + optional neutral preprocessor.
2. Fetcher concerns do not leak into pipeline state decisions.
3. Source metadata and pipeline event records remain distinct.
4. Replaying the same completed event does not duplicate logical records.
5. Raw and normalized artifacts are inspectable and referenced by event records.
6. Neutral preprocessing results are persisted as artifacts before being recorded as successful.
7. The terminal preprocess-complete status is written only after every configured required preprocess task succeeds.
8. Capture-only mode has a defined terminal completion state and does not require AI preprocessing.
9. Failure behavior is explicit when introduced; no hidden infinite retries.
10. Tests pass locally and in CI.

## 14. Split policy for future specs

Keep this document as the single pipeline SDD until one stage has independent design pressure.

Split a stage into its own SDD only when at least one is true:

- It has its own public port and multiple implementations.
- It needs a separate state machine.
- It has provider/backend-specific policy.
- It has enough tests and acceptance criteria to review independently.

Likely future split candidates:

- failure/retry SDD;
- neutral preprocessing orchestration SDD;
- event versioning/fingerprint SDD;
- pipeline observability/run-summary SDD.

Do not split specs just to make the docs look more enterprise. Split only when review and implementation benefit from the separation.
