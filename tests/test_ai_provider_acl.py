import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from shiyi import AIProviderACL, AIProviderRequest, ContentItem, content_item_id

NOW = datetime(2026, 7, 19, tzinfo=UTC)


class FakeProvider:
    name = "fake"

    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.requests: list[AIProviderRequest] = []

    async def complete(self, request: AIProviderRequest) -> dict[str, Any]:
        self.requests.append(request)
        return self.response


def test_acl_maps_provider_json_to_neutral_content_fields() -> None:
    first_item = _item("1")
    second_item = _item("2")
    provider = FakeProvider(
        {
            "items": [
                {
                    "id": first_item.id,
                    "language": "en",
                    "summary": "中立摘要",
                    "categories": ["AI"],
                    "tags": ["model"],
                },
                {
                    "id": second_item.id,
                    "language": "en",
                    "summary": "第二条摘要",
                    "categories": [],
                    "tags": [],
                },
            ]
        }
    )
    acl = AIProviderACL(provider, summary_language="zh")

    fields = asyncio.run(acl.process_many((first_item, second_item)))

    assert fields[first_item.id].summary == "中立摘要"
    assert fields[first_item.id].summary_language == "zh"
    assert fields[first_item.id].categories == ("AI",)
    assert fields[second_item.id].summary == "第二条摘要"
    assert len(provider.requests) == 1
    assert first_item.id in provider.requests[0].prompt
    assert second_item.id in provider.requests[0].prompt
    assert "untrusted data" in provider.requests[0].prompt


def test_acl_does_not_call_provider_when_summary_is_present() -> None:
    provider = FakeProvider({"items": []})
    acl = AIProviderACL(provider)

    fields = asyncio.run(acl.process_many((_item("1", summary="Source summary"),)))

    assert fields == {}
    assert provider.requests == []


def test_acl_rejects_provider_results_for_unrequested_ids() -> None:
    provider = FakeProvider(
        {
            "items": [
                {
                    "id": "unexpected",
                    "language": "en",
                    "summary": "摘要",
                    "categories": [],
                    "tags": [],
                }
            ]
        }
    )
    acl = AIProviderACL(provider)

    with pytest.raises(ValueError, match="response ids"):
        asyncio.run(acl.process_many((_item("1"),)))


def _item(source_item_id: str, *, summary: str | None = None) -> ContentItem:
    return ContentItem(
        id=content_item_id(source_id="source", source_item_id=source_item_id),
        source_id="source",
        source_item_id=source_item_id,
        kind="article",
        title=f"Article {source_item_id}",
        collected_at=NOW,
        content="Untrusted article content.",
        summary=summary,
        content_hash="a" * 64,
        ready_at=NOW,
        updated_at=NOW,
    )
