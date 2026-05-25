# Shiyi Source Strategy

- Status: Canonical source expansion strategy
- Last updated: 2026-05-25
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

Near-term sequencing rule:

- prioritize official low-noise sources first;
- keep community/media/social sources for later phases where downstream consumers can cluster same-topic items and use discussion intensity as an importance signal;
- keep that aggregation/ranking logic out of Shiyi itself.

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
- explicit item-level `content_completeness` derived from source-neutral MVP `content_depth` (`complete`, `partial`, or `summary_only`), so consumers can exclude incomplete records from decision-grade source-ready counts;
- opt-in live smoke if the source is public and brittle enough to warrant reachability checks.

If a source cannot satisfy this gate yet, keep it experimental and out of default source lists.

### 2.1 Registry/status review contract

`shiyi sources --include-backlog` is the machine-readable review surface for source
readiness. Every row must expose:

- `source_category`: initially `official`, `community`, or `social_media`;
- `fetcher_family`: the adapter/fetcher technical shape, such as `rss`,
  `rss-detail`, `article-index`, `changelog`, `ssr-detail`, or a deferred
  structured/embedded-data candidate label;
- optional `authority_tier` for within-category source authority when category alone is not
  enough, especially future social-media accounts;
- compatibility `family` may remain in JSON temporarily as an alias for `fetcher_family`;
- compatibility `detail_capture_mode`: `listing-only`, `summary-only`,
  `canonical-detail`, or `structured-api`, emitted only as derived capture evidence/status
  during migration, not as a manual readiness premise;
- `default_content_depth`: `complete`, `partial`, or `summary_only` when the source is
  built in;
- `content_completeness`: `complete`, `partial`, or `summary_only` when a built-in source
  emits normalized items; deferred backlog rows keep this null until implemented;
- derived `readiness_status`: `ready`, `degraded`, or `deferred`;
- derived `source_ready`: true only for `content_completeness=complete`;
- `defer_reason`: required for every incomplete or deferred row;
- `traceability_refs`: doc/test/fixture references supporting the row;
- for `structured-api` surfaces, `structured_api_gate`, `structured_api_blockers`,
  and `structured_api_traceability_refs`, so JSON/API candidates cannot be promoted by
  adapter optimism alone;
- derived `counts_as_official_source_ready`: the coverage bit consumers should use for
  official source-ready counts.

Only rows with `source_category=official`, `content_completeness=complete`,
non-empty `traceability_refs`, and no defer/blocker state count as official source-ready
coverage. `readiness_status`, `source_ready`, and `counts_as_official_source_ready` are
review labels derived from that evidence; they are not independent item-level truths.
`degraded`, `deferred`, `community`, `social_media`, and `later-high-noise` backlog rows
must remain visible for planning, but they do not count toward M2 official source-ready
coverage.

Structured/API candidates must pass all objective gate checks before they can become
source-ready: stable official endpoint, stable item IDs or deterministic canonical IDs,
reliable published timestamps, canonical URLs, complete payloads, bounded fixtures,
repeatable extraction tests, and traceability references. `qwen-research`,
`minimax-news`, and `google-antigravity-changelog` deliberately remain structured/API or
embedded-data backlog rows until these checks are proven; `bytedance-seed-blog` is the
current ready structured/SSR example.

### 2.2 US05 adapter admission/package boundary

US05 hardens the boundary around the existing normalized/export contract. It does not
redesign the Shiyi -> AI Weekly handoff. The handoff remains `internal-item.v1` inside
Shiyi and `shiyi-export-item.v1` for downstream consumers.

Candidate adapters should be classified before implementation:

- `core_official`: public official source, no credentials, no private data, no browser
  state, no heavy non-default runtime, bounded fixtures, repeatable tests, stable IDs or
  URLs and timestamps, and `content_completeness=complete`.
