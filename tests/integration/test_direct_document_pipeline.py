import asyncio
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from shiyi import (
    CaptureConfig,
    CaptureRunner,
    FileSystemBlobStore,
    MarkdownContentProcessor,
    MemoryContentItemStore,
    Source,
)
from shiyi.adapters.document import DirectDocumentAdapter
from shiyi.fetchers.fake import FakeWebFetcher
from shiyi.ports.fetcher import FetchResult

NOW = datetime(2026, 8, 9, tzinfo=UTC)


def test_pdf_document_pipeline_is_idempotent_and_retains_original_blob(tmp_path: Path) -> None:
    url = "https://example.com/system-card.pdf"
    pdf = _text_pdf()
    source = Source(
        id="system-card",
        adapter="direct-document",
        target=url,
        options={
            "content_kind": "system_card",
            "document_format": "pdf",
            "published_at": "2026-08-04T00:00:00Z",
        },
    )
    adapter = DirectDocumentAdapter(
        web_fetcher=FakeWebFetcher(
            {
                url: FetchResult(
                    url=url,
                    status_code=200,
                    content="",
                    body=pdf,
                    content_type="application/pdf",
                    fetched_at=NOW,
                )
            }
        )
    )
    store = MemoryContentItemStore()
    blobs = FileSystemBlobStore(tmp_path / "blobs")
    runner = CaptureRunner(
        config=CaptureConfig(sources=(source,)),
        adapters=(adapter,),
        processor=MarkdownContentProcessor(clock=lambda: NOW),
        content_store=store,
        blob_store=blobs,
        clock=lambda: NOW,
    )

    first = asyncio.run(runner.run_once())
    second = asyncio.run(runner.run_once())
    [item] = store.items.values()

    assert first.processed == 1
    assert second.skipped == 1
    assert len(store.items) == 1
    assert item.ready_at == NOW
    assert item.raw_ref is not None
    assert item.raw_ref.media_type == "application/pdf"
    assert asyncio.run(blobs.get(item.raw_ref)) == pdf


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
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref})}
    )
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 72 720 Td (System card evidence) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(content)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()
