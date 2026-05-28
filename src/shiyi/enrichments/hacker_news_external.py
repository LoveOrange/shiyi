"""Hacker News external-target enrichment stage."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from html import unescape
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

from pydantic import Field

from shiyi._time import utc_isoformat
from shiyi.domain.models import ArtifactRef, ArtifactWrite, SourceType, StrictModel
from shiyi.fetchers.http import HttpWebFetcher
from shiyi.ports.fetcher import FetcherError, FetchErrorKind, FetchResult, WebFetcher
from shiyi.stores.filesystem import FileSystemArtifactStore

HACKER_NEWS_EXTERNAL_TARGET_ENRICHMENT_VERSION = "external_target_enrichment.v1"
HACKER_NEWS_EXTERNAL_TARGET_FETCHER_VERSION = "hn-external-target-fetch-v1"
HACKER_NEWS_EXTERNAL_TARGET_NORMALIZER_VERSION = "hn-external-target-normalize-v1"
HACKER_NEWS_EXTERNAL_TARGET_SOURCE = "hacker-news-external-target"

FetchStatus = Literal[
    "fetched",
    "fetch_failed",
    "robots_disallowed",
    "dynamic_content",
    "paywall",
    "inaccessible",
]

_SCRIPT_OR_STYLE_PATTERN = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.I | re.S)
_TITLE_PATTERN = re.compile(r"<title\b[^>]*>(.*?)</title>", re.I | re.S)
_H1_PATTERN = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.I | re.S)
_TAG_PATTERN = re.compile(r"<[^>]+>")
_WHITESPACE_PATTERN = re.compile(r"\s+")
_SENTENCE_PATTERN = re.compile(r"(?<=[.!?])\s+")
_SENTENCE_TERMINATORS = ".!?"
_FETCHED_TEXT_MIN_CHARS = 80
_SUMMARY_SENTENCE_MIN_CHARS = 40


class ExternalTargetEnrichmentProvenance(StrictModel):
    """Audit fields for the dedicated external-target enrichment stage."""

    fetcher: str = HACKER_NEWS_EXTERNAL_TARGET_SOURCE
    fetcher_version: str = HACKER_NEWS_EXTERNAL_TARGET_FETCHER_VERSION
    normalizer_version: str = HACKER_NEWS_EXTERNAL_TARGET_NORMALIZER_VERSION
    fetched_at: str
    raw_artifact_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    normalized_artifact_ref: ArtifactRef | None = Field(
        default=None, exclude_if=lambda value: value is None
    )
    http_status: int | None = Field(default=None, exclude_if=lambda value: value is None)
    failure_reason: str | None = Field(default=None, exclude_if=lambda value: value is None)
    model: dict[str, Any] | None = Field(default=None, exclude_if=lambda value: value is None)
    prompt: dict[str, Any] | None = Field(default=None, exclude_if=lambda value: value is None)
    usage: dict[str, Any] | None = Field(default=None, exclude_if=lambda value: value is None)


class ExternalTargetEnrichment(StrictModel):
    """Exportable HN external-target enrichment object."""

    schema_version: Literal["external_target_enrichment.v1"] = "external_target_enrichment.v1"
    target_url: str
    final_url: str | None = Field(default=None, exclude_if=lambda value: value is None)
    external_title: str | None = Field(default=None, exclude_if=lambda value: value is None)
    source_type: SourceType = "unknown"
    factual_summary: str | None = Field(default=None, exclude_if=lambda value: value is None)
    fetch_status: FetchStatus
    content_hash: str | None = Field(default=None, exclude_if=lambda value: value is None)
    provenance: ExternalTargetEnrichmentProvenance


@dataclass(frozen=True, slots=True)
class ExternalTargetEnrichmentSummary:
    """Machine-readable summary for one external-target enrichment run."""

    source: str
    workspace: str
    processed: int
    enriched: int
    skipped: int
    failed: int
    artifacts: int
    errors: tuple[str, ...] = ()


async def enrich_hacker_news_external_targets(
    *,
    workspace: Path,
    limit: int | None = None,
    web_fetcher: WebFetcher | None = None,
    overwrite: bool = False,
) -> ExternalTargetEnrichmentSummary:
    """Fetch HN external target pages and attach exportable enrichment metadata."""
    metadata_path = workspace / "event-records.sqlite"
    if not metadata_path.exists():
        return ExternalTargetEnrichmentSummary(
            source="hacker-news",
            workspace=str(workspace),
            processed=0,
            enriched=0,
            skipped=0,
            failed=0,
            artifacts=0,
        )

    fetcher = web_fetcher or HttpWebFetcher(raw_cache_root=workspace / "data" / "raw")
    artifact_store = FileSystemArtifactStore(workspace / "artifacts")
    processed = 0
    enriched = 0
    skipped = 0
    failed = 0
    artifacts = 0
    errors: list[str] = []
    for row in _hacker_news_rows(metadata_path):
        if limit is not None and processed >= limit:
            break
        metadata = _metadata_from_json(row["metadata_json"])
        target_url = _target_url(metadata)
        if target_url is None:
            skipped += 1
            continue
        if not overwrite and isinstance(metadata.get("external_target_enrichment"), dict):
            skipped += 1
            continue

        try:
            enrichment, artifact_count = await _fetch_enrichment(
                target_url=target_url,
                upstream_id=str(metadata.get("upstream_id") or row["event_id"]),
                web_fetcher=fetcher,
                artifact_store=artifact_store,
            )
            artifacts += artifact_count
            _save_enrichment(
                metadata_path=metadata_path,
                idempotency_key=str(row["idempotency_key"]),
                metadata={
                    **metadata,
                    "external_target_enrichment": enrichment.model_dump(mode="json"),
                },
            )
            processed += 1
            if enrichment.fetch_status == "fetched":
                enriched += 1
            else:
                failed += 1
        except Exception as error:
            processed += 1
            failed += 1
            errors.append(f"{row['idempotency_key']}: {type(error).__name__}: {error}")

    return ExternalTargetEnrichmentSummary(
        source="hacker-news",
        workspace=str(workspace),
        processed=processed,
        enriched=enriched,
        skipped=skipped,
        failed=failed,
        artifacts=artifacts,
        errors=tuple(errors),
    )


def external_target_enrichment_from_metadata(
    metadata: dict[str, Any],
) -> ExternalTargetEnrichment | None:
    """Return a validated external-target enrichment object from event metadata."""
    value = metadata.get("external_target_enrichment")
    if not isinstance(value, dict):
        return None
    return ExternalTargetEnrichment.model_validate(value)


def _hacker_news_rows(metadata_path: Path) -> list[sqlite3.Row]:
    with sqlite3.connect(metadata_path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT event_id, idempotency_key, source_json, metadata_json, captured_at
            FROM events
            WHERE metadata_json IS NOT NULL
            ORDER BY captured_at DESC, event_id ASC
            """
        ).fetchall()
    return [row for row in rows if _source_kind(row["source_json"]) == "hacker-news"]


