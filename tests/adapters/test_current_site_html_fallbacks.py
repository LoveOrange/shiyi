from datetime import UTC, datetime

from shiyi.adapters.changelog import (
    parse_cohere_blog_detail,
    parse_cohere_blog_index,
    parse_deepseek_news_index,
    parse_gemini_api_changelog,
    parse_mistral_news_detail,
    parse_mistral_news_index,
)


def test_mistral_rendered_news_card_fallback() -> None:
    index = """
    <a href="/news/robostral-navigate/" class="group/news border">
      <span><p>Research</p></span>
      <h2>Introducing Robostral Navigate</h2>
      <p>Our first model built for embodied navigation.</p>
      <footer><p>July 8, 2026</p><p>By Mistral AI</p></footer>
    </a>
    """

    [entry] = parse_mistral_news_index(index)

    assert entry.entry_id == "robostral-navigate"
    assert entry.occurred_at == datetime(2026, 7, 8, tzinfo=UTC)
    assert entry.link == "https://mistral.ai/news/robostral-navigate/"
    assert entry.fallback_body == "Our first model built for embodied navigation."

    detail = parse_mistral_news_detail(
        """
        <meta property="og:title" content="Introducing Robostral Navigate | Mistral AI">
        <article>Introducing Robostral Navigate\nNavigation article body.</article>
        """,
        entry,
    )
    assert detail.complete is True
    assert "Navigation article body" in detail.body


def test_cohere_rendered_blog_card_and_article_fallback() -> None:
    index = """
    <a class="flex flex-1 flex-col" href="/blog/the-total-cost-of-ai-ownership">
      <p>The total cost of AI ownership</p>
      <span><p>Jul 15, 2026</p><p>10 min read</p></span>
    </a>
    """

    [entry] = parse_cohere_blog_index(index)

    assert entry.entry_id == "the-total-cost-of-ai-ownership"
    assert entry.occurred_at == datetime(2026, 7, 15, tzinfo=UTC)
    assert entry.link == "https://cohere.com/blog/the-total-cost-of-ai-ownership"

    detail = parse_cohere_blog_detail(
        """
        <h1>The total cost of AI ownership</h1>
        <p class="blog-header-description">A practical guide to AI costs.</p>
        <article><div class="portable-text-breaks">
          <p>Rendered Cohere article body.</p><h2>AI costs</h2>
        </div></article>
        """,
        entry,
    )
    assert detail.complete is True
    assert detail.occurred_at is None
    assert detail.body == "Rendered Cohere article body.\nAI costs"
    assert detail.summary == "A practical guide to AI costs."


def test_deepseek_index_ignores_pagination_link_from_last_dated_block() -> None:
    entries = parse_deepseek_news_index(
        """
        <h2>Date: 2024-07-25</h2><h3>New API Features</h3>
        <p><a href="/news/news0725">Read the news</a></p>
        <h2>Date: 2024-05-17</h2><h3>deepseek-chat</h3><p>Model update.</p>
        <nav class="pagination-nav"><a href="/news/news0725">Previous</a></nav>
        """
    )

    assert [entry.link for entry in entries] == ["https://api-docs.deepseek.com/news/news0725"]


def test_gemini_changelog_uses_stable_date_title() -> None:
    [entry] = parse_gemini_api_changelog(
        """
        ## July 6, 2026

        - Added `gemini-4-preview` with a very long explanatory sentence.
        """
    )

    assert entry.title == "Gemini API updates — 2026-07-06"
