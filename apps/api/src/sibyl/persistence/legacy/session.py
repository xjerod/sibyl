"""Legacy relational session scope."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager


@asynccontextmanager
async def get_legacy_session() -> AsyncGenerator[object]:
    from sibyl.db.connection import get_session

    async with get_session() as session:
        yield session
