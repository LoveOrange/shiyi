# Shiyi AI Provider SDD

- Status: Draft
- Last updated: 2026-05-12
- Scope: AI provider boundary after local MVP

## MVP decision

The MVP ships with `LocalHeuristicAIProvider` only. A real LLM provider is explicitly outside the MVP boundary.

This keeps the MVP focused on reliable capture, normalization, persistence, idempotency, and traceability. Real LLM providers introduce secrets, cost, schema retries, model variance, rate limits, and safety policy. Those are important, but they should not block the local capture MVP.

## Required provider contract

A real provider implementation must satisfy the existing `AIProvider` port:

```python
class AIProvider(Protocol):
    @property
    def name(self) -> str: ...

    async def run(self, task: EnrichmentTask, event: CaptureEvent) -> EnrichmentResult: ...
```

## Design requirements before implementation

- Provider configuration must not hard-code secrets.
- Model identity must be recorded in every `EnrichmentResult`.
- Usage metadata should include input/output tokens when available.
- Provider raw responses may be stored as artifacts only when policy allows it.
- Output must be schema-validated before metadata is marked enriched.
- Rate limits and retry behavior must be explicit.

## First real provider candidate

The first real provider should be a single OpenAI-compatible chat/completions implementation or responses API implementation with structured JSON output. Anthropic can follow once the provider config and schema retry story are stable.
