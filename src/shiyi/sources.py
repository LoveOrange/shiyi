"""Built-in source registry and backlog metadata."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
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
from shiyi.domain.models import CaptureWindow, ContentDepth
from shiyi.fetchers.http import HttpWebFetcher
from shiyi.ports.adapter import Adapter

SourceName = Literal[
    "openai",
    "anthropic",
    "huggingface-blog",
    "google-research-blog",
    "deepmind-blog",
    "deepseek-news",
    "z-ai-blog",
    "moonshot-kimi-changelog",
    "bytedance-seed-blog",
    "gemini-api-changelog",
    "mistral-news",
    "microsoft-ai-blog",
    "cohere-blog",
]
SourceFamily: TypeAlias = Literal[
    "rss",
    "article-index",
    "rss-detail",
    "changelog",
    "ssr-detail",
]
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
    entry_url: str
    default_content_depth: ContentDepth
    source_ready: bool
    notes: str
    factory: SourceAdapterFactory = field(repr=False, compare=False)

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
    entry_url: str
    reason: str


@dataclass(frozen=True, slots=True)
class SourceSummary:
    """JSON-friendly source registry row for CLI/status output."""

    name: str
    status: SourceStatus
    family: str
    entry_url: str
    source_kind: str | None = None
    adapter_name: str | None = None
    default_content_depth: str | None = None
    source_ready: bool | None = None
    bucket: str | None = None
    notes: str | None = None


def build_source_adapter(
    source: SourceName,
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    """Build a registered built-in source adapter."""
    return source_definition(source).create_adapter(window=window, raw_cache_root=raw_cache_root)


def source_definition(source: SourceName) -> SourceDefinition:
    """Return one built-in source definition by source name."""
    try:
        return _SOURCE_DEFINITIONS_BY_NAME[source]
    except KeyError as error:
        msg = f"unknown source: {source}"
        raise ValueError(msg) from error


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
        name=definition.name,
        status="built-in",
        source_kind=definition.source_kind,
        adapter_name=definition.adapter_name,
        family=definition.family,
        entry_url=definition.entry_url,
        default_content_depth=definition.default_content_depth,
        source_ready=definition.source_ready,
        notes=definition.notes,
    )


def _backlog_summary(item: SourceBacklogItem) -> SourceSummary:
    return SourceSummary(
        name=item.name,
        status="deferred",
        family="backlog",
        entry_url=item.entry_url,
        bucket=item.bucket,
        notes=item.reason,
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
    _ignore_raw_cache_root(raw_cache_root)
    return huggingface_blog_adapter(window=window)


def _google_research_blog_adapter(
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> Adapter:
    _ignore_raw_cache_root(raw_cache_root)
    return google_research_blog_adapter(window=window)


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


def _source_names(definitions: Iterable[SourceDefinition]) -> tuple[SourceName, ...]:
    return tuple(definition.name for definition in definitions)


SOURCE_DEFINITIONS: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        name="openai",
        source_kind="openai-news",
        adapter_name="openai-news-rss",
        family="rss",
        entry_url="https://openai.com/news/rss.xml",
        default_content_depth="summary_only",
        source_ready=False,
        notes="generic RSS; discovery-grade unless feed content carries full body",
        factory=_openai_adapter,
    ),
    SourceDefinition(
        name="anthropic",
        source_kind="anthropic-news",
        adapter_name="anthropic-news-index",
        family="article-index",
        entry_url=ANTHROPIC_NEWS_URL,
        default_content_depth="full_page",
        source_ready=True,
        notes="index discovery plus official article detail pages",
        factory=_anthropic_adapter,
    ),
    SourceDefinition(
        name="huggingface-blog",
        source_kind="huggingface-blog",
        adapter_name="huggingface-blog-rss",
        family="rss",
        entry_url="https://huggingface.co/blog/feed.xml",
        default_content_depth="summary_only",
        source_ready=False,
        notes="generic RSS; candidate for P3 declarative RSS config",
        factory=_huggingface_blog_adapter,
    ),
    SourceDefinition(
        name="google-research-blog",
        source_kind="google-research-blog",
        adapter_name="google-research-blog-rss",
        family="rss",
        entry_url="https://research.google/blog/rss/",
        default_content_depth="summary_only",
        source_ready=False,
        notes="generic RSS; candidate for P3 declarative RSS config",
        factory=_google_research_blog_adapter,
    ),
    SourceDefinition(
        name="deepmind-blog",
        source_kind="deepmind-blog",
        adapter_name="deepmind-blog-detail",
        family="rss-detail",
        entry_url=DEEPMIND_BLOG_RSS_URL,
        default_content_depth="full_page",
        source_ready=True,
        notes="RSS discovery plus canonical article detail pages",
        factory=_deepmind_blog_adapter,
    ),
    SourceDefinition(
        name="deepseek-news",
        source_kind="deepseek-news",
        adapter_name="deepseek-news-article",
        family="article-index",
        entry_url=DEEPSEEK_UPDATES_URL,
        default_content_depth="full_page",
        source_ready=True,
        notes="official updates page used as discovery index",
        factory=_deepseek_news_adapter,
    ),
    SourceDefinition(
        name="z-ai-blog",
        source_kind="z-ai-blog",
        adapter_name="z-ai-blog-article",
        family="article-index",
        entry_url=Z_AI_RELEASE_NOTES_URL,
        default_content_depth="full_page",
        source_ready=True,
        notes="release-note discovery plus official blog detail payload",
        factory=_z_ai_blog_adapter,
    ),
    SourceDefinition(
        name="moonshot-kimi-changelog",
        source_kind="moonshot-kimi-changelog",
        adapter_name="moonshot-kimi-changelog-page",
        family="changelog",
        entry_url=MOONSHOT_KIMI_CHANGELOG_URL,
        default_content_depth="feed_full_content",
        source_ready=True,
        notes="official changelog; downstream should treat as engineering radar by default",
        factory=_moonshot_kimi_changelog_adapter,
    ),
    SourceDefinition(
        name="bytedance-seed-blog",
        source_kind="bytedance-seed-blog",
        adapter_name="bytedance-seed-blog-ssr",
        family="ssr-detail",
        entry_url=BYTEDANCE_SEED_BLOG_URL,
        default_content_depth="full_page",
        source_ready=True,
        notes="official SSR embedded-data index plus article detail pages",
        factory=_bytedance_seed_blog_adapter,
    ),
    SourceDefinition(
        name="gemini-api-changelog",
        source_kind="gemini-api-changelog",
        adapter_name="gemini-api-changelog-page",
        family="changelog",
        entry_url=GEMINI_API_CHANGELOG_URL,
        default_content_depth="feed_full_content",
        source_ready=True,
        notes="official changelog; downstream should treat as engineering radar by default",
        factory=_gemini_api_changelog_adapter,
    ),
    SourceDefinition(
        name="mistral-news",
        source_kind="mistral-news",
        adapter_name="mistral-news-article",
        family="article-index",
        entry_url=MISTRAL_NEWS_URL,
        default_content_depth="full_page",
        source_ready=True,
        notes="static news index plus official article detail pages",
        factory=_mistral_news_adapter,
    ),
    SourceDefinition(
        name="microsoft-ai-blog",
        source_kind="microsoft-ai-blog",
        adapter_name="microsoft-ai-blog-rss",
        family="rss",
        entry_url=MICROSOFT_AI_BLOG_FEED_URL,
        default_content_depth="feed_full_content",
        source_ready=True,
        notes="WordPress RSS currently carries decision-grade feed content",
        factory=_microsoft_ai_blog_adapter,
    ),
    SourceDefinition(
        name="cohere-blog",
        source_kind="cohere-blog",
        adapter_name="cohere-blog-article",
        family="article-index",
        entry_url=COHERE_BLOG_URL,
        default_content_depth="full_page",
        source_ready=True,
        notes="official blog, but downstream may demote high-level partnership/marketing posts",
        factory=_cohere_blog_adapter,
    ),
)
BUILTIN_SOURCE_NAMES: tuple[SourceName, ...] = _source_names(SOURCE_DEFINITIONS)
_SOURCE_DEFINITIONS_BY_NAME: dict[SourceName, SourceDefinition] = {
    definition.name: definition for definition in SOURCE_DEFINITIONS
}

SOURCE_BACKLOG: tuple[SourceBacklogItem, ...] = (
    SourceBacklogItem(
        name="qwen-research",
        bucket="p3-json-api-fetcher",
        entry_url="https://qwen.ai/research",
        reason=(
            "official SPA/JSON source; requires generic JSON/API fetcher and fixture-size boundary "
            "before becoming built-in"
        ),
    ),
    SourceBacklogItem(
        name="minimax-news",
        bucket="p3-json-api-fetcher",
        entry_url="https://www.minimax.io/news",
        reason=(
            "official site needs JSON endpoint extraction; HTML/schema dates were unstable "
            "in P2.5 audit"
        ),
    ),
    SourceBacklogItem(
        name="langchain-blog",
        bucket="p3-registry-candidate",
        entry_url="https://blog.langchain.com/",
        reason=(
            "tooling ecosystem source; add through declarative registry/readiness gate, "
            "not P2.5 hand-wiring"
        ),
    ),
    SourceBacklogItem(
        name="llamaindex-blog",
        bucket="p3-registry-candidate",
        entry_url="https://www.llamaindex.ai/blog",
        reason="tooling ecosystem source; candidate after source registry/config exists",
    ),
    SourceBacklogItem(
        name="vercel-ai-sdk",
        bucket="p3-registry-candidate",
        entry_url="https://vercel.com/blog",
        reason=(
            "tooling ecosystem source; needs source metadata and noise classification before "
            "default capture"
        ),
    ),
    SourceBacklogItem(
        name="github-trending-or-community-feeds",
        bucket="later-high-noise",
        entry_url="https://github.com/trending",
        reason="high-noise community signal; defer until higher-noise source policy exists",
    ),
)
