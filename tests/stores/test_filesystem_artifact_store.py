import asyncio
from pathlib import Path

import pytest

from shiyi.domain.models import ArtifactRef, ArtifactWrite
from shiyi.stores.filesystem import FileSystemArtifactStore


@pytest.mark.parametrize("content", [b"hello", b"<html>hello</html>"])
def test_filesystem_artifact_store_round_trip(tmp_path: Path, content: bytes) -> None:
    store = FileSystemArtifactStore(tmp_path)
    artifact = ArtifactWrite(kind="raw", media_type="text/plain", content=content)

    ref = asyncio.run(store.put(artifact))
    read = asyncio.run(store.get(ref))

    assert read.content == content
    assert asyncio.run(store.exists(ref))


def test_filesystem_artifact_store_rejects_path_escape(tmp_path: Path) -> None:
    store = FileSystemArtifactStore(tmp_path)
    ref = ArtifactRef(
        uri="../escape",
        kind="raw",
        media_type="text/plain",
        size_bytes=0,
        sha256="abc",
    )

    with pytest.raises(ValueError, match="escapes store root"):
        asyncio.run(store.exists(ref))
