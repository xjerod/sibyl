"""Active graph runtime helpers for higher-level service layers."""

from sibyl_core.services.legacy_graph import (
    ActiveGraphRuntime,
    LegacyGraphRuntime,
    count_entities_by_type,
    execute_graph_query,
    execute_legacy_graph_query,
    get_graph_client,
    get_graph_runtime,
    get_legacy_graph_client,
    get_legacy_graph_runtime,
)

__all__ = [
    "ActiveGraphRuntime",
    "LegacyGraphRuntime",
    "count_entities_by_type",
    "execute_graph_query",
    "execute_legacy_graph_query",
    "get_graph_client",
    "get_graph_runtime",
    "get_legacy_graph_client",
    "get_legacy_graph_runtime",
]
