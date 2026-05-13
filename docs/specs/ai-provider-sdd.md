# Shiyi Neutral Preprocessing Provider SDD

- Status: Review
- Last updated: 2026-05-12
- Scope: optional neutral preprocessing provider boundary after capture/normalize core

## 1. Scope decision

Shiyi is not a domain insight engine. Provider-backed AI work inside Shiyi must be limited to neutral preprocessing that is reusable by multiple downstream products.

Allowed boundary:

```text
Shiyi = Capture + Normalize + Neutral Preprocess + Distribution
Briefly / AI Insight / Demand Radar = Domain Enrichment + Ranking + Product Output
```

## 2. MVP decision

The MVP can ship without a real LLM provider. The existing `LocalHeuristicAIProvider` is the current deterministic local provider for neutral annotations.

P0 correctness should depend on:

- reliable capture;
- raw artifact persistence;
- normalized/canonical artifact persistence;
- event records;
- idempotent replay.

Neutral preprocessing is optional and belongs to P1.

## 3. Allowed neutral preprocessing

Provider-backed work is in scope only when it is domain-neutral and reusable:

- language detection;
- translation helper fields;
- short neutral summary for preview/indexing;
- entity extraction: companies, products, people, papers, models, organizations;
- coarse topic/category labels;
- content quality/spam/near-duplicate signals;
- chunking and embeddings for retrieval.

## 4. Out of scope

Provider-backed work is out of scope when it creates business opinions or product-specific decisions:

- Briefly vertical insight judgment;
- AI R&D trend analysis;
- demand radar pain-point or opportunity scoring;
- weekly-report inclusion decisions;
- ranking, prioritization, or editorial selection;
- business conclusion generation;
- prompts that only one downstream product understands.

## 5. MVP provider contract

`EnrichmentTask` and `EnrichmentResult` are the MVP names for neutral, reusable annotation work. Do not expand `EnrichmentTask` with product-specific insight behavior. If a downstream product needs domain enrichment, it should run its own pipeline on Shiyi's normalized artifacts.

```python
class AIProvider(Protocol):
    async def run(self, task: EnrichmentTask, event: InternalItem) -> EnrichmentResult: ...
```

The provider may use `InternalItem` provenance and source metadata, but provider output must remain neutral and reusable.

## 6. Design requirements before real provider implementation

- Provider configuration must not hard-code secrets.
- Model identity must be recorded in every result.
- Usage metadata should include input/output tokens when available.
- Provider raw responses may be stored as artifacts only when policy allows it.
- Output must be schema-validated before an annotation is recorded as successful.
- Rate limits and retry behavior must be explicit.
- Every provider task must document why it is neutral and reusable.

## 7. First real provider candidate

The first real provider can be a single OpenAI-compatible structured-output implementation, but it should implement neutral preprocessing only. Anthropic can follow once provider config, schema retry, and artifact storage policy are stable.