- `optional_official`: public official source with the same neutral contract and test
  evidence as core, but requiring a non-default runtime or dependency that must not bloat
  default Shiyi. Optional official adapters are not required for US06.
- `private_closed`: source access depends on credentials, private account data, browser
  state, closed workspace state, or other user-specific authorization. These adapters must
  not enter Shiyi core or US06 source-ready coverage.
- `deferred_official`: official source whose endpoint, IDs, timestamps, canonical URLs,
  complete payloads, fixtures, or repeatable tests are not proven yet, or whose current
  output is only `partial` or `summary_only`.
- `bfl_m3_future`: community, social-media, media, or other high-noise sources that need
  downstream aggregation, topic merging, discussion weighting, or ranking before they are
  useful.

Current examples:

- Cursor and GitHub Copilot remain `core_official` examples from US04.
- OpenAI remains a degraded/deferred official source-ready example because current
  unauthenticated evidence is summary-only.
- Kiro, Antigravity, Qwen, and MiniMax remain `deferred_official`.
- GitHub Trending/community feeds remain `bfl_m3_future`.

The adapter admission policy is intentionally not a plugin mechanism. Until an actual
optional/private adapter is approved, package placement stays at documentation and policy
level. Default Shiyi must remain credential-free, private-data-free, browser-state-free,
and free of heavy optional runtime requirements.

## 3. Adapter families

### 3.1 RSS / Atom feed sources

Use when the source exposes stable feed entries with title, link, ID, and published/updated time.

RSS/Atom should be treated primarily as discovery metadata unless the feed contains the complete article body. For P2.5 and later, a built-in adapter must fetch the canonical article page or official structured detail payload when available, persist that detail raw artifact, and normalize the detail content into decision-grade Markdown. For RSS-discovered sources, the decision-grade adapter payload should be the canonical detail surface itself—usually the original article webpage, otherwise an official structured detail payload when that is the stable source of truth. Summary-only feed entries are allowed only as an explicit degraded fallback.

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

API and embedded-data sources usually need stronger pagination, checkpoint, completeness, and rate-limit tests before being treated as default built-ins. Official-used JSON or SSR payloads are acceptable only when they can be fixture-backed without browser automation. The structured/API readiness gate blocks promotion unless the implementation proves stable endpoint identity, stable item IDs, reliable timestamps, canonical URLs, complete payloads, bounded fixtures, repeatable extraction tests, and traceability refs.

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

For Shiyi, these should remain neutral captured source material. Clustering, trend detection, same-topic merging across overlapping sources, and discussion-based importance weighting belong downstream.

## 4. Built-in source status

Current built-ins:

- `openai` — OpenAI news RSS feed; explicit discovery-grade defer until a compliant canonical detail path is available;
- `anthropic` — Anthropic news index parser;
- `huggingface-blog` — Hugging Face Blog RSS discovery plus canonical article detail pages;
- `google-research-blog` — Google Research Blog RSS discovery plus canonical article detail pages;
- `deepmind-blog` — Google DeepMind Blog RSS discovery plus canonical article detail pages;
- `deepseek-news` — DeepSeek official news pages discovered from API docs updates page;
- `z-ai-blog` — Z.ai / GLM official blog posts discovered from the Mintlify release notes page;
- `moonshot-kimi-changelog` — Kimi Open Platform static changelog page;
- `bytedance-seed-blog` — ByteDance Seed SSR blog index plus article detail pages;
- `gemini-api-changelog` — Gemini API official changelog text page;
- `mistral-news` — static news index plus official article detail pages;
- `microsoft-ai-blog` — Microsoft AI Blog WordPress feed with decision-grade feed content;
- `cohere-blog` — Cohere official blog index plus official detail payload;
- `cursor-changelog` — Cursor official changelog page with SSR article entries and canonical changelog URLs;
- `github-copilot-changelog` — GitHub Blog Copilot label RSS feed with full `content:encoded` changelog bodies.

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

