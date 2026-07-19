import asyncio
from pathlib import Path

import pytest

from shiyi import BlobRef, FileSystemBlobStore


def test_filesystem_blob_store_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    store = FileSystemBlobStore(tmp_path)

    first = asyncio.run(store.put(b"hello", media_type="text/plain"))
    second = asyncio.run(store.put(b"hello", media_type="text/plain"))

    assert first == second
    assert asyncio.run(store.get(first)) == b"hello"
    assert asyncio.run(store.exists(first)) is True
    assert len(list(tmp_path.rglob(first.sha256))) == 1


def test_filesystem_blob_store_rejects_a_different_store() -> None:
    store = FileSystemBlobStore(Path("unused"))
    ref = BlobRef(
        store="cos",
        key="raw/key",
        sha256="a" * 64,
        media_type="text/html",
        size=1,
    )

    with pytest.raises(ValueError, match="belongs to"):
        asyncio.run(store.get(ref))
