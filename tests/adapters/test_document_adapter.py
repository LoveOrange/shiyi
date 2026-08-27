import asyncio
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from shiyi.adapters.document import DirectDocumentAdapter
from shiyi.domain.models import CaptureWindow, Source, SourceItem
from shiyi.fetchers.fake import FakeWebFetcher
from shiyi.ports.fetcher import FetchResult

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "direct-document" / "raw"
FETCHED_AT = datetime(2026, 8, 9, 8, 30, tzinfo=UTC)


def test_direct_html_document_preserves_source_metadata() -> None:
    url = "https://example.com/research/direct-document"
    adapter = DirectDocumentAdapter(
        web_fetcher=FakeWebFetcher({url: (FIXTURE_ROOT / "article.html").read_text()})
    )

    [item] = asyncio.run(_collect(adapter, _source(url=url, document_format="html")))

    assert item.source_item_id == "https://example.com/research/direct-document"
    assert str(item.canonical_url) == "https://example.com/research/direct-document"
    assert item.published_at == datetime(2026, 8, 3, 7, tzinfo=UTC)
    assert item.summary == "An official description for deterministic capture."
    assert item.metadata == {
        "title": "Direct document capture",
        "is_complete": True,
        "language": "en",
        "author": "Example Research",
    }
    assert item.payload.type == "html"
    assert item.raw_content is None


def test_direct_html_document_can_preserve_an_operator_declared_canonical_url() -> None:
    requested_url = "https://example.com/article/"
    localized_url = "https://example.com/zh/article/"
    html = (
        "<html lang='zh'><head><title>本地化文章</title>"
        f"<link rel='canonical' href='{localized_url}'></head>"
        "<body><main><h1>本地化文章</h1><p>正文</p></main></body></html>"
    )
    adapter = DirectDocumentAdapter(web_fetcher=FakeWebFetcher({requested_url: html}))
    source = _source(
        url=requested_url,
        document_format="html",
        options={"canonical_url": requested_url},
    )

    [item] = asyncio.run(_collect(adapter, source))

    assert item.source_item_id == requested_url.rstrip("/")
    assert str(item.canonical_url) == requested_url.rstrip("/")
    assert item.metadata["language"] == "zh"


def test_direct_markdown_document_uses_heading_as_title() -> None:
    url = "https://example.com/guide.md"
    adapter = DirectDocumentAdapter(
        web_fetcher=FakeWebFetcher({url: (FIXTURE_ROOT / "guide.md").read_text()})
    )

    [item] = asyncio.run(_collect(adapter, _source(url=url, document_format="markdown")))

    assert item.source_item_id == url
    assert item.metadata["title"] == "Direct Markdown guide"
    assert item.payload.type == "text"
    assert item.payload.content_type == "text/markdown"


def test_direct_pdf_document_extracts_text_and_preserves_original_bytes() -> None:
    url = "https://example.com/system-card.pdf"
    pdf = _text_pdf()
    adapter = DirectDocumentAdapter(
        web_fetcher=FakeWebFetcher(
            {
                url: FetchResult(
                    url=url,
                    status_code=200,
                    content="",
                    body=pdf,
                    content_type="application/pdf",
                    fetched_at=FETCHED_AT,
                )
            }
        )
    )
    source = _source(
        url=url,
        document_format="pdf",
        options={
            "title": "GPT-Live System Card",
            "published_at": "2026-08-04T00:00:00Z",
        },
    )

    [item] = asyncio.run(_collect(adapter, source))

    assert item.published_at == datetime(2026, 8, 4, tzinfo=UTC)
    assert item.payload.type == "text"
    assert "corrected August 4" in item.payload.text
    assert item.raw_content == pdf
    assert item.raw_media_type == "application/pdf"


def test_direct_document_rejects_unexpected_content_type() -> None:
    url = "https://example.com/system-card.pdf"
    adapter = DirectDocumentAdapter(
        web_fetcher=FakeWebFetcher(
            {
                url: FetchResult(
                    url=url,
                    status_code=200,
                    content="blocked",
                    body=b"blocked",
                    content_type="text/html",
                    fetched_at=FETCHED_AT,
                )
            }
        )
    )

    with pytest.raises(ValueError, match="expected pdf document"):
        asyncio.run(_collect(adapter, _source(url=url, document_format="pdf")))


def test_direct_document_respects_capture_window() -> None:
    url = "https://example.com/guide.md"
    adapter = DirectDocumentAdapter(
        web_fetcher=FakeWebFetcher({url: (FIXTURE_ROOT / "guide.md").read_text()}),
        window=CaptureWindow(since=datetime(2026, 8, 1, tzinfo=UTC)),
    )

    items = asyncio.run(_collect(adapter, _source(url=url, document_format="markdown")))

    assert items == []


async def _collect(adapter: DirectDocumentAdapter, source: Source) -> list[SourceItem]:
    return [item async for item in adapter.capture(source)]


def _source(
    *,
    url: str,
    document_format: str,
    options: dict[str, str] | None = None,
) -> Source:
    return Source(
        id="direct-document-test",
        adapter="direct-document",
        target=url,
        options={
            "content_kind": "document",
            "document_format": document_format,
            **(options or {}),
        },
    )


def _text_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
        }
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (GPT-Live System Card corrected August 4) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    writer.add_metadata({"/Title": "GPT-Live System Card"})
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
