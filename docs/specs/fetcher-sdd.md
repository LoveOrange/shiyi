# Shiyi Fetcher SDD

- Status: Accepted for v0.2
- Last updated: 2026-05-14
- Scope: shared web/RSS/sitemap fetching infrastructure and event-level raw fetch cache

## 1. Purpose

The fetcher layer provides the minimum reusable crawling capability required by Shiyi's main capture flow.

It exists to keep network concerns out of adapters:

- HTTP client lifecycle
- timeout
- redirects
- retry for transient failures
- error mapping into stable `FetcherError` categories
- user-agent
- safe XML parsing for sitemap-like documents
- simple event-level raw cache for full item fetches

The fetcher layer is intentionally not a crawler framework, scheduler, semantic cache, or pipeline state manager.

## 2. Design principles

1. **Simple first** — avoid candidate/discovery frameworks until the main flow proves they are needed.
2. **Adapter owns source semantics** — the adapter decides which entry metadata identifies a raw item.
3. **Fetcher owns transport mechanics** — the fetcher uses `source + raw_key` only as a filesystem cache path.
4. **Pipeline owns processing state** — normalization, artifact persistence, event record status, and optional neutral preprocessing remain pipeline concerns.
5. **Event-level raw only for now** — source-level snapshots such as full RSS XML/index HTML are not part of this design.

## 3. Main flow

```text
Fetcher fetches lightweight listing/index/feed
-> Adapter parses entry-level metadata
-> Adapter computes raw_key from metadata it trusts
-> Fetcher fetches full item with source + raw_key
   -> cache hit: read local raw.html, skip remote full fetch
   -> cache miss: fetch remote full content, save raw.html
-> Adapter emits InternalItem with event-level raw payload
-> Pipeline persists raw artifact, normalizes, persists event records, enriches
```

For feeds where the entry already contains enough event-level raw content, the adapter may emit a `InternalItem` directly without a second full-page fetch.

## 4. Boundaries

### Fetcher responsibilities

- Retrieve remote text resources.
- Parse generic RSS/Atom and sitemap documents into simple fetcher DTOs.
- Optionally cache full event-level raw content under an adapter-defined key.
- Return fetch metadata such as URL, status code, content type, fetched time, cache status, and cache path.

### Adapter responsibilities

- Choose which fetcher(s) to call.
- Parse source-specific structures.
- Define `raw_key` from entry-level metadata.
- Construct `InternalItem` payloads and source metadata without leaking third-party DTOs into the pipeline.
- Apply source-specific date/window filtering.

### Pipeline responsibilities

- Check processing idempotency through event record store.
- Persist raw artifacts from `InternalItem.payload`.
- Normalize content.
- Persist normalized artifacts and event records.
- Run optional neutral preprocessing.
- Persist annotation/preprocess artifacts and event records.

## 5. Explicit non-goals

The fetcher layer must not:

- Query SQLite event records.
- Decide whether an item is normalized, enriched, or complete.
- Know about normalized Markdown, semantic input, model versions, tags, summaries, annotations, or preprocess outputs.
- Compute semantic fingerprints.
- Own source-level snapshot persistence.
- Replace pipeline idempotency.

## 6. Ports

### `WebFetcher`

```python
async def fetch(
    url: str,
    *,
    source: str | None = None,
    raw_key: str | None = None,
) -> FetchResult
```

`source` and `raw_key` are optional. When omitted, the fetcher performs a normal remote fetch.

When both are supplied and the fetcher has a `raw_cache_root`, they activate event-level raw caching.

### `RssFetcher`

```python
async def fetch(feed_url: str) -> RssFeed
```

Fetches a feed and exposes normalized RSS/Atom entries. It does not apply event-level raw caching by default because the feed is a listing/source document, not a full event raw item.

### Fetch errors

Fetcher implementations should map provider-specific failures to `FetcherError` so adapters do not depend on a concrete HTTP client. Current categories are:

- `timeout`
- `transport`
- `http_status` with optional `status_code`

`FetcherError` must include the attempted URL. When the caller supplied `source`, it should also preserve that source context so adapter diagnostics can identify which source boundary failed without catching `httpx` or SDK exceptions directly.

Adapters may catch these errors for source-specific diagnostics, but they should not reach below the fetcher to catch `httpx` or SDK exceptions directly.

### `SitemapFetcher`

```python
async def fetch(sitemap_url: str) -> Sitemap
```

Fetches a sitemap and exposes URL entries plus optional `lastmod` values. XML parsing must use a safe parser.

## 7. Data contracts

### `FetchResult`

- `url`: final fetched URL
- `status_code`: HTTP status code or `200` for cache hits
- `content`: fetched or cached text content
- `content_type`: response content type when available
- `fetched_at`: time when fetch/cache read occurred
- `from_cache`: whether content came from the event-level raw cache
- `raw_cache_path`: filesystem path used for the cache entry, when applicable

