import os
from collections.abc import Callable, Sequence

import httpx
import pytest

from shiyi.adapters.anthropic import ANTHROPIC_NEWS_URL, _extract_article_urls
from shiyi.adapters.antigravity import (
    ANTIGRAVITY_CHANGELOG_URL,
    parse_antigravity_changelog,
)
from shiyi.adapters.cn_official import (
    BIGMODEL_RELEASES_URL,
    KIMI_CODE_CHANGELOG_URL,
    KIMI_RESEARCH_URL,
    MINIMAX_API_UPDATES_URL,
    MINIMAX_MODEL_RELEASES_URL,
    QWEN_CODE_BLOG_URL,
    QWEN_MODEL_RELEASES_URL,
    parse_bigmodel_releases,
    parse_kimi_code_changelog,
    parse_kimi_research_index,
    parse_minimax_api_updates,
    parse_minimax_model_releases,
    parse_qwen_code_blog_index,
    parse_qwen_model_releases,
)
from shiyi.adapters.github_releases import (
    github_releases_api_url,
    parse_github_releases,
)

HTTP_OK = 200
CN_SOURCE_CASES: tuple[tuple[str, Callable[[str], Sequence[object]]], ...] = (
    (KIMI_RESEARCH_URL, parse_kimi_research_index),
    (KIMI_CODE_CHANGELOG_URL, parse_kimi_code_changelog),
    (QWEN_MODEL_RELEASES_URL, parse_qwen_model_releases),
    (QWEN_CODE_BLOG_URL, parse_qwen_code_blog_index),
    (BIGMODEL_RELEASES_URL, parse_bigmodel_releases),
    (MINIMAX_MODEL_RELEASES_URL, parse_minimax_model_releases),
    (MINIMAX_API_UPDATES_URL, parse_minimax_api_updates),
)
HARNESS_RELEASE_URLS = (
    github_releases_api_url("openclaw/openclaw"),
    github_releases_api_url("NousResearch/hermes-agent"),
    github_releases_api_url("deepseek-ai/deepseek-harness"),
    github_releases_api_url("openai/codex"),
    github_releases_api_url("anthropics/claude-code"),
)


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


@pytest.mark.skipif(
    os.getenv("SHIYI_RUN_LIVE_TESTS") != "1",
    reason="live public source smoke tests are opt-in",
)
@pytest.mark.parametrize(("url", "parser"), CN_SOURCE_CASES)
def test_cn_official_source_contract_is_live(
    url: str, parser: Callable[[str], Sequence[object]]
) -> None:
    response = httpx.get(url, follow_redirects=True, timeout=30)

    assert response.status_code == HTTP_OK
    assert parser(response.text)


@pytest.mark.skipif(
    os.getenv("SHIYI_RUN_LIVE_TESTS") != "1",
    reason="live public source smoke tests are opt-in",
)
@pytest.mark.parametrize("url", HARNESS_RELEASE_URLS)
def test_official_harness_github_releases_are_live(url: str) -> None:
    response = httpx.get(
        url,
        follow_redirects=True,
        timeout=30,
        headers={"user-agent": "Shiyi live source test"},
    )

    assert response.status_code == HTTP_OK
    assert parse_github_releases(response.text)


@pytest.mark.skipif(
    os.getenv("SHIYI_RUN_LIVE_TESTS") != "1",
    reason="live public source smoke tests are opt-in",
)
def test_google_antigravity_changelog_is_live() -> None:
    response = httpx.get(ANTIGRAVITY_CHANGELOG_URL, follow_redirects=True, timeout=30)

    assert response.status_code == HTTP_OK
    assert parse_antigravity_changelog(response.text)