def _source_kind(source_json: str | None) -> str | None:
    if source_json is None:
        return None
    decoded = json.loads(source_json)
    if not isinstance(decoded, dict):
        return None
    value = decoded.get("kind")
    return str(value) if value else None


def _metadata_from_json(value: str | None) -> dict[str, Any]:
    if value is None:
        return {}
    decoded = json.loads(value)
    if not isinstance(decoded, dict):
        msg = "event metadata must decode to a JSON object"
        raise TypeError(msg)
    return decoded


def _target_url(metadata: dict[str, Any]) -> str | None:
    value = metadata.get("external_target_url")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


async def _fetch_enrichment(
    *,
    target_url: str,
    upstream_id: str,
    web_fetcher: WebFetcher,
    artifact_store: FileSystemArtifactStore,
) -> tuple[ExternalTargetEnrichment, int]:
    raw_key = _raw_key(upstream_id=upstream_id, target_url=target_url)
    try:
        result = await web_fetcher.fetch(
            target_url,
            source=HACKER_NEWS_EXTERNAL_TARGET_SOURCE,
            raw_key=raw_key,
        )
    except FetcherError as error:
        return _failure_enrichment(target_url=target_url, error=error), 0

    raw_ref = await artifact_store.put(
        ArtifactWrite(
            kind="raw",
            media_type=result.content_type or "text/html",
            content=result.content.encode(),
            suggested_name=f"{raw_key}.html",
        )
    )
    status = _content_status(result.content)
    title = _external_title(result.content) or _title_from_url(str(result.url))
    if status != "fetched":
        return (
            ExternalTargetEnrichment(
                target_url=target_url,
                final_url=str(result.url),
                external_title=title,
                source_type=_source_type_for_url(str(result.url)),
                fetch_status=status,
                provenance=_success_provenance(result=result, raw_ref=raw_ref),
            ),
            1,
        )

    plain_text = _html_to_text(result.content)
    normalized_text = _normalized_external_text(
        title=title,
        final_url=str(result.url),
        text=plain_text,
    )
    normalized_ref = await artifact_store.put(
        ArtifactWrite(
            kind="normalized",
            media_type="text/markdown",
            content=normalized_text.encode(),
            suggested_name=f"{raw_key}.md",
        )
    )
    return (
        ExternalTargetEnrichment(
            target_url=target_url,
            final_url=str(result.url),
            external_title=title,
            source_type=_source_type_for_url(str(result.url)),
            factual_summary=_factual_summary(plain_text, title),
            fetch_status="fetched",
            content_hash=hashlib.sha256(normalized_text.encode()).hexdigest(),
            provenance=_success_provenance(
                result=result,
                raw_ref=raw_ref,
                normalized_ref=normalized_ref,
            ),
        ),
        2,
    )


