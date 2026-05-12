import os

import httpx
import pytest

from shiyi.adapters.anthropic import ANTHROPIC_NEWS_URL, _extract_article_urls


@pytest.mark.skipif(
    os.getenv("SHIYI_RUN_LIVE_TESTS") != "1",
    reason="live public source smoke tests are opt-in",
)
def test_anthropic_news_public_index_has_article_links() -> None:
    html = httpx.get(ANTHROPIC_NEWS_URL, follow_redirects=True, timeout=30).text
    urls = _extract_article_urls(html, ANTHROPIC_NEWS_URL, limit=3)

    assert len(urls) >= 1
    assert all(url.startswith("https://www.anthropic.com/news/") for url in urls)


@pytest.mark.skipif(
    os.getenv("SHIYI_RUN_LIVE_TESTS") != "1",
    reason="live public source smoke tests are opt-in",
)
def test_openai_news_public_rss_is_available() -> None:
    response = httpx.get("https://openai.com/news/rss.xml", follow_redirects=True, timeout=30)

    expected_status = 200
    rss_prefix_chars = 200
    assert response.status_code == expected_status
    assert "<rss" in response.text[:rss_prefix_chars].lower()
