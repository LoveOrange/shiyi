# Capture Runner SDD

- Status: Accepted
- Owner: Shiyi contributors
- Last updated: 2026-07-19
- Scope: `CaptureRunner` orchestration from configured sources to canonical `ContentItem` upserts
- Architecture: [`../architecture.md`](../architecture.md)

## 1. Objective

Run enabled source captures with the smallest deterministic orchestration that provides Briefly-ready, idempotent `ContentItem` documents.

## 2. Inputs and outputs

Input:

- `CaptureConfig` containing enabled `Source` targets;
- adapter implementations keyed by source adapter kind;
- one deterministic `ContentProcessor`;
- one `ContentItemStore`;
- optional `BlobStore`.

Output:

- upserted `ContentItem` documents;
- raw Blob references when configured;
- a run summary containing per-source processed, skipped, and failed counts.

## 3. Contracts

```python
class SourceAdapter(Protocol):
    @property
    def kind(self) -> str: ...

    def capture(self, source: Source) -> AsyncIterator[SourceItem]: ...


class ContentProcessor(Protocol):
    async def process(
        self,
        item: SourceItem,
        *,
        raw_ref: BlobRef | None,
    ) -> ContentItem: ...


class ContentItemStore(Protocol):
    async def get(self, item_id: str) -> ContentItem | None: ...
    async def upsert(self, item: ContentItem) -> None: ...


class BlobStore(Protocol):
    async def put(self, content: bytes, *, media_type: str) -> BlobRef: ...
```

The runner receives concrete implementations. It does not discover plugins at runtime during MVP.

## 4. Flow

For every enabled `Source` in configuration order:

1. Resolve exactly one adapter from `Source.adapter`.
2. Invoke `adapter.capture(source)`.
3. Validate each `SourceItem` and ensure it belongs to the requested source.
4. Persist raw bytes through `BlobStore` when raw retention is enabled. Use the
   adapter-preserved `SourceItem.raw_content` and `raw_media_type` when present;
   otherwise use the emitted payload bytes and media type.
5. Convert the source item to a canonical `ContentItem` using deterministic processing, promoting any non-empty source-provided summary.
6. Upsert deterministic content using `ContentItem.id`.
7. Record the outcome in the in-memory run summary.

One item failure does not stop later items or sources. An unresolved adapter fails that source and does not fall back to another implementation.

## 5. Identity and idempotency

`ContentItem.id` is the only durable idempotency key. The default identity material is source id plus source-native item id. When a native id is unavailable, the processor may use a canonical URL, but the chosen material must remain stable across runs.

`content_hash` is derived from canonical content and detects revisions. It is not a second identity.

Repeated capture:

- must upsert the same document id;
- must not create duplicate raw blobs for identical bytes;
- may update content, objective metrics, summary, labels, and `updated_at`;
- must preserve source identity and provenance.

There is no public `EventRecord`, event status machine, or duplicate `idempotency_key` field.

## 6. Readiness

The deterministic processor validates the required `ContentItem` fields. `ready_at` is set when the configured Briefly readiness requirements are satisfied.

Creators and optional AI fields are not globally required. If a specific Briefly deployment requires a summary, that requirement belongs to the configured readiness policy, not the base domain model.

AI availability is irrelevant to capture readiness because `CaptureRunner` never invokes AI.

## 7. Post-capture AI boundary

Optional AI enrichment runs separately through `AIEnrichmentRunner -> AIProviderACL -> AIProvider`. The full contract lives in [`ai-provider-sdd.md`](ai-provider-sdd.md).

Allowed optional output fields are:

- `language` when source/deterministic detection did not provide one;
- `summary`, only when the `ContentItem` does not already have one;
- `summary_language`;
- `categories`;
- `tags`.

AI may not modify ids, source provenance, canonical URL, creators, published time, collected time, original content, content hash, objective metrics, or Blob references.

`ContentItem.summary` is the only summary gate. If it is non-empty, the enrichment query does not select the item. No summary status or origin model is added for the MVP.

The ACL does not expose classify/extract/summarize task variants. One structured neutral enrichment request is enough for the MVP.

## 8. Errors and run summary

Every failure includes:

- source id;
- source item id when available;
- stage;
- exception type and message.

Stages are limited to:

- adapter resolution;
- capture;
- raw Blob persistence;
- deterministic processing;
- ContentItem upsert.

Retries belong to the adapter for source I/O or to the store implementation for transient storage errors. The runner does not hide infinite retries.

## 9. Test boundary

Required contract tests cover:

1. config with multiple sources sharing one adapter;
2. adapter receives the correct source target;
3. source-specific DTOs stop inside the adapter;
4. deterministic repeated runs upsert one item id;
5. identical raw bytes produce one Blob reference;
6. transformed binary documents retain their original bytes while canonical
   content remains Markdown;
7. one source failure does not block another source;
8. missing creators remain valid;
9. Briefly-ready queries return only `ready_at != null` documents.

AI ACL, provider, and enrichment-runner tests belong to the separate post-capture boundary and must prove that provider failure leaves the captured document unchanged.
