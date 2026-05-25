"""Built-in source registry and backlog metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol, TypeAlias

from shiyi.adapters.anthropic import ANTHROPIC_NEWS_URL, anthropic_news_adapter
from shiyi.adapters.bytedance_seed import BYTEDANCE_SEED_BLOG_URL, bytedance_seed_blog_adapter
from shiyi.adapters.changelog import (
    COHERE_BLOG_URL,
    DEEPSEEK_UPDATES_URL,
    GEMINI_API_CHANGELOG_URL,
    MISTRAL_NEWS_URL,
    MOONSHOT_KIMI_CHANGELOG_URL,
    Z_AI_RELEASE_NOTES_URL,
    cohere_blog_adapter,
    deepseek_news_adapter,
    gemini_api_changelog_adapter,
    mistral_news_adapter,
    moonshot_kimi_changelog_adapter,
    z_ai_blog_adapter,
)
from shiyi.adapters.deepmind import DEEPMIND_BLOG_RSS_URL, deepmind_blog_adapter
from shiyi.adapters.rss import (
    MICROSOFT_AI_BLOG_FEED_URL,
    google_research_blog_adapter,
    huggingface_blog_adapter,
    microsoft_ai_blog_adapter,
    openai_news_adapter,
)
from shiyi.domain.models import (
    CaptureWindow,
    ContentCompleteness,
    ContentDepth,
    content_completeness_from_depth,
    is_item_ready_content_completeness,
)
from shiyi.fetchers.http import HttpWebFetcher
from shiyi.ports.adapter import Adapter
from shiyi.source_readiness import StructuredApiGateStatus, StructuredApiReadinessEvidence


class SourceName(StrEnum):
    """Canonical built-in source names accepted by capture commands."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    HUGGINGFACE_BLOG = "huggingface-blog"
    GOOGLE_RESEARCH_BLOG = "google-research-blog"
    DEEPMIND_BLOG = "deepmind-blog"
    DEEPSEEK_NEWS = "deepseek-news"
    Z_AI_BLOG = "z-ai-blog"
    MOONSHOT_KIMI_CHANGELOG = "moonshot-kimi-changelog"
    BYTEDANCE_SEED_BLOG = "bytedance-seed-blog"
    GEMINI_API_CHANGELOG = "gemini-api-changelog"
    MISTRAL_NEWS = "mistral-news"
    MICROSOFT_AI_BLOG = "microsoft-ai-blog"
    COHERE_BLOG = "cohere-blog"


SourceFamily: TypeAlias = Literal[
    "rss",
    "article-index",
    "rss-detail",
    "changelog",
    "ssr-detail",
]
SourceCategory: TypeAlias = Literal["official", "community", "social_media"]
DetailCaptureMode: TypeAlias = Literal[
    "listing-only",
    "summary-only",
    "canonical-detail",
    "structured-api",
]
ReadinessStatus: TypeAlias = Literal["ready", "degraded", "deferred"]
AuthorityTier: TypeAlias = Literal["primary", "secondary", "unverified"]
BacklogBucket: TypeAlias = Literal[
    "p3-registry-candidate",
    "p3-json-api-fetcher",
    "later-high-noise",
]
SourceStatus: TypeAlias = Literal["built-in", "deferred"]


