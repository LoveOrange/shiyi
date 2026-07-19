"""Typed domain contracts for Shiyi's Briefly-first capture flow."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

NonEmptyString = Annotated[str, Field(min_length=1)]


class StrictModel(BaseModel):
    """Base model with explicit, immutable fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, validate_assignment=True)


class Source(StrictModel):
    """One independently identifiable collection target."""

    id: NonEmptyString
    adapter: NonEmptyString
    target: NonEmptyString
    enabled: bool = True
    options: dict[str, Any] = Field(default_factory=dict)


class CaptureConfig(StrictModel):
    """Declarative list of sources selected for a capture run."""

    sources: tuple[Source, ...]

    @model_validator(mode="after")
    def source_ids_are_unique(self) -> CaptureConfig:
        """Reject ambiguous duplicate source identities."""
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            msg = "CaptureConfig source ids must be unique"
            raise ValueError(msg)
        return self


class TextPayload(StrictModel):
    """Plain-text source payload."""

    type: Literal["text"] = "text"
    text: NonEmptyString
    content_type: NonEmptyString = "text/plain"


class HtmlPayload(StrictModel):
    """HTML source payload with an optional canonical URL."""

    type: Literal["html"] = "html"
    html: NonEmptyString
    url: HttpUrl | None = None


class BinaryPayload(StrictModel):
    """Binary source payload already referenced outside the process."""

    type: Literal["binary"] = "binary"
    media_type: NonEmptyString
    bytes_ref: NonEmptyString


CapturePayload = Annotated[TextPayload | HtmlPayload | BinaryPayload, Field(discriminator="type")]


def payload_bytes(payload: CapturePayload) -> bytes:
    """Return the stable byte representation retained by the Blob store."""
    if isinstance(payload, TextPayload):
        return payload.text.encode()
    if isinstance(payload, HtmlPayload):
        return payload.html.encode()
    return payload.bytes_ref.encode()


def payload_media_type(payload: CapturePayload) -> str:
    """Return the payload media type."""
    if isinstance(payload, TextPayload):
        return payload.content_type
    if isinstance(payload, HtmlPayload):
        return "text/html"
    return payload.media_type


def payload_content_hash(payload: CapturePayload) -> str:
    """Return a deterministic SHA-256 hash for a source payload."""
    return sha256(payload_bytes(payload)).hexdigest()


class CaptureWindow(StrictModel):
    """Optional time and count window used by source adapters."""

    since: datetime | None = None
    until: datetime | None = None
    max_items: int | None = Field(default=None, gt=0)

    def includes(self, published_at: datetime | None) -> bool:
        """Return whether a date is inside the half-open capture window."""
        if published_at is None:
            return self.since is None and self.until is None
        if (since := self.since) and published_at < since:
            return False
        return not ((until := self.until) and published_at >= until)


class SourceItem(StrictModel):
    """Transient SourceAdapter -> ContentProcessor boundary."""

    schema_version: Literal["source-item.v1"] = "source-item.v1"
    source_id: NonEmptyString
    source_item_id: NonEmptyString
    kind: NonEmptyString
    canonical_url: HttpUrl | None = None
    collected_at: datetime
    published_at: datetime | None = None
    summary: str | None = None
    payload: CapturePayload
    metadata: dict[str, Any] = Field(default_factory=dict)


class BlobRef(StrictModel):
    """Content-addressed reference to raw, large, or cold bytes."""

    store: NonEmptyString
    key: NonEmptyString
    sha256: NonEmptyString
    media_type: NonEmptyString
    size: int = Field(ge=0)


class ContentItem(StrictModel):
    """Canonical persisted document consumed by Briefly."""

    schema_version: Literal["content-item.v1"] = "content-item.v1"
    id: NonEmptyString
    source_id: NonEmptyString
    source_item_id: NonEmptyString
    kind: NonEmptyString
    canonical_url: HttpUrl | None = None
    title: NonEmptyString
    creators: tuple[NonEmptyString, ...] = ()
    published_at: datetime | None = None
    collected_at: datetime
    language: str | None = None
    content: NonEmptyString
    content_format: Literal["markdown"] = "markdown"
    summary: str | None = None
    summary_language: str | None = None
    categories: tuple[NonEmptyString, ...] = ()
    tags: tuple[NonEmptyString, ...] = ()
    metrics: dict[str, int | float] = Field(default_factory=dict)
    raw_ref: BlobRef | None = None
    content_hash: NonEmptyString
    extra: dict[str, Any] = Field(default_factory=dict)
    ready_at: datetime | None = None
    updated_at: datetime


class AIContentFields(StrictModel):
    """Optional neutral fields proposed by an AI processor."""

    language: str | None = None
    summary: str | None = None
    summary_language: str | None = None
    categories: tuple[NonEmptyString, ...] = ()
    tags: tuple[NonEmptyString, ...] = ()


def content_item_id(*, source_id: str, source_item_id: str) -> str:
    """Return Shiyi's deterministic global identity for a source item."""
    return sha256(f"{source_id}\0{source_item_id}".encode()).hexdigest()
