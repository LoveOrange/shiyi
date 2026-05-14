import asyncio
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
import respx

from shiyi.fetchers.fake import FakeWebFetcher
from shiyi.fetchers.http import HttpRssFetcher, HttpSitemapFetcher, HttpWebFetcher
from shiyi.ports.fetcher import FetcherError, FetchErrorKind


async def _skip_retry_sleep(delay: float) -> None:
    assert delay >= 0


def test_http_web_fetcher_returns_fetch_result_with_provenance_fields() -> None:
    ok_status = 200
    with respx.mock:
        respx.get("https://example.com/page").mock(
            return_value=httpx.Response(
                ok_status, text="hello", headers={"content-type": "text/plain"}
            )
        )
        result = asyncio.run(HttpWebFetcher().fetch("https://example.com/page"))

    assert str(result.url) == "https://example.com/page"
    assert result.status_code == ok_status
    assert result.content == "hello"
    assert result.content_type == "text/plain"
    assert result.fetched_at.tzinfo is UTC
    assert result.from_cache is False
    assert result.raw_cache_path is None


def test_http_web_fetcher_reuses_adapter_defined_raw_cache(tmp_path: Path) -> None:
    cache_root = tmp_path
    route_calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal route_calls
        route_calls += 1
        return httpx.Response(200, text=f"remote-{route_calls}")

    with respx.mock:
        respx.get("https://example.com/article").mock(side_effect=handler)
        fetcher = HttpWebFetcher(raw_cache_root=cache_root)
        first = asyncio.run(
            fetcher.fetch("https://example.com/article", source="example", raw_key="abc123")
        )
        second = asyncio.run(
            fetcher.fetch("https://example.com/article", source="example", raw_key="abc123")
        )

    expected_path = cache_root / "example" / "abc123" / "raw.html"
    assert first.content == "remote-1"
    assert first.from_cache is False
    assert first.raw_cache_path == expected_path
    assert second.content == "remote-1"
    assert second.from_cache is True
    assert second.raw_cache_path == expected_path
    assert route_calls == 1
    assert expected_path.read_text() == "remote-1"


def test_http_rss_fetcher_parses_multiple_entries_without_missing_records() -> None:
    feed = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>Example</title>
      <item>
        <guid>post-1</guid><title>First</title><link>https://example.com/1</link>
        <pubDate>Tue, 12 May 2026 00:00:00 GMT</pubDate>
        <description><![CDATA[<p>First summary</p>]]></description>
      </item>
      <item>
        <guid>post-2</guid><title>Second</title><link>https://example.com/2</link>
        <pubDate>Wed, 13 May 2026 00:00:00 GMT</pubDate>
        <description><![CDATA[<p>Second summary</p>]]></description>
      </item>
    </channel></rss>
    """
    with respx.mock:
        respx.get("https://example.com/rss.xml").mock(return_value=httpx.Response(200, text=feed))
        result = asyncio.run(HttpRssFetcher().fetch("https://example.com/rss.xml"))

    assert [entry.entry_id for entry in result.entries] == ["post-1", "post-2"]
    assert [entry.title for entry in result.entries] == ["First", "Second"]
    assert result.entries[0].html == "<p>First summary</p>"
    assert result.entries[1].published_at == datetime(2026, 5, 13, tzinfo=UTC)


def test_http_rss_fetcher_returns_empty_feed_collection() -> None:
    feed = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>Empty</title></channel></rss>
    """
    with respx.mock:
        respx.get("https://example.com/rss.xml").mock(return_value=httpx.Response(200, text=feed))
        result = asyncio.run(HttpRssFetcher().fetch("https://example.com/rss.xml"))

    assert result.entries == ()


def test_http_sitemap_fetcher_parses_multiple_entries_without_missing_records() -> None:
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/a</loc><lastmod>2026-05-12T00:00:00Z</lastmod></url>
      <url><loc>https://example.com/b</loc><lastmod>2026-05-13T00:00:00Z</lastmod></url>
    </urlset>
    """
    with respx.mock:
        respx.get("https://example.com/sitemap.xml").mock(
            return_value=httpx.Response(200, text=sitemap)
        )
        result = asyncio.run(HttpSitemapFetcher().fetch("https://example.com/sitemap.xml"))

    assert [str(entry.loc) for entry in result.entries] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert result.entries[0].lastmod == datetime(2026, 5, 12, tzinfo=UTC)
    assert result.entries[1].lastmod == datetime(2026, 5, 13, tzinfo=UTC)


def test_http_sitemap_fetcher_returns_empty_collection() -> None:
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>
    """
    with respx.mock:
        respx.get("https://example.com/sitemap.xml").mock(
            return_value=httpx.Response(200, text=sitemap)
        )
        result = asyncio.run(HttpSitemapFetcher().fetch("https://example.com/sitemap.xml"))

    assert result.entries == ()


