import asyncio
from datetime import UTC, datetime

from shiyi.domain.models import CaptureEvent, HtmlPayload, Provenance, SourceIdentity, TextPayload
from shiyi.normalizers.html import HtmlMarkdownNormalizer


def test_html_markdown_normalizer_extracts_article_markdown() -> None:
    normalizer = HtmlMarkdownNormalizer()
    event = CaptureEvent(
        id="evt_1",
        source=SourceIdentity(kind="blog"),
        occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
        payload=HtmlPayload(
            html="<html><body><article><h1>Hello</h1><p>World</p></article></body></html>"
        ),
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
    event = CaptureEvent(
        id="evt_1",
        source=SourceIdentity(kind="blog"),
        occurred_at=datetime(2026, 5, 12, tzinfo=UTC),
        payload=TextPayload(text="hello"),
        provenance=Provenance(
            adapter_name="test",
            adapter_version="0.1.0",
            fetched_at=datetime(2026, 5, 12, tzinfo=UTC),
        ),
        idempotency_key="blog:evt_1",
    )

    assert asyncio.run(normalizer.normalize(event)) is None
