# Shiyi Capture Pipeline SDD

- Status: Review
- Owner: Shiyi contributors
- Last updated: 2026-05-16
- Scope: capture pipeline orchestration from adapter internal items to durable raw/normalized artifacts, event records, and optional neutral annotation artifacts

## 1. Purpose

This document specifies the Capture Pipeline behavior for Shiyi. It is the single pipeline-level SDD for now.

We intentionally keep the pipeline stages in one document because the hard part is not an individual stage; it is the ordering, boundary, and state transition between stages. Split stage-specific SDDs only when a stage develops enough independent complexity to justify it.

The pipeline coordinates these responsibilities:

1. Consume `InternalItem` objects from an adapter.
2. Use idempotency to skip already-complete logical items.
3. Persist raw source payloads as artifacts.
4. Normalize item payloads into canonical artifacts when a normalizer is configured.
5. Persist processing state in an `EventRecordStore`.
6. Optionally run configured neutral enrichment tasks through an `AIProvider`.
7. Persist validated neutral annotation results as artifacts.
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

### 3.1 InternalItem

`InternalItem` is the normalized Adapter -> Pipeline input boundary emitted by adapters and consumed by the pipeline.

Required v1 schema semantics:

- `schema_version`: fixed schema marker. MVP value is `internal-item.v1`; change this only when the Adapter -> Pipeline contract intentionally changes.
- `id`: stable item ID inside Shiyi.
- `source`: source identity.
- `captured_at`: time Shiyi captured or fetched the item payload.
- `occurred_at`: source item timestamp when available, otherwise discovery/fetch time.
- `payload`: typed raw-ish item payload (`html`, `text`, or `binary`). For source-ready built-in adapters, this should be the event-level full article/detail payload when the source exposes one, not merely a listing/feed summary. If discovery started from RSS, changelog, or another listing surface, the decision-grade payload should be the dereferenced canonical detail surface itself—usually the full article webpage, otherwise an official structured detail payload when that is the stable source of truth.
- `content_hash`: deterministic SHA-256 over normalized payload material. It is for traceability/change detection, not source dedupe.
- `provenance`: adapter name/version, source item ID, and fetch timestamp.
- `idempotency_key`: stable logical dedupe key for replay safety.
- `metadata`: source/item descriptive metadata. This is not pipeline processing state. Source-neutral content-depth markers may live here until a dedicated content-quality model exists. Use `content_depth` with one of `full_page`, `feed_full_content`, `summary_only`, `partial`, or `blocked`; only `full_page` and `feed_full_content` are decision-grade by default.

Version policy: because Shiyi is still MVP, breaking schema changes rename/update the v1 contract directly across code, tests, and docs. Add a new schema version only when a real external consumer needs two versions to coexist.

### 3.2 Artifact

An artifact is durable content stored outside event-record storage.

Pipeline-created artifact kinds:

- `raw`: original payload material from the item.
- `normalized`: canonical Markdown/text or other normalized form.
- `enrichment`: artifact kind for validated neutral annotation JSON.

### 3.3 EventRecord

`EventRecord` is the pipeline processing ledger for one logical internal item.

It tracks:

- event ID;
- idempotency key;
- processing status;
- raw artifact reference;
- normalized artifact reference;
- last error when applicable;
- annotation artifact references through the store implementation.

`EventRecord` is deliberately not called metadata because `InternalItem.metadata` already means source/item descriptive metadata.

### 3.4 Neutral annotation / EnrichmentResult

`EnrichmentResult` is the MVP result model for a neutral annotation. It may represent reusable facts such as neutral summaries, entities, coarse topics, language, quality signals, chunks, or embeddings.

The pipeline treats provider output as untrusted until it has been parsed into the domain model and persisted as an annotation artifact. Product-specific insight output is out of scope.

## 4. Ports used by the pipeline

The pipeline depends on explicit ports only:

