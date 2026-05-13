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
    """Identifies the external system that produced an internal item."""

    kind: NonEmptyString
    uri: HttpUrl | None = None
    account_id: str | None = None


class Provenance(StrictModel):
    """Traceable source metadata for a normalized internal item."""

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


class CaptureWindow(StrictModel):
    """Optional time and count window for source discovery."""

    since: datetime | None = None
    until: datetime | None = None
    max_items: int | None = Field(default=None, gt=0)

    def includes(self, occurred_at: datetime | None) -> bool:
        """Return whether an item date is inside the half-open capture window."""
        if occurred_at is None:
            return self.since is None and self.until is None
        if (since := self.since) and occurred_at < since:
            return False
        return not ((until := self.until) and occurred_at >= until)


class InternalItem(StrictModel):
    """Canonical Adapter -> Pipeline boundary object."""

    id: NonEmptyString
    source: SourceIdentity
    occurred_at: datetime
    payload: CapturePayload
    provenance: Provenance
    idempotency_key: NonEmptyString
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClassifyTask(StrictModel):
    """Classify an internal item into one or more configured tags."""

    type: Literal["classify"] = "classify"
    labels: tuple[NonEmptyString, ...]


class ExtractTask(StrictModel):
    """Extract structured information from an internal item."""

    type: Literal["extract"] = "extract"
    schema_: dict[str, Any] = Field(alias="schema")


class SummarizeTask(StrictModel):
    """Summarize an internal item."""

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


ArtifactKind = Literal["raw", "normalized", "enrichment"]


class ArtifactWrite(StrictModel):
    """Artifact content to persist outside event-record storage."""

    kind: ArtifactKind
    media_type: NonEmptyString
    content: bytes
    suggested_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactRef(StrictModel):
    """Stable reference to a stored artifact."""

    uri: NonEmptyString
    kind: ArtifactKind
    media_type: NonEmptyString
    size_bytes: int = Field(ge=0)
    sha256: NonEmptyString


class ArtifactRead(StrictModel):
    """Stored artifact content plus reference metadata."""

    ref: ArtifactRef
    content: bytes


EventStatus = Literal["persisted", "enriched", "partially_enriched", "failed"]


class EventRecord(StrictModel):
    """Processing ledger record for one logical internal item."""

    event_id: NonEmptyString
    idempotency_key: NonEmptyString
    status: EventStatus
    raw_artifact: ArtifactRef | None = None
    normalized_artifact: ArtifactRef | None = None
    last_error: str | None = None
