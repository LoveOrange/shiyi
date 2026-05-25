"""Reusable source-readiness gates for official fetch surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

DEFAULT_STRUCTURED_FIXTURE_MAX_BYTES = 256 * 1024

StructuredApiGateStatus = Literal["ready", "blocked"]
StructuredApiReadinessBlocker = Literal[
    "stable_official_endpoint",
    "stable_item_ids",
    "reliable_published_timestamps",
    "canonical_urls",
    "complete_payloads",
    "bounded_fixtures",
    "repeatable_extraction_tests",
    "traceability_refs",
]


@dataclass(frozen=True, slots=True)
class StructuredApiReadinessEvidence:
    """Objective evidence required before an official structured source is source-ready."""

    stable_official_endpoint: bool = False
    stable_item_ids: bool = False
    reliable_published_timestamps: bool = False
    canonical_urls: bool = False
    complete_payloads: bool = False
    bounded_fixtures: bool = False
    repeatable_extraction_tests: bool = False
    traceability_refs: tuple[str, ...] = ()

    @property
    def blockers(self) -> tuple[StructuredApiReadinessBlocker, ...]:
        """Return unmet structured/API readiness requirements."""
        blockers: list[StructuredApiReadinessBlocker] = []
        if not self.stable_official_endpoint:
            blockers.append("stable_official_endpoint")
        if not self.stable_item_ids:
            blockers.append("stable_item_ids")
        if not self.reliable_published_timestamps:
            blockers.append("reliable_published_timestamps")
        if not self.canonical_urls:
            blockers.append("canonical_urls")
        if not self.complete_payloads:
            blockers.append("complete_payloads")
        if not self.bounded_fixtures:
            blockers.append("bounded_fixtures")
        if not self.repeatable_extraction_tests:
            blockers.append("repeatable_extraction_tests")
        if not self.traceability_refs:
            blockers.append("traceability_refs")
        return tuple(blockers)

    @property
    def status(self) -> StructuredApiGateStatus:
        """Return the structured/API gate status."""
        return "ready" if not self.blockers else "blocked"

    @property
    def source_ready(self) -> bool:
        """Return whether the structured/API source can be considered source-ready."""
        return self.status == "ready"


@dataclass(frozen=True, slots=True)
class FixtureSizeCheck:
    """Bounded fixture-size evidence for structured/detail payload tests."""

    path: str
    size_bytes: int
    max_bytes: int = DEFAULT_STRUCTURED_FIXTURE_MAX_BYTES

    @property
    def ok(self) -> bool:
        """Return whether the fixture stays inside the reviewable size boundary."""
        return self.size_bytes <= self.max_bytes


def check_fixture_size(
    path: Path,
    *,
    max_bytes: int = DEFAULT_STRUCTURED_FIXTURE_MAX_BYTES,
) -> FixtureSizeCheck:
    """Return a deterministic size check for one committed fixture."""
    return FixtureSizeCheck(path=str(path), size_bytes=path.stat().st_size, max_bytes=max_bytes)
