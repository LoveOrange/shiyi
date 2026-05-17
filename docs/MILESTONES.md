# Shiyi Milestones

- Status: Canonical milestone plan
- Last updated: 2026-05-16
- Owners: Lin, Kana, Kurisu

Repository docs are the milestone source of truth. Notion task pages should reference these milestones and track execution only.

## 1. Progress summary

Current assessment: Shiyi has completed the first usable capture-to-export foundation and P2 contract hardening. The next active step is small-slice, readiness-gated official source expansion.

The next strategic turn is not “pause source expansion forever”. It is:

```text
source-readiness gate complete -> add low-noise official sources -> scale adapters/source registry -> support higher-noise community sources
```

## 2. Milestone map

### M0 — Product and architecture alignment

- Status: Done
- Result: Shiyi is defined as shared information capture infrastructure, not a downstream insight product.
- Evidence:
  - `docs/PRODUCT_SPEC.md`
  - `docs/architecture.md`
  - `docs/specs/scope-sdd.md`
  - `docs/adr/0001-core-extension-boundaries.md`

Acceptance:

- product boundary is explicit;
- downstream consumers own ranking/editorial/business judgments;
- Shiyi owns source capture, normalization, provenance, idempotency, and distribution.

### P1 — Capture-to-export foundation

- Status: Done
- Notion task family: `SHIYI-P1-01` through `SHIYI-P1-05`
- Result: first end-to-end local foundation is usable.

Completed scope:

- Fetcher interface and minimal implementation;
- Adapter to `InternalItem` path;
- `InternalItem` schema and normalization contract;
- pipeline to filesystem artifacts plus SQLite event records;
- upstream read/export minimal interface;
- OpenAI and Anthropic built-in sources;
- CLI capture/list/export;
- `idempotency_key` replay safety;
- local quality gates.

Exit criteria:

- `uv run shiyi capture` works for first built-in sources;
- rerun skips already-complete records;
- export output is consumer-safe and excludes third-party raw DTO leakage;
- default tests/lint/typecheck pass.

### P2 — Test boundary and contract hardening

- Status: Done
- Notion task family: `SHIYI-P2-01` through `SHIYI-P2-05`
- Goal: make source/adapter growth safe enough that future source expansion does not break core contracts.
- Result: P2-01 through P2-05 are complete and merged through `44fab61 test: harden export read contracts`.

Scope:

- test layer definition and fixture policy;
- fetcher contract tests;
- adapter fixture and `InternalItem` schema tests;
- pipeline-to-persistence integration tests;
- export/read contract tests and E2E smoke;
- new source readiness gate.

Acceptance:

- every built-in source has sanitized raw fixture coverage;
- adapter output passes `InternalItem` validation;
- `idempotency_key` stability and non-collision are tested;
- invalid/missing required source fields fail clearly;
- time parsing and half-open windows are tested where relevant;
- pipeline replay and duplicate behavior are covered;
- export/read tests prove downstream consumers do not need source-specific DTOs;
- default CI remains credential-free and network-free;
- live public-source smoke tests remain opt-in.

Decision gate before leaving P2:

- If a new source cannot satisfy the readiness gate, it must remain experimental and out of default source lists.

### P2.5 — Source expansion batch 1: official low-noise sources

- Status: In progress
- Goal: increase AI R&D source coverage with stable official sources while preserving P2 contracts.

Recommended first batch:

1. Google Research Blog / Google DeepMind / Gemini official updates;
2. Hugging Face Blog;
3. Meta AI official updates;
4. Microsoft AI / Azure AI official updates;
5. optional: Mistral or Cohere official updates if stable feeds are available.

Current implementation slices:

