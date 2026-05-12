import asyncio
from pathlib import Path

import httpx
import respx

from shiyi.fetchers.http import HttpRssFetcher, HttpSitemapFetcher, HttpWebFetcher


def test_http_web_fetcher_returns_fetch_result() -> None:
    with respx.mock:
        respx.get("https://example.com/page").mock(
            return_value=httpx.Response(200, text="hello", headers={"content-type": "text/plain"})
        )
        result = asyncio.run(HttpWebFetcher().fetch("https://example.com/page"))

    assert str(result.url) == "https://example.com/page"
    assert result.content == "hello"
    assert result.content_type == "text/plain"


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

    assert first.content == "remote-1"
    assert first.from_cache is False
    assert second.content == "remote-1"
    assert second.from_cache is True
    assert route_calls == 1
    assert (cache_root / "example" / "abc123" / "raw.html").read_text() == "remote-1"


def test_http_rss_fetcher_parses_entries() -> None:
    feed = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><item>
      <guid>post-1</guid><title>Hello</title><link>https://example.com/1</link>
      <pubDate>Tue, 12 May 2026 00:00:00 GMT</pubDate>
      <description><![CDATA[<p>Summary</p>]]></description>
    </item></channel></rss>
    """
    with respx.mock:
        respx.get("https://example.com/rss.xml").mock(return_value=httpx.Response(200, text=feed))
        result = asyncio.run(HttpRssFetcher().fetch("https://example.com/rss.xml"))

    assert len(result.entries) == 1
    assert result.entries[0].entry_id == "post-1"
    assert result.entries[0].published_at is not None


def test_http_sitemap_fetcher_parses_lastmod() -> None:
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/a</loc><lastmod>2026-05-12T00:00:00Z</lastmod></url>
    </urlset>
    """
    with respx.mock:
        respx.get("https://example.com/sitemap.xml").mock(
            return_value=httpx.Response(200, text=sitemap)
        )
        result = asyncio.run(HttpSitemapFetcher().fetch("https://example.com/sitemap.xml"))

    assert len(result.entries) == 1
    assert str(result.entries[0].loc) == "https://example.com/a"
    assert result.entries[0].lastmod is not None
