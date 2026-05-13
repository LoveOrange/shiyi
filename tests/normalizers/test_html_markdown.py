import asyncio
from datetime import UTC, datetime

from shiyi.domain.models import (
    HtmlPayload,
    InternalItem,
    Provenance,
    SourceIdentity,
    TextPayload,
    payload_content_hash,
)
from shiyi.normalizers.html import HtmlMarkdownNormalizer


def test_html_markdown_normalizer_extracts_article_markdown() -> None:
    normalizer = HtmlMarkdownNormalizer()
    payload = HtmlPayload(
        html="<html><body><article><h1>Hello</h1><p>World</p></article></body></html>"
    )
    event = InternalItem(
        id="evt_1",
        source=SourceIdentity(kind="blog"),
        captured_at=datetime(2026, 5, 12, tzinfo=UTC),
        occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
        payload=payload,
        content_hash=payload_content_hash(payload),
        provenance=Provenance(
            adapter_name="test",
            adapter_version="0.1.0",
            fetched_at=datetime(2026, 5, 12, tzinfo=UTC),
        ),
        idempotency_key="blog:evt_1",
    )

    artifact = asyncio.run(normalizer.normalize(event))

    assert artifact is not None
    assert artifact.kind == "normalized"
    assert artifact.media_type == "text/markdown"
    assert b"# Hello" in artifact.content
    assert b"World" in artifact.content


def test_html_markdown_normalizer_ignores_non_html_payloads() -> None:
    normalizer = HtmlMarkdownNormalizer()
    payload = TextPayload(text="hello")
    event = InternalItem(
        id="evt_1",
        source=SourceIdentity(kind="blog"),
        captured_at=datetime(2026, 5, 12, tzinfo=UTC),
        occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
        payload=payload,
        content_hash=payload_content_hash(payload),
        provenance=Provenance(
            adapter_name="test",
            adapter_version="0.1.0",
            fetched_at=datetime(2026, 5, 12, tzinfo=UTC),
        ),
        idempotency_key="blog:evt_1",
    )

    assert asyncio.run(normalizer.normalize(event)) is None
