# Shiyi Source Strategy

- Last updated: 2026-07-19
- Priority: stable Briefly inputs before open-source breadth

## Source definition

A `Source` is one independently identifiable target with:

- stable `id`;
- adapter key;
- target;
- enabled state;
- adapter-specific options;
- an independent checkpoint boundary.

Source is a declarative record. `CaptureRunner` selects it and `SourceAdapter` performs the acquisition.

## Source versus creator

Source represents where and how Shiyi collects. Creator is only optional attribution on the resulting content.

- An X account captured directly can be a Source.
- An account appearing in X search results is a creator, not the search Source.
- A Reddit subreddit or search query can be a Source.
- A Reddit poster may be absent from `creators` without invalidating the item.

Multiple X accounts should normally be separate Source records in one `CaptureConfig`, all sharing `XCaptureAdapter`. This preserves independent checkpoints and failure isolation.

## Briefly-first admission

Add a built-in source only when it has:

1. a clear Briefly use case;
2. stable target identity and source-native item identity;
3. repeatable public acquisition or explicitly managed credentials;
4. bounded fixtures and deterministic adapter tests;
5. canonical detail content or an explicit incomplete fallback;
6. objective timestamps and provenance.

Do not add a source because it might someday support opportunity discovery. That interpretation belongs downstream.

## Current built-ins

The current registry includes:

- OpenAI news;
- Anthropic news;
- Hugging Face blog;
- Google Research blog;
- Google DeepMind blog;
- DeepSeek news;
- Z.ai blog;
- Moonshot Kimi changelog;
- ByteDance Seed blog;
- Gemini API changelog;
- Mistral news;
- Microsoft AI blog;
- Cohere blog;
- Cursor changelog;
- GitHub Copilot changelog;
- Hacker News top stories.

The registry is intentionally declarative and small. Planning backlog, admission scoring, traceability matrices, and downstream ranking policy belong in specs/issues rather than runtime domain models.

## Content policy

- Prefer canonical article/detail content over listing previews.
- Preserve original language normalized content.
- Record reliable title, URL, published time, and optional creators.
- Store objective platform metrics without interpreting them.
- Set `metadata.is_complete = false` for preview-only fallback; persisted output remains not ready.
- Never emit Signal, Trend, Opportunity, credibility, or ranking fields.

## Adapter contract

```python
class SourceAdapter(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def version(self) -> str: ...
    def capture(self, source: Source) -> AsyncIterator[SourceItem]: ...
```

Implementations should be named by acquisition role, for example `XCaptureAdapter`, `RedditCaptureAdapter`, or `RssCaptureAdapter`.

## Future breadth

After Briefly is stable, source expansion may include social media, forums, video platforms, repositories, papers, email, chat, and user-provided feeds. New source kinds reuse the same `SourceItem -> ContentItem` boundary rather than adding product-specific models.
