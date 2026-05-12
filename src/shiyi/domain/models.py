"""Typed domain contracts for the Shiyi capture pipeline."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

NonEmptyString = Annotated[str, Field(min_length=1)]


class StrictModel(BaseModel):
    """Base model with strict, extension-friendly defaults."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class SourceIdentity(StrictModel):
    """Identifies the external system that produced a capture event."""

    kind: NonEmptyString
    uri: HttpUrl | None = None
    account_id: str | None = None


class Provenance(StrictModel):
    """Traceable source metadata for a normalized capture event."""

    adapter_name: NonEmptyString
    adapter_version: NonEmptyString
    fetched_at: datetime
    source_item_id: str | None = None


class TextPayload(StrictModel):
    """Plain text payload."""

    type: Literal["text"] = "text"
    text: NonEmptyString
    content_type: str = "text/plain"


class HtmlPayload(StrictModel):
    """HTML payload with optional canonical URL."""

    type: Literal["html"] = "html"
    html: NonEmptyString
    url: HttpUrl | None = None


class BinaryPayload(StrictModel):
    """Binary payload referenced by durable storage instead of inline bytes."""

    type: Literal["binary"] = "binary"
    media_type: NonEmptyString
    bytes_ref: NonEmptyString


CapturePayload = Annotated[TextPayload | HtmlPayload | BinaryPayload, Field(discriminator="type")]


class CaptureEvent(StrictModel):
    """Normalized boundary object emitted by adapters and consumed by core."""

    id: NonEmptyString
    source: SourceIdentity
    occurred_at: datetime
    payload: CapturePayload
    provenance: Provenance
    idempotency_key: NonEmptyString
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassifyTask(StrictModel):
    """Classify a capture event into one or more configured labels."""

    type: Literal["classify"] = "classify"
    labels: tuple[NonEmptyString, ...]


class ExtractTask(StrictModel):
    """Extract structured information from a capture event."""

    type: Literal["extract"] = "extract"
    schema_: dict[str, Any] = Field(alias="schema")


class SummarizeTask(StrictModel):
    """Summarize a capture event."""

    type: Literal["summarize"] = "summarize"
    max_tokens: int | None = Field(default=None, gt=0)


EnrichmentTask = Annotated[ClassifyTask | ExtractTask | SummarizeTask, Field(discriminator="type")]


class ModelIdentity(StrictModel):
    """Identifies the model used by an AI provider."""

    provider: NonEmptyString
    name: NonEmptyString
    version: str | None = None


class TokenUsage(StrictModel):
    """Optional usage accounting for an enrichment call."""

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cost_micros: int | None = Field(default=None, ge=0)


class EnrichmentResult(StrictModel):
    """Validated AI enrichment result."""

    task_type: Literal["classify", "extract", "summarize"]
    output: Any
    model: ModelIdentity
    usage: TokenUsage | None = None


class Checkpoint(StrictModel):
    """Durable adapter cursor committed after successful processing."""

    adapter_name: NonEmptyString
    cursor: NonEmptyString
    committed_at: datetime
