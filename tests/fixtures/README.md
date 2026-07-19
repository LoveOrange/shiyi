# Test Fixtures

Fixtures protect Shiyi's source-boundary contracts without live third-party requests.

```text
<source>/
  raw/            # sanitized HTTP/API/feed/detail payloads
  source-item/    # optional expected SourceItem JSON
  content-item/   # optional expected canonical ContentItem JSON
```

Raw fixtures are the primary source-adapter evidence. Golden `SourceItem` and `ContentItem` files should be added only when they protect a stable contract that is difficult to express with focused assertions.

Rules:

1. Never commit secrets, cookies, tokens, or unnecessary personal data.
2. Keep fixtures bounded and preserve only the source structure needed by the test.
3. Third-party DTO fields must stop inside the adapter.
4. Source identity and source-native item identity must remain stable across repeated parsing.
5. Consumer golden output is the canonical `ContentItem`; do not create another export/event schema.
6. Do not include Signal, Trend, Opportunity, ranking, or editorial fields.

See [`../../docs/testing-boundary.md`](../../docs/testing-boundary.md).
