from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, cast

from pymongo import AsyncMongoClient

from shiyi import ContentItem, content_item_id
from shiyi.stores.mongo import MongoContentItemStore

NOW = datetime(2026, 7, 19, tzinfo=UTC)


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self._documents = documents

    def sort(self, _keys: object) -> FakeCursor:
        return self

    async def to_list(self, *, length: int) -> list[dict[str, Any]]:
        return self._documents[:length]


class FakeCollection:
    def __init__(self) -> None:
        self.documents: dict[str, dict[str, Any]] = {}
        self.indexes: list[tuple[object, dict[str, object]]] = []
        self.queries: list[dict[str, object]] = []

    async def find_one(self, query: Mapping[str, object]) -> dict[str, Any] | None:
        return self.documents.get(str(query["_id"]))

    async def replace_one(
        self,
        query: Mapping[str, object],
        document: Mapping[str, Any],
        *,
        upsert: bool,
    ) -> None:
        assert upsert is True
        self.documents[str(query["_id"])] = dict(document)

    def find(self, query: Mapping[str, object]) -> FakeCursor:
        self.queries.append(dict(query))
        return FakeCursor(list(self.documents.values()))

    async def create_index(self, keys: object, **options: object) -> None:
        self.indexes.append((keys, options))


class FakeDatabase:
    def __init__(self, collection: FakeCollection) -> None:
        self._collection = collection

    def __getitem__(self, _name: str) -> FakeCollection:
        return self._collection


class FakeClient:
    def __init__(self) -> None:
        self.collection = FakeCollection()

    def __getitem__(self, _name: str) -> FakeDatabase:
        return FakeDatabase(self.collection)

    async def close(self) -> None:
        return None


def test_mongo_store_maps_content_id_to_mongo_id_and_round_trips() -> None:
    client = FakeClient()
    store = _store(client)
    item = _item()

    asyncio.run(store.upsert(item))
    loaded = asyncio.run(store.get(item.id))

    assert client.collection.documents[item.id]["_id"] == item.id
    assert "id" not in client.collection.documents[item.id]
    assert loaded == item


def test_mongo_store_restores_utc_to_naive_bson_datetimes() -> None:
    client = FakeClient()
    store = _store(client)
    item = _item()
    asyncio.run(store.upsert(item))
    client.collection.documents[item.id]["published_at"] = NOW.replace(tzinfo=None)
    client.collection.documents[item.id]["collected_at"] = NOW.replace(tzinfo=None)
    client.collection.documents[item.id]["ready_at"] = NOW.replace(tzinfo=None)
    client.collection.documents[item.id]["updated_at"] = NOW.replace(tzinfo=None)

    loaded = asyncio.run(store.get(item.id))

    assert loaded == item


def test_mongo_indexes_keep_categories_and_tags_separate() -> None:
    client = FakeClient()
    store = _store(client)

    asyncio.run(store.ensure_indexes())

    category_indexes = [index for index in client.collection.indexes if "categories" in repr(index)]
    tag_indexes = [index for index in client.collection.indexes if "tags" in repr(index)]
    assert len(category_indexes) == 1
    assert len(tag_indexes) == 1
    assert "tags" not in repr(category_indexes[0])
    assert "categories" not in repr(tag_indexes[0])
    canonical_indexes = [
        index for index in client.collection.indexes if "canonical_url" in repr(index)
    ]
    assert len(canonical_indexes) == 1
    assert canonical_indexes[0][1]["unique"] is True


def test_mongo_store_selects_ready_items_with_missing_summary() -> None:
    client = FakeClient()
    store = _store(client)
    item = _item()
    asyncio.run(store.upsert(item))

    loaded = asyncio.run(store.list_missing_summary(limit=5))

    assert loaded == [item]
    assert client.collection.queries == [
        {
            "ready_at": {"$ne": None},
            "$or": [
                {"summary": {"$exists": False}},
                {"summary": None},
                {"summary": ""},
            ],
        }
    ]


def _store(client: FakeClient) -> MongoContentItemStore:
    typed_client = cast(AsyncMongoClient[Mapping[str, Any]], cast(object, client))
    return MongoContentItemStore(typed_client)


def _item() -> ContentItem:
    return ContentItem(
        id=content_item_id(source_id="openai-news", source_item_id="1"),
        source_id="openai-news",
        source_item_id="1",
        kind="article",
        canonical_url="https://openai.com/news/1",
        title="News",
        published_at=NOW,
        collected_at=NOW,
        content="News body\n",
        content_hash="a" * 64,
        ready_at=NOW,
        updated_at=NOW,
    )
