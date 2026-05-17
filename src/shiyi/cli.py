"""Command-line entry point for local Shiyi capture runs."""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from shiyi.domain.models import (
    CaptureWindow,
    ClassifyTask,
    EnrichmentResult,
    EnrichmentTask,
    InternalItem,
    ModelIdentity,
    SummarizeTask,
)
from shiyi.export import export_items
from shiyi.normalizers.html import HtmlMarkdownNormalizer
from shiyi.pipeline.runner import CapturePipeline, PipelineRunSummary
from shiyi.sources import BUILTIN_SOURCE_NAMES, SourceName, build_source_adapter, source_summaries
from shiyi.stores.filesystem import FileSystemArtifactStore
from shiyi.stores.sqlite import SQLiteEventRecordStore

DATE_ONLY_LENGTH = 10


@dataclass(frozen=True, slots=True)
class CaptureSummary:
    """Human and machine-readable capture run summary."""

    source: str
    workspace: str
    processed: int
    total_events: int
    enriched_events: int
    enrichments: int
    artifacts: int
    skipped: int = 0
    failed: int = 0
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EventSummary:
    """Compact processing-record summary for one captured record."""

    event_id: str
    idempotency_key: str
    status: str
    updated_at: str
    has_raw_artifact: bool
    has_normalized_artifact: bool


class LocalHeuristicAIProvider:
    """Deterministic local enrichment provider for MVP capture smoke runs."""

    name = "local-heuristic"

    async def run(self, task: EnrichmentTask, event: InternalItem) -> EnrichmentResult:
        """Return simple structured enrichment without external AI calls."""
        title = str(event.metadata.get("title", ""))
        if task.type == "classify":
            output: object = {"tags": _infer_tags(title)}
        elif task.type == "summarize":
            output = {"summary": title or event.id}
        else:
            output = {
                "title": title,
                "source": event.source.kind,
                "url": event.metadata.get("link"),
            }
        return EnrichmentResult(
            task_type=task.type,
            output=output,
            model=ModelIdentity(provider=self.name, name="local-rules", version="0.1.0"),
        )


