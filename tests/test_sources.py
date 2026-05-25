from dataclasses import fields
from pathlib import Path
from typing import get_args

import pytest

from shiyi import (
    BUILTIN_SOURCE_NAMES,
    SOURCE_BACKLOG,
    Adapter,
    AuthorityTier,
    ContentCompleteness,
    ContentDepth,
    SourceCategory,
    SourceDefinition,
    SourceName,
    StructuredApiReadinessEvidence,
    build_source_adapter,
    iter_builtin_sources,
    source_definition,
    source_summaries,
)
from shiyi.domain.models import CaptureWindow


def test_source_registry_covers_builtin_source_name_enum() -> None:
    assert tuple(source.value for source in SourceName) == BUILTIN_SOURCE_NAMES
    assert tuple(source.name.value for source in iter_builtin_sources()) == BUILTIN_SOURCE_NAMES


def test_source_registry_builds_adapter_without_cli_branching() -> None:
    adapter = build_source_adapter(
        "microsoft-ai-blog",
        window=CaptureWindow(max_items=1),
    )

    assert adapter.name == "microsoft-ai-blog-rss"
    assert source_definition("microsoft-ai-blog").source_kind == "microsoft-ai-blog"


def test_source_registry_summaries_expose_builtin_metadata_without_factories() -> None:
    summaries = source_summaries()

    microsoft = next(summary for summary in summaries if summary.name == "microsoft-ai-blog")
    openai = next(summary for summary in summaries if summary.name == "openai")
    huggingface = next(summary for summary in summaries if summary.name == "huggingface-blog")
    google_research = next(
        summary for summary in summaries if summary.name == "google-research-blog"
    )
    bytedance = next(summary for summary in summaries if summary.name == "bytedance-seed-blog")
    assert microsoft.status == "built-in"
    assert microsoft.source_category == "official"
    assert microsoft.detail_capture_mode == "listing-only"
    assert microsoft.content_completeness == "complete"
    assert microsoft.readiness_status == "ready"
    assert microsoft.default_content_depth == "complete"
    assert microsoft.source_ready is True
    assert microsoft.counts_as_official_source_ready is True
    assert openai.source_ready is False
    assert openai.detail_capture_mode == "summary-only"
    assert openai.content_completeness == "summary_only"
    assert openai.readiness_status == "degraded"
    assert openai.counts_as_official_source_ready is False
    assert openai.default_content_depth == "summary_only"
    assert openai.defer_reason is not None
    assert "canonical detail" in openai.defer_reason
    assert huggingface.source_category == "official"
    assert huggingface.detail_capture_mode == "canonical-detail"
    assert huggingface.content_completeness == "complete"
    assert huggingface.readiness_status == "ready"
    assert huggingface.default_content_depth == "complete"
    assert huggingface.source_ready is True
    assert huggingface.defer_reason is None
    assert huggingface.counts_as_official_source_ready is True
    assert google_research.detail_capture_mode == "canonical-detail"
    assert google_research.readiness_status == "ready"
    assert google_research.default_content_depth == "complete"
    assert google_research.source_ready is True
    assert google_research.defer_reason is None
    assert bytedance.detail_capture_mode == "structured-api"
    assert bytedance.structured_api_gate == "ready"
    assert bytedance.structured_api_blockers == ()
    assert bytedance.structured_api_traceability_refs
    assert all(summary.defer_reason for summary in summaries if summary.source_ready is False)
    assert all(summary.traceability_refs for summary in summaries)
    assert all(not hasattr(summary, "factory") for summary in summaries)