```python
class Adapter(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    def discover(self) -> AsyncIterator[InternalItem]: ...

class Normalizer(Protocol):
    async def normalize(self, event: InternalItem) -> ArtifactWrite | None: ...

class ArtifactStore(Protocol):
    async def put(self, artifact: ArtifactWrite) -> ArtifactRef: ...
    async def get(self, ref: ArtifactRef) -> ArtifactRead: ...
    async def exists(self, ref: ArtifactRef) -> bool: ...

class EventRecordStore(Protocol):
    async def find_by_idempotency_key(self, idempotency_key: str) -> EventRecord | None: ...
    async def save_event(
        self,
        event: InternalItem,
        *,
        raw_artifact: ArtifactRef | None,
        normalized_artifact: ArtifactRef | None,
    ) -> EventRecord: ...
    async def save_enrichment(
        self,
        event: InternalItem,
        result: EnrichmentResult,
        artifact: ArtifactRef,
    ) -> EventRecord: ...
    async def mark_enriched(self, event: InternalItem) -> EventRecord: ...


class AIProvider(Protocol):
    @property
    def name(self) -> str: ...
    async def run(self, task: EnrichmentTask, event: InternalItem) -> EnrichmentResult: ...
```

## 5. End-to-end flow

The MVP pipeline flow is:

```text
Adapter.discover()
  -> InternalItem
  -> find existing EventRecord by idempotency_key
  -> skip duplicate idempotency keys seen in the same run
  -> skip if an existing record is already complete for the configured pipeline
  -> convert InternalItem.payload to raw ArtifactWrite
  -> ArtifactStore.put(raw)
  -> Normalizer.normalize(event) when configured
  -> ArtifactStore.put(normalized) when normalizer returns content
  -> EventRecordStore.save_event(..., status=persisted)
  -> for each configured EnrichmentTask:
       AIProvider.run(task, event)
       serialize result as enrichment ArtifactWrite
       ArtifactStore.put(enrichment)
       EventRecordStore.save_enrichment(...)
  -> EventRecordStore.mark_enriched(...) after all configured tasks succeed
  -> return PipelineRunSummary with processed/skipped/failed/artifact/error counts
```

Item-level failure handling records explicit failure metadata without turning the whole run into a mystery E2E failure:

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
    for task in enrichment_tasks:
      result = ai_provider.run(task, event)
      enrichment_ref = persist_enrichment(event, task, result)
      event_record_store.save_enrichment(event, result, enrichment_ref)
    event_record_store.mark_enriched(event)
  except item_error as error:
    event_record_store.save_failure(event, available_artifact_refs, error_context)
    record failed run outcome and continue with the next item
