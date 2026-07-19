"""Briefly-first built-in CaptureConfig and SourceAdapter composition."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

from shiyi.adapters.anthropic import ANTHROPIC_NEWS_URL, anthropic_news_adapter
from shiyi.adapters.bytedance_seed import BYTEDANCE_SEED_BLOG_URL, bytedance_seed_blog_adapter
from shiyi.adapters.changelog import (
    COHERE_BLOG_URL,
    CURSOR_CHANGELOG_URL,
    DEEPSEEK_UPDATES_URL,
    GEMINI_API_CHANGELOG_URL,
    MISTRAL_NEWS_URL,
    MOONSHOT_KIMI_CHANGELOG_URL,
    Z_AI_RELEASE_NOTES_URL,
    cohere_blog_adapter,
    cursor_changelog_adapter,
    deepseek_news_adapter,
    gemini_api_changelog_adapter,
    mistral_news_adapter,
    moonshot_kimi_changelog_adapter,
    z_ai_blog_adapter,
)
from shiyi.adapters.deepmind import DEEPMIND_BLOG_RSS_URL, deepmind_blog_adapter
from shiyi.adapters.hacker_news import HACKER_NEWS_TOP_STORIES_URL, hacker_news_topstories_adapter
from shiyi.adapters.rss import (
    GITHUB_COPILOT_CHANGELOG_FEED_URL,
    MICROSOFT_AI_BLOG_FEED_URL,
    github_copilot_changelog_adapter,
    google_research_blog_adapter,
    huggingface_blog_adapter,
    microsoft_ai_blog_adapter,
    openai_news_adapter,
)
from shiyi.domain.models import CaptureConfig, CaptureWindow, Source
from shiyi.fetchers.http import HttpWebFetcher
from shiyi.ports.source_adapter import SourceAdapter


class SourceName(StrEnum):
    """User-facing names for built-in Briefly sources."""

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
    CURSOR_CHANGELOG = "cursor-changelog"
    GITHUB_COPILOT_CHANGELOG = "github-copilot-changelog"
    HACKER_NEWS = "hacker-news"


AdapterFactory = Callable[[CaptureWindow | None, Path | None], SourceAdapter]


@dataclass(frozen=True, slots=True)
class BuiltinSource:
    """One declarative source plus its MVP composition-time adapter factory."""

    name: SourceName
    source: Source
    description: str
    factory: AdapterFactory


@dataclass(frozen=True, slots=True)
class SourceSummary:
    """Small JSON-friendly view used by the CLI."""

    name: str
    id: str
    adapter: str
    target: str
    enabled: bool
    content_kind: str
    description: str


def builtin_source(name: SourceName | str) -> BuiltinSource:
    """Return a built-in source definition by user-facing name."""
    try:
        source_name = name if isinstance(name, SourceName) else SourceName(name)
    except ValueError as error:
        msg = f"unknown source: {name}"
        raise ValueError(msg) from error
    return _BUILTIN_BY_NAME[source_name]


def build_capture_config(names: Sequence[SourceName | str]) -> CaptureConfig:
    """Build one declarative config from selected built-in sources."""
    return CaptureConfig(sources=tuple(builtin_source(name).source for name in names))


def build_source_adapters(
    config: CaptureConfig,
    *,
    window: CaptureWindow | None,
    raw_cache_root: Path | None = None,
) -> tuple[SourceAdapter, ...]:
    """Compose the unique adapter implementations required by a config."""
    adapters: dict[str, SourceAdapter] = {}
    for source in config.sources:
        definition = _BUILTIN_BY_ID.get(source.id)
        if definition is None:
            msg = f"no built-in adapter factory for Source {source.id!r}"
            raise ValueError(msg)
        adapter = definition.factory(window, raw_cache_root)
        if adapter.name != source.adapter:
            msg = (
                f"Source {source.id!r} selects adapter {source.adapter!r}, "
                f"factory produced {adapter.name!r}"
            )
            raise ValueError(msg)
        adapters.setdefault(adapter.name, adapter)
    return tuple(adapters.values())


def source_summaries() -> list[SourceSummary]:
    """Return concise configured-source metadata without planning backlog state."""
    return [
        SourceSummary(
            name=definition.name.value,
            id=definition.source.id,
            adapter=definition.source.adapter,
            target=definition.source.target,
            enabled=definition.source.enabled,
            content_kind=str(definition.source.options["content_kind"]),
            description=definition.description,
        )
        for definition in BUILTIN_SOURCES
    ]


def source_summary_dicts() -> list[dict[str, object]]:
    """Return JSON-ready source summaries."""
    return [asdict(summary) for summary in source_summaries()]


def _factory(
    builder: Callable[..., SourceAdapter],
    *,
    use_raw_cache: bool = False,
) -> AdapterFactory:
    def create(window: CaptureWindow | None, raw_cache_root: Path | None) -> SourceAdapter:
        if use_raw_cache and raw_cache_root is not None:
            return builder(window=window, web_fetcher=HttpWebFetcher(raw_cache_root=raw_cache_root))
        return builder(window=window)

    return create


BUILTIN_SOURCES: tuple[BuiltinSource, ...] = (
    BuiltinSource(
        name=SourceName.OPENAI,
        source=Source(
            id="openai-news",
            adapter="openai-news-rss",
            target="https://openai.com/news/rss.xml",
            options={"content_kind": "article"},
        ),
        description="OpenAI official news RSS",
        factory=_factory(openai_news_adapter),
    ),
    BuiltinSource(
        name=SourceName.ANTHROPIC,
        source=Source(
            id="anthropic-news",
            adapter="anthropic-news-index",
            target=ANTHROPIC_NEWS_URL,
            options={"content_kind": "article"},
        ),
        description="Anthropic official news index and article details",
        factory=_factory(anthropic_news_adapter, use_raw_cache=True),
    ),
    BuiltinSource(
        name=SourceName.HUGGINGFACE_BLOG,
        source=Source(
            id="huggingface-blog",
            adapter="huggingface-blog-detail",
            target="https://huggingface.co/blog/feed.xml",
            options={"content_kind": "article"},
        ),
        description="Hugging Face official blog",
        factory=_factory(huggingface_blog_adapter, use_raw_cache=True),
    ),
    BuiltinSource(
        name=SourceName.GOOGLE_RESEARCH_BLOG,
        source=Source(
            id="google-research-blog",
            adapter="google-research-blog-detail",
            target="https://research.google/blog/rss/",
            options={"content_kind": "article"},
        ),
        description="Google Research official blog",
        factory=_factory(google_research_blog_adapter, use_raw_cache=True),
    ),
    BuiltinSource(
        name=SourceName.DEEPMIND_BLOG,
        source=Source(
            id="deepmind-blog",
            adapter="deepmind-blog-detail",
            target=DEEPMIND_BLOG_RSS_URL,
            options={"content_kind": "article"},
        ),
        description="Google DeepMind official blog",
        factory=_factory(deepmind_blog_adapter),
    ),
    BuiltinSource(
        name=SourceName.DEEPSEEK_NEWS,
        source=Source(
            id="deepseek-news",
            adapter="deepseek-news-article",
            target=DEEPSEEK_UPDATES_URL,
            options={"content_kind": "article"},
        ),
        description="DeepSeek official updates and article details",
        factory=_factory(deepseek_news_adapter),
    ),
    BuiltinSource(
        name=SourceName.Z_AI_BLOG,
        source=Source(
            id="z-ai-blog",
            adapter="z-ai-blog-article",
            target=Z_AI_RELEASE_NOTES_URL,
            options={"content_kind": "article"},
        ),
        description="Z.ai release notes and blog details",
        factory=_factory(z_ai_blog_adapter),
    ),
    BuiltinSource(
        name=SourceName.MOONSHOT_KIMI_CHANGELOG,
        source=Source(
            id="moonshot-kimi-changelog",
            adapter="moonshot-kimi-changelog-page",
            target=MOONSHOT_KIMI_CHANGELOG_URL,
            options={"content_kind": "release_note"},
        ),
        description="Moonshot Kimi official changelog",
        factory=_factory(moonshot_kimi_changelog_adapter),
    ),
    BuiltinSource(
        name=SourceName.BYTEDANCE_SEED_BLOG,
        source=Source(
            id="bytedance-seed-blog",
            adapter="bytedance-seed-blog-ssr",
            target=BYTEDANCE_SEED_BLOG_URL,
            options={"content_kind": "article"},
        ),
        description="ByteDance Seed official blog",
        factory=_factory(bytedance_seed_blog_adapter),
    ),
    BuiltinSource(
        name=SourceName.GEMINI_API_CHANGELOG,
        source=Source(
            id="gemini-api-changelog",
            adapter="gemini-api-changelog-page",
            target=GEMINI_API_CHANGELOG_URL,
            options={"content_kind": "release_note"},
        ),
        description="Gemini API official changelog",
        factory=_factory(gemini_api_changelog_adapter),
    ),
    BuiltinSource(
        name=SourceName.MISTRAL_NEWS,
        source=Source(
            id="mistral-news",
            adapter="mistral-news-article",
            target=MISTRAL_NEWS_URL,
            options={"content_kind": "article"},
        ),
        description="Mistral official news",
        factory=_factory(mistral_news_adapter),
    ),
    BuiltinSource(
        name=SourceName.MICROSOFT_AI_BLOG,
        source=Source(
            id="microsoft-ai-blog",
            adapter="microsoft-ai-blog-rss",
            target=MICROSOFT_AI_BLOG_FEED_URL,
            options={"content_kind": "article"},
        ),
        description="Microsoft AI official blog RSS",
        factory=_factory(microsoft_ai_blog_adapter),
    ),
    BuiltinSource(
        name=SourceName.COHERE_BLOG,
        source=Source(
            id="cohere-blog",
            adapter="cohere-blog-article",
            target=COHERE_BLOG_URL,
            options={"content_kind": "article"},
        ),
        description="Cohere official blog",
        factory=_factory(cohere_blog_adapter),
    ),
    BuiltinSource(
        name=SourceName.CURSOR_CHANGELOG,
        source=Source(
            id="cursor-changelog",
            adapter="cursor-changelog-page",
            target=CURSOR_CHANGELOG_URL,
            options={"content_kind": "release_note"},
        ),
        description="Cursor official changelog",
        factory=_factory(cursor_changelog_adapter, use_raw_cache=True),
    ),
    BuiltinSource(
        name=SourceName.GITHUB_COPILOT_CHANGELOG,
        source=Source(
            id="github-copilot-changelog",
            adapter="github-copilot-changelog-rss",
            target=GITHUB_COPILOT_CHANGELOG_FEED_URL,
            options={"content_kind": "release_note"},
        ),
        description="GitHub Copilot official changelog",
        factory=_factory(github_copilot_changelog_adapter),
    ),
    BuiltinSource(
        name=SourceName.HACKER_NEWS,
        source=Source(
            id="hacker-news",
            adapter="hacker-news-topstories-api",
            target=HACKER_NEWS_TOP_STORIES_URL,
            options={"content_kind": "forum_thread"},
        ),
        description="Hacker News public top stories",
        factory=_factory(hacker_news_topstories_adapter),
    ),
)

BUILTIN_SOURCE_NAMES: tuple[str, ...] = tuple(source.name.value for source in BUILTIN_SOURCES)
_BUILTIN_BY_NAME = {source.name: source for source in BUILTIN_SOURCES}
_BUILTIN_BY_ID = {source.source.id: source for source in BUILTIN_SOURCES}
