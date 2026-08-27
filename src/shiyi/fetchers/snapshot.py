"""Operator-supplied, hash-verified snapshots for bounded capture exceptions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import HttpUrl, TypeAdapter

from shiyi.ports.fetcher import FetchResult, WebFetcher

OPERATOR_SNAPSHOT_MANIFEST_SCHEMA = "shiyi-operator-snapshot-manifest.v1"
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_HTTP_URL = TypeAdapter(HttpUrl)


@dataclass(frozen=True, slots=True)
class _Snapshot:
    url: str
    path: Path
    sha256: str
    content_type: str
    acquired_at: datetime


class OperatorSnapshotWebFetcher:
    """Resolve explicitly mapped snapshots before delegating ordinary HTTP fetches."""

    def __init__(
        self,
        *,
        snapshots: dict[str, _Snapshot],
        fallback: WebFetcher,
    ) -> None:
        """Create a fetcher from already validated exact-URL mappings."""
        self._snapshots = snapshots
        self._fallback = fallback

    @classmethod
    def from_manifest(
        cls,
        manifest_path: Path,
        *,
        fallback: WebFetcher,
    ) -> OperatorSnapshotWebFetcher:
        """Load an operator manifest and fail closed on malformed provenance."""
        return cls(snapshots=_load_manifest(manifest_path), fallback=fallback)

    async def fetch(
        self,
        url: str,
        *,
        source: str | None = None,
        raw_key: str | None = None,
    ) -> FetchResult:
        """Return a verified snapshot for an exact URL or use the ordinary fetcher."""
        snapshot = self._snapshots.get(_http_url(url))
        if snapshot is None:
            return await self._fallback.fetch(url, source=source, raw_key=raw_key)

        body = snapshot.path.read_bytes()
        actual_sha256 = sha256(body).hexdigest()
        if actual_sha256 != snapshot.sha256:
            msg = (
                f"operator snapshot hash mismatch for {snapshot.url}: "
                f"expected {snapshot.sha256}, got {actual_sha256}"
            )
            raise ValueError(msg)
        return FetchResult(
            url=snapshot.url,
            status_code=200,
            content=body.decode("utf-8"),
            body=body,
            content_type=snapshot.content_type,
            fetched_at=snapshot.acquired_at,
            from_cache=True,
            raw_cache_path=snapshot.path,
        )


def _load_manifest(manifest_path: Path) -> dict[str, _Snapshot]:
    manifest = _json_object(manifest_path)
    if manifest.get("schemaVersion") != OPERATOR_SNAPSHOT_MANIFEST_SCHEMA:
        msg = f"unsupported operator snapshot manifest schema in {manifest_path}"
        raise ValueError(msg)
    if manifest.get("contentReviewRequired") is not True:
        msg = "operator snapshot manifest must retain contentReviewRequired: true"
        raise ValueError(msg)
    snapshots = manifest.get("snapshots")
    if not isinstance(snapshots, list) or not snapshots:
        msg = "operator snapshot manifest snapshots must be a non-empty list"
        raise ValueError(msg)

    root = manifest_path.resolve().parent
    resolved: dict[str, _Snapshot] = {}
    for index, raw_snapshot in enumerate(snapshots):
        if not isinstance(raw_snapshot, dict):
            msg = f"operator snapshot manifest entry {index} must be an object"
            raise TypeError(msg)
        snapshot = _snapshot(raw_snapshot, root=root, index=index)
        if snapshot.url in resolved:
            msg = f"duplicate operator snapshot URL: {snapshot.url}"
            raise ValueError(msg)
        resolved[snapshot.url] = snapshot
    return resolved


def _snapshot(raw: dict[str, Any], *, root: Path, index: int) -> _Snapshot:
    url = _http_url(_required_text(raw, "url", index=index))
    raw_path = Path(_required_text(raw, "path", index=index))
    if raw_path.is_absolute():
        msg = f"operator snapshot entry {index} path must be relative"
        raise ValueError(msg)
    path = (root / raw_path).resolve()
    if not path.is_relative_to(root):
        msg = f"operator snapshot entry {index} path escapes the manifest directory"
        raise ValueError(msg)
    if not path.is_file():
        msg = f"operator snapshot entry {index} file does not exist: {raw_path}"
        raise ValueError(msg)

    expected_sha256 = _required_text(raw, "sha256", index=index).lower()
    if _SHA256_PATTERN.fullmatch(expected_sha256) is None:
        msg = f"operator snapshot entry {index} sha256 must be 64 lowercase hex characters"
        raise ValueError(msg)
    content_type = _required_text(raw, "contentType", index=index)
    acquired_at = _datetime(_required_text(raw, "acquiredAt", index=index), index=index)
    return _Snapshot(
        url=url,
        path=path,
        sha256=expected_sha256,
        content_type=content_type,
        acquired_at=acquired_at,
    )


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        msg = f"operator snapshot manifest must be a JSON object: {path}"
        raise TypeError(msg)
    return value


def _required_text(raw: dict[str, Any], key: str, *, index: int) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        msg = f"operator snapshot entry {index} field {key!r} must be a non-empty string"
        raise ValueError(msg)
    return value.strip()


def _datetime(value: str, *, index: int) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        msg = f"operator snapshot entry {index} acquiredAt must be an ISO-8601 timestamp"
        raise ValueError(msg) from error
    if parsed.tzinfo is None:
        msg = f"operator snapshot entry {index} acquiredAt must include a timezone"
        raise ValueError(msg)
    return parsed.astimezone(UTC)


def _http_url(value: str) -> str:
    return str(_HTTP_URL.validate_python(value))
