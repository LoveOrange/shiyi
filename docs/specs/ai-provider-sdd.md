# Optional AI Processor SDD

- Status: Accepted
- Owner: Shiyi contributors
- Last updated: 2026-07-19
- Scope: neutral, optional preprocessing of a deterministic `ContentItem`

## 1. Decision

AI is optional preprocessing inside Shiyi. Capture, identity, normalization, hashing, deduplication, readiness policy, and persistence remain deterministic.

The Briefly-first MVP uses one structured request/response boundary instead of a generic task system.

## 2. Allowed output

The processor may propose only:

- language when not already known;
- neutral summary when the item has no summary;
- summary language;
- an optional configured-language title;
- simple categories;
- simple tags.

It must not produce Signal, Trend, Opportunity, ranking, credibility, recommendation, or editorial fields.

## 3. Contract

```python
class AIContentFields(BaseModel):
    language: str | None = None
    summary: str | None = None
    summary_language: str | None = None
    translated_title: str | None = None
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()


class AIProcessor(Protocol):
    async def process(self, item: ContentItem) -> AIContentFields: ...
```

Provider identity and token/cost usage may be logged as operational telemetry. They are not part of the canonical `ContentItem` product contract unless a concrete audit requirement appears.

## 4. Merge rules

Deterministic code validates provider output and owns the merge.

- AI cannot overwrite ids, provenance, URL, source facts, timestamps, creators, original content, content hash, metrics, or Blob references.
- Empty, invalid, or over-limit fields are rejected.
- Categories and tags are bounded and deduplicated.
- Existing valid source/deterministic language wins over an AI guess.
- Existing non-empty summary wins. The processor does not request or generate another summary when `ContentItem.summary` is non-empty.
- Failure preserves the deterministic `ContentItem` and is reported in the run summary.

## 5. Language policy

Preserve normalized content in its original language. Do not translate every full document during MVP.

When Briefly requires a common reading language, configure the summary language and optionally a translated title. Record both `language` and `summary_language` explicitly.

## 6. MVP non-goals

- classify/extract/summarize task variants;
- model-specific domain objects in the canonical content schema;
- enrichment artifact ledgers;
- agent loops or arbitrary prompt execution;
- AI as a prerequisite for durable capture.