```

## 6. Stage specifications

### 6.1 Discover stage

Input: `Adapter`.

Output: async stream of `InternalItem` objects.

Rules:

- The adapter owns source-specific discovery, parsing, source metadata, and idempotency key construction.
- For built-in source-ready adapters, discovery may start from RSS/index/changelog entries, but the adapter/fetcher boundary must resolve the canonical article/detail content before emitting a decision-grade `InternalItem`.
- For RSS/listing-driven sources, this means the emitted decision-grade item should be based on the dereferenced original article/detail surface, not the feed/listing text itself.
- The pipeline must not know source-specific HTML/RSS/API structure.
- Adapter failures should be surfaced as typed errors in future work; the pipeline should not silently drop items.

### 6.2 Validate stage

Input: `InternalItem`.

Output: valid item or failure.

Rules:

- Pydantic model construction validates structural fields.
- The pipeline may add semantic validation later: payload size, required provenance, supported content type.
- Invalid items must not produce durable artifacts unless explicitly stored for debugging under policy.

Current status: model validation exists; explicit pipeline semantic validation is still minimal.

### 6.3 Dedupe/resume stage

Input: `item.idempotency_key`.

Output: process, skip, or resume decision.

Rules:

- `EventRecordStore.find_by_idempotency_key` is the only pipeline-level idempotency lookup.
- Duplicate idempotency keys inside one run are skipped after the first attempt.
- If enrichment tasks are configured, an existing `enriched` record is complete and should be skipped.
- If no enrichment tasks are configured, an existing `persisted` or `enriched` record is complete and should be skipped.
- If an existing record is incomplete or failed, the pipeline may resume/retry using the same idempotency key.
- The pipeline must not consult fetch raw cache for processing idempotency. Fetch cache only avoids repeated full-page downloads.

MVP status rule: `failed` records are candidates for reprocessing; `persisted` records are complete only for pipelines without configured enrichment tasks.

### 6.4 Raw artifact stage

Input: `InternalItem.payload`.

Output: raw `ArtifactRef`.

Rules:

- `html` payload becomes `text/html` raw artifact.
- `text` payload uses its declared content type.
- `binary` payload records a reference payload as raw content until real binary handling is introduced.
- The pipeline persists event-level raw artifacts even if fetcher-level raw cache was hit. Fetch cache and durable pipeline artifacts are separate concerns.
- For P2.5 source-ready built-ins, the raw artifact should preserve the full article/detail payload used for normalization. For RSS/listing-driven sources, this raw artifact should usually be the canonical detail webpage HTML, unless an official structured detail payload is the stable canonical surface. Listing/feed summaries alone are degraded records and must be marked with `content_depth=summary_only` before they reach consumers.

### 6.5 Normalize stage

Input: `InternalItem` and optional `Normalizer`.

Output: normalized `ArtifactRef | None`.

Rules:

- Normalization is optional.
- Normalizer input is the validated `InternalItem`; normalizers must not depend on third-party feed/page structures.
- Normalized output for source-ready built-ins should reflect the full article/detail payload rather than a discovery/feed snippet. If input is `summary_only`, `partial`, or `blocked`, the normalized artifact should not pretend to be decision-grade full content.
- A normalized output is an `ArtifactWrite` with `kind="normalized"`, canonical media type, bytes content, and optional normalizer metadata.
- If no normalizer is configured, the pipeline still persists raw and event-record state.
- If the normalizer returns `None`, no normalized artifact is written; this means the payload is unsupported or already canonical, not failure.
- Normalizers must not write artifacts or event records directly.
- Normalizer exceptions fail the current item, not unrelated processable items. The pipeline records a `failed` event record with available artifact context and continues.

Current MVP normalizer: HTML to Markdown/text artifact.

### 6.6 Save event record stage

Input: event, raw artifact ref, normalized artifact ref.

Output: `EventRecord`.

Rules:

- Saving an event record records that the item payload and available normalized artifact have been persisted.
- MVP status after this stage is `persisted`. `persisted` means raw and optional normalized artifacts are durable and referenced; it does not mean configured enrichment or semantic annotation is complete.
- This stage must not embed artifact blobs; it stores references.
- Persistent records store the trace fields required by P1-04: source, captured_at, content_hash, idempotency_key, adapter_name, and adapter_version.
- `InternalItem.metadata` may be stored in a future schema if needed, but it remains source/item descriptive metadata, not pipeline state.

### 6.7 Optional neutral annotation stage

Input: configured `EnrichmentTask` list plus the `InternalItem`.

Output: one neutral annotation result per task.

Rules:

- Neutral annotation tasks are explicit pipeline configuration.
- Providers must not persist final records directly.
- The pipeline must not let annotation work bypass normalization indefinitely once canonical-content provider input is introduced; otherwise normalized artifacts become decorative instead of canonical.
- Product-specific insight prompts, ranking, or business opinions are out of scope.

Current MVP tasks are local heuristic annotations only.

### 6.8 Persist enrichment artifact stage

Input: neutral annotation result.

Output: enrichment `ArtifactRef` and updated `EventRecord`.

Rules:

- Neutral annotation results are serialized as JSON enrichment artifacts.
- `save_enrichment` records the enrichment artifact reference.
- The pipeline marks `enriched` only after every configured task succeeds.
- If task 1 succeeds and task 2 fails, the item must not be marked `enriched`; otherwise replay would incorrectly skip an incomplete item.
- P2-04 hardens raw/normalization failure persistence and retry behavior; enrichment-row dedupe and partial-enrichment resume are future hardening, not part of the P2-04 exit gate.
- The CLI MVP configures enrichment tasks, so `enriched` is the terminal complete state used for replay skipping.

### 6.9 Observe stage

Input: run results and stage outcomes.

Output: CLI summary, logs, and future metrics/traces.

Rules:

- The pipeline should expose enough counts for daily operation: discovered, processed, already_complete, duplicate, skipped, failed, enriched.
- Current `run_once` returns `PipelineRunSummary` with processed, skipped, failed, artifact-write count, and structured item errors.
- CLI summary derives total item count, enriched item count, enrichment row count, and persisted artifact count from the local store, and includes run skipped/failed/error fields.

## 7. State model

MVP persisted `EventRecord.status` values:

```text
persisted
  raw and optional normalized artifacts have been persisted; configured enrichment tasks are not guaranteed complete.

enriched
  all configured neutral annotation tasks completed and their enrichment artifacts were recorded. This is the MVP terminal completion state used for replay skipping.

partially_enriched
  reserved for future partial-task recovery; not required by the current happy path.

