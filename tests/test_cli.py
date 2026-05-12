import json
import sqlite3
from pathlib import Path

from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from shiyi.cli import (
    CaptureSummary,
    SourceName,
    _capture_summary,
    _format_summary,
    list_events,
    main,
)


def test_format_summary_outputs_json_line() -> None:
    expected_processed = 2
    expected_enrichments = 4
    summary = CaptureSummary(
        source="openai",
        workspace=".shiyi/openai",
        processed=expected_processed,
        total_events=2,
        enriched_events=2,
        enrichments=expected_enrichments,
        artifacts=8,
    )

    payload = json.loads(_format_summary(summary))

    assert payload["source"] == "openai"
    assert payload["processed"] == expected_processed
    assert payload["enrichments"] == expected_enrichments


def test_capture_summary_reads_sqlite_and_artifact_counts(tmp_path: Path) -> None:
    expected_total_events = 2
    expected_enrichments = 2
    artifacts_root = tmp_path / "artifacts" / "raw" / "ab"
    artifacts_root.mkdir(parents=True)
    (artifacts_root / "abc").write_text("hello")
    with sqlite3.connect(tmp_path / "metadata.sqlite") as connection:
        connection.executescript(
            """
            CREATE TABLE events (status TEXT NOT NULL);
            CREATE TABLE enrichments (id INTEGER PRIMARY KEY AUTOINCREMENT);
            INSERT INTO events (status) VALUES ('enriched'), ('persisted');
            INSERT INTO enrichments DEFAULT VALUES;
            INSERT INTO enrichments DEFAULT VALUES;
            """
        )

    summary = _capture_summary(source="anthropic", workspace=tmp_path, processed=1)

    assert summary.total_events == expected_total_events
    assert summary.enriched_events == 1
    assert summary.enrichments == expected_enrichments
    assert summary.artifacts == 1


def test_main_capture_prints_summary(
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    expected_artifacts = 3

    async def fake_run_capture(  # noqa: PLR0913
        *,
        source: SourceName,
        workspace: Path,
        limit: int | None,
        max_items: int | None = None,
        since: object | None = None,
        until: object | None = None,
    ) -> CaptureSummary:
        assert source == "openai"
        assert workspace == tmp_path
        assert limit is None
        assert max_items == 1
        assert since is not None
        assert until is not None
        return CaptureSummary(
            source="openai",
            workspace=str(workspace),
            processed=1,
            total_events=1,
            enriched_events=1,
            enrichments=2,
            artifacts=expected_artifacts,
        )

    monkeypatch.setattr("shiyi.cli.run_capture", fake_run_capture)

    main(
        [
            "capture",
            "--source",
            "openai",
            "--workspace",
            str(tmp_path),
            "--max-items",
            "1",
            "--since",
            "2026-05-12",
            "--until",
            "2026-05-13",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert payload["processed"] == 1
    assert payload["artifacts"] == expected_artifacts


def test_list_events_reads_sqlite_rows(tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "metadata.sqlite") as connection:
        connection.executescript(
            """
            CREATE TABLE events (
              event_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL,
              status TEXT NOT NULL,
              raw_artifact_json TEXT,
              normalized_artifact_json TEXT,
              updated_at TEXT NOT NULL
            );
            INSERT INTO events (
              event_id, idempotency_key, status, raw_artifact_json,
              normalized_artifact_json, updated_at
            ) VALUES (
              'evt_1', 'source:evt_1', 'enriched', '{}', '{}', '2026-05-12T00:00:00Z'
            );
            """
        )

    events = list_events(workspace=tmp_path, limit=10)

    assert len(events) == 1
    assert events[0].event_id == "evt_1"
    assert events[0].has_raw_artifact
    assert events[0].has_normalized_artifact


def test_main_list_prints_event_summaries(capsys: CaptureFixture[str], tmp_path: Path) -> None:
    with sqlite3.connect(tmp_path / "metadata.sqlite") as connection:
        connection.executescript(
            """
            CREATE TABLE events (
              event_id TEXT NOT NULL,
              idempotency_key TEXT NOT NULL,
              status TEXT NOT NULL,
              raw_artifact_json TEXT,
              normalized_artifact_json TEXT,
              updated_at TEXT NOT NULL
            );
            INSERT INTO events (
              event_id, idempotency_key, status, raw_artifact_json,
              normalized_artifact_json, updated_at
            ) VALUES (
              'evt_1', 'source:evt_1', 'enriched', '{}', NULL, '2026-05-12T00:00:00Z'
            );
            """
        )

    main(["list", "--workspace", str(tmp_path)])

    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["event_id"] == "evt_1"
    assert payload[0]["has_normalized_artifact"] is False