class SourceAdapterFactory(Protocol):
    """Factory for a capture adapter registered by source name."""

    def __call__(
        self,
        *,
        window: CaptureWindow | None,
        raw_cache_root: Path | None = None,
    ) -> Adapter:
        """Build an adapter for one capture window."""
        ...


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    """Registry entry for one built-in capture source."""

    name: SourceName
    source_kind: str
    adapter_name: str
    family: SourceFamily
    source_category: SourceCategory
    detail_capture_mode: DetailCaptureMode
    entry_url: str
    default_content_depth: ContentDepth
    notes: str
    traceability_refs: tuple[str, ...]
    factory: SourceAdapterFactory = field(repr=False, compare=False)
    authority_tier: AuthorityTier | None = None
    defer_reason: str | None = None
    structured_api_readiness: StructuredApiReadinessEvidence | None = None

    def __post_init__(self) -> None:
        """Validate the source-readiness contract at import time."""
        if self.default_content_completeness == "complete":
            if self.defer_reason is not None:
                msg = f"complete source must not carry defer_reason: {self.name.value}"
                raise ValueError(msg)
        elif not self.defer_reason:
            msg = f"incomplete source must carry defer_reason: {self.name.value}"
            raise ValueError(msg)
        if not self.traceability_refs:
            msg = f"source must carry traceability refs: {self.name.value}"
            raise ValueError(msg)
        if self.detail_capture_mode == "structured-api" and (
            self.structured_api_readiness is None or not self.structured_api_readiness.source_ready
        ):
            msg = f"structured-api built-in source must pass readiness gate: {self.name.value}"
            raise ValueError(msg)

    @property
    def default_content_completeness(self) -> ContentCompleteness:
        """Return the item-level completeness implied by the default content depth."""
        completeness = content_completeness_from_depth(self.default_content_depth)
        if completeness is None:
            msg = f"built-in source must carry default content completeness: {self.name.value}"
            raise ValueError(msg)
        return completeness

    @property
    def readiness_status(self) -> ReadinessStatus:
        """Return the review label derived from content completeness."""
        return "ready" if self.source_ready else "degraded"

    @property
    def source_ready(self) -> bool:
        """Return the source-ready review label derived from content completeness."""
        return is_item_ready_content_completeness(self.default_content_completeness)

    def create_adapter(
        self,
        *,
        window: CaptureWindow | None,
        raw_cache_root: Path | None = None,
    ) -> Adapter:
        """Create the adapter represented by this source definition."""
        return self.factory(window=window, raw_cache_root=raw_cache_root)


@dataclass(frozen=True, slots=True)
class SourceBacklogItem:
    """Deferred source candidate captured during P2.5 handoff."""

    name: str
    bucket: BacklogBucket
    source_category: SourceCategory
    detail_capture_mode: DetailCaptureMode
    entry_url: str
    reason: str
    traceability_refs: tuple[str, ...]
    authority_tier: AuthorityTier | None = None
    structured_api_readiness: StructuredApiReadinessEvidence | None = None
    readiness_status: Literal["deferred"] = "deferred"
    content_completeness: ContentCompleteness | None = None

    def __post_init__(self) -> None:
        """Validate deferred structured/API candidates carry explicit gate evidence."""
        if self.detail_capture_mode == "structured-api" and self.structured_api_readiness is None:
            msg = f"structured-api backlog source must carry readiness gate: {self.name}"
            raise ValueError(msg)

    @property
    def source_ready(self) -> bool:
        """Return whether this backlog candidate counts as source-ready coverage."""
        return False


@dataclass(frozen=True, slots=True)
class SourceSummary:
    """JSON-friendly source registry row for CLI/status output."""

    name: str
    status: SourceStatus
    family: str
    entry_url: str
    source_category: SourceCategory | None = None
    authority_tier: AuthorityTier | None = None
    detail_capture_mode: DetailCaptureMode | None = None
    content_completeness: ContentCompleteness | None = None
    readiness_status: ReadinessStatus | None = None
    source_ready: bool = False
    counts_as_official_source_ready: bool = False
    traceability_refs: tuple[str, ...] = ()
    source_kind: str | None = None
    adapter_name: str | None = None
    default_content_depth: str | None = None
    defer_reason: str | None = None
    structured_api_gate: StructuredApiGateStatus | None = None
    structured_api_blockers: tuple[str, ...] = ()
    structured_api_traceability_refs: tuple[str, ...] = ()
    bucket: str | None = None
    notes: str | None = None

    def __post_init__(self) -> None:
        """Derive review labels from category, completeness, traceability, and defer state."""
        source_ready = self.status == "built-in" and is_item_ready_content_completeness(
            self.content_completeness
        )
        counts_as_official_source_ready = (
            self.source_category == "official"
            and source_ready
            and bool(self.traceability_refs)
            and self.defer_reason is None
        )
        object.__setattr__(self, "source_ready", source_ready)
        object.__setattr__(
            self,
            "counts_as_official_source_ready",
            counts_as_official_source_ready,
        )