def test_source_registry_handoff_backlog_separates_deferred_sources() -> None:
    summaries = source_summaries(include_backlog=True)

    assert {item.name for item in SOURCE_BACKLOG} <= {summary.name for summary in summaries}
    qwen = next(summary for summary in summaries if summary.name == "qwen-research")
    community = next(
        summary for summary in summaries if summary.name == "github-trending-or-community-feeds"
    )
    assert qwen.status == "deferred"
    assert qwen.bucket == "p3-json-api-fetcher"
    assert qwen.source_category == "official"
    assert qwen.detail_capture_mode == "structured-api"
    assert qwen.content_completeness is None
    assert qwen.readiness_status == "deferred"
    assert qwen.source_ready is False
    assert qwen.counts_as_official_source_ready is False
    assert qwen.defer_reason == qwen.notes
    assert qwen.traceability_refs
    assert qwen.structured_api_gate == "blocked"
    assert set(qwen.structured_api_blockers) == {
        "stable_official_endpoint",
        "stable_item_ids",
        "reliable_published_timestamps",
        "canonical_urls",
        "complete_payloads",
        "bounded_fixtures",
        "repeatable_extraction_tests",
    }
    assert community.source_category == "community"
    assert community.detail_capture_mode == "listing-only"
    assert community.content_completeness is None
    assert community.readiness_status == "deferred"
    assert community.bucket == "later-high-noise"
    assert community.source_ready is False
    assert community.counts_as_official_source_ready is False


def test_source_registry_readiness_contract_covers_review_states() -> None:
    summaries = {summary.name: summary for summary in source_summaries(include_backlog=True)}

    assert summaries["huggingface-blog"].readiness_status == "ready"
    assert summaries["openai"].readiness_status == "degraded"
    assert summaries["qwen-research"].readiness_status == "deferred"
    assert summaries["huggingface-blog"].content_completeness == "complete"
    assert summaries["openai"].content_completeness == "summary_only"
    assert summaries["qwen-research"].content_completeness is None
    assert summaries["microsoft-ai-blog"].detail_capture_mode == "listing-only"
    assert summaries["google-research-blog"].detail_capture_mode == "canonical-detail"
    assert summaries["bytedance-seed-blog"].detail_capture_mode == "structured-api"
    assert summaries["bytedance-seed-blog"].structured_api_gate == "ready"
    assert summaries["qwen-research"].structured_api_gate == "blocked"


def test_source_registry_uses_minimal_taxonomies_and_derived_readiness() -> None:
    source_definition_fields = {field.name for field in fields(SourceDefinition)}

    assert get_args(ContentDepth) == ("complete", "partial", "summary_only")
    assert get_args(ContentCompleteness) == ("complete", "partial", "summary_only")
    assert get_args(SourceCategory) == ("official", "community", "social_media")
    assert get_args(AuthorityTier) == ("primary", "secondary", "unverified")
    assert "readiness_status" not in source_definition_fields
    assert "source_ready" not in source_definition_fields
    assert "counts_as_official_source_ready" not in source_definition_fields


def test_high_noise_community_backlog_never_counts_as_official_source_ready() -> None:
    summaries = source_summaries(include_backlog=True)

    official_coverage_names = {
        summary.name for summary in summaries if summary.counts_as_official_source_ready
    }
    assert "github-trending-or-community-feeds" not in official_coverage_names
    assert "qwen-research" not in official_coverage_names
    assert "openai" not in official_coverage_names
    assert all(
        not summary.counts_as_official_source_ready
        for summary in summaries
        if summary.source_category == "community" or summary.bucket == "later-high-noise"
    )
    assert {"huggingface-blog", "google-research-blog"} <= official_coverage_names


def test_source_registry_rejects_unknown_source() -> None:
    with pytest.raises(ValueError, match="unknown source"):
        source_definition("not-a-source")


def test_structured_api_builtins_must_pass_readiness_gate() -> None:
    def factory(*, window: CaptureWindow | None, raw_cache_root: Path | None = None) -> Adapter:
        _ = window, raw_cache_root
        msg = "factory should not be called by source definition validation"
        raise AssertionError(msg)

    with pytest.raises(ValueError, match="structured-api built-in source must pass"):
        SourceDefinition(
            name=SourceName.BYTEDANCE_SEED_BLOG,
            source_kind="example-structured",
            adapter_name="example-structured",
            family="ssr-detail",
            source_category="official",
            detail_capture_mode="structured-api",
            entry_url="https://example.com",
            default_content_depth="complete",
            notes="invalid structured gate",
            traceability_refs=("tests/test_sources.py",),
            factory=factory,
            structured_api_readiness=StructuredApiReadinessEvidence(
                stable_official_endpoint=True,
                traceability_refs=("tests/test_sources.py",),
            ),
        )
