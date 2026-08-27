"""Command-line entry point for configured Shiyi capture runs."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from pydantic import BaseModel

from shiyi.ai import AIProviderACL, CodexCLIProvider
from shiyi.domain.models import CaptureWindow, ContentItem
from shiyi.normalizers.html import MarkdownContentProcessor
from shiyi.pipeline.ai_enrichment import AIEnrichmentRunner, AIEnrichmentSummary
from shiyi.pipeline.runner import CaptureRunner, CaptureRunSummary
from shiyi.ports.content_item_store import ContentItemStore
from shiyi.ports.source_adapter import SourceAdapter
from shiyi.sources import (
    BUILTIN_SOURCE_NAMES,
    SourceName,
    build_capture_config,
    build_source_adapters,
    source_summary_dicts,
)
from shiyi.stores.filesystem import FileSystemBlobStore
from shiyi.stores.mongo import MongoContentItemStore

DATE_ONLY_LENGTH = 10
DEFAULT_MONGO_URI = "mongodb://localhost:27017"


@dataclass(frozen=True, slots=True)
class CaptureSummary:
    """Human and machine-readable capture outcome."""

    sources: tuple[str, ...]
    workspace: str
    processed: int
    skipped: int
    failed: int
    blobs: int
    errors: tuple[str, ...]


def main(argv: Sequence[str] | None = None) -> None:
    """Run the Shiyi CLI."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "capture":
        capture_summary = asyncio.run(
            run_capture(
                sources=tuple(args.source),
                workspace=args.workspace,
                mongo_uri=args.mongo_uri,
                database=args.database,
                collection=args.collection,
                max_items=args.max_items,
                since=args.since,
                until=args.until,
                operator_snapshot_manifest=args.operator_snapshot_manifest,
            )
        )
        sys.stdout.write(_format_json(capture_summary))
    elif args.command == "enrich":
        enrichment_summary = asyncio.run(
            run_ai_enrichment(
                provider=args.provider,
                mongo_uri=args.mongo_uri,
                database=args.database,
                collection=args.collection,
                limit=args.limit,
                summary_language=args.summary_language,
                max_content_chars=args.max_content_chars,
                codex_executable=args.codex_executable,
                codex_timeout=args.codex_timeout,
            )
        )
        sys.stdout.write(_format_json(enrichment_summary))
    elif args.command in {"list", "export"}:
        items = asyncio.run(
            list_content_items(
                mongo_uri=args.mongo_uri,
                database=args.database,
                collection=args.collection,
                since=args.since,
                until=args.until,
                source_ids=tuple(args.source),
                limit=args.limit,
            )
        )
        sys.stdout.write(_format_json(items))
    elif args.command == "sources":
        sys.stdout.write(_format_json(source_summary_dicts()))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="shiyi")
    subcommands = parser.add_subparsers(dest="command", required=True)

    capture = subcommands.add_parser("capture", help="Capture configured sources once")
    capture.add_argument(
        "--source",
        action="append",
        choices=BUILTIN_SOURCE_NAMES,
        required=True,
        help="Built-in source to capture; repeat to run multiple sources",
    )
    capture.add_argument("--workspace", type=Path, default=Path(".shiyi"))
    capture.add_argument("--max-items", type=_positive_int, default=5)
    capture.add_argument("--since", type=_parse_datetime_arg, default=None)
    capture.add_argument("--until", type=_parse_datetime_arg, default=None)
    capture.add_argument(
        "--operator-snapshot-manifest",
        type=Path,
        default=None,
        help=(
            "Explicit hash-verified operator snapshot manifest; exact mapped URLs use "
            "snapshots and all other URLs retain ordinary acquisition"
        ),
    )
    _add_mongo_arguments(capture)

    for command in ("list", "export"):
        read = subcommands.add_parser(command, help=f"{command.title()} ready ContentItems")
        read.add_argument("--source", action="append", default=[])
        read.add_argument("--limit", type=_positive_int, default=20)
        read.add_argument("--since", type=_parse_datetime_arg, default=None)
        read.add_argument("--until", type=_parse_datetime_arg, default=None)
        _add_mongo_arguments(read)

    enrich = subcommands.add_parser(
        "enrich",
        help="Backfill missing summaries through an explicit AI provider",
    )
    enrich.add_argument("--provider", choices=("codex-cli",), required=True)
    enrich.add_argument("--limit", type=_positive_int, default=5)
    enrich.add_argument("--summary-language", default="zh")
    enrich.add_argument("--max-content-chars", type=_positive_int, default=20_000)
    enrich.add_argument("--codex-executable", default="codex")
    enrich.add_argument("--codex-timeout", type=_positive_float, default=300.0)
    _add_mongo_arguments(enrich)

    subcommands.add_parser("sources", help="List built-in configured sources")
    return parser


def _add_mongo_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--mongo-uri",
        default=os.environ.get("SHIYI_MONGO_URI", DEFAULT_MONGO_URI),
    )
    parser.add_argument("--database", default="shiyi")
    parser.add_argument("--collection", default="content_items")


