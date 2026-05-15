# Shiyi Source Strategy

- Status: Canonical source expansion strategy
- Last updated: 2026-05-14
- Owners: Lin, Kana, Kurisu

Shiyi's long-term goal is broad source coverage. The strategy is to add many sources through stable adapter families and readiness gates, not through fragile one-off scrapers.

## 1. Source expansion thesis

Shiyi should eventually capture many source types:

- official blogs and RSS/Atom feeds;
- web pages and sitemaps;
- public APIs;
- repositories and package ecosystems;
- research/paper indexes;
- developer communities;
- social/chat/email/local files when terms, auth, and privacy boundaries are clear.

But source count is not the first quality metric. The first quality metric is whether a source can be replayed, audited, normalized, exported, and consumed without leaking third-party DTOs or business-specific judgment into Shiyi core.

## 2. Source readiness gate

A built-in source should not be merged into default source lists unless it has:

- sanitized raw fixture;
- adapter contract test from raw fixture to `InternalItem`;
- `idempotency_key` stability test;
- `idempotency_key` non-collision test for distinct logical events;
- invalid or missing required field coverage;
- timestamp and half-open window coverage when the source carries time fields;
- fake fetcher or mocked fetcher coverage;
- pipeline integration smoke when the source is part of built-in capture;
- export/read smoke proving consumer output excludes source-specific raw DTO fields;
- opt-in live smoke if the source is public and brittle enough to warrant reachability checks.

If a source cannot satisfy this gate yet, keep it experimental and out of default source lists.

## 3. Adapter families

### 3.1 RSS / Atom feed sources

Use when the source exposes stable feed entries with title, link, ID, and published/updated time.

This should become the fastest source expansion path. Many official blogs should not require bespoke adapters beyond source configuration plus a generic feed adapter.

Examples:

- OpenAI news RSS — implemented;
- Hugging Face Blog, if feed is stable;
- provider/company blogs with RSS or Atom feeds.

### 3.2 Sitemap + article page sources

Use when the source exposes sitemap or index pages but not complete feed entries.

The adapter should own source-specific discovery and raw-key definition. The shared fetcher should own HTTP mechanics and event-level raw cache only.

Examples:

- Anthropic news index — implemented;
- official research/news index pages without full RSS.

### 3.3 Public API sources

Use when the source provides structured API access, pagination, and stable IDs.

Examples:

- Hacker News API;
- GitHub API;
- arXiv API;
- Papers with Code or equivalent APIs.

API sources usually need stronger pagination, checkpoint, and rate-limit tests before being treated as default built-ins.

### 3.4 Repository/package ecosystem sources

Use for software/tooling signals.

Examples:

- GitHub releases;
- repository activity;
- package changelogs;
- framework documentation/blog updates.

These sources should not become product-specific popularity ranking inside Shiyi. Shiyi captures the neutral event; consumers decide whether it matters.

### 3.5 Community, social, and media sources

Use with caution. These sources are often high-noise and need downstream aggregation/ranking.

Examples:

- Hacker News discussions;
- GitHub Trending;
- tech media;
- social/community feeds.

For Shiyi, these should remain neutral captured source material. Clustering, trend detection, and editorial decisions belong downstream.

## 4. Built-in source status

Current built-ins:

- `openai` — OpenAI news RSS feed;
- `anthropic` — Anthropic news index parser.

These provide the first two patterns: feed and index/page capture.

## 5. Recommended expansion batches

### Batch 1 — Official AI source coverage

Goal: improve AI Weekly source coverage with low-noise official sources.

Recommended candidates:

1. Google DeepMind / Google AI / Gemini official updates;
2. Meta AI official updates;
3. Microsoft AI / Azure AI official updates;
4. Hugging Face Blog;
5. Mistral official updates;
6. Cohere official updates.

Selection rule:

- prefer RSS/Atom or stable sitemap/index pages;
- avoid sources requiring brittle browser automation;
- every source must pass the readiness gate.

### Batch 2 — AI tooling and agent ecosystem

Goal: capture engineering/tooling signals for developer-oriented weekly reports and product tracking.

Candidate sources:

- LangChain;
- LlamaIndex;
- Vercel AI SDK;
- Weights & Biases;
- Modal;
- Replicate;
- selected framework release feeds.

Selection rule:

- prefer official changelog/blog/release feeds;
- avoid deriving importance inside Shiyi;
- consumers decide whether a tool update is weekly-report worthy.

### Batch 3 — Research and community signals

Goal: capture higher-noise sources after source registry and consumer aggregation are ready.

Candidate sources:

- Hacker News;
- GitHub Trending or repository activity;
- arXiv;
- Papers with Code;
- MIT Technology Review;
- TechCrunch;
- The Verge;
- VentureBeat;
- The Information if access/terms permit.

Selection rule:

- treat these as neutral source material;
- require source-specific rate-limit and pagination behavior;
- expect downstream consumers to cluster/rank/filter.

## 6. Source naming

Built-in source identifiers should be stable, lowercase, and descriptive.

Examples:

- `openai-news` for canonical source kind;
- CLI alias may remain `openai` for convenience;
- `anthropic-news` for Anthropic news content;
- future IDs should use provider or organization plus feed type, e.g. `huggingface-blog`.

The stable replay identity field is `idempotency_key`. Do not introduce `dedupe_key` in source contracts.

## 7. What not to do

Do not add a broad crawler before source contracts are stable.

Do not let a consumer's ranking rubric become Shiyi logic.

Do not merge source-specific DTOs into pipeline or export tests as substitutes for `InternalItem`.

Do not rely on live network calls for default CI.

Do not hide source failures behind empty successful exports.

## 8. Relationship to consumers

`briefly-ai-weekly` may ask for more sources, but Shiyi should translate those requests into neutral source contracts.

Example:

```text
AI Weekly need: more model/company/product signals
Shiyi response: add official AI provider blogs/feeds with stable provenance
Consumer response: classify, rank, aggregate, and render weekly entries downstream
```

This keeps Shiyi broadly useful instead of turning it into one weekly-report backend.
