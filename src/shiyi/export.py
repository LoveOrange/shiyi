"""Minimal upstream read/export helpers for local Shiyi workspaces."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from shiyi._time import utc_isoformat
from shiyi.domain.models import ArtifactRef, SourceIdentity, StrictModel

DEFAULT_EXPORT_LIMIT = 20


class ExportedItem(StrictModel):
    """Standardized upstream view of one persisted capture item."""

    schema_version: Literal["shiyi-export-item.v1"] = "shiyi-export-item.v1"
    event_id: str
    idempotency_key: str
    status: str
    source: SourceIdentity | None
    captured_at: str | None
    content_hash: str | None
    adapter_name: str | None
    adapter_version: str | None
    normalized_artifact_uri: str | None = None
    normalized_media_type: str | None = None
    normalized_content: str | None = Field(default=None)


def export_items(
    *,
    workspace: Path,
    since: datetime | None = None,
    until: datetime | None = None,
    sources: Sequence[str] = (),
    limit: int = DEFAULT_EXPORT_LIMIT,
) -> list[ExportedItem]:
    """Read persisted normalized items for upstream consumers.

    The MVP reads from the local SQLite event ledger plus normalized artifact files.
    Time filters use a half-open captured_at window: since is inclusive and until is
    exclusive. Default ordering is captured_at descending, with event_id ascending as
    the deterministic tie-breaker. It intentionally returns Shiyi's canonical trace +
    normalized content, not third-party adapter DTOs.
    """
    if limit <= 0:
        return []

    metadata_path = workspace / "event-records.sqlite"
    artifacts_root = workspace / "artifacts"
    if not metadata_path.exists():
        return []

    rows = _read_rows(metadata_path=metadata_path, since=since, until=until)
    source_filter = set(sources)
    exported: list[ExportedItem] = []
    for row in rows:
        source = _source_from_json(row["source_json"])
        if source_filter and (source is None or source.kind not in source_filter):
            continue
        normalized_ref = _artifact_from_json(row["normalized_artifact_json"])
        exported.append(
            ExportedItem(
                event_id=str(row["event_id"]),
                idempotency_key=str(row["idempotency_key"]),
                status=str(row["status"]),
                source=source,
                captured_at=row["captured_at"],
                content_hash=row["content_hash"],
                adapter_name=row["adapter_name"],
                adapter_version=row["adapter_version"],
                normalized_artifact_uri=normalized_ref.uri if normalized_ref else None,
                normalized_media_type=normalized_ref.media_type if normalized_ref else None,
                normalized_content=_read_artifact_text(artifacts_root, normalized_ref),
            )
        )
        if len(exported) >= limit:
            break
    return exported


def _read_rows(
    *, metadata_path: Path, since: datetime | None, until: datetime | None
) -> list[sqlite3.Row]:
    params: list[str] = []
    if since is not None:
        params.append(utc_isoformat(since))
    if until is not None:
        params.append(utc_isoformat(until))

    query = _export_query(has_since=since is not None, has_until=until is not None)
    with sqlite3.connect(metadata_path) as connection:
        connection.row_factory = sqlite3.Row
        return list(connection.execute(query, params).fetchall())


def _export_query(*, has_since: bool, has_until: bool) -> str:
    if has_since and has_until:
        return """
            SELECT event_id, idempotency_key, status, normalized_artifact_json,
                   source_json, captured_at, content_hash, adapter_name, adapter_version
            FROM events
            WHERE normalized_artifact_json IS NOT NULL
              AND captured_at >= ? AND captured_at < ?
            ORDER BY captured_at DESC, event_id ASC
        """
    if has_since:
        return """
            SELECT event_id, idempotency_key, status, normalized_artifact_json,
                   source_json, captured_at, content_hash, adapter_name, adapter_version
            FROM events
            WHERE normalized_artifact_json IS NOT NULL
              AND captured_at >= ?
            ORDER BY captured_at DESC, event_id ASC
        """
    if has_until:
        return """
            SELECT event_id, idempotency_key, status, normalized_artifact_json,
                   source_json, captured_at, content_hash, adapter_name, adapter_version
            FROM events
            WHERE normalized_artifact_json IS NOT NULL
              AND captured_at < ?
            ORDER BY captured_at DESC, event_id ASC
        """
    return """
        SELECT event_id, idempotency_key, status, normalized_artifact_json,
               source_json, captured_at, content_hash, adapter_name, adapter_version
        FROM events
        WHERE normalized_artifact_json IS NOT NULL
        ORDER BY captured_at DESC, event_id ASC
    """


def _artifact_from_json(value: str | None) -> ArtifactRef | None:
    if value is None:
        return None
    return ArtifactRef.model_validate_json(value)


def _source_from_json(value: str | None) -> SourceIdentity | None:
    if value is None:
        return None
    return SourceIdentity.model_validate_json(value)


def _read_artifact_text(root: Path, ref: ArtifactRef | None) -> str | None:
    if ref is None:
        return None
    path = (root / ref.uri).resolve()
    root_path = root.resolve()
    if not path.is_relative_to(root_path):
        msg = f"artifact reference escapes store root: {ref.uri}"
        raise ValueError(msg)
    return path.read_text()
