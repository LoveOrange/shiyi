import asyncio
import json
from hashlib import sha256
from pathlib import Path

import pytest

from shiyi.fetchers.fake import FakeWebFetcher
from shiyi.fetchers.snapshot import OperatorSnapshotWebFetcher


def test_operator_snapshot_fetcher_verifies_and_returns_exact_mapped_bytes(
    tmp_path: Path,
) -> None:
    url = "https://example.com/article/"
    content = b"<!doctype html><html><body>official snapshot</body></html>"
    snapshot_path = tmp_path / "article.html"
    snapshot_path.write_bytes(content)
    manifest_path = _manifest(tmp_path, url=url, digest=sha256(content).hexdigest())
    fallback = FakeWebFetcher({})
    fetcher = OperatorSnapshotWebFetcher.from_manifest(manifest_path, fallback=fallback)

    result = asyncio.run(fetcher.fetch(url, source="official", raw_key="raw-key"))

    assert result.body == content
    assert result.content_type == "text/html; charset=utf-8"
    assert result.from_cache is True
    assert result.raw_cache_path == snapshot_path
    assert fallback.calls == []


def test_operator_snapshot_fetcher_delegates_unmapped_urls(tmp_path: Path) -> None:
    mapped_url = "https://example.com/article/"
    ordinary_url = "https://example.com/ordinary"
    content = b"snapshot"
    (tmp_path / "article.html").write_bytes(content)
    manifest_path = _manifest(tmp_path, url=mapped_url, digest=sha256(content).hexdigest())
    fallback = FakeWebFetcher({ordinary_url: "ordinary content"})
    fetcher = OperatorSnapshotWebFetcher.from_manifest(manifest_path, fallback=fallback)

    result = asyncio.run(fetcher.fetch(ordinary_url, source="ordinary", raw_key="key"))

    assert result.content == "ordinary content"
    assert fallback.calls[0].source == "ordinary"
    assert fallback.calls[0].raw_key == "key"


def test_operator_snapshot_fetcher_fails_if_bytes_change_after_manifest_load(
    tmp_path: Path,
) -> None:
    url = "https://example.com/article/"
    snapshot_path = tmp_path / "article.html"
    snapshot_path.write_bytes(b"approved bytes")
    manifest_path = _manifest(
        tmp_path,
        url=url,
        digest=sha256(b"approved bytes").hexdigest(),
    )
    fetcher = OperatorSnapshotWebFetcher.from_manifest(
        manifest_path,
        fallback=FakeWebFetcher({}),
    )
    snapshot_path.write_bytes(b"changed bytes")

    with pytest.raises(ValueError, match="hash mismatch"):
        asyncio.run(fetcher.fetch(url))


def test_operator_snapshot_manifest_rejects_paths_outside_its_directory(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / "outside.html"
    outside.write_bytes(b"outside")
    manifest = {
        "schemaVersion": "shiyi-operator-snapshot-manifest.v1",
        "contentReviewRequired": True,
        "snapshots": [
            {
                "url": "https://example.com/article/",
                "path": "../outside.html",
                "sha256": sha256(b"outside").hexdigest(),
                "contentType": "text/html",
                "acquiredAt": "2026-08-16T00:00:00Z",
            }
        ],
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="escapes"):
        OperatorSnapshotWebFetcher.from_manifest(manifest_path, fallback=FakeWebFetcher({}))


def _manifest(tmp_path: Path, *, url: str, digest: str) -> Path:
    manifest = {
        "schemaVersion": "shiyi-operator-snapshot-manifest.v1",
        "contentReviewRequired": True,
        "snapshots": [
            {
                "url": url,
                "path": "article.html",
                "sha256": digest,
                "contentType": "text/html; charset=utf-8",
                "acquiredAt": "2026-08-16T00:00:00Z",
            }
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest))
    return path