async def run_capture(  # noqa: PLR0913
    *,
    sources: Sequence[SourceName | str],
    workspace: Path,
    mongo_uri: str = DEFAULT_MONGO_URI,
    database: str = "shiyi",
    collection: str = "content_items",
    max_items: int | None = 5,
    since: datetime | None = None,
    until: datetime | None = None,
    content_store: ContentItemStore | None = None,
    adapters: Sequence[SourceAdapter] | None = None,
    operator_snapshot_manifest: Path | None = None,
) -> CaptureSummary:
    """Run one configured capture and return a compact outcome."""
    workspace.mkdir(parents=True, exist_ok=True)
    config = build_capture_config(sources)
    window = CaptureWindow(since=since, until=until, max_items=max_items)
    resolved_adapters = (
        tuple(adapters)
        if adapters is not None
        else build_source_adapters(
            config,
            window=window,
            raw_cache_root=workspace / "raw-cache",
            operator_snapshot_manifest=operator_snapshot_manifest,
        )
    )

    owned_store = content_store is None
    store = content_store or MongoContentItemStore.from_uri(
        mongo_uri,
        database=database,
        collection=collection,
    )
    if owned_store:
        await cast(MongoContentItemStore, store).ensure_indexes()
    runner = CaptureRunner(
        config=config,
        adapters=resolved_adapters,
        processor=MarkdownContentProcessor(),
        content_store=store,
        blob_store=FileSystemBlobStore(workspace / "blobs"),
    )
    try:
        result = await runner.run_once()
    finally:
        if owned_store:
            await cast(MongoContentItemStore, store).close()
    return _capture_summary(configured_sources=sources, workspace=workspace, result=result)


async def list_content_items(  # noqa: PLR0913
    *,
    mongo_uri: str,
    database: str,
    collection: str,
    since: datetime | None,
    until: datetime | None,
    source_ids: Sequence[str],
    limit: int,
) -> list[ContentItem]:
    """Read ready canonical items from MongoDB."""
    store = MongoContentItemStore.from_uri(
        mongo_uri,
        database=database,
        collection=collection,
    )
    try:
        return await store.list_ready(
            since=since,
            until=until,
            source_ids=source_ids,
            limit=limit,
        )
    finally:
        await store.close()


async def run_ai_enrichment(  # noqa: PLR0913
    *,
    provider: str,
    mongo_uri: str = DEFAULT_MONGO_URI,
    database: str = "shiyi",
    collection: str = "content_items",
    limit: int = 5,
    summary_language: str = "zh",
    max_content_chars: int = 20_000,
    codex_executable: str = "codex",
    codex_timeout: float = 300.0,
    content_store: ContentItemStore | None = None,
    acl: AIProviderACL | None = None,
) -> AIEnrichmentSummary:
    """Backfill missing summaries through a provider ACL without adding workflow state."""
    if provider != "codex-cli":
        msg = f"unsupported AI provider: {provider}"
        raise ValueError(msg)
    resolved_acl = acl or AIProviderACL(
        CodexCLIProvider(
            executable=codex_executable,
            timeout_seconds=codex_timeout,
        ),
        summary_language=summary_language,
        max_content_chars=max_content_chars,
    )
    owned_store = content_store is None
    store = content_store or MongoContentItemStore.from_uri(
        mongo_uri,
        database=database,
        collection=collection,
    )
    runner = AIEnrichmentRunner(content_store=store, acl=resolved_acl)
    try:
        return await runner.run(limit=limit)
    finally:
        if owned_store:
            await cast(MongoContentItemStore, store).close()


def _capture_summary(
    *,
    configured_sources: Sequence[SourceName | str],
    workspace: Path,
    result: CaptureRunSummary,
) -> CaptureSummary:
    return CaptureSummary(
        sources=tuple(str(source) for source in configured_sources),
        workspace=str(workspace),
        processed=result.processed,
        skipped=result.skipped,
        failed=result.failed,
        blobs=result.blobs,
        errors=tuple(
            f"{error.source_id}/{error.source_item_id or '-'} {error.stage}: {error.message}"
            for error in result.errors
        ),
    )


def _parse_datetime_arg(value: str) -> datetime:
    try:
        if len(value) == DATE_ONLY_LENGTH:
            parsed = datetime.fromisoformat(value).replace(tzinfo=UTC)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        msg = f"invalid ISO date/time: {value}"
        raise argparse.ArgumentTypeError(msg) from error
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        msg = "value must be greater than zero"
        raise argparse.ArgumentTypeError(msg)
    return parsed


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        msg = "value must be greater than zero"
        raise argparse.ArgumentTypeError(msg)
    return parsed


def _format_json(value: object) -> str:
    return f"{json.dumps(_jsonable(value), indent=2, sort_keys=True)}\n"


def _jsonable(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value