- `huggingface-blog` — Hugging Face Blog RSS at `https://huggingface.co/blog/feed.xml` is used only as discovery. Emitted source identity is the canonical blog article URL such as `https://huggingface.co/blog/open-r1`; normalized/exported content comes from the article detail body and carries `content_depth=complete`.
- `google-research-blog` — Google Research Blog RSS at `https://research.google/blog/rss/` is used only as discovery. Emitted source identity is the canonical research blog URL such as `https://research.google/blog/catalyzing-scientific-impact-through-global-partnerships-and-open-resources`; normalized/exported content comes from the canonical detail page and carries `content_depth=complete`.
- `deepmind-blog` — Google DeepMind Blog RSS at `https://deepmind.google/blog/rss.xml` is used only as discovery. Emitted source identity is the canonical article URL such as `https://deepmind.google/blog/alphaevolve-impact/`; normalized/exported content comes from the article-scoped detail body, not the feed summary or whole page chrome.

Deferred with explicit reason:

- `openai` — RSS entries are summary-only in the current audit, and unauthenticated canonical detail fetches return a managed browser challenge instead of stable article HTML. Keep it out of source-ready counts until an official structured detail surface or compliant detail-fetch path exists.

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
- official low-noise sources beat broader but noisier coverage in this phase;
- if discovery comes from RSS or another listing surface, treat that surface as entry-only and normalize from the canonical detail page/payload instead of the listing snippet;
- avoid sources requiring brittle browser automation;
- if a source depends on downstream aggregation/ranking to be useful, defer it instead of forcing it into P2.5;
- every source must pass the readiness gate.

### Batch 2 — AI tooling and agent ecosystem

Goal: capture engineering/tooling signals for developer-oriented weekly reports and product tracking.

Candidate sources:

- Cursor changelog;
- Kiro changelog;
- Google Antigravity changelog;
- GitHub Copilot changelog;
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

US04 AI-coding official source outcome:

- `cursor-changelog` is built in as a ready official changelog source. The adapter parses
  SSR changelog articles from `https://cursor.com/changelog`, deduplicates repeated
  entries by canonical URL, and derives stable IDs from canonical changelog paths so
  same-day posts do not collide.
- `github-copilot-changelog` is built in as a ready official RSS source. The adapter uses
  the Copilot label feed at `https://github.blog/changelog/label/copilot/feed/`; current
  WordPress entries carry complete `content:encoded` article bodies and stable GUIDs.
- `kiro-changelog` stays deferred. The official feed has timestamps and canonical links,
  but several descriptions are summary-only with ellipses, and patch links require
  fixture-backed complete detail extraction for fragment-specific entries before source-ready
  promotion.
- `google-antigravity-changelog` stays deferred. The official changelog shell is
  JS-rendered; promotion requires stable embedded-data extraction with stable IDs,
  timestamps, canonical URLs, complete payloads, bounded fixtures, and repeatable parser
  tests. Curling a minified bundle is not enough evidence for readiness.
- `vercel-ai-sdk` and `langchain-blog` remain pending/deferred; they are useful ecosystem
  sources but not the near-term AI-coding bottleneck for US04.

### Batch 3 — Research and community signals

Goal: capture higher-noise sources after source registry and consumer aggregation are ready.

These sources become materially more useful only once downstream consumers can cluster same-topic items across community/media overlap and optionally use discussion volume as an importance dimension.

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
- expect downstream consumers to cluster/rank/filter, including same-topic merging and discussion-based weighting where useful.

## 6. Source naming

Built-in source identifiers should be stable, lowercase, and descriptive.

Examples:

- `openai-news` for canonical source kind;
- CLI alias may remain `openai` for convenience;
- `anthropic-news` for Anthropic news content;
- `huggingface-blog` for Hugging Face Blog article content discovered through RSS;
- `google-research-blog` for Google Research Blog article content discovered through RSS;
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
