# Shiyi Product Spec

- Status: Canonical product source of truth
- Last updated: 2026-05-16
- Owners: Lin, Kana, Kurisu
- Repository: `shiyi`

This document is the canonical product spec for Shiyi. Notion may track tasks, ownership, dates, and execution status, but product decisions, milestone definitions, architecture/product boundaries, and source strategy should live in this repository.

If an older Notion PRD or task note conflicts with this repository, the repository wins after Lin/Kana/Kurisu alignment.

## 1. Mission

Shiyi is the stable information-capture substrate for multiple downstream information collection and organization systems.

Its long-term goal is to capture as many useful information sources as possible while keeping the core data flow stable, replay-safe, inspectable, and reusable.

In one line:

```text
Shiyi = stable source acquisition + canonical capture + provenance + neutral distribution
```

Shiyi is named after 拾遺: collecting important signals that would otherwise be missed.

## 2. Supported downstream consumers

Shiyi is not built for one newsletter or one ranking model. It should become the shared bottom layer for multiple products and workflows, including:

- `briefly-ai-weekly` / AI R&D weekly reporting;
- demand radar and product opportunity discovery;
- Briefly-style vertical intelligence products;
- future local or team workflows that need reliable source capture.

Each consumer may apply its own domain taxonomy, ranking, clustering, editorial judgment, and output format. Those consumer-specific choices must not leak back into Shiyi core.

## 3. Product boundary

### 3.1 Shiyi owns

Shiyi owns reusable capture infrastructure:

- source acquisition boundaries;
- fetchers and source-specific adapters;
- source windows for daily and backfill capture;
- stable adapter-to-core contracts;
- complete source-page/detail acquisition for built-in adapters when the source exposes canonical article pages or official structured detail payloads;
- raw source artifact persistence;
- source-independent normalization into canonical text/Markdown/artifacts;
- provenance, event records, statuses, and idempotency;
- optional neutral preprocessing that is reusable across consumers;
- export/read/distribution mechanisms for downstream products.

### 3.2 Shiyi does not own

Shiyi must not own downstream product logic:

- weekly-report inclusion decisions;
- demand/opportunity scoring;
- investment or competitive analysis conclusions;
- product-specific ranking, prioritization, or editorial selection;
- consumer-specific prompts, schemas, or tone;
- publishing to Discord, Notion, email, websites, or other product surfaces.

Those belong to consumer repositories such as `briefly-ai-weekly`.

## 4. Current progress assessment

As of 2026-05-16, Shiyi has moved from product/architecture exploration into a usable early infrastructure base with its P2 contract hardening gate complete and P2.5 full-content source readiness under active implementation.

### 4.1 Completed foundation

- Product boundary is clear: Shiyi is capture infrastructure, not an insight product.
- Core architecture is documented around ports/adapters, raw artifacts, event records, and replay safety.
- MVP implementation exists with:
  - `InternalItem` domain boundary;
  - OpenAI RSS adapter;
  - Anthropic news adapter;
  - shared HTTP/RSS/Sitemap fetcher layer;
  - HTML-to-Markdown normalization;
  - filesystem artifact store;
  - SQLite event record store;
  - CLI capture/list/export;
  - half-open capture windows: `since` inclusive, `until` exclusive;
  - replay safety via `idempotency_key`.
- P1 Notion tasks are all marked done.
- Default local gates are green at the latest assessment: format, lint, typecheck, and tests.

### 4.2 Current milestone state

P2 test-boundary work is complete. The repository has a contract-oriented testing boundary in `docs/testing-boundary.md`, plus green fixture-backed coverage for fetchers, adapters, `InternalItem`, pipeline-to-persistence behavior, and export/read contracts.

The active next milestone is P2.5: add a small slice of official, low-noise sources without weakening the P2 readiness gate. Lin's current priority for P2.5 is the full-content gate: every built-in adapter must capture the complete article/detail page when available, not merely RSS/index summaries.

### 4.3 Main risk

The main risk is adding sources faster than contracts can protect them.

Shiyi's strategic goal is broad source coverage, but broad coverage without stable adapter contracts would produce a fragile crawler pile. The correct sequence is:

```text
contract gate complete -> low-noise source expansion -> registry/ops -> higher-noise community sources
```

## 5. Product principles

1. **Stable substrate before feature breadth.** Source expansion is essential, but every new source must preserve traceability, idempotency, and export safety.
2. **Adapters are replaceable.** Source-specific logic belongs behind adapter boundaries; core should not depend on third-party DTOs.
3. **Raw capture is first-class.** Raw payloads, fetch metadata, and provenance must remain auditable.
4. **Full content beats previews.** For source-ready built-in adapters, RSS/index/changelog snippets are discovery metadata by default. When discovery starts from RSS or another listing surface, Shiyi should dereference to the canonical article/detail page before exposing an item as decision-grade. Official structured detail payloads remain acceptable when they are the stable canonical detail surface.
5. **Normalized content is consumer-safe.** Downstream products should read stable Shiyi output without knowing source-specific DTOs.
6. **Partial content is explicit.** Summary-only or partial records may exist as degraded fallback, but they must be marked source-neutrally with `content_depth` and must not count as AI Weekly source-ready evidence. Allowed `content_depth` values are `full_page`, `feed_full_content`, `summary_only`, `partial`, and `blocked`; only the first two are decision-grade by default.
7. **Neutral preprocessing only.** Optional AI work inside Shiyi may summarize, extract entities, detect language, chunk, embed, or provide generic quality signals; it must not decide business importance.
8. **Official low-noise sources come first.** P2.5 and adjacent source-expansion work should prioritize reusable official low-noise sources before community, social, or media coverage.
9. **Aggregation belongs downstream.** Cross-source topic merging, discussion-volume weighting, and other importance/ranking logic belong to downstream consumers, not Shiyi core.
10. **Defer aggressively, expand by leverage.** If a candidate source cannot yet satisfy the readiness gate or only becomes useful after downstream aggregation, keep it on the defer list. Follow an 80/20 expansion rule: add the most reusable general sources first, then revisit high-value deferred sources later.
11. **Idempotency is product language.** The stable replay identity is `idempotency_key`; do not rename it to `dedupe_key`.
12. **Local-first until contracts stabilize.** The MVP should stay easy to run locally, inspect, and test without services or credentials.
13. **Notion is task management only.** Repository docs are the source of truth for product and design decisions.

