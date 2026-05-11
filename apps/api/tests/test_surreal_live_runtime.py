from __future__ import annotations

import os
from contextlib import suppress
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from graphiti_core.nodes import EntityNode

from sibyl_core.backends.surreal import SurrealDriver
from sibyl_core.graph.surreal.ops.entity_node_ops import SurrealEntityNodeOperations

pytestmark = pytest.mark.skipif(
    os.environ.get("SIBYL_LIVE_SURREAL_TESTS") != "1",
    reason="live SurrealDB runtime smoke tests are disabled",
)


@pytest.mark.asyncio
async def test_live_surreal_server_round_trips_graph_entity() -> None:
    group_id = str(uuid4())
    entity_id = f"nightly-{uuid4().hex}"
    driver = SurrealDriver(
        os.environ.get("SIBYL_SURREAL_URL", "memory://"),
        username=os.environ.get("SIBYL_SURREAL_USERNAME", ""),
        password=os.environ.get("SIBYL_SURREAL_PASSWORD", ""),
    ).clone(group_id)
    ops = SurrealEntityNodeOperations()

    try:
        await driver.build_indices_and_constraints(delete_existing=True)
        await ops.save(
            driver,
            EntityNode(
                uuid=entity_id,
                name="Nightly Surreal runtime",
                group_id=group_id,
                summary="SurrealDB server smoke test",
                labels=["Pattern"],
                attributes={"runtime": "surreal"},
                created_at=datetime.now(UTC).replace(tzinfo=None),
            ),
        )

        fetched = await ops.get_by_uuid(driver, entity_id)

        assert fetched.uuid == entity_id
        assert fetched.group_id == group_id
        assert fetched.attributes == {"runtime": "surreal"}
    finally:
        with suppress(Exception):
            await ops.delete_by_group_id(driver, group_id)
        await driver.close()