- `huggingface-blog` through the reusable RSS adapter path;
- `google-research-blog` through the reusable RSS adapter path;
- `deepmind-blog` through a narrow RSS-discovery/detail-page adapter with the feed used only as a discovery index;
- `deepseek-news` through an official news adapter with the updates page used only as a discovery index;
- `z-ai-blog` through an official blog adapter with release notes used only as a discovery index;
- `moonshot-kimi-changelog` through a static changelog-page adapter;
- `bytedance-seed-blog` through official SSR embedded-data index plus article detail pages;
- text-only RSS and changelog entries remain exportable through canonical Markdown normalization;
- `qwen-research` and `minimax-news` are audited but deferred until JSON/API completeness and fixture boundaries are stronger;
- source registry/config remains deferred to P3.

Acceptance:

- at least four additional official/low-noise sources are captured through reusable adapter patterns;
- every built-in P2.5 adapter can read full article/detail content from the canonical article URL or an official structured detail payload when the source exposes one;
- RSS/index/changelog snippets are treated as discovery metadata or degraded fallback only, not as sufficient decision-grade article content;
- each source has raw detail fixture coverage, adapter contract test, idempotency stability test, invalid-field test, and export/read smoke;
- normalized/exported content contains decision-grade detail content and not merely an RSS summary; summary-only/partial records must be explicitly marked and excluded from AI Weekly source-ready counts;
- source-specific parsing does not leak into pipeline or export contracts;
- source coverage improves AI Weekly candidate quality in a real 14-day export review;
- no product-specific weekly-report ranking is added to Shiyi.

### P3 — Source registry and adapter scale-out

- Status: Planned
- Goal: make adding many sources systematic instead of hand-wiring every source into CLI conditionals.

Scope:

- source registry/config file;
- generic RSS/Atom source declarations where possible;
- source enable/disable controls;
- source health/status output;
- standardized source metadata fields;
- adapter family docs and examples;
- initial batch for tooling/agent ecosystem sources.

Candidate sources:

- LangChain;
- LlamaIndex;
- Vercel AI SDK;
- Weights & Biases;
- Modal;
- Replicate;
- selected model/provider official blogs.

Acceptance:

- adding a simple RSS/blog source does not require bespoke CLI branching;
- source health can be inspected without reading artifacts manually;
- `shiyi sources` or equivalent lists registered source status;
- fixtures and readiness checks remain mandatory for built-in sources.

### P4 — Consumer distribution and operations

- Status: Planned
- Goal: make Shiyi reliable as a substrate for multiple consumers, not just one local script.

Scope:

- richer export/read options;
- stable JSONL or local API contract;
- run summaries and structured operational counters;
- source-level failure reporting;
- backfill and daily overlap recipes;
- examples for `briefly-ai-weekly` and Demand Radar consumers.

Acceptance:

- consumers can read the last N days without knowing source-specific storage details;
- export order, filters, and trace fields are documented and tested;
- failures are observable enough for scheduled runs;
- consumer examples stay outside Shiyi's product-specific logic.

### P5 — Higher-noise and community source support

- Status: Planned
- Goal: safely capture community, research, and market sources that require stronger normalization and downstream interpretation.

Candidate areas:

- Hacker News;
- GitHub Trending or repository activity feeds;
- arXiv / papers;
- Papers with Code;
- selected tech media;
- social/community feeds when terms and reliability are clear.

Acceptance:

- high-noise sources are captured as neutral source material, not ranked insights;
- consumer products perform aggregation/ranking downstream;
- source-specific rate limits, terms, and failure modes are explicit;
- default Shiyi output remains traceable, replay-safe, and consumer-safe.

## 3. Current priority

Do not add broad community/media/research sources until P2 readiness is strong enough.

It is acceptable to parallelize source discovery and fixture research for P2.5, but production source additions should follow the readiness gate.

Current work order:

1. Finish P2 contract breadth.
2. Start P2.5 with official low-noise sources.
3. Add P3 registry support before source count becomes hard to manage.
4. Only then move into higher-noise sources.

## 4. Review rules

Milestone changes must be reflected here first, then mirrored to Notion tasks if execution tracking is needed.

Major changes require review/alignment from:

- PM/product owner: Kana;
- architect/implementation owner: Kurisu;
- product owner: Lin.