def main(argv: Sequence[str] | None = None) -> None:
    """Run the Shiyi CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "capture":
        summary = asyncio.run(
            run_capture(
                source=args.source,
                workspace=args.workspace,
                limit=args.limit,
                max_items=args.max_items,
                since=args.since,
                until=args.until,
            )
        )
        sys.stdout.write(_format_summary(summary))
    elif args.command == "list":
        listed_events = list_events(workspace=args.workspace, limit=args.limit)
        sys.stdout.write(_format_json(listed_events))
    elif args.command == "export":
        exported_events = export_items(
            workspace=args.workspace,
            since=args.since,
            until=args.until,
            sources=tuple(args.source),
            limit=args.limit,
            source_ready_only=args.source_ready_only,
        )
        sys.stdout.write(_format_json(exported_events))
    elif args.command == "sources":
        sys.stdout.write(_format_json(source_summaries(include_backlog=args.include_backlog)))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shiyi")
    subcommands = parser.add_subparsers(dest="command", required=True)
    capture = subcommands.add_parser("capture", help="Run a local capture once")
    capture.add_argument(
        "--source",
        choices=BUILTIN_SOURCE_NAMES,
        required=True,
    )
    capture.add_argument("--workspace", type=Path, default=Path(".shiyi"))
    capture.add_argument("--limit", type=int, default=None, help="Deprecated debug item cap")
    capture.add_argument(
        "--max-items", type=int, default=None, help="Maximum items after date filtering"
    )
    capture.add_argument(
        "--since",
        type=_parse_datetime_arg,
        default=None,
        help="Inclusive UTC date/time, e.g. 2026-05-12",
    )
    capture.add_argument(
        "--until",
        type=_parse_datetime_arg,
        default=None,
        help="Exclusive UTC date/time, e.g. 2026-05-13",
    )

    list_events = subcommands.add_parser("list", help="List captured records")
    list_events.add_argument("--workspace", type=Path, default=Path(".shiyi"))
    list_events.add_argument("--limit", type=int, default=20)

    export = subcommands.add_parser("export", help="Export normalized captured items")
    export.add_argument("--workspace", type=Path, default=Path(".shiyi"))
    export.add_argument(
        "--since",
        type=_parse_datetime_arg,
        default=None,
        help="Inclusive UTC captured_at date/time, e.g. 2026-05-12",
    )
    export.add_argument(
        "--until",
        type=_parse_datetime_arg,
        default=None,
        help="Exclusive UTC captured_at date/time, e.g. 2026-05-13",
    )
    export.add_argument(
        "--source",
        action="append",
        default=[],
        help="Source kind filter; repeat for OR semantics",
    )
    export.add_argument("--limit", type=_positive_int, default=20)
    export.add_argument(
        "--source-ready-only",
        action="store_true",
        help="Only export records whose content_depth is source-ready.",
    )
    sources = subcommands.add_parser("sources", help="List registered sources and handoff backlog")
    sources.add_argument(
        "--include-backlog",
        action="store_true",
        help="Include deferred P3/high-noise source backlog rows.",
    )
    return parser


async def run_capture(  # noqa: PLR0913
    *,
    source: SourceName | str,
    workspace: Path,
    limit: int | None,
    max_items: int | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
) -> CaptureSummary:
    """Run one local capture for a source and return a summary."""
    workspace.mkdir(parents=True, exist_ok=True)
    metadata_path = workspace / "event-records.sqlite"
    item_cap = max_items if max_items is not None else limit
    window = CaptureWindow(since=since, until=until, max_items=item_cap or 5)
    raw_cache_root = workspace / "data" / "raw"
    adapter = build_source_adapter(source, window=window, raw_cache_root=raw_cache_root)
    pipeline = CapturePipeline(
        adapter=adapter,
        ai_provider=LocalHeuristicAIProvider(),
        artifact_store=FileSystemArtifactStore(workspace / "artifacts"),
        event_record_store=SQLiteEventRecordStore(metadata_path),
        normalizer=HtmlMarkdownNormalizer(),
        enrichment_tasks=[
            SummarizeTask(max_tokens=120),
            ClassifyTask(labels=("model", "product", "safety", "research", "company")),
        ],
    )
    run_summary = await pipeline.run_once()
    return _capture_summary(source=source, workspace=workspace, run_summary=run_summary)


def _capture_summary(  # noqa: PLR0913
    *,
    source: SourceName | str,
    workspace: Path,
    run_summary: PipelineRunSummary | None = None,
    processed: int | None = None,
    skipped: int = 0,
    failed: int = 0,
    errors: Sequence[str] = (),
) -> CaptureSummary:
    metadata_path = workspace / "event-records.sqlite"
    total_events = 0
    enriched_events = 0
    enrichments = 0
    if metadata_path.exists():
        with sqlite3.connect(metadata_path) as connection:
            total_events = int(connection.execute("SELECT COUNT(*) FROM events").fetchone()[0])
            enriched_events = int(
                connection.execute(
                    "SELECT COUNT(*) FROM events WHERE status = 'enriched'"
                ).fetchone()[0]
            )
            enrichments = int(connection.execute("SELECT COUNT(*) FROM enrichments").fetchone()[0])

    artifacts_root = workspace / "artifacts"
    artifacts = (
        sum(1 for path in artifacts_root.rglob("*") if path.is_file())
        if artifacts_root.exists()
        else 0
    )
    if run_summary is not None:
        processed_count = run_summary.processed
        skipped_count = run_summary.skipped
        failed_count = run_summary.failed
        error_messages = tuple(error.message for error in run_summary.errors)
    else:
        processed_count = processed or 0
        skipped_count = skipped
        failed_count = failed
        error_messages = tuple(errors)

    return CaptureSummary(
        source=source.value if isinstance(source, SourceName) else source,
        workspace=str(workspace),
        processed=processed_count,
        total_events=total_events,
        enriched_events=enriched_events,
        enrichments=enrichments,
        artifacts=artifacts,
        skipped=skipped_count,
        failed=failed_count,
        errors=error_messages,
    )


def list_events(*, workspace: Path, limit: int) -> list[EventSummary]:
    """List captured records from a workspace."""
    metadata_path = workspace / "event-records.sqlite"
    if not metadata_path.exists():
        return []
    with sqlite3.connect(metadata_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT event_id, idempotency_key, status, raw_artifact_json,
                   normalized_artifact_json, updated_at
            FROM events
            ORDER BY updated_at DESC, event_id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        EventSummary(
            event_id=str(row["event_id"]),
            idempotency_key=str(row["idempotency_key"]),
            status=str(row["status"]),
            updated_at=str(row["updated_at"]),
            has_raw_artifact=row["raw_artifact_json"] is not None,
            has_normalized_artifact=row["normalized_artifact_json"] is not None,
        )
        for row in rows
    ]


def _format_summary(summary: CaptureSummary) -> str:
    return _format_json(summary)


def _format_json(payload: object) -> str:
    data: Any
    if isinstance(payload, list):
        data = [_jsonable(item) for item in payload]
    else:
        data = _jsonable(payload)
    return f"{json.dumps(data, ensure_ascii=False, sort_keys=True)}\n"


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(cast(Any, value))
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    return value


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        msg = "must be >= 1"
        raise argparse.ArgumentTypeError(msg)
    return parsed


def _parse_datetime_arg(value: str) -> datetime:
    normalized = value.strip()
    if len(normalized) == DATE_ONLY_LENGTH:
        normalized = f"{normalized}T00:00:00+00:00"
    else:
        normalized = normalized.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _infer_tags(title: str) -> list[str]:
    normalized = title.lower()
    tags: list[str] = []
    if "safety" in normalized or "secure" in normalized or "security" in normalized:
        tags.append("safety")
    if "claude" in normalized or "gpt" in normalized or "model" in normalized:
        tags.append("model")
    if "api" in normalized or "product" in normalized:
        tags.append("product")
    return tags or ["announcement"]


if __name__ == "__main__":
    main()
