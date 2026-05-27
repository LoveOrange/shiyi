"""Typed domain contracts for the Shiyi capture pipeline."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Annotated, Any, Literal, cast, get_args

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

NonEmptyString = Annotated[str, Field(min_length=1)]
ContentDepth = Literal["complete", "partial", "summary_only"]
ContentCompleteness = Literal["complete", "partial", "summary_only"]
SourceType = Literal["changelog", "release_notes", "blog", "docs", "research", "news", "unknown"]
SOURCE_READY_CONTENT_DEPTHS: frozenset[ContentDepth] = frozenset(("complete",))
CONTENT_DEPTH_COMPLETENESS: dict[ContentDepth, ContentCompleteness] = {
    "complete": "complete",
    "summary_only": "summary_only",
    "partial": "partial",
}


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


def payload_content_hash(payload: CapturePayload) -> str:
    """Return a deterministic SHA-256 hash for an internal item payload."""
    if isinstance(payload, TextPayload):
        material = f"text\0{payload.content_type}\0{payload.text}"
    elif isinstance(payload, HtmlPayload):
        material = f"html\0{payload.html}"
    else:
        material = f"binary\0{payload.media_type}\0{payload.bytes_ref}"
    return sha256(material.encode()).hexdigest()


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

    schema_version: Literal["internal-item.v1"] = "internal-item.v1"
    id: NonEmptyString
    source: SourceIdentity
    captured_at: datetime
    occurred_at: datetime
    payload: CapturePayload
    content_hash: NonEmptyString
    provenance: Provenance
    idempotency_key: NonEmptyString
    metadata: dict[str, Any] = Field(default_factory=dict)


def content_depth_from_metadata(metadata: dict[str, Any]) -> ContentDepth | None:
    """Return source-neutral content-depth metadata, validating known values."""
    value = metadata.get("content_depth")
    if value is None:
        return None
    if value in get_args(ContentDepth):
        return cast(ContentDepth, value)
    msg = f"unsupported content_depth: {value!r}"
    raise ValueError(msg)


def is_source_ready_content_depth(content_depth: ContentDepth | str | None) -> bool:
    """Return whether content depth is decision-grade for AI Weekly by default."""
    return content_completeness_from_depth(content_depth) == "complete"


def content_completeness_from_depth(
    content_depth: ContentDepth | str | None,
) -> ContentCompleteness | None:
    """Derive item-level completeness from the MVP content-depth contract."""
    if content_depth is None:
        return None
    if content_depth not in CONTENT_DEPTH_COMPLETENESS:
        msg = f"unsupported content_depth: {content_depth!r}"
        raise ValueError(msg)
    return CONTENT_DEPTH_COMPLETENESS[content_depth]


def is_item_ready_content_completeness(
    content_completeness: ContentCompleteness | str | None,
) -> bool:
    """Return whether content completeness is decision-grade by default."""
    return content_completeness == "complete"


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
    source: SourceIdentity | None = None
    captured_at: datetime | None = None
    occurred_at: datetime | None = None
    content_hash: str | None = None
    adapter_name: str | None = None
    adapter_version: str | None = None
    content_depth: ContentDepth | None = None
    last_error: str | None = None
