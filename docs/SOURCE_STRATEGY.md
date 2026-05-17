# Shiyi Source Strategy

- Status: Canonical source expansion strategy
- Last updated: 2026-05-16
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
- sanitized raw detail/full-article fixture when the source exposes canonical article content;
- adapter contract test from raw fixture to `InternalItem`;
- `idempotency_key` stability test;
- `idempotency_key` non-collision test for distinct logical events;
- invalid or missing required field coverage;
- timestamp and half-open window coverage when the source carries time fields;
- fake fetcher or mocked fetcher coverage;
- pipeline integration smoke when the source is part of built-in capture;
- export/read smoke proving consumer output excludes source-specific raw DTO fields;
- normalized/exported content quality assertions proving consumers receive full article/detail content, not merely RSS/index summaries;
- explicit degraded-state metadata via source-neutral `content_depth` for `summary_only`, `partial`, or `blocked` records so consumers can exclude them from decision-grade source-ready counts;
- opt-in live smoke if the source is public and brittle enough to warrant reachability checks.

If a source cannot satisfy this gate yet, keep it experimental and out of default source lists.

## 3. Adapter families

### 3.1 RSS / Atom feed sources

Use when the source exposes stable feed entries with title, link, ID, and published/updated time.

RSS/Atom should be treated primarily as discovery metadata unless the feed contains the complete article body. For P2.5 and later, a built-in adapter must fetch the canonical article page or official structured detail payload when available, persist that detail raw artifact, and normalize the detail content into decision-grade Markdown. Summary-only feed entries are allowed only as an explicit degraded fallback.

This should become the fastest source expansion path. Many official blogs should not require bespoke adapters beyond source configuration plus a generic feed adapter plus full-detail fetch.

Examples:

- OpenAI news RSS — implemented;
- Hugging Face Blog RSS — implemented in the first P2.5 RSS-first slice;
- Google Research Blog RSS — implemented in the first P2.5 RSS-first slice;
- provider/company blogs with RSS or Atom feeds.

### 3.2 Sitemap + article page sources

Use when the source exposes sitemap or index pages but not complete feed entries.

The adapter should own source-specific discovery and raw-key definition. The shared fetcher should own HTTP mechanics and event-level raw cache only.

Examples:

- Anthropic news index — implemented;
- official research/news index pages without full RSS.

### 3.3 Public API / embedded-data sources

Use when the source provides structured API access, SSR embedded data, pagination, and stable IDs.

Examples:

- Hacker News API;
- GitHub API;
- arXiv API;
- Papers with Code or equivalent APIs.

API and embedded-data sources usually need stronger pagination, checkpoint, completeness, and rate-limit tests before being treated as default built-ins. Official-used JSON or SSR payloads are acceptable only when they can be fixture-backed without browser automation.

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
- `anthropic` — Anthropic news index parser;
- `huggingface-blog` — Hugging Face Blog RSS feed;
- `google-research-blog` — Google Research Blog RSS feed;
- `deepmind-blog` — Google DeepMind Blog RSS discovery plus canonical article detail pages;
- `deepseek-news` — DeepSeek official news pages discovered from API docs updates page;
- `z-ai-blog` — Z.ai / GLM official blog posts discovered from the Mintlify release notes page;
- `moonshot-kimi-changelog` — Kimi Open Platform static changelog page;
- `bytedance-seed-blog` — ByteDance Seed SSR blog index plus article detail pages.

These provide four patterns: reusable feed capture, RSS-discovery/detail-page capture, index/page capture, and stable official changelog/embedded-data capture.
The P2.5 slices intentionally keep implementation hand-wired; source registry/config belongs to P3.

## 5. Recommended expansion batches

### Batch 1 — Official AI source coverage

Goal: improve AI Weekly source coverage with low-noise official sources.

Recommended candidates:

1. Google Research Blog / Google DeepMind / Gemini official updates;
2. Hugging Face Blog;
3. Meta AI official updates;
4. Microsoft AI / Azure AI official updates;
5. Mistral official updates;
6. Cohere official updates.

Overseas official Slice B implementation outcome:

- `deepmind-blog` — Google DeepMind Blog RSS at `https://deepmind.google/blog/rss.xml` is used only as discovery. Emitted source identity is the canonical article URL such as `https://deepmind.google/blog/alphaevolve-impact/`; normalized/exported content comes from the article-scoped detail body, not the feed summary or whole page chrome.

China provider P2.5-03 audit and implementation outcome:

Implemented in the first China-provider slice:

- `deepseek-news` — official DeepSeek news pages. The API docs updates page at `https://api-docs.deepseek.com/updates` is used only as a discovery index; emitted source identity is the `/news/*` article URL.
- `z-ai-blog` — official Z.ai / GLM blog posts. Mintlify release notes at `https://docs.z.ai/release-notes/new-released.md` are used only to discover candidate official blog URLs such as `https://z.ai/blog/glm-5.1`.
- `moonshot-kimi-changelog` — Kimi Open Platform changelog at `https://platform.kimi.com/blog/posts/changelog`; static page exposes dated Chinese release sections. Use `platform.kimi.com` as primary and treat legacy Moonshot domains as fallbacks, not separate sources.
- `bytedance-seed-blog` — ByteDance Seed blog at `https://seed.bytedance.com/zh/blog`; SSR `window._ROUTER_DATA` exposes stable article IDs, title keys, publish timestamps, categories, and detail-page content. Chinese is the primary locale when both official Chinese and English variants exist; the English URL is retained as metadata/fallback to avoid duplicate items.

Audited but deferred from default built-ins:

- `qwen-research` — `https://qwen.ai/research` is official but SPA-only; current useful data comes from official-used JSON endpoints such as `page_config` / `api/v2/article/retrieval`. The legacy `qwenlm.github.io/blog/index.xml` RSS exists but is explicitly stale and must not be primary. Add only after a dedicated JSON/API adapter covers pagination, completeness, and fixture size.
- `minimax-news` — `https://www.minimax.io/news` is official, but reliable extraction should use `/nezha/en/news` JSON endpoints only. HTML/schema dates are unstable and the observed list-vs-detail completeness needs confirmation before this becomes a default built-in.
- Tencent Hunyuan, Baidu Qianfan/Wenxin/ERNIE, StepFun, Huawei Cloud Pangu/ModelArts, 01.AI/Yi, Baichuan, ModelBest, Alibaba Cloud Qwen posts, and Volcano Ark release pages stay in the audit backlog unless their official feed/changelog/blog pages satisfy the readiness gate.

Selection rule:

- prefer RSS/Atom, stable changelog pages, stable sitemap/index pages, or official-used JSON/SSR payloads with stable IDs and timestamps;
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
- `huggingface-blog` for Hugging Face Blog RSS content;
- `google-research-blog` for Google Research Blog RSS content;
- `deepmind-blog` for Google DeepMind Blog article content discovered through RSS;
- `deepseek-news` for DeepSeek official news article content;
- `z-ai-blog` for Z.ai / GLM official blog article content;
- `moonshot-kimi-changelog` for Kimi platform changelog entries;
- `bytedance-seed-blog` for ByteDance Seed official blog content;
- future IDs should use provider or organization plus feed type.

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