failed
  the item attempt failed after the pipeline had enough `InternalItem` context to record diagnostics. `last_error` stores the boundary/stage context.
```

MVP transitions:

```text
new -> persisted -> enriched
new -> failed -> persisted
existing complete -> skip without writing a new record
```

Rules:

- Status transitions belong to `EventRecordStore`; adapters do not set pipeline processing status.
- Fetch raw cache hits do not imply `persisted` or `enriched`.
- Event records are the source of truth for pipeline replay behavior in MVP.
- `skipped` is a run outcome or summary counter, not a persisted event-record status.

## 8. Idempotency and replay

### 8.1 Idempotency key

Adapters provide `idempotency_key`. Recommended shape:

```text
<source-kind>:<source-item-id-or-canonical-url>
```

Rules:

- The same logical source item must produce the same idempotency key across overlapping runs.
- The pipeline must not create duplicate logical item records for the same key.
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
- annotation/enrichment JSON;
- content digest and size;
- backend-specific URI layout.

### 9.2 EventRecordStore owns processing ledger

Event record store owns:

- idempotency key lookup;
- status transitions;
- artifact references;
- annotation/enrichment references;
- last error and retry metadata when retry persistence is introduced.

### 9.3 InternalItem.metadata remains descriptive

`InternalItem.metadata` may include source-level facts such as title, author, URL, tags from the source, feed fields, or adapter-specific hints.

It must not become the pipeline status ledger. That belongs to `EventRecord`.

## 10. Failure behavior

MVP item-level failure behavior is intentionally simple and explicit:

- Raw persistence failure: mark event failed if possible; do not continue to normalization/enrichment.
- Normalization failure: keep raw artifact, mark failed with the raw artifact reference when possible, and continue with later items.
- Event record write failure: fail fast if failure state cannot be recorded; resume state is unreliable.
- AI provider failure: preserve already-written raw/normalized artifacts and mark the event failed instead of marking it enriched.
- Annotation artifact failure: do not mark the enrichment task successful.
- Parse/fetch failures inside adapters should become explicit failures in adapter results or typed exceptions in a future adapter contract revision.

Possible retry metadata fields when the retry task exists:

- `last_error`;
- `retry_count`;
- `last_attempt_at`;
- `next_retry_at | None`;
- `retryable`.

Add these only when needed by daily capture operations. Do not add unused fields just to make the schema look complete.

## 11. Observability and summaries

Pipeline/run summaries include:

- source;
- workspace;
- discovered count;
- processed count;
- skipped/already-complete count;
- failed count;
- enriched event count;
- annotation/enrichment row count;
- artifact count;
- raw-cache hit count when fetchers expose it;
- run duration.

Current CLI summary includes:

- source;
- workspace;
- processed;
- skipped;
- failed;
- errors;
- total events;
- enriched events;
- enrichment rows;
- artifact count.

## 12. Testing requirements

### 12.1 Existing required coverage

The MVP must keep tests for:

- domain model validation;
- fake adapter + fake AI provider pipeline behavior;
- duplicate already-complete record skip;
- raw artifact persistence;
- normalized artifact persistence;
- annotation/enrichment artifact persistence;
- filesystem artifact store;
- SQLite event record store;
- CLI capture/list behavior;
- OpenAI and Anthropic adapter behavior with fake fetchers.

### 12.2 Required next tests

Later hardening should add tests for:

- retry metadata updates beyond `last_error`;
- enrichment-row dedupe and partial-enrichment resume behavior;
- AI provider failure behavior;
- overlapping daily capture window idempotency at pipeline summary level.

## 13. Acceptance criteria

A pipeline change is acceptable only if:

1. The main flow remains simple: adapter -> pipeline -> artifact store + event record store + optional neutral enrichment.
2. Fetcher concerns do not leak into pipeline state decisions.
3. Source metadata and pipeline event records remain distinct.
4. Replaying the same completed item does not duplicate logical records.
5. Raw and normalized artifacts are inspectable and referenced by event records.
6. Neutral enrichment results are persisted as artifacts before being recorded as successful.
7. The terminal `enriched` status is written only after every configured enrichment task succeeds.
8. Completion and failure states remain explicit; no hidden partial-success terminal state.
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
- neutral enrichment orchestration SDD;
- event versioning/fingerprint SDD;
- pipeline observability/run-summary SDD.

Do not split specs just to make the docs look more enterprise. Split only when review and implementation benefit from the separation.
