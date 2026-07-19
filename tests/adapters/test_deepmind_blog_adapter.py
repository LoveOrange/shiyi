import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from shiyi import CaptureWindow, Source, SourceItem
from shiyi.adapters.deepmind import deepmind_blog_adapter
from shiyi.domain.models import HtmlPayload
from shiyi.fetchers.fake import FakeRssFetcher, FakeWebFetcher
from shiyi.ports.fetcher import RssEntry, RssFeed

FIXTURE_ROOT = Path(__file__).parents[1] / "fixtures" / "deepmind-blog"
DEEPMIND_RSS_URL = "https://deepmind.google/blog/rss.xml"
ALPHAEVOLVE_URL = "https://deepmind.google/blog/alphaevolve-impact/"
OLD_URL = "https://deepmind.google/blog/old-out-of-window/"
SECOND_URL = "https://deepmind.google/blog/second-in-window/"
FETCHED_AT = datetime(2026, 5, 14, 8, 30, tzinfo=UTC)


def test_deepmind_blog_adapter_emits_article_scoped_complete_payload() -> None:
    rss_fetcher = FakeRssFetcher(
        {
            DEEPMIND_RSS_URL: RssFeed.model_validate_json(
                (FIXTURE_ROOT / "raw" / "feed.json").read_text()
            )
        }
    )
    web_fetcher = FakeWebFetcher(
        {ALPHAEVOLVE_URL: (FIXTURE_ROOT / "raw" / "alphaevolve-impact.html").read_text()},
        fetched_at=FETCHED_AT,
    )
    adapter = deepmind_blog_adapter(
        limit=1,
        rss_fetcher=rss_fetcher,
        web_fetcher=web_fetcher,
    )

    items = asyncio.run(_collect_items(adapter.capture(_source())))

    assert rss_fetcher.calls == [DEEPMIND_RSS_URL]
    assert [call.url for call in web_fetcher.calls] == [ALPHAEVOLVE_URL]
    assert len(items) == 1
    item = items[0]
    assert item.source_id == "deepmind-blog"
    assert item.source_item_id == "alphaevolve-impact"
    assert str(item.canonical_url) == ALPHAEVOLVE_URL
    assert item.metadata["is_complete"] is True
    assert item.summary is not None
    assert (
        item.metadata["title"]
        == "AlphaEvolve: How our Gemini-powered coding agent is scaling impact across fields"
    )
    assert isinstance(item.payload, HtmlPayload)
    payload_html = item.payload.html
    assert "Driving social impact and sustainability" in payload_html
    assert "Improving AI infrastructure" in payload_html
    assert "Related posts" not in payload_html
    assert "Explore our next generation AI systems" not in payload_html
    assert "Your browser does not support the video tag" not in payload_html


def test_deepmind_blog_source_item_identity_is_stable_per_canonical_url() -> None:
    feed = RssFeed(
        url=DEEPMIND_RSS_URL,
        fetched_at=FETCHED_AT,
        entries=(
            _entry(
                entry_id=ALPHAEVOLVE_URL,
                title="AlphaEvolve",
                link=ALPHAEVOLVE_URL,
                published_at=datetime(2026, 5, 7, tzinfo=UTC),
            ),
            _entry(
                entry_id=SECOND_URL,
                title="Second DeepMind",
                link=SECOND_URL,
                published_at=datetime(2026, 5, 8, tzinfo=UTC),
            ),
        ),
    )
    adapter = deepmind_blog_adapter(
        rss_fetcher=FakeRssFetcher({DEEPMIND_RSS_URL: feed}),
        web_fetcher=FakeWebFetcher(
            {
                ALPHAEVOLVE_URL: (FIXTURE_ROOT / "raw" / "alphaevolve-impact.html").read_text(),
                SECOND_URL: _article_html(
                    url=SECOND_URL,
                    title="Second DeepMind Article",
                    body="Second article canonical body.",
                ),
            },
            fetched_at=FETCHED_AT,
        ),
    )

    items = asyncio.run(_collect_items(adapter.capture(_source())))

    expected_distinct_items = 2
    assert [item.source_item_id for item in items] == [
        "alphaevolve-impact",
        "second-in-window",
    ]
    assert len({item.source_item_id for item in items}) == expected_distinct_items


def test_deepmind_blog_missing_detail_url_fails_clearly() -> None:
    feed = RssFeed(
        url=DEEPMIND_RSS_URL,
        fetched_at=FETCHED_AT,
        entries=(
            RssEntry(
                entry_id="not-a-url",
                title="Missing detail URL",
                link=None,
                html="summary only",
                published_at=datetime(2026, 5, 7, tzinfo=UTC),
            ),
        ),
    )
    adapter = deepmind_blog_adapter(
        rss_fetcher=FakeRssFetcher({DEEPMIND_RSS_URL: feed}),
        web_fetcher=FakeWebFetcher({}, fetched_at=FETCHED_AT),
    )

    try:
        asyncio.run(_collect_items(adapter.capture(_source())))
    except ValueError as error:
        assert "DeepMind RSS entry missing canonical detail URL" in str(error)
    else:  # pragma: no cover - keeps the failure message explicit when the contract regresses.
        message = "expected missing detail URL to fail"
        raise AssertionError(message)


