"""Shiyi public API."""

from shiyi.adapters.rss import RssFeedAdapter, openai_news_adapter
from shiyi.domain.models import (
    ArtifactRead,
    ArtifactRef,
    ArtifactWrite,
    BinaryPayload,
    CaptureEvent,
    EnrichmentResult,
    EventRecord,
    ExtractTask,
    HtmlPayload,
    ModelIdentity,
    Provenance,
    SourceIdentity,
    SummarizeTask,
    TextPayload,
    TokenUsage,
)
from shiyi.normalizers.html import HtmlMarkdownNormalizer
from shiyi.pipeline.runner import CapturePipeline
from shiyi.ports.adapter import Adapter
from shiyi.ports.ai_provider import AIProvider
from shiyi.ports.artifact_store import ArtifactStore
from shiyi.ports.metadata_store import MetadataStore
from shiyi.ports.normalizer import Normalizer

__all__ = [
    "AIProvider",
    "Adapter",
    "ArtifactRead",
    "ArtifactRef",
    "ArtifactStore",
    "ArtifactWrite",
    "BinaryPayload",
    "CaptureEvent",
    "CapturePipeline",
    "EnrichmentResult",
    "EventRecord",
    "ExtractTask",
    "HtmlMarkdownNormalizer",
    "HtmlPayload",
    "MetadataStore",
    "ModelIdentity",
    "Normalizer",
    "Provenance",
    "RssFeedAdapter",
    "SourceIdentity",
    "SummarizeTask",
    "TextPayload",
    "TokenUsage",
    "openai_news_adapter",
]
