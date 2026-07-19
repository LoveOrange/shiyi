"""Raw and large content Blob storage port."""

from __future__ import annotations

from typing import Protocol

from shiyi.domain.models import BlobRef


class BlobStore(Protocol):
    """Stores content-addressed raw, large, or cold bytes."""

    async def put(self, content: bytes, *, media_type: str) -> BlobRef:
        """Persist bytes and return a stable content-addressed reference."""
        ...

    async def get(self, ref: BlobRef) -> bytes:
        """Read bytes by reference."""
        ...

    async def exists(self, ref: BlobRef) -> bool:
        """Return whether referenced bytes exist."""
        ...