def test_deepmind_blog_window_and_limit_gate_detail_fetches() -> None:
    feed = RssFeed(
        url=DEEPMIND_RSS_URL,
        fetched_at=FETCHED_AT,
        entries=(
            _entry(
                entry_id=OLD_URL,
                title="Old out of window",
                link=OLD_URL,
                published_at=datetime(2026, 5, 5, tzinfo=UTC),
            ),
            _entry(
                entry_id=ALPHAEVOLVE_URL,
                title="AlphaEvolve",
                link=ALPHAEVOLVE_URL,
                published_at=datetime(2026, 5, 7, tzinfo=UTC),
            ),
            _entry(
                entry_id=SECOND_URL,
                title="Second in window but over limit",
                link=SECOND_URL,
                published_at=datetime(2026, 5, 8, tzinfo=UTC),
            ),
        ),
    )
    rss_fetcher = FakeRssFetcher({DEEPMIND_RSS_URL: feed})
    web_fetcher = FakeWebFetcher(
        {
            ALPHAEVOLVE_URL: (FIXTURE_ROOT / "raw" / "alphaevolve-impact.html").read_text(),
            OLD_URL: "<html><body>old should not be fetched</body></html>",
            SECOND_URL: "<html><body>second should not be fetched</body></html>",
        },
        fetched_at=FETCHED_AT,
    )
    adapter = deepmind_blog_adapter(
        rss_fetcher=rss_fetcher,
        web_fetcher=web_fetcher,
        window=CaptureWindow(
            since=datetime(2026, 5, 7, tzinfo=UTC),
            until=datetime(2026, 5, 9, tzinfo=UTC),
            max_items=1,
        ),
    )

    items = asyncio.run(_collect_items(adapter.capture(_source())))

    assert [item.source_item_id for item in items] == ["alphaevolve-impact"]
    assert rss_fetcher.calls == [DEEPMIND_RSS_URL]
    assert [call.url for call in web_fetcher.calls] == [ALPHAEVOLVE_URL]


def test_deepmind_external_product_redirect_keeps_feed_identity_and_is_not_ready() -> None:
    feed_url = "https://deepmind.google/blog/introducing-antigravity-2/"
    feed = RssFeed(
        url=DEEPMIND_RSS_URL,
        fetched_at=FETCHED_AT,
        entries=(
            RssEntry(
                entry_id=feed_url,
                title="Introducing Google Antigravity 2.0",
                link=feed_url,
                html="",
                published_at=datetime(2026, 7, 18, tzinfo=UTC),
            ),
        ),
    )
    adapter = deepmind_blog_adapter(
        rss_fetcher=FakeRssFetcher({DEEPMIND_RSS_URL: feed}),
        web_fetcher=FakeWebFetcher(
            {
                feed_url: """
                <html><head><link rel="canonical" href="https://antigravity.google/"></head>
                <body><main><h1>Google Antigravity</h1><p>Product landing page.</p></main></body>
                </html>
                """
            },
            fetched_at=FETCHED_AT,
        ),
    )

    [item] = asyncio.run(_collect_items(adapter.capture(_source())))

    assert item.source_item_id == "introducing-antigravity-2"
    assert str(item.canonical_url) == "https://antigravity.google/"
    assert item.metadata["title"] == "Introducing Google Antigravity 2.0"
    assert item.metadata["is_complete"] is False


def _entry(*, entry_id: str, title: str, link: str, published_at: datetime) -> RssEntry:
    return RssEntry(
        entry_id=entry_id,
        title=title,
        link=link,
        html="summary only",
        summary_html="summary only",
        published_at=published_at,
    )


def _article_html(*, url: str, title: str, body: str) -> str:
    return f"""
    <html>
      <head>
        <link rel="canonical" href="{url}">
        <script type="application/ld+json">
          {{
            "@type": "BlogPosting",
            "mainEntityOfPage": {{"url": "{url}"}},
            "headline": "{title}",
            "datePublished": "2026-05-08T00:00:00+00:00"
          }}
        </script>
      </head>
      <body>
        <main id="page-content">
          <section class="section-cover"><h1>{title}</h1></section>
          <section><p>{body}</p></section>
        </main>
      </body>
    </html>
    """


async def _collect_items(events: AsyncIterator[SourceItem]) -> list[SourceItem]:
    return [event async for event in events]


def _source() -> Source:
    return Source(
        id="deepmind-blog",
        adapter="deepmind-blog-detail",
        target=DEEPMIND_RSS_URL,
        options={"content_kind": "article"},
    )
