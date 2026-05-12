# Contributing to Shiyi

Shiyi is early, but the quality bar is intentionally high.

## Expectations

- Keep public contracts small, typed, and documented.
- Add or update tests for behavior changes.
- Use ADRs for architecture decisions that affect extension boundaries.
- Treat AI outputs as untrusted until validated.
- Prefer explicit failure modes over hidden fallback behavior.

## Development checks

```bash
uv sync
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```
