"""Command-line entry point for local Shiyi capture runs."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Literal

from shiyi.adapters.anthropic import anthropic_news_adapter
from shiyi.adapters.rss import openai_news_adapter
from shiyi.domain.models import (
    CaptureEvent,
    ClassifyTask,
    EnrichmentResult,
    EnrichmentTask,
    ModelIdentity,
    SummarizeTask,
)
from shiyi.normalizers.html import HtmlMarkdownNormalizer
from shiyi.pipeline.runner import CapturePipeline
from shiyi.stores.filesystem import FileSystemArtifactStore
from shiyi.stores.sqlite import SQLiteMetadataStore

SourceName = Literal["openai", "anthropic"]


class LocalHeuristicAIProvider:
    """Deterministic local enrichment provider for MVP capture smoke runs."""

    name = "local-heuristic"

    async def run(self, task: EnrichmentTask, event: CaptureEvent) -> EnrichmentResult:
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


def main() -> None:
    """Run the Shiyi CLI."""
    parser = argparse.ArgumentParser(prog="shiyi")
    subcommands = parser.add_subparsers(dest="command", required=True)
    capture = subcommands.add_parser("capture", help="Run a local capture once")
    capture.add_argument("--source", choices=["openai", "anthropic"], required=True)
    capture.add_argument("--workspace", type=Path, default=Path(".shiyi"))
    capture.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()

    if args.command == "capture":
        processed = asyncio.run(
            run_capture(source=args.source, workspace=args.workspace, limit=args.limit)
        )
        sys.stdout.write(f"processed={processed}\n")


async def run_capture(*, source: SourceName, workspace: Path, limit: int) -> int:
    """Run one local capture for a source and return processed event count."""
    workspace.mkdir(parents=True, exist_ok=True)
    adapter = (
        openai_news_adapter(limit=limit)
        if source == "openai"
        else anthropic_news_adapter(limit=limit)
    )
    pipeline = CapturePipeline(
        adapter=adapter,
        ai_provider=LocalHeuristicAIProvider(),
        artifact_store=FileSystemArtifactStore(workspace / "artifacts"),
        metadata_store=SQLiteMetadataStore(workspace / "metadata.sqlite"),
        normalizer=HtmlMarkdownNormalizer(),
        enrichment_tasks=[
            SummarizeTask(max_tokens=120),
            ClassifyTask(labels=("model", "product", "safety", "research", "company")),
        ],
    )
    return await pipeline.run_once()


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
