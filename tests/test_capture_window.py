from datetime import UTC, datetime

from shiyi.domain.models import CaptureWindow


def test_capture_window_is_since_inclusive_until_exclusive() -> None:
    window = CaptureWindow(
        since=datetime(2026, 5, 12, tzinfo=UTC),
        until=datetime(2026, 5, 13, tzinfo=UTC),
    )

    assert window.includes(datetime(2026, 5, 12, tzinfo=UTC))
    assert window.includes(datetime(2026, 5, 12, 12, tzinfo=UTC))
    assert not window.includes(datetime(2026, 5, 13, tzinfo=UTC))
    assert not window.includes(datetime(2026, 5, 11, 23, 59, tzinfo=UTC))


def test_capture_window_without_date_filters_allows_unknown_dates() -> None:
    assert CaptureWindow(max_items=10).includes(None)
    assert not CaptureWindow(since=datetime(2026, 5, 12, tzinfo=UTC)).includes(None)
