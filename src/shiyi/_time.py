"""Datetime helpers for Shiyi's stable storage/export contracts."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_isoformat(value: datetime) -> str:
    """Return a canonical UTC ISO-8601 string for a timezone-aware datetime."""
    if value.tzinfo is None or value.utcoffset() is None:
        msg = "datetime must be timezone-aware"
        raise ValueError(msg)
    return value.astimezone(UTC).isoformat()


def datetime_from_isoformat(value: str) -> datetime:
    """Parse an ISO-8601 datetime string and return the same instant in UTC."""
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        msg = "datetime string must include a timezone offset"
        raise ValueError(msg)
    return parsed.astimezone(UTC)
