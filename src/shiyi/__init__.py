"""Shiyi public API."""

from shiyi.adapters.anthropic import AnthropicNewsAdapter, anthropic_news_adapter
from shiyi.adapters.bytedance_seed import ByteDanceSeedBlogAdapter, bytedance_seed_blog_adapter
from shiyi.adapters.changelog import (
    ArticleDetail,
    ArticleIndexEntry,
    ChangelogEntry,
    ChangelogPageAdapter,
    OfficialArticleAdapter,
    deepseek_news_adapter,
    deepseek_updates_adapter,
    moonshot_kimi_changelog_adapter,
    z_ai_blog_adapter,
    z_ai_release_notes_adapter,
)
from shiyi.adapters.deepmind import DeepMindArticle, DeepMindBlogAdapter, deepmind_blog_adapter
from shiyi.adapters.rss import (
    RssFeedAdapter,
    google_research_blog_adapter,
    huggingface_blog_adapter,
    openai_news_adapter,
)
from shiyi.domain.models import (
    ArtifactRead,
    ArtifactRef,
    ArtifactWrite,
    BinaryPayload,
    CaptureWindow,
    ClassifyTask,
    ContentDepth,
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
    content_depth_from_metadata,
    is_source_ready_content_depth,
    payload_content_hash,
)
from shiyi.export import ExportedItem, export_items
from shiyi.normalizers.html import HtmlMarkdownNormalizer
from shiyi.pipeline.runner import CapturePipeline, PipelineRunError, PipelineRunSummary
from shiyi.ports.adapter import Adapter
from shiyi.ports.ai_provider import AIProvider
from shiyi.ports.artifact_store import ArtifactStore
from shiyi.ports.event_record_store import EventRecordStore
from shiyi.ports.normalizer import Normalizer

__all__ = [
    "AIProvider",
    "Adapter",
    "AnthropicNewsAdapter",
    "ArticleDetail",
    "ArticleIndexEntry",
    "ArtifactRead",
    "ArtifactRef",
    "ArtifactStore",
    "ArtifactWrite",
    "BinaryPayload",
    "ByteDanceSeedBlogAdapter",
    "CapturePipeline",
    "CaptureWindow",
    "ChangelogEntry",
    "ChangelogPageAdapter",
    "ClassifyTask",
    "ContentDepth",
    "DeepMindArticle",
    "DeepMindBlogAdapter",
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
    "OfficialArticleAdapter",
    "PipelineRunError",
    "PipelineRunSummary",
    "Provenance",
    "RssFeedAdapter",
    "SourceIdentity",
    "SummarizeTask",
    "TextPayload",
    "TokenUsage",
    "anthropic_news_adapter",
    "bytedance_seed_blog_adapter",
    "content_depth_from_metadata",
    "deepmind_blog_adapter",
    "deepseek_news_adapter",
    "deepseek_updates_adapter",
    "export_items",
    "google_research_blog_adapter",
    "huggingface_blog_adapter",
    "is_source_ready_content_depth",
    "moonshot_kimi_changelog_adapter",
    "openai_news_adapter",
    "payload_content_hash",
    "z_ai_blog_adapter",
    "z_ai_release_notes_adapter",
]
