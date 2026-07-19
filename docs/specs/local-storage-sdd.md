# Content Storage SDD

- Status: Accepted
- Owner: Shiyi contributors
- Last updated: 2026-07-19
- Scope: canonical `ContentItem` storage plus raw/large/cold Blob storage

## 1. Decision

Use MongoDB as the canonical hot/query store for `ContentItem`. Use filesystem storage initially, and COS later, for raw, oversized, or cold bytes referenced by `BlobRef`.

SQLite event records and filesystem artifacts are not parallel canonical representations.

## 2. ContentItemStore

The MVP persistence port is:

```python
class ContentItemStore(Protocol):
    async def get(self, item_id: str) -> ContentItem | None: ...
    async def upsert(self, item: ContentItem) -> None: ...
```

MongoDB uses deterministic `ContentItem.id` as `_id`. Repeated writes replace/update the same logical document.

Briefly reads documents whose `ready_at` is non-null. Incremental reads should use `(updated_at, _id)` ordering.

## 3. BlobStore

Raw or large content may be written through:

```python
class BlobStore(Protocol):
    async def put(self, content: bytes, *, media_type: str) -> BlobRef: ...
```

Blob keys are content-addressed by SHA-256 so repeated identical bytes do not duplicate storage.

`BlobRef` contains store, key, hash, media type, and byte size. A later COS implementation preserves this logical contract.

## 4. Inline and referenced content

Normalized Markdown normally remains inline in MongoDB for Briefly queries. Raw HTML/API payloads, attachments, unusually large normalized content, and cold archived bodies belong in Blob storage.

The application must enforce a document-size guard below MongoDB's hard BSON limit. Moving content to Blob storage must preserve hash verification and an auditable reference.

## 5. Indexes

Initial MongoDB indexes:

```text
{ published_at: -1, _id: 1 }
{ source_id: 1, published_at: -1 }
{ categories: 1, published_at: -1 }
{ tags: 1, published_at: -1 }
{ language: 1, published_at: -1 }
{ updated_at: 1, _id: 1 }
```

Do not combine `categories` and `tags` into one compound index because both are arrays.

## 6. Validation and operations

- Configure MongoDB schema validation for the canonical contract.
- Bound category, tag, creator, metrics, and `extra` sizes.
- Use a replica set, backups, and restore verification before Briefly production launch.
- Give Briefly read-only credentials.
- Verify SHA-256 before deleting a local or inline copy during COS migration.

## 7. Non-goals

- event status tables;
- separate enrichment result tables;
- multiple competing canonical stores;
- search engines or analytics warehouses as the source of truth;
- premature hot/cold orchestration before volume requires it.
