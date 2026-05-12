"""SQLite-backed event record store."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from shiyi.domain.models import ArtifactRef, CaptureEvent, EnrichmentResult, EventRecord


class SQLiteEventRecordStore:
    """Stores event processing records and enrichment references in SQLite."""

    name = "sqlite-event-record-store"

    def __init__(self, path: Path) -> None:
        """Create an event record store backed by a SQLite database path."""
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    async def find_by_idempotency_key(self, idempotency_key: str) -> EventRecord | None:
        """Find an event record by idempotency key."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT event_id, idempotency_key, status, raw_artifact_json,
                       normalized_artifact_json, last_error
                FROM events
                WHERE idempotency_key = ?
                """,
                (idempotency_key,),
            ).fetchone()
        if row is None:
            return None
        return _row_to_event_record(row)

    async def save_event(
        self,
        event: CaptureEvent,
        *,
        raw_artifact: ArtifactRef | None,
        normalized_artifact: ArtifactRef | None,
    ) -> EventRecord:
        """Create or update an event processing record."""
        now = _utc_now()
        raw_json = raw_artifact.model_dump_json() if raw_artifact else None
        normalized_json = normalized_artifact.model_dump_json() if normalized_artifact else None
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO events (
                  event_id, idempotency_key, status, raw_artifact_json,
                  normalized_artifact_json, last_error, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                  event_id = excluded.event_id,
                  status = excluded.status,
                  raw_artifact_json = excluded.raw_artifact_json,
                  normalized_artifact_json = excluded.normalized_artifact_json,
                  last_error = excluded.last_error,
                  updated_at = excluded.updated_at
                """,
                (
                    event.id,
                    event.idempotency_key,
                    "persisted",
                    raw_json,
                    normalized_json,
                    None,
                    now,
                    now,
                ),
            )
        record = await self.find_by_idempotency_key(event.idempotency_key)
        if record is None:
            msg = "event record was not persisted"
            raise RuntimeError(msg)
        return record

    async def save_enrichment(
        self,
        event: CaptureEvent,
        result: EnrichmentResult,
        artifact: ArtifactRef,
    ) -> EventRecord:
        """Record a validated enrichment result without marking the event complete."""
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO enrichments (
                  event_id, task_type, artifact_json, model_json, created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event.id,
                    result.task_type,
                    artifact.model_dump_json(),
                    result.model.model_dump_json(),
                    now,
                ),
            )
        record = await self.find_by_idempotency_key(event.idempotency_key)
        if record is None:
            msg = "event record was not found after enrichment"
            raise RuntimeError(msg)
        return record

    async def mark_enriched(self, event: CaptureEvent) -> EventRecord:
        """Mark an event fully enriched after all configured tasks succeed."""
        now = _utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE events
                SET status = ?, updated_at = ?
                WHERE idempotency_key = ?
                """,
                ("enriched", now, event.idempotency_key),
            )
        record = await self.find_by_idempotency_key(event.idempotency_key)
        if record is None:
            msg = "event record was not found after marking enriched"
            raise RuntimeError(msg)
        return record

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  event_id TEXT NOT NULL,
                  idempotency_key TEXT NOT NULL UNIQUE,
                  status TEXT NOT NULL,
                  raw_artifact_json TEXT,
                  normalized_artifact_json TEXT,
                  last_error TEXT,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS enrichments (
                  id INTEGER PRIMARY KEY AUTOINCREMENT,
                  event_id TEXT NOT NULL,
                  task_type TEXT NOT NULL,
                  artifact_json TEXT NOT NULL,
                  model_json TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        return connection


def _row_to_event_record(row: sqlite3.Row) -> EventRecord:
    raw_artifact = _artifact_from_json(row["raw_artifact_json"])
    normalized_artifact = _artifact_from_json(row["normalized_artifact_json"])
    return EventRecord(
        event_id=row["event_id"],
        idempotency_key=row["idempotency_key"],
        status=row["status"],
        raw_artifact=raw_artifact,
        normalized_artifact=normalized_artifact,
        last_error=row["last_error"],
    )


def _artifact_from_json(value: str | None) -> ArtifactRef | None:
    if value is None:
        return None
    return ArtifactRef.model_validate_json(value)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()
