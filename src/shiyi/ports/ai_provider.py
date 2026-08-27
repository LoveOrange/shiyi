"""Provider-neutral outbound AI completion port."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AIProviderRequest:
    """Structured request accepted by every external AI provider."""

    prompt: str
    output_schema: dict[str, Any]


class AIProvider(Protocol):
    """Completes one provider-neutral structured AI request."""

    name: str

    async def complete(self, request: AIProviderRequest) -> dict[str, Any]:
        """Return one JSON object conforming to ``request.output_schema``."""
        ...
