# Shiyi Fetcher SDD

- Status: Draft
- Last updated: 2026-05-12
- Scope: shared web/RSS/sitemap fetching infrastructure for post-MVP v0.2

## Purpose

Adapters should not own crawling concerns. Fetching, timeout, retry, user-agent, and future rate limiting belong below adapters in shared fetcher infrastructure.

## Boundaries

- Fetchers retrieve source material and expose typed fetch results.
- Adapters parse source-specific structure and map fetched data to `CaptureEvent`.
- Pipeline remains responsible for normalization, artifacts, metadata, enrichment, and idempotency.

## Ports

- `WebFetcher.fetch(url, source=None, raw_key=None) -> FetchResult`
- `RssFetcher.fetch(feed_url) -> RssFeed`
- `SitemapFetcher.fetch(sitemap_url) -> Sitemap`

## MVP policy

- Use one shared `httpx.AsyncClient` per default web fetcher instance.
- Set an explicit user-agent.
- Set explicit timeout.
- Use minimal bounded retry for transient HTTP/network failures.
- Keep rate limiting simple for v0.2; richer token-bucket policy can follow.


## Event-level raw cache

Fetcher-level caching stays deliberately simple. Adapters define an event-level `raw_key` from the entry metadata they trust, such as URL, source item id, title, or published date. The fetcher does not interpret those fields.

When both `source` and `raw_key` are supplied, `HttpWebFetcher` stores or reads the full raw response at:

```text
{raw_cache_root}/{source}/{raw_key}/raw.html
```

If the file already exists, the fetcher returns that local raw content and skips the remote full-page request. Listing/index/RSS fetches normally omit `raw_key`, so they are not treated as event-level raw cache entries.

This cache only avoids repeated full fetches. Pipeline metadata still decides whether normalization and enrichment are complete.
