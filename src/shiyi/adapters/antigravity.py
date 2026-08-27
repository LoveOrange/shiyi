"""Google Antigravity official product changelog adapter."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urljoin

from selectolax.parser import HTMLParser, Node

from shiyi.adapters.changelog import ChangelogEntry, ChangelogPageAdapter
from shiyi.domain.models import CaptureWindow
from shiyi.ports.fetcher import WebFetcher

ANTIGRAVITY_CHANGELOG_URL = "https://www.antigravity.google/changelog"
ANTIGRAVITY_BASE_URL = "https://www.antigravity.google"
_PRODUCT_LABELS = {
    "hub": "Antigravity 2.0",
    "cli": "Antigravity CLI",
    "ide": "Antigravity IDE",
    "sdk": "Antigravity SDK",
}
_DISPLAY_DATE_PATTERN = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+\d{1,2},\s+\d{4}\b"
)


def antigravity_changelog_adapter(
    *,
    limit: int | None = None,
    window: CaptureWindow | None = None,
    web_fetcher: WebFetcher | None = None,
) -> ChangelogPageAdapter:
    """Create the official Antigravity Hub, CLI, IDE, and SDK changelog adapter."""
    return ChangelogPageAdapter(
        name="google-antigravity-changelog-page",
        parser=parse_antigravity_changelog,
        limit=limit,
        window=window,
        web_fetcher=web_fetcher,
    )


def parse_antigravity_changelog(content: str) -> tuple[ChangelogEntry, ...]:
    """Parse all product panels from the server-rendered Antigravity changelog."""
    parser = HTMLParser(content)
    entries: list[ChangelogEntry] = []
    for panel in parser.css("[data-list-panel]"):
        product_key = str(panel.attributes.get("data-list-panel") or "")
        product_label = _PRODUCT_LABELS.get(product_key)
        if product_label is None:
            continue
        entries.extend(_panel_entries(panel, product_key=product_key, product_label=product_label))
    if not entries:
        msg = "Antigravity changelog produced no release entries"
        raise ValueError(msg)
    return tuple(
        sorted(entries, key=lambda entry: (entry.occurred_at, entry.entry_id), reverse=True)
    )


def _panel_entries(
    panel: Node,
    *,
    product_key: str,
    product_label: str,
) -> list[ChangelogEntry]:
    entries: list[ChangelogEntry] = []
    for row in panel.css("[data-section-row]"):
        version_node = row.css_first("a.version-link")
        title_node = row.css_first("[data-h3-pin]")
        date_container = row.css_first("[data-date-pin]")
        if version_node is None or title_node is None or date_container is None:
            continue
        version = _clean_text(version_node.text(separator=" ", strip=True))
        release_title = _clean_text(title_node.text(separator=" ", strip=True))
        href = str(version_node.attributes.get("href") or "")
        date_match = _DISPLAY_DATE_PATTERN.search(
            _clean_text(date_container.text(separator=" ", strip=True))
        )
        if not version or not release_title or not href or date_match is None:
            continue
        entries.append(
            ChangelogEntry(
                entry_id=f"{product_key}:{version}",
                title=f"{product_label} {version}: {release_title}",
                occurred_at=datetime.strptime(date_match.group(0), "%B %d, %Y").replace(tzinfo=UTC),
                body=_release_body(row, fallback=release_title),
                link=urljoin(ANTIGRAVITY_BASE_URL, href),
            )
        )
    return entries


def _release_body(row: Node, *, fallback: str) -> str:
    content = row.css_first("[data-content-ref]")
    if content is None:
        return fallback
    parts: list[str] = []
    lead = content.css_first(".changes")
    if lead is not None:
        lead_text = _clean_text(lead.text(separator=" ", strip=True))
        if lead_text:
            parts.append(lead_text)
    for details in content.css("details"):
        summary = details.css_first("summary")
        items = [
            _clean_text(item.text(separator=" ", strip=True))
            for item in details.css("li")
            if _clean_text(item.text(separator=" ", strip=True))
        ]
        if not items:
            continue
        heading = _clean_text(summary.text(separator=" ", strip=True)) if summary else "Changes"
        parts.extend((heading, *(f"- {item}" for item in items)))
    return "\n".join(parts) or fallback


def _clean_text(value: str) -> str:
    return " ".join(value.split())
