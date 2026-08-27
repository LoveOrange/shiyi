# AI Provider ACL SDD

- Status: Accepted
- Owner: Shiyi contributors
- Last updated: 2026-07-19
- Scope: optional neutral enrichment after deterministic capture

## 1. Decision

Every external AI integration goes through `AIProviderACL`. `CaptureRunner` never calls an AI provider and never depends on AI success. The only MVP AI entry is the bounded post-capture `AIEnrichmentRunner`.

```text
ContentItemStore
-> AIEnrichmentRunner
-> AIProviderACL
-> AIProvider
-> provider implementation
```

This is an anti-corruption layer, not a generic AI framework:

- `AIEnrichmentRunner` selects ready `ContentItem` records whose `summary` is empty;
- `AIProviderACL` maps canonical content into a narrow structured prompt and validates provider JSON;
- `AIProvider` exposes only a provider-neutral structured completion operation;
- implementations such as `CodexCLIProvider` own authentication and invocation details;
- deterministic merge code remains the only component allowed to update `ContentItem`.

## 2. Contracts

```python
@dataclass(frozen=True)
class AIProviderRequest:
    prompt: str
    output_schema: dict[str, Any]


class AIProvider(Protocol):
    name: str

    async def complete(self, request: AIProviderRequest) -> dict[str, Any]: ...


class AIProviderACL:
    async def process_many(
        self,
        items: Sequence[ContentItem],
    ) -> dict[str, AIContentFields]: ...
```

Provider SDK objects, model names, command-line output, token metadata, and authentication details stop at the provider implementation. They never enter `ContentItem` or the Briefly contract.

## 3. Allowed output

The ACL may return only:

- original content language when not already known;
- a neutral summary when the item has no summary;
- configured summary language;
- simple categories;
- simple tags.

It must not produce Signal, Trend, Opportunity, ranking, credibility, recommendation, or editorial fields.

Provider output is untrusted. The ACL requires exactly one result for every requested `ContentItem.id`, rejects duplicate or unexpected IDs, constrains summary and label sizes, and validates the full JSON object. Deterministic code then bounds, deduplicates, and merges the allowed fields without replacing source facts.

## 4. Summary and state rule

`ContentItem.summary` is the only enrichment gate.

- A non-empty source summary skips AI completely.
- A successful AI summary makes the item ineligible for later enrichment runs.
- A failure leaves `summary` empty, so a later bounded run naturally retries it.
- No AI status, origin, task, job, or artifact ledger is persisted.

The command reads a small newest-first batch and sends that batch in one provider request. The default is five records with at most 20,000 content characters per record. These limits reduce subscription usage and bound provider context.

## 5. Codex CLI provider

`CodexCLIProvider` is the MVP provider for a trusted local machine. It uses the officially supported [`codex exec` non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) with an output JSON Schema.

Before enrichment it runs `codex login status` and requires ChatGPT authentication. It refuses API-key authentication to avoid accidental usage-based billing. The completion run:

- is ephemeral;
- ignores user config and execution rules;
- disables web search;
- uses a dedicated read-only permission profile limited to runtime files and the empty temporary workspace;
- disables network access for model-generated commands;
- inherits no shell environment variables;
- receives only selected content fields on standard input;
- never receives the MongoDB URI or Shiyi infrastructure configuration.

Codex's own authenticated service connection still works; the network restriction applies to model-generated tools. OpenAI documents ChatGPT login as subscription access and API-key login as usage-based access in [Codex authentication](https://learn.chatgpt.com/docs/auth).

Run a deliberately bounded batch:

```bash
uv run shiyi enrich \
  --provider codex-cli \
  --summary-language zh \
  --limit 5
```

The provider is a local MVP bridge, not a public or multi-tenant inference service. A scheduler may invoke it only on a trusted host with a dedicated Codex login and within subscription limits.

## 6. Future providers

A later OpenAI API or local-model implementation replaces only `AIProvider`. It reuses the same ACL, output validation, summary gate, deterministic merge, MongoDB query, and `ContentItem` contract.

Do not add a provider registry, generic task engine, prompt database, retry ledger, or model-specific domain fields until a concrete Briefly requirement needs them.