def build_source_adapter(
    source: SourceName | str,
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    """Build a registered built-in source adapter."""
    return source_definition(source).create_adapter(window=window, raw_cache_root=raw_cache_root)


def source_definition(source: SourceName | str) -> SourceDefinition:
    """Return one built-in source definition by source name."""
    try:
        source_name = source if isinstance(source, SourceName) else SourceName(source)
    except ValueError as error:
        msg = f"unknown source: {source}"
        raise ValueError(msg) from error
    return _SOURCE_DEFINITIONS_BY_NAME[source_name]


def iter_builtin_sources() -> tuple[SourceDefinition, ...]:
    """Return built-in source definitions in CLI display order."""
    return SOURCE_DEFINITIONS


def iter_source_backlog() -> tuple[SourceBacklogItem, ...]:
    """Return P2.5 deferred/backlog source candidates in handoff order."""
    return SOURCE_BACKLOG


def source_summaries(*, include_backlog: bool = False) -> list[SourceSummary]:
    """Return JSON-friendly registry rows for built-in and optional backlog sources."""
    rows = [_source_summary(definition) for definition in SOURCE_DEFINITIONS]
    if include_backlog:
        rows.extend(_backlog_summary(item) for item in SOURCE_BACKLOG)
    return rows


def _source_summary(definition: SourceDefinition) -> SourceSummary:
    return SourceSummary(
        name=definition.name.value,
        status="built-in",
        source_kind=definition.source_kind,
        adapter_name=definition.adapter_name,
        family=definition.family,
        source_category=definition.source_category,
        authority_tier=definition.authority_tier,
        detail_capture_mode=definition.detail_capture_mode,
        content_completeness=definition.default_content_completeness,
        readiness_status=definition.readiness_status,
        entry_url=definition.entry_url,
        default_content_depth=definition.default_content_depth,
        defer_reason=definition.defer_reason,
        notes=definition.notes,
        traceability_refs=definition.traceability_refs,
        structured_api_gate=(
            definition.structured_api_readiness.status
            if definition.structured_api_readiness
            else None
        ),
        structured_api_blockers=(
            definition.structured_api_readiness.blockers
            if definition.structured_api_readiness
            else ()
        ),
        structured_api_traceability_refs=(
            definition.structured_api_readiness.traceability_refs
            if definition.structured_api_readiness
            else ()
        ),
    )


def _backlog_summary(item: SourceBacklogItem) -> SourceSummary:
    return SourceSummary(
        name=item.name,
        status="deferred",
        family="backlog",
        source_category=item.source_category,
        authority_tier=item.authority_tier,
        detail_capture_mode=item.detail_capture_mode,
        content_completeness=item.content_completeness,
        readiness_status=item.readiness_status,
        entry_url=item.entry_url,
        bucket=item.bucket,
        defer_reason=item.reason,
        notes=item.reason,
        traceability_refs=item.traceability_refs,
        structured_api_gate=(
            item.structured_api_readiness.status if item.structured_api_readiness else None
        ),
        structured_api_blockers=(
            item.structured_api_readiness.blockers if item.structured_api_readiness else ()
        ),
        structured_api_traceability_refs=(
            item.structured_api_readiness.traceability_refs if item.structured_api_readiness else ()
        ),
    )


def _openai_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    _ignore_raw_cache_root(raw_cache_root)
    return openai_news_adapter(window=window)


def _anthropic_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    web_fetcher = HttpWebFetcher(raw_cache_root=raw_cache_root) if raw_cache_root else None
    return anthropic_news_adapter(window=window, web_fetcher=web_fetcher)


def _huggingface_blog_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    web_fetcher = HttpWebFetcher(raw_cache_root=raw_cache_root) if raw_cache_root else None
    return huggingface_blog_adapter(window=window, web_fetcher=web_fetcher)


def _google_research_blog_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    web_fetcher = HttpWebFetcher(raw_cache_root=raw_cache_root) if raw_cache_root else None
    return google_research_blog_adapter(window=window, web_fetcher=web_fetcher)


def _deepmind_blog_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    _ignore_raw_cache_root(raw_cache_root)
    return deepmind_blog_adapter(window=window)


def _deepseek_news_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    _ignore_raw_cache_root(raw_cache_root)
    return deepseek_news_adapter(window=window)


def _z_ai_blog_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    _ignore_raw_cache_root(raw_cache_root)
    return z_ai_blog_adapter(window=window)


def _moonshot_kimi_changelog_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    _ignore_raw_cache_root(raw_cache_root)
    return moonshot_kimi_changelog_adapter(window=window)


def _bytedance_seed_blog_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    _ignore_raw_cache_root(raw_cache_root)
    return bytedance_seed_blog_adapter(window=window)


def _gemini_api_changelog_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    _ignore_raw_cache_root(raw_cache_root)
    return gemini_api_changelog_adapter(window=window)


def _mistral_news_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    _ignore_raw_cache_root(raw_cache_root)
    return mistral_news_adapter(window=window)


def _microsoft_ai_blog_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    _ignore_raw_cache_root(raw_cache_root)
    return microsoft_ai_blog_adapter(window=window)


def _cohere_blog_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    _ignore_raw_cache_root(raw_cache_root)
    return cohere_blog_adapter(window=window)


def _ignore_raw_cache_root(raw_cache_root: Path | None) -> None:
    _ = raw_cache_root


SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        name=SourceName.OPENAI,
        source_kind="openai-news",
        adapter_name="openai-news-rss",
        family="rss",
        source_category="official",
        detail_capture_mode="summary-only",
        entry_url="https://openai.com/news/rss.xml",
        default_content_depth="summary_only",
        notes="generic RSS remains discovery-grade until a compliant canonical detail path exists",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/openai-news/export/running-codex-safely.json",
        ),
        defer_reason=(
            "OpenAI RSS entries observed in the readiness audit are summary-only, while "
            "unauthenticated canonical detail fetches return a managed browser challenge instead "
            "of stable article HTML. Keep OpenAI out of source-ready counts until an official "
            "structured detail surface or compliant detail-fetch path is available."
        ),
        factory=_openai_adapter,
    ),
    SourceDefinition(
        name=SourceName.ANTHROPIC,
        source_kind="anthropic-news",
        adapter_name="anthropic-news-index",
        family="article-index",
        source_category="official",
        detail_capture_mode="canonical-detail",
        entry_url=ANTHROPIC_NEWS_URL,
        default_content_depth="complete",
        notes="index discovery plus official article detail pages",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/anthropic-news/export/claude-design-anthropic-labs.json",
        ),
        factory=_anthropic_adapter,
    ),
    SourceDefinition(
        name=SourceName.HUGGINGFACE_BLOG,
        source_kind="huggingface-blog",
        adapter_name="huggingface-blog-detail",
        family="rss-detail",
        source_category="official",
        detail_capture_mode="canonical-detail",
        entry_url="https://huggingface.co/blog/feed.xml",
        default_content_depth="complete",
        notes="RSS discovery plus canonical blog detail pages",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/huggingface-blog/export/open-r1.json",
        ),
        factory=_huggingface_blog_adapter,
    ),
    SourceDefinition(
        name=SourceName.GOOGLE_RESEARCH_BLOG,
        source_kind="google-research-blog",
        adapter_name="google-research-blog-detail",
        family="rss-detail",
        source_category="official",
        detail_capture_mode="canonical-detail",
        entry_url="https://research.google/blog/rss/",
        default_content_depth="complete",
        notes="RSS discovery plus canonical blog detail pages",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/google-research-blog/export/catalyzing-scientific-impact.json",
        ),
        factory=_google_research_blog_adapter,
    ),
    SourceDefinition(
        name=SourceName.DEEPMIND_BLOG,
        source_kind="deepmind-blog",
        adapter_name="deepmind-blog-detail",
        family="rss-detail",
        source_category="official",
        detail_capture_mode="canonical-detail",
        entry_url=DEEPMIND_BLOG_RSS_URL,
        default_content_depth="complete",
        notes="RSS discovery plus canonical article detail pages",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/deepmind-blog/export/alphaevolve-impact.json",
        ),
        factory=_deepmind_blog_adapter,
    ),
    SourceDefinition(
        name=SourceName.DEEPSEEK_NEWS,
        source_kind="deepseek-news",
        adapter_name="deepseek-news-article",
        family="article-index",
        source_category="official",
        detail_capture_mode="canonical-detail",
        entry_url=DEEPSEEK_UPDATES_URL,
        default_content_depth="complete",
        notes="official updates page used as discovery index",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/deepseek-news/export/deepseek-v4.json",
        ),
        factory=_deepseek_news_adapter,
    ),
    SourceDefinition(
        name=SourceName.Z_AI_BLOG,
        source_kind="z-ai-blog",
        adapter_name="z-ai-blog-article",
        family="article-index",
        source_category="official",
        detail_capture_mode="canonical-detail",
        entry_url=Z_AI_RELEASE_NOTES_URL,
        default_content_depth="complete",
        notes="release-note discovery plus official blog detail payload",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/z-ai-blog/export/glm-5-1.json",
        ),
        factory=_z_ai_blog_adapter,
    ),
    SourceDefinition(
        name=SourceName.MOONSHOT_KIMI_CHANGELOG,
        source_kind="moonshot-kimi-changelog",
        adapter_name="moonshot-kimi-changelog-page",
        family="changelog",
        source_category="official",
        detail_capture_mode="listing-only",
        entry_url=MOONSHOT_KIMI_CHANGELOG_URL,
        default_content_depth="complete",
        notes="official changelog; downstream should treat as engineering radar by default",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/moonshot-kimi-changelog/export/kimi-k2-think.json",
        ),
        factory=_moonshot_kimi_changelog_adapter,
    ),
    SourceDefinition(
        name=SourceName.BYTEDANCE_SEED_BLOG,
        source_kind="bytedance-seed-blog",
        adapter_name="bytedance-seed-blog-ssr",
        family="ssr-detail",
        source_category="official",
        detail_capture_mode="structured-api",
        entry_url=BYTEDANCE_SEED_BLOG_URL,
        default_content_depth="complete",
        notes="official SSR embedded-data index plus article detail pages",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/bytedance-seed-blog/export/seed3d-2-0.json",
        ),
        structured_api_readiness=StructuredApiReadinessEvidence(
            stable_official_endpoint=True,
            stable_item_ids=True,
            reliable_published_timestamps=True,
            canonical_urls=True,
            complete_payloads=True,
            bounded_fixtures=True,
            repeatable_extraction_tests=True,
            traceability_refs=(
                "tests/adapters/test_adapter_internal_item_contract.py",
                "tests/integration/test_boundary_e2e_export_golden.py",
                "tests/test_source_readiness.py",
            ),
        ),
        factory=_bytedance_seed_blog_adapter,
    ),
    SourceDefinition(
        name=SourceName.GEMINI_API_CHANGELOG,
        source_kind="gemini-api-changelog",
        adapter_name="gemini-api-changelog-page",
        family="changelog",
        source_category="official",
        detail_capture_mode="listing-only",
        entry_url=GEMINI_API_CHANGELOG_URL,
        default_content_depth="complete",
        notes="official changelog; downstream should treat as engineering radar by default",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/gemini-api-changelog/export/2026-05-07.json",
        ),
        factory=_gemini_api_changelog_adapter,
    ),
    SourceDefinition(
        name=SourceName.MISTRAL_NEWS,
        source_kind="mistral-news",
        adapter_name="mistral-news-article",
        family="article-index",
        source_category="official",
        detail_capture_mode="canonical-detail",
        entry_url=MISTRAL_NEWS_URL,
        default_content_depth="complete",
        notes="static news index plus official article detail pages",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/mistral-news/export/vibe-remote-agents.json",
        ),
        factory=_mistral_news_adapter,
    ),
    SourceDefinition(
        name=SourceName.MICROSOFT_AI_BLOG,
        source_kind="microsoft-ai-blog",
        adapter_name="microsoft-ai-blog-rss",
        family="rss",
        source_category="official",
        detail_capture_mode="listing-only",
        entry_url=MICROSOFT_AI_BLOG_FEED_URL,
        default_content_depth="complete",
        notes="WordPress RSS currently carries decision-grade feed content",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/microsoft-ai-blog/export/frontier-transformation-readiness.json",
        ),
        factory=_microsoft_ai_blog_adapter,
    ),
    SourceDefinition(
        name=SourceName.COHERE_BLOG,
        source_kind="cohere-blog",
        adapter_name="cohere-blog-article",
        family="article-index",
        source_category="official",
        detail_capture_mode="canonical-detail",
        entry_url=COHERE_BLOG_URL,
        default_content_depth="complete",
        notes="official blog, but downstream may demote high-level partnership/marketing posts",
        traceability_refs=(
            "docs/SOURCE_STRATEGY.md#built-in-source-status",
            "tests/fixtures/cohere-blog/export/cohere-sovereign-ai-nvidia.json",
        ),
        factory=_cohere_blog_adapter,
    ),
)
BUILTIN_SOURCE_NAMES: tuple[str, ...] = tuple(
    definition.name.value for definition in SOURCE_DEFINITIONS
)
_SOURCE_DEFINITIONS_BY_NAME: dict[SourceName, SourceDefinition] = {
    definition.name: definition for definition in SOURCE_DEFINITIONS
}

