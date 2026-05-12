import json
import sqlite3
from pathlib import Path

from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

from shiyi.cli import CaptureSummary, SourceName, _capture_summary, _format_summary, main


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

    async def fake_run_capture(
        *,
        source: SourceName,
        workspace: Path,
        limit: int,
    ) -> CaptureSummary:
        assert source == "openai"
        assert workspace == tmp_path
        assert limit == 1
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

    main(["capture", "--source", "openai", "--workspace", str(tmp_path), "--limit", "1"])

    payload = json.loads(capsys.readouterr().out)
    assert payload["processed"] == 1
    assert payload["artifacts"] == expected_artifacts
