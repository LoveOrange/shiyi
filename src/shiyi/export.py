"""Minimal upstream read/export helpers for local Shiyi workspaces."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import Field, model_validator

from shiyi._time import utc_isoformat
from shiyi.domain.models import (
    ArtifactRef,
    ContentCompleteness,
    ContentDepth,
    SourceIdentity,
    SourceType,
    StrictModel,
    content_completeness_from_depth,
    is_item_ready_content_completeness,
)
from shiyi.enrichments.hacker_news_external import external_target_enrichment_from_metadata
from shiyi.sources import SourceCategory, iter_builtin_sources

DEFAULT_EXPORT_LIMIT = 20


class ExportedItem(StrictModel):
    """Standardized upstream view of one persisted capture item."""

    schema_version: Literal["shiyi-export-item.v1"] = "shiyi-export-item.v1"
    event_id: str
    idempotency_key: str
    status: str
    source: SourceIdentity | None
    source_category: SourceCategory | None = None
    source_type: SourceType = "unknown"
    upstream_id: str | None = None
    upstream_parent_id: str | None = None
    canonical_discussion_url: str | None = None
    external_target_url: str | None = None
    external_target_enrichment: dict[str, Any] | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    source_metrics: dict[str, int | float] = Field(default_factory=dict)
    captured_at: str | None
    occurred_at: str | None = None
    published_at: str | None = None
    content_hash: str | None
    adapter_name: str | None
    adapter_version: str | None
    content_depth: ContentDepth | None = None
    content_completeness: ContentCompleteness | None = None
    source_ready: bool = False
    normalized_artifact_uri: str | None = None
    normalized_media_type: str | None = None
    normalized_content: str | None = Field(default=None)

    @model_validator(mode="before")
    @classmethod
    def derive_readiness_labels(cls, data: object) -> object:
        """Derive item readiness labels from content depth to avoid split truth."""
        if not isinstance(data, dict):
            return data
        content_depth = cast(str | None, data.get("content_depth"))
        content_completeness = content_completeness_from_depth(content_depth)
        supplied_completeness = cast(str | None, data.get("content_completeness"))
        if supplied_completeness is not None and supplied_completeness != content_completeness:
            msg = (
                "content_completeness must be derived from content_depth: "
                f"{supplied_completeness!r} != {content_completeness!r}"
            )
            raise ValueError(msg)
        source_ready = is_item_ready_content_completeness(content_completeness)
        supplied_source_ready = data.get("source_ready")
        if supplied_source_ready is not None and supplied_source_ready != source_ready:
            msg = (
                "source_ready must be derived from content_completeness: "
                f"{supplied_source_ready!r} != {source_ready!r}"
            )
            raise ValueError(msg)
        return {
            **data,
            "content_completeness": content_completeness,
            "source_ready": source_ready,
        }


def export_items(  # noqa: PLR0913
    *,
    workspace: Path,
    since: datetime | None = None,
    until: datetime | None = None,
    sources: Sequence[str] = (),
    limit: int = DEFAULT_EXPORT_LIMIT,
    source_ready_only: bool = False,
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
        metadata = _metadata_from_json(row["metadata_json"])
        normalized_ref = _artifact_from_json(row["normalized_artifact_json"])
        content_depth = row["content_depth"]
        content_completeness = content_completeness_from_depth(content_depth)
        source_ready = is_item_ready_content_completeness(content_completeness)
        if source_ready_only and not source_ready:
            continue
        exported.append(
            ExportedItem(
                event_id=str(row["event_id"]),
                idempotency_key=str(row["idempotency_key"]),
                status=str(row["status"]),
                source=source,
                source_category=_source_category_for_source(source),
                source_type=_source_type_for_source(source),
                upstream_id=_string_metadata(metadata, "upstream_id"),
                upstream_parent_id=_string_metadata(metadata, "upstream_parent_id"),
                canonical_discussion_url=_string_metadata(metadata, "canonical_discussion_url"),
                external_target_url=_string_metadata(metadata, "external_target_url"),
                external_target_enrichment=_external_target_enrichment_from_metadata(metadata),
                source_metrics=_source_metrics_from_metadata(metadata),
                captured_at=row["captured_at"],
                occurred_at=row["occurred_at"],
                published_at=row["occurred_at"],
                content_hash=row["content_hash"],
                adapter_name=row["adapter_name"],
                adapter_version=row["adapter_version"],
                content_depth=content_depth,
                content_completeness=content_completeness,
                source_ready=source_ready,
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
        _ensure_export_columns(connection)
        return list(connection.execute(query, params).fetchall())


def _export_query(*, has_since: bool, has_until: bool) -> str:
    if has_since and has_until:
        return """
            SELECT event_id, idempotency_key, status, normalized_artifact_json,
                   source_json, captured_at, occurred_at, content_hash,
                   adapter_name, adapter_version, content_depth, metadata_json
            FROM events
            WHERE normalized_artifact_json IS NOT NULL
              AND captured_at >= ? AND captured_at < ?
            ORDER BY captured_at DESC, event_id ASC
        """
    if has_since:
        return """
            SELECT event_id, idempotency_key, status, normalized_artifact_json,
                   source_json, captured_at, occurred_at, content_hash,
                   adapter_name, adapter_version, content_depth, metadata_json
            FROM events
            WHERE normalized_artifact_json IS NOT NULL
              AND captured_at >= ?
            ORDER BY captured_at DESC, event_id ASC
        """
    if has_until:
        return """
            SELECT event_id, idempotency_key, status, normalized_artifact_json,
                   source_json, captured_at, occurred_at, content_hash,
                   adapter_name, adapter_version, content_depth, metadata_json
            FROM events
            WHERE normalized_artifact_json IS NOT NULL
              AND captured_at < ?
            ORDER BY captured_at DESC, event_id ASC
        """
    return """
        SELECT event_id, idempotency_key, status, normalized_artifact_json,
               source_json, captured_at, occurred_at, content_hash,
               adapter_name, adapter_version, content_depth, metadata_json
        FROM events
        WHERE normalized_artifact_json IS NOT NULL
        ORDER BY captured_at DESC, event_id ASC
    """


def _ensure_export_columns(connection: sqlite3.Connection) -> None:
    columns = {row[1] for row in connection.execute("PRAGMA table_info(events)")}
    if "content_depth" not in columns:
        connection.execute("ALTER TABLE events ADD COLUMN content_depth TEXT")
    if "occurred_at" not in columns:
        connection.execute("ALTER TABLE events ADD COLUMN occurred_at TEXT")
    if "metadata_json" not in columns:
        connection.execute("ALTER TABLE events ADD COLUMN metadata_json TEXT")


def _artifact_from_json(value: str | None) -> ArtifactRef | None:
    if value is None:
        return None
    return ArtifactRef.model_validate_json(value)


def _source_from_json(value: str | None) -> SourceIdentity | None:
    if value is None:
        return None
    return SourceIdentity.model_validate_json(value)


def _metadata_from_json(value: str | None) -> dict[str, Any]:
    if value is None:
        return {}
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        msg = "event metadata must decode to a JSON object"
        raise TypeError(msg)
    return decoded


def _string_metadata(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    return str(value)


def _source_metrics_from_metadata(metadata: dict[str, Any]) -> dict[str, int | float]:
    value = metadata.get("source_metrics")
    if not isinstance(value, dict):
        return {}
    return {
        str(key): metric
        for key, metric in value.items()
        if isinstance(metric, int | float) and not isinstance(metric, bool)
    }


def _external_target_enrichment_from_metadata(metadata: dict[str, Any]) -> dict[str, Any] | None:
    enrichment = external_target_enrichment_from_metadata(metadata)
    if enrichment is None:
        return None
    return enrichment.model_dump(mode="json")


def _source_type_for_source(source: SourceIdentity | None) -> SourceType:
    if source is None:
        return "unknown"
    return _SOURCE_TYPES_BY_IDENTITY.get(source.kind, "unknown")


def _source_category_for_source(source: SourceIdentity | None) -> SourceCategory | None:
    if source is None:
        return None
    return _SOURCE_CATEGORIES_BY_IDENTITY.get(source.kind)


_SOURCE_TYPES_BY_IDENTITY: dict[str, SourceType] = {
    identity: definition.source_type
    for definition in iter_builtin_sources()
    for identity in (definition.name.value, definition.source_kind)
}
_SOURCE_CATEGORIES_BY_IDENTITY: dict[str, SourceCategory] = {
    identity: definition.source_category
    for definition in iter_builtin_sources()
    for identity in (definition.name.value, definition.source_kind)
}


def _read_artifact_text(root: Path, ref: ArtifactRef | None) -> str | None:
    if ref is None:
        return None
    path = (root / ref.uri).resolve()
    root_path = root.resolve()
    if not path.is_relative_to(root_path):
        msg = f"artifact reference escapes store root: {ref.uri}"
        raise ValueError(msg)
    return path.read_text()