SOURCE_BACKLOG: tuple[SourceBacklogItem, ...] = (
    SourceBacklogItem(
        name="qwen-research",
        bucket="p3-json-api-fetcher",
        source_category="official",
        detail_capture_mode="structured-api",
        entry_url="https://qwen.ai/research",
        reason=(
            "official SPA/JSON source; requires generic JSON/API fetcher and fixture-size boundary "
            "before becoming built-in"
        ),
        traceability_refs=("docs/SOURCE_STRATEGY.md#batch-1--official-ai-source-coverage",),
        structured_api_readiness=StructuredApiReadinessEvidence(
            traceability_refs=("docs/SOURCE_STRATEGY.md#batch-1--official-ai-source-coverage",),
        ),
    ),
    SourceBacklogItem(
        name="minimax-news",
        bucket="p3-json-api-fetcher",
        source_category="official",
        detail_capture_mode="structured-api",
        entry_url="https://www.minimax.io/news",
        reason=(
            "official site needs JSON endpoint extraction; HTML/schema dates were unstable "
            "in P2.5 audit"
        ),
        traceability_refs=("docs/SOURCE_STRATEGY.md#batch-1--official-ai-source-coverage",),
        structured_api_readiness=StructuredApiReadinessEvidence(
            traceability_refs=("docs/SOURCE_STRATEGY.md#batch-1--official-ai-source-coverage",),
        ),
    ),
    SourceBacklogItem(
        name="langchain-blog",
        bucket="p3-registry-candidate",
        source_category="official",
        detail_capture_mode="canonical-detail",
        entry_url="https://blog.langchain.com/",
        reason=(
            "tooling ecosystem source; add through declarative registry/readiness gate, "
            "not P2.5 hand-wiring"
        ),
        traceability_refs=("docs/SOURCE_STRATEGY.md#batch-2--ai-tooling-and-agent-ecosystem",),
    ),
    SourceBacklogItem(
        name="llamaindex-blog",
        bucket="p3-registry-candidate",
        source_category="official",
        detail_capture_mode="canonical-detail",
        entry_url="https://www.llamaindex.ai/blog",
        reason="tooling ecosystem source; candidate after source registry/config exists",
        traceability_refs=("docs/SOURCE_STRATEGY.md#batch-2--ai-tooling-and-agent-ecosystem",),
    ),
    SourceBacklogItem(
        name="vercel-ai-sdk",
        bucket="p3-registry-candidate",
        source_category="official",
        detail_capture_mode="canonical-detail",
        entry_url="https://vercel.com/blog",
        reason=(
            "tooling ecosystem source; needs source metadata and noise classification before "
            "default capture"
        ),
        traceability_refs=("docs/SOURCE_STRATEGY.md#batch-2--ai-tooling-and-agent-ecosystem",),
    ),
    SourceBacklogItem(
        name="github-trending-or-community-feeds",
        bucket="later-high-noise",
        source_category="community",
        detail_capture_mode="listing-only",
        entry_url="https://github.com/trending",
        reason="high-noise community signal; defer until higher-noise source policy exists",
        traceability_refs=("docs/SOURCE_STRATEGY.md#batch-3--research-and-community-signals",),
    ),
)
