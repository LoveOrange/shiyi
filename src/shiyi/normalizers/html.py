"""HTML/text to canonical Markdown normalizer."""

from __future__ import annotations

from markdownify import markdownify as markdownify_html
from selectolax.parser import HTMLParser

from shiyi.domain.models import ArtifactWrite, InternalItem


class HtmlMarkdownNormalizer:
    """Converts HTML and text capture payloads into canonical Markdown artifacts."""

    name = "html-markdown-normalizer"

    async def normalize(self, event: InternalItem) -> ArtifactWrite | None:
        """Normalize text-like payloads to Markdown and leave binary payloads unchanged."""
        if event.payload.type == "text":
            return ArtifactWrite(
                kind="normalized",
                media_type="text/markdown",
                content=f"{event.payload.text.strip()}\n".encode(),
                suggested_name=f"{event.id}.md",
                metadata={"normalizer": self.name},
            )
        if event.payload.type != "html":
            return None

        cleaned_html = _extract_main_html(event.payload.html)
        markdown = markdownify_html(cleaned_html, heading_style="ATX").strip()
        if not markdown:
            markdown = markdownify_html(event.payload.html, heading_style="ATX").strip()

        return ArtifactWrite(
            kind="normalized",
            media_type="text/markdown",
            content=f"{markdown}\n".encode(),
            suggested_name=f"{event.id}.md",
            metadata={"normalizer": self.name},
        )


def _extract_main_html(html: str) -> str:
    parser = HTMLParser(html)
    for selector in ("article", "main", "body"):
        node = parser.css_first(selector)
        if node is not None and node.html is not None:
            return node.html
    return html