def test_http_web_fetcher_retries_transient_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shiyi.fetchers.http.asyncio.sleep", _skip_retry_sleep)
    expected_call_count = 2
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(200, text="ok")

    with respx.mock:
        respx.get("https://example.com/retry").mock(side_effect=handler)
        result = asyncio.run(HttpWebFetcher(retries=1).fetch("https://example.com/retry"))

    assert result.content == "ok"
    assert calls == expected_call_count


def test_http_web_fetcher_maps_retryable_status_after_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shiyi.fetchers.http.asyncio.sleep", _skip_retry_sleep)
    service_unavailable = 503
    expected_call_count = 2
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(service_unavailable, text="temporarily unavailable")

    with respx.mock:
        respx.get("https://example.com/busy").mock(side_effect=handler)

        with pytest.raises(FetcherError) as error_info:
            asyncio.run(
                HttpWebFetcher(retries=1).fetch(
                    "https://example.com/busy",
                    source="example-source",
                )
            )

    assert calls == expected_call_count
    assert error_info.value.kind is FetchErrorKind.HTTP_STATUS
    assert error_info.value.status_code == service_unavailable
    assert error_info.value.url == "https://example.com/busy"
    assert error_info.value.source == "example-source"


def test_http_web_fetcher_does_not_retry_permanent_status_error() -> None:
    not_found = 404
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(not_found)

    with respx.mock:
        respx.get("https://example.com/missing").mock(side_effect=handler)

        with pytest.raises(FetcherError) as error_info:
            asyncio.run(
                HttpWebFetcher(retries=3).fetch(
                    "https://example.com/missing",
                    source="example-source",
                )
            )

    assert calls == 1
    assert error_info.value.kind is FetchErrorKind.HTTP_STATUS
    assert error_info.value.status_code == not_found
    assert error_info.value.url == "https://example.com/missing"
    assert error_info.value.source == "example-source"


def test_http_web_fetcher_maps_timeout_error() -> None:
    with respx.mock:
        respx.get("https://example.com/slow").mock(side_effect=httpx.TimeoutException("boom"))

        with pytest.raises(FetcherError) as error_info:
            asyncio.run(
                HttpWebFetcher(retries=0).fetch(
                    "https://example.com/slow",
                    source="example-source",
                )
            )

    assert error_info.value.kind is FetchErrorKind.TIMEOUT
    assert error_info.value.status_code is None
    assert error_info.value.source == "example-source"


def test_http_web_fetcher_maps_transport_error() -> None:
    with respx.mock:
        respx.get("https://example.com/broken").mock(side_effect=httpx.TransportError("boom"))

        with pytest.raises(FetcherError) as error_info:
            asyncio.run(
                HttpWebFetcher(retries=0).fetch(
                    "https://example.com/broken",
                    source="example-source",
                )
            )

    assert error_info.value.kind is FetchErrorKind.TRANSPORT
    assert error_info.value.status_code is None
    assert error_info.value.source == "example-source"


def test_fake_web_fetcher_records_adapter_call_shape() -> None:
    fetcher = FakeWebFetcher({"https://example.com/a": "alpha"})

    result = asyncio.run(fetcher.fetch("https://example.com/a", source="example", raw_key="abc"))

    assert result.content == "alpha"
    assert fetcher.calls[0].url == "https://example.com/a"
    assert fetcher.calls[0].source == "example"
    assert fetcher.calls[0].raw_key == "abc"


def test_fake_web_fetcher_error_keeps_source_context() -> None:
    fetcher = FakeWebFetcher({})

    with pytest.raises(FetcherError) as error_info:
        asyncio.run(fetcher.fetch("https://example.com/missing", source="example"))

    assert error_info.value.kind is FetchErrorKind.TRANSPORT
    assert error_info.value.url == "https://example.com/missing"
    assert error_info.value.source == "example"
