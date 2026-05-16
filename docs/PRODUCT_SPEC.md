# Shiyi Product Spec

- Status: Canonical product source of truth
- Last updated: 2026-05-15
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

As of 2026-05-15, Shiyi has moved from product/architecture exploration into a usable early infrastructure base with its P2 contract hardening gate complete.

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

The active next milestone is P2.5: add a small slice of official, low-noise sources without weakening the P2 readiness gate.

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
4. **Normalized content is consumer-safe.** Downstream products should read stable Shiyi output without knowing source-specific DTOs.
5. **Neutral preprocessing only.** Optional AI work inside Shiyi may summarize, extract entities, detect language, chunk, embed, or provide generic quality signals; it must not decide business importance.
6. **Idempotency is product language.** The stable replay identity is `idempotency_key`; do not rename it to `dedupe_key`.
7. **Local-first until contracts stabilize.** The MVP should stay easy to run locally, inspect, and test without services or credentials.
8. **Notion is task management only.** Repository docs are the source of truth for product and design decisions.

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

- `openai` — OpenAI news RSS feed;
- `anthropic` — Anthropic news index parser;
- `huggingface-blog` — Hugging Face Blog RSS feed;
- `google-research-blog` — Google Research Blog RSS feed.

These prove the first two adapter patterns: reusable feed-style capture and index-page/article capture.
The P2.5 RSS-first slice is still deliberately small; source registry/config and broader batch scale-out remain P3 work.

### 7.2 Near-term expansion policy

Start with official, low-noise, mostly RSS/API/blog sources. They improve AI Weekly coverage without forcing Shiyi to solve ranking, community aggregation, or spam filtering too early.

Recommended next batch:

- Google Research Blog / Google DeepMind / Gemini official updates;
- Hugging Face Blog;
- Meta AI official updates;
- Microsoft AI / Azure AI official updates;
- Mistral / Cohere official updates if stable feeds are available.

Second batch:

- LangChain;
- LlamaIndex;
- Vercel AI SDK;
- Weights & Biases;
- Modal;
- Replicate.

Higher-noise sources such as Hacker News, GitHub Trending, arXiv, Papers with Code, and tech media should wait until source registry, aggregation policy, and consumer-side ranking are clearer.

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
