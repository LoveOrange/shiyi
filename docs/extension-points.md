# Shiyi Extension Points

Shiyi keeps four required capture/storage ports and one optional provider-neutral AI port during the Briefly-first MVP.

## SourceAdapter

```python
class SourceAdapter(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    def capture(self, source: Source) -> AsyncIterator[SourceItem]: ...
```

Adapters perform source-specific acquisition and keep third-party DTOs private. `Source.adapter` selects an implementation; `Source.target` and options describe what that implementation should collect.

## ContentProcessor

```python
class ContentProcessor(Protocol):
    async def process(
        self,
        item: SourceItem,
        *,
        raw_ref: BlobRef | None,
    ) -> ContentItem: ...
```

The default processor deterministically converts text-like payloads to Markdown, promotes source-neutral fields, computes identity and content hash, and evaluates base readiness.

## ContentItemStore

```python
class ContentItemStore(Protocol):
    async def get(self, item_id: str) -> ContentItem | None: ...
    async def upsert(self, item: ContentItem) -> None: ...
    async def list_ready(...) -> list[ContentItem]: ...
```

MongoDB is the production implementation. Test doubles may use memory, but they do not define another production authority.

## BlobStore

```python
class BlobStore(Protocol):
    async def put(self, content: bytes, *, media_type: str) -> BlobRef: ...
    async def get(self, ref: BlobRef) -> bytes: ...
    async def exists(self, ref: BlobRef) -> bool: ...
```

Filesystem storage is the initial implementation. COS can implement the same content-addressed contract later.

## AIProvider and ACL

```python
class AIProvider(Protocol):
    name: str

    async def complete(self, request: AIProviderRequest) -> dict[str, Any]: ...
```

`AIProviderACL` is the only bridge from `ContentItem` to this port. It owns prompt construction, the non-empty-summary gate, strict structured-output validation, and mapping back to `AIContentFields`. `AIEnrichmentRunner` owns bounded post-capture selection and deterministic persistence.

`CodexCLIProvider` is the first implementation. Future API or local-model integrations implement `AIProvider`; they do not receive `ContentItem` directly and do not change the Briefly contract.

## MVP guardrail

Do not add runtime plugin discovery, generic task graphs, event ledgers, compatibility wrappers, or extra storage families until a concrete Briefly acceptance criterion needs them.
