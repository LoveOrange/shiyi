"""Official GitHub Releases API adapter for product release notes."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

from shiyi.domain.models import CaptureWindow, Source, SourceItem, TextPayload
from shiyi.fetchers.http import HttpWebFetcher
from shiyi.ports.fetcher import WebFetcher

GITHUB_RELEASES_API_TEMPLATE = "https://api.github.com/repos/{repository}/releases?per_page=100"
GITHUB_REPOSITORY_PATH_PARTS = 2


@dataclass(frozen=True, slots=True)
class GitHubRelease:
    """Source-neutral fields retained from one official GitHub release."""

    release_id: str
    tag_name: str
    title: str
    published_at: datetime
    canonical_url: str
    body: str
    prerelease: bool
    author: str | None = None


class GitHubReleasesAdapter:
    """Captures up to 100 recent official releases from one GitHub repository."""

    version = "0.1.0"

    def __init__(
        self,
        *,
        web_fetcher: WebFetcher | None = None,
        limit: int | None = None,
        window: CaptureWindow | None = None,
    ) -> None:
        """Create the shared GitHub release-notes adapter."""
        self._web_fetcher = web_fetcher or HttpWebFetcher()
        self._window = window or CaptureWindow(max_items=limit)

    @property
    def name(self) -> str:
        """Stable adapter name shared by official GitHub release sources."""
        return "github-releases-api"

    async def capture(self, source: Source) -> AsyncIterator[SourceItem]:
        """Fetch releases, apply the capture window, and emit complete release notes."""
        result = await self._web_fetcher.fetch(source.target)
        emitted = 0
        for release in parse_github_releases(result.content):
            if not self._window.includes(release.published_at):
                continue
            metadata: dict[str, object] = {
                "title": release.title,
                "link": release.canonical_url,
                "is_complete": True,
                "tag_name": release.tag_name,
                "prerelease": release.prerelease,
            }
            if release.author is not None:
                metadata["creators"] = (release.author,)
            yield SourceItem(
                source_id=source.id,
                source_item_id=release.release_id,
                kind=_content_kind(source),
                canonical_url=release.canonical_url,
                collected_at=result.fetched_at,
                published_at=release.published_at,
                payload=TextPayload(text=_release_payload(release)),
                metadata=metadata,
            )
            emitted += 1
            if self._window.max_items is not None and emitted >= self._window.max_items:
                break


def github_releases_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> GitHubReleasesAdapter:
    """Create the shared official GitHub Releases API adapter."""
    return GitHubReleasesAdapter(limit=limit, window=window, web_fetcher=web_fetcher)


def github_releases_api_url(repository: str) -> str:
    """Return the bounded official Releases API URL for an owner/repository pair."""
    parts = repository.strip("/").split("/")
    if len(parts) != GITHUB_REPOSITORY_PATH_PARTS or not all(parts):
        msg = f"GitHub repository must be owner/name, got {repository!r}"
        raise ValueError(msg)
    return GITHUB_RELEASES_API_TEMPLATE.format(repository="/".join(parts))


def parse_github_releases(content: str) -> tuple[GitHubRelease, ...]:
    """Parse the public GitHub Releases API response and exclude draft releases."""
    parsed: object = json.loads(content)
    if not isinstance(parsed, list):
        msg = "GitHub Releases response must be a JSON array"
        raise TypeError(msg)

    releases: list[GitHubRelease] = []
    for index, raw_release in enumerate(parsed):
        if not isinstance(raw_release, Mapping):
            msg = f"GitHub release at index {index} must be an object"
            raise TypeError(msg)
        release = cast(Mapping[str, object], raw_release)
        if release.get("draft") is True:
            continue
        tag_name = _required_string(release, "tag_name", index=index)
        title = _optional_string(release.get("name")) or tag_name
        releases.append(
            GitHubRelease(
                release_id=_release_id(release, index=index),
                tag_name=tag_name,
                title=title,
                published_at=_datetime_utc(_required_string(release, "published_at", index=index)),
                canonical_url=_required_string(release, "html_url", index=index),
                body=_optional_string(release.get("body")) or "",
                prerelease=release.get("prerelease") is True,
                author=_release_author(release),
            )
        )
    return tuple(sorted(releases, key=lambda release: release.published_at, reverse=True))


def _release_payload(release: GitHubRelease) -> str:
    lines = [
        release.title,
        "",
        f"Version: {release.tag_name}",
        f"Published: {release.published_at.isoformat()}",
        f"Canonical link: {release.canonical_url}",
    ]
    if release.prerelease:
        lines.append("Release channel: prerelease")
    if release.body:
        lines.extend(("", release.body))
    return "\n".join(lines)


def _release_id(release: Mapping[str, object], *, index: int) -> str:
    value = release.get("id")
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        msg = f"GitHub release at index {index} missing required field id"
        raise TypeError(msg)
    release_id = str(value).strip()
    if not release_id:
        msg = f"GitHub release at index {index} has empty field id"
        raise ValueError(msg)
    return release_id


def _required_string(release: Mapping[str, object], field: str, *, index: int) -> str:
    value = _optional_string(release.get(field))
    if value is None:
        msg = f"GitHub release at index {index} missing required field {field}"
        raise ValueError(msg)
    return value


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _release_author(release: Mapping[str, object]) -> str | None:
    author = release.get("author")
    if not isinstance(author, Mapping):
        return None
    return _optional_string(author.get("login"))


def _datetime_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _content_kind(source: Source) -> str:
    value = source.options.get("content_kind", "release_note")
    return value if isinstance(value, str) and value else "release_note"