def _failure_enrichment(*, target_url: str, error: FetcherError) -> ExternalTargetEnrichment:
    now = utc_isoformat(datetime.now(UTC))
    return ExternalTargetEnrichment(
        target_url=target_url,
        source_type=_source_type_for_url(target_url),
        fetch_status=_status_from_error(error),
        provenance=ExternalTargetEnrichmentProvenance(
            fetched_at=now,
            http_status=error.status_code,
            failure_reason=str(error),
        ),
    )


def _success_provenance(
    *,
    result: FetchResult,
    raw_ref: ArtifactRef,
    normalized_ref: ArtifactRef | None = None,
) -> ExternalTargetEnrichmentProvenance:
    return ExternalTargetEnrichmentProvenance(
        fetched_at=utc_isoformat(result.fetched_at),
        raw_artifact_ref=raw_ref,
        normalized_artifact_ref=normalized_ref,
        http_status=result.status_code,
    )


def _status_from_error(error: FetcherError) -> FetchStatus:
    lowered = str(error).lower()
    if "robots" in lowered:
        return "robots_disallowed"
    if error.kind is FetchErrorKind.HTTP_STATUS and error.status_code in {401, 402, 403, 451}:
        return "inaccessible"
    return "fetch_failed"


def _content_status(html: str) -> FetchStatus:
    text = _html_to_text(html).lower()
    if "robots disallowed" in text or "blocked by robots" in text:
        return "robots_disallowed"
    if "requires javascript" in text or "enable javascript" in text:
        return "dynamic_content"
    if "paywall" in text or "subscribe to continue" in text:
        return "paywall"
    if len(text) < _FETCHED_TEXT_MIN_CHARS:
        return "inaccessible"
    return "fetched"


def _external_title(html: str) -> str | None:
    for pattern in (_TITLE_PATTERN, _H1_PATTERN):
        match = pattern.search(html)
        if match is None:
            continue
        title = _clean_text(match.group(1))
        if title:
            return title
    return None


def _normalized_external_text(*, title: str | None, final_url: str, text: str) -> str:
    lines = []
    if title:
        lines.append(f"# {title}")
        lines.append("")
    lines.append(f"Canonical link: {final_url}")
    lines.append("")
    lines.append(text)
    return "\n".join(lines).strip() + "\n"


def _factual_summary(text: str, title: str | None) -> str | None:
    cleaned = _html_to_text(text)
    if title:
        cleaned = cleaned.replace(title, " ", 1)
    cleaned = re.sub(r"canonical link:\s+\S+", " ", cleaned, flags=re.I)
    sentences = [
        sentence.strip()
        for sentence in _SENTENCE_PATTERN.split(cleaned)
        if _is_summary_sentence(sentence)
    ]
    if not sentences:
        return None
    summary = " ".join(sentences[:2])
    if summary[-1] not in _SENTENCE_TERMINATORS:
        summary += "."
    return summary


def _is_summary_sentence(sentence: str) -> bool:
    if len(sentence) < _SUMMARY_SENTENCE_MIN_CHARS:
        return False
    lowered = sentence.lower()
    return not lowered.startswith(("canonical link:", "source:", "external target:"))


def _html_to_text(html: str) -> str:
    without_scripts = _SCRIPT_OR_STYLE_PATTERN.sub(" ", html)
    without_tags = _TAG_PATTERN.sub(" ", without_scripts)
    return _clean_text(without_tags)


def _clean_text(value: str) -> str:
    return _WHITESPACE_PATTERN.sub(" ", unescape(value)).strip()


def _title_from_url(url: str) -> str | None:
    parsed = urlparse(url)
    slug = Path(parsed.path.rstrip("/")).name
    if not slug:
        return None
    return slug.replace("-", " ").replace("_", " ").title()


def _source_type_for_url(url: str) -> SourceType:
    parsed = urlparse(url)
    lowered = f"{parsed.netloc}{parsed.path}".lower()
    if "docs" in lowered or "documentation" in lowered:
        return "docs"
    if "/blog" in lowered or "blog." in lowered:
        return "blog"
    if "arxiv.org" in lowered or "research" in lowered:
        return "research"
    if "changelog" in lowered or "release" in lowered:
        return "changelog"
    return "unknown"


def _raw_key(*, upstream_id: str, target_url: str) -> str:
    digest = hashlib.sha256(target_url.encode()).hexdigest()[:12]
    cleaned_id = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", upstream_id).strip("-")
    return f"{cleaned_id or 'unknown'}-{digest}"


def _save_enrichment(
    *,
    metadata_path: Path,
    idempotency_key: str,
    metadata: dict[str, Any],
) -> None:
    now = utc_isoformat(datetime.now(UTC))
    with sqlite3.connect(metadata_path) as connection:
        connection.execute(
            """
            UPDATE events
            SET metadata_json = ?, updated_at = ?
            WHERE idempotency_key = ?
            """,
            (json.dumps(metadata, sort_keys=True), now, idempotency_key),
        )
