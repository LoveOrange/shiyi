"""Shiyi public API."""

from shiyi.domain.models import (
    AIContentFields,
    BinaryPayload,
    BlobRef,
    CaptureConfig,
    CaptureWindow,
    ContentItem,
    HtmlPayload,
    Source,
    SourceItem,
    TextPayload,
    content_item_id,
    payload_bytes,
    payload_content_hash,
    payload_media_type,
)
from shiyi.export import export_items
from shiyi.normalizers.html import MarkdownContentProcessor
from shiyi.pipeline.runner import CaptureRunError, CaptureRunner, CaptureRunSummary
from shiyi.ports.ai_processor import AIProcessor
from shiyi.ports.blob_store import BlobStore
from shiyi.ports.content_item_store import ContentItemStore
from shiyi.ports.content_processor import ContentProcessor
from shiyi.ports.source_adapter import SourceAdapter
from shiyi.sources import (
    BUILTIN_SOURCE_NAMES,
    BUILTIN_SOURCES,
    BuiltinSource,
    SourceName,
    SourceSummary,
    build_capture_config,
    build_source_adapters,
    builtin_source,
    source_summaries,
)
from shiyi.stores.filesystem import FileSystemBlobStore
from shiyi.stores.memory import MemoryContentItemStore
from shiyi.stores.mongo import MongoContentItemStore

__all__ = [
    "BUILTIN_SOURCES",
    "BUILTIN_SOURCE_NAMES",
    "AIContentFields",
    "AIProcessor",
    "BinaryPayload",
    "BlobRef",
    "BlobStore",
    "BuiltinSource",
    "CaptureConfig",
    "CaptureRunError",
    "CaptureRunSummary",
    "CaptureRunner",
    "CaptureWindow",
    "ContentItem",
    "ContentItemStore",
    "ContentProcessor",
    "FileSystemBlobStore",
    "HtmlPayload",
    "MarkdownContentProcessor",
    "MemoryContentItemStore",
    "MongoContentItemStore",
    "Source",
    "SourceAdapter",
    "SourceItem",
    "SourceName",
    "SourceSummary",
    "TextPayload",
    "build_capture_config",
    "build_source_adapters",
    "builtin_source",
    "content_item_id",
    "export_items",
    "payload_bytes",
    "payload_content_hash",
    "payload_media_type",
    "source_summaries",
]
