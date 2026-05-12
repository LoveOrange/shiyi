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

- `WebFetcher.fetch(url) -> FetchResult`
- `RssFetcher.fetch(feed_url) -> RssFeed`
- `SitemapFetcher.fetch(sitemap_url) -> Sitemap`

## MVP policy

- Use one shared `httpx.AsyncClient` per default web fetcher instance.
- Set an explicit user-agent.
- Set explicit timeout.
- Use minimal bounded retry for transient HTTP/network failures.
- Keep rate limiting simple for v0.2; richer token-bucket policy can follow.
