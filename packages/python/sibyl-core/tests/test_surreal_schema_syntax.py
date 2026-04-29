"""Regression checks for SurrealDB schema syntax accepted by the server parser."""

from __future__ import annotations

from sibyl_core.backends.surreal.auth_schema import AUTH_SCHEMA_DEFINITIONS
from sibyl_core.backends.surreal.content_schema import CONTENT_SCHEMA_DEFINITIONS
from sibyl_core.backends.surreal.schema import EDGE_DEFINITIONS, NODE_DEFINITIONS


def test_flexible_object_fields_keep_server_accepted_token_order() -> None:
    schema = "\n".join(
        (
            AUTH_SCHEMA_DEFINITIONS,
            CONTENT_SCHEMA_DEFINITIONS,
            NODE_DEFINITIONS,
            EDGE_DEFINITIONS,
        )
    )

    assert "FLEXIBLE TYPE object" not in schema
    assert "TYPE object FLEXIBLE" in schema