### `RssEntry`

- `entry_id`
- `title`
- `link`
- `html`
- `published_at`

### `SitemapEntry`

- `loc`
- `lastmod`

## 8. Cursor, checkpoint, and time-window scope

The current built-in fetcher ports do not accept pagination cursors, durable checkpoints, `since`, or `until` arguments.

That is deliberate for v0.2:

- RSS and sitemap fetchers return the complete parsed collection supplied by the fetched document.
- Web fetcher returns one text resource.
- Source-specific pagination, cursor interpretation, and capture-window filtering belong to adapters when a source needs them.
- Durable checkpoint/progress commits belong to the pipeline or a future explicit source-state port, not to generic fetchers.

Fetcher contract tests therefore cover multi-entry and empty parsed collections, retry/error classification, raw payload provenance, cache behavior, and timestamp preservation. If a future fetcher grows cursor/checkpoint or time-window parameters, it must add contract tests proving cursor input is honored, progress advances only after the successful fetch boundary, and `since` is inclusive while `until` is exclusive.

## 9. Event-level raw cache

The raw cache is a fetcher-level optimization for avoiding repeated full item fetches.

Adapters define `raw_key`. The fetcher does not know, inspect, validate, or care which metadata fields are used. The examples below are adapter strategy examples only; they must never become fetcher-level semantics.

Possible adapter raw key input examples:

```text
source + canonical_url
source + source_item_id
source + canonical_url + title + published_or_updated
```

The exact choice belongs to each adapter because source metadata stability differs. Fetcher implementations must treat `raw_key` as an opaque path segment supplied by the adapter.

When `raw_cache_root`, `source`, and `raw_key` are present, `HttpWebFetcher` uses this path:

```text
{raw_cache_root}/{source}/{raw_key}/raw.html
```

Example:

```text
.shiyi/anthropic/data/raw/anthropic-news/37cc778a.../raw.html
```

Cache behavior:

1. If `raw.html` exists, return it with `from_cache=True` and do not call the remote full-item URL.
2. If it does not exist, fetch the remote URL, write the response body to `raw.html`, and return it with `from_cache=False`.
3. If `source` or `raw_key` is missing, skip cache handling and fetch normally.

This cache only saves network calls. It does not mean the event has been normalized, persisted, or marked complete.

## 10. Current source usage

### Anthropic news

Current flow:

1. Fetch `https://www.anthropic.com/news` as a listing page.
2. Extract article URLs.
3. Compute adapter-defined `raw_key` from entry-level metadata.
4. Fetch each article page through `WebFetcher.fetch(url, source="anthropic-news", raw_key=...)`.
5. Emit `InternalItem` with article HTML as event-level raw payload.

Current raw key:

```text
sha256("anthropic-news\n{article_url}")
```

This is intentionally simple. If Anthropic metadata later proves useful for update detection, the Anthropic adapter may change its raw-key definition without changing fetcher behavior.

### OpenAI RSS

Current flow:

1. Fetch `https://openai.com/news/rss.xml` as a feed/listing document.
2. Parse entries.
3. Emit `InternalItem` from RSS entry content/summary.

OpenAI currently does not use full-page raw cache because the RSS entry already provides event-level raw content for the MVP flow.

## 11. HTTP policy

`HttpWebFetcher` must provide:

- explicit timeout
- redirects enabled
- explicit user-agent
- bounded minimal retry for transient network/HTTP failures

Retryable failures include:

- timeout/transport errors
- HTTP 408
- HTTP 429
- HTTP 500/502/503/504

Rate limiting remains simple for v0.2. A richer token-bucket policy can be added later if source pressure requires it.

## 12. Safety and correctness notes

- Sitemap/XML parsing must use `defusedxml` or another safe XML parser.
- Cache paths must be derived from adapter-provided hash-like keys, not arbitrary URLs.
- Cache hits should not bypass pipeline event records checks.
- Listing/feed fetches should not be cached as event-level raw unless an adapter explicitly treats them as an event item.

## 13. Test requirements

The fetcher design is covered by contract tests that localize failures to the retrieval boundary:

- Web fetch result test, including URL, status, content type, fetched time, cache flag, and raw cache path provenance.
- Raw cache hit/miss test proving the second full fetch skips the remote request while preserving the adapter-defined cache path.
- RSS parser tests for multiple entries and empty feeds.
- Sitemap parser tests for multiple entries and empty sitemaps.
- Retry/error policy tests proving transient status failures are retried, exhausted retryable failures become `FetcherError`, permanent status failures are not retried, and timeout/transport errors use stable error kinds with URL/source context.
- Adapter tests using fake fetchers, including `FakeWebFetcher` for deterministic adapter call-shape checks.
- Domain/adapter tests, not fetcher tests, own half-open capture-window filtering until a fetcher port explicitly accepts `since`/`until`.
- End-to-end capture smoke test proving raw cache files are created and pipeline idempotency still works.
