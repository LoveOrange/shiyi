"""Shiyi public API."""

from shiyi.adapters.anthropic import AnthropicNewsAdapter, anthropic_news_adapter
from shiyi.adapters.rss import RssFeedAdapter, openai_news_adapter
from shiyi.domain.models import (
    ArtifactRead,
    ArtifactRef,
    ArtifactWrite,
    BinaryPayload,
    CaptureWindow,
    ClassifyTask,
    EnrichmentResult,
    EventRecord,
    ExtractTask,
    HtmlPayload,
    InternalItem,
    ModelIdentity,
    Provenance,
    SourceIdentity,
    SummarizeTask,
    TextPayload,
    TokenUsage,
    payload_content_hash,
)
from shiyi.export import ExportedItem, export_items
from shiyi.normalizers.html import HtmlMarkdownNormalizer
from shiyi.pipeline.runner import CapturePipeline
from shiyi.ports.adapter import Adapter
from shiyi.ports.ai_provider import AIProvider
from shiyi.ports.artifact_store import ArtifactStore
from shiyi.ports.event_record_store import EventRecordStore
from shiyi.ports.normalizer import Normalizer

__all__ = [
    "AIProvider",
    "Adapter",
    "AnthropicNewsAdapter",
    "ArtifactRead",
    "ArtifactRef",
    "ArtifactStore",
    "ArtifactWrite",
    "BinaryPayload",
    "CapturePipeline",
    "CaptureWindow",
    "ClassifyTask",
    "EnrichmentResult",
    "EventRecord",
    "EventRecordStore",
    "ExportedItem",
    "ExtractTask",
    "HtmlMarkdownNormalizer",
    "HtmlPayload",
    "InternalItem",
    "ModelIdentity",
    "Normalizer",
    "Provenance",
    "RssFeedAdapter",
    "SourceIdentity",
    "SummarizeTask",
    "TextPayload",
    "TokenUsage",
    "anthropic_news_adapter",
    "export_items",
    "openai_news_adapter",
    "payload_content_hash",
]
