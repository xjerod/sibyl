from __future__ import annotations

import os
from contextlib import suppress
from uuid import uuid4

import pytest

from sibyl_core.models.entities import Entity, EntityType
from sibyl_core.services.native_graph import (
    NativeEntityManager,
    NativeSurrealGraphClient,
    prepare_native_graph_schema,
)

pytestmark = pytest.mark.skipif(
    os.environ.get("SIBYL_LIVE_SURREAL_TESTS") != "1",
    reason="live SurrealDB runtime smoke tests are disabled",
)


@pytest.mark.asyncio
async def test_live_surreal_server_round_trips_native_entity() -> None:
    group_id = str(uuid4())
    entity_id = f"nightly-{uuid4().hex}"
    client = NativeSurrealGraphClient(
        group_id=group_id,
        url=os.environ.get("SIBYL_SURREAL_URL", "memory://"),
        username=os.environ.get("SIBYL_SURREAL_USERNAME", ""),
        password=os.environ.get("SIBYL_SURREAL_PASSWORD", ""),
    )
    manager = NativeEntityManager(client, group_id=group_id)

    try:
        await prepare_native_graph_schema(client)
        await manager.create_direct(
            Entity(
                id=entity_id,
                entity_type=EntityType.PATTERN,
                name="Nightly Surreal runtime",
                description="SurrealDB server smoke test",
                organization_id=group_id,
                metadata={"runtime": "surreal"},
            )
        )

        fetched = await manager.get(entity_id)

        assert fetched.id == entity_id
        assert fetched.organization_id == group_id
        assert fetched.metadata["runtime"] == "surreal"
    finally:
        with suppress(Exception):
            await manager.delete(entity_id)
        await client.close()
