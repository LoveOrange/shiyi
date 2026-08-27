"""MongoDB canonical ContentItem store."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from bson import BSON
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient

from shiyi.domain.models import ContentItem

MAX_CONTENT_ITEM_BSON_BYTES = 15 * 1024 * 1024


class MongoContentItemStore:
    """Persists canonical ContentItem documents with deterministic MongoDB `_id`."""

    def __init__(
        self,
        client: AsyncMongoClient[Mapping[str, Any]],
        *,
        database: str = "shiyi",
        collection: str = "content_items",
    ) -> None:
        """Create a store from one event-loop-scoped async Mongo client."""
        self._client = client
        self._collection = client[database][collection]

    @classmethod
    def from_uri(
        cls,
        uri: str,
        *,
        database: str = "shiyi",
        collection: str = "content_items",
    ) -> MongoContentItemStore:
        """Create a store and async client from a MongoDB connection URI."""
        client: AsyncMongoClient[Mapping[str, Any]] = AsyncMongoClient(uri)
        return cls(client, database=database, collection=collection)

    async def get(self, item_id: str) -> ContentItem | None:
        """Return one canonical item by deterministic id."""
        document = await self._collection.find_one({"_id": item_id})
        if document is None:
            return None
        return _content_item_from_document(document)

    async def upsert(self, item: ContentItem) -> None:
        """Replace or insert the complete canonical document."""
        document = _content_item_document(item)
        document_size = len(BSON.encode(document))
        if document_size > MAX_CONTENT_ITEM_BSON_BYTES:
            msg = (
                f"ContentItem {item.id} is {document_size} BSON bytes; "
                f"limit is {MAX_CONTENT_ITEM_BSON_BYTES}"
            )
            raise ValueError(msg)
        await self._collection.replace_one({"_id": item.id}, document, upsert=True)

    async def list_ready(
        self,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        source_ids: Sequence[str] = (),
        limit: int = 20,
    ) -> list[ContentItem]:
        """List ready canonical items for export or consumer reads."""
        if limit <= 0:
            return []
        query: dict[str, Any] = {"ready_at": {"$ne": None}}
        collected_at: dict[str, datetime] = {}
        if since is not None:
            collected_at["$gte"] = since
        if until is not None:
            collected_at["$lt"] = until
        if collected_at:
            query["collected_at"] = collected_at
        if source_ids:
            query["source_id"] = {"$in": list(source_ids)}

        cursor = self._collection.find(query).sort(
            [("published_at", DESCENDING), ("_id", ASCENDING)]
        )
        documents = await cursor.to_list(length=limit)
        return [_content_item_from_document(document) for document in documents]

    async def list_missing_summary(self, *, limit: int = 20) -> list[ContentItem]:
        """List newest ready canonical items that still need a summary."""
        if limit <= 0:
            return []
        query: dict[str, Any] = {
            "ready_at": {"$ne": None},
            "$or": [
                {"summary": {"$exists": False}},
                {"summary": None},
                {"summary": ""},
            ],
        }
        cursor = self._collection.find(query).sort(
            [("published_at", DESCENDING), ("_id", ASCENDING)]
        )
        documents = await cursor.to_list(length=limit)
        return [_content_item_from_document(document) for document in documents]

    async def ensure_indexes(self) -> None:
        """Create the initial Briefly query indexes."""
        await self._collection.create_index(
            [("source_id", ASCENDING), ("canonical_url", ASCENDING)],
            unique=True,
            partialFilterExpression={"canonical_url": {"$type": "string"}},
        )
        await self._collection.create_index([("published_at", DESCENDING), ("_id", ASCENDING)])
        await self._collection.create_index(
            [("source_id", ASCENDING), ("published_at", DESCENDING)]
        )
        await self._collection.create_index(
            [("categories", ASCENDING), ("published_at", DESCENDING)]
        )
        await self._collection.create_index([("tags", ASCENDING), ("published_at", DESCENDING)])
        await self._collection.create_index([("language", ASCENDING), ("published_at", DESCENDING)])
        await self._collection.create_index([("updated_at", ASCENDING), ("_id", ASCENDING)])

    async def close(self) -> None:
        """Close the owned async Mongo client."""
        await self._client.close()


def _content_item_document(item: ContentItem) -> dict[str, Any]:
    document = item.model_dump(mode="python")
    document["_id"] = document.pop("id")
    if item.canonical_url is not None:
        document["canonical_url"] = str(item.canonical_url)
    return document


def _content_item_from_document(document: Mapping[str, Any]) -> ContentItem:
    data = dict(document)
    data["id"] = str(data.pop("_id"))
    for field in ("published_at", "collected_at", "ready_at", "updated_at"):
        value = data.get(field)
        if isinstance(value, datetime):
            data[field] = (
                value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
            )
    return ContentItem.model_validate(data)