## 6. Core flow

```text
Source
-> Fetcher
-> Adapter
-> InternalItem
-> CapturePipeline
-> Raw artifact
-> Normalized artifact
-> Optional neutral annotation
-> Event record
-> Export/read distribution
-> Consumer product pipeline
```

## 7. Source strategy

Shiyi should scale source coverage through batches, not through a broad crawler free-for-all.

### 7.1 Built-in source status

Current built-in sources:

- `openai` — OpenAI news RSS feed; explicit discovery-grade defer until a compliant canonical detail path is available;
- `anthropic` — Anthropic news index parser;
- `huggingface-blog` — Hugging Face Blog RSS discovery plus canonical article detail pages;
- `google-research-blog` — Google Research Blog RSS discovery plus canonical article detail pages;
- `deepmind-blog` — Google DeepMind Blog RSS discovery plus canonical article detail pages;
- `deepseek-news` — DeepSeek official news article pages, discovered from the API docs updates page;
- `z-ai-blog` — Z.ai / GLM official blog posts, discovered from the Mintlify release notes page;
- `moonshot-kimi-changelog` — Kimi Open Platform static changelog page;
- `bytedance-seed-blog` — ByteDance Seed SSR blog index plus article detail pages, with Chinese primary and English retained as fallback metadata.

These prove four adapter patterns: reusable feed-style capture, RSS-discovery/detail-page capture, index-page/article capture, and stable official changelog/embedded-data capture.
The P2.5 slices are still deliberately small; source registry/config and broader batch scale-out remain P3 work.

P2.5 source readiness now requires full-content capture. A built-in source is not ready for AI Weekly consumption if its normalized/exported content is only a feed summary, index excerpt, or changelog teaser while a canonical detail page or official detail payload exists.

### 7.2 Near-term expansion policy

Start with official, low-noise, mostly RSS/API/blog sources. They improve AI Weekly coverage without forcing Shiyi to solve ranking, community aggregation, or spam filtering too early.

Selection rule for this phase:

- prefer official sources that add broad reusable coverage with stable provenance;
- if discovery starts from RSS/feed/changelog surfaces, treat them as entry points only and normalize from the canonical detail surface instead of the feed snippet;
- if a source needs cross-source clustering, topic merging, or discussion-volume weighting before it becomes useful, defer it until downstream aggregation is ready;
- keep a growing defer list on purpose; follow the 80/20 rule and land the highest-leverage general sources first.

Recommended next batch:

- Google DeepMind / Gemini official updates beyond the Google Research RSS slice;
- Meta AI official updates;
- Microsoft AI / Azure AI official updates;
- Mistral / Cohere official updates if stable feeds are available;
- audited China-provider follow-ups such as `qwen-research` or `minimax-news` only after their JSON/API completeness and fixture boundaries are proven.

Second batch:

- LangChain;
- LlamaIndex;
- Vercel AI SDK;
- Weights & Biases;
- Modal;
- Replicate.

Higher-noise sources such as Hacker News, GitHub Trending, arXiv, Papers with Code, and tech media should wait until source registry, aggregation policy, and consumer-side ranking are clearer. When those sources are added later, Shiyi should still capture neutral events only; same-topic clustering and discussion-based importance weighting belong downstream.

Detailed source expansion policy lives in `docs/SOURCE_STRATEGY.md`.

## 8. Repository information architecture

Project-level canonical docs:

- `docs/PRODUCT_SPEC.md` — product mission, boundary, and principles;
- `docs/MILESTONES.md` — milestone plan and acceptance gates;
- `docs/SOURCE_STRATEGY.md` — source categories, batches, and readiness gate;
- `docs/testing-boundary.md` — engineering test and source-readiness gate.

Implementation-facing docs:

- `docs/architecture.md` — architecture overview;
- `docs/extension-points.md` — port/extension reference;
- `docs/specs/*.md` — component-level SDDs.

Historical/process docs:

- dated progress reviews, handoffs, and process notes should not remain as tracked repository docs
  after durable decisions are folded into project-level canonical docs;
- use issues, PRs, Discord handoffs, or git history for historical trace instead of expanding the
  active `docs/` surface.

Notion should contain only:

- tasks;
- task ownership;
- due dates;
- status;
- short execution notes that point back to repository docs.

## 9. Review and change policy

Goal, milestone, architecture, or source-expansion strategy changes require alignment from:

- PM/product owner: Kana;
- architect/implementation owner: Kurisu;
- final product owner: Lin.

Small reversible implementation details may proceed with normal engineering review, but product boundaries and milestone definitions must be updated in repository docs first.
