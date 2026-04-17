"""Legacy persistence adapters for the Postgres and FalkorDB runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sibyl.persistence.legacy.auth import (
        InvalidAuthClaimsError,
        LegacyAuthContextResolver,
        LegacyOrganizationMembershipRepository,
        LegacyOrganizationRepository,
        LegacySessionRepository,
        LegacyUserRepository,
        UserNotFoundError,
    )
    from sibyl.persistence.legacy.graph import (
        LegacyEntityStore,
        LegacyGraphStore,
        LegacyKnowledgeReadAdapter,
        LegacyKnowledgeWriteAdapter,
        LegacyRelationshipStore,
        LegacySearchIndex,
        ensure_legacy_graph_indexes,
        execute_legacy_debug_query,
        get_legacy_graph_stats_payload,
        get_legacy_knowledge_read_adapter,
        graph_stats_payload,
        reset_legacy_graph_runtime,
    )

__all__ = [
    "InvalidAuthClaimsError",
    "LegacyAuthContextResolver",
    "LegacyOrganizationMembershipRepository",
    "LegacyOrganizationRepository",
    "LegacySessionRepository",
    "LegacyUserRepository",
    "LegacyEntityStore",
    "LegacyGraphStore",
    "LegacyKnowledgeReadAdapter",
    "LegacyKnowledgeWriteAdapter",
    "LegacyRelationshipStore",
    "LegacySearchIndex",
    "ensure_legacy_graph_indexes",
    "execute_legacy_debug_query",
    "get_legacy_graph_stats_payload",
    "get_legacy_knowledge_read_adapter",
    "graph_stats_payload",
    "reset_legacy_graph_runtime",
    "UserNotFoundError",
]


def __getattr__(name: str) -> Any:
    if name in set(__all__):
        from sibyl.persistence.legacy.auth import (
            InvalidAuthClaimsError,
            LegacyAuthContextResolver,
            LegacyOrganizationMembershipRepository,
            LegacyOrganizationRepository,
            LegacySessionRepository,
            LegacyUserRepository,
            UserNotFoundError,
        )

        exports = {
            "InvalidAuthClaimsError": InvalidAuthClaimsError,
            "LegacyAuthContextResolver": LegacyAuthContextResolver,
            "LegacyOrganizationMembershipRepository": LegacyOrganizationMembershipRepository,
            "LegacyOrganizationRepository": LegacyOrganizationRepository,
            "LegacySessionRepository": LegacySessionRepository,
            "LegacyUserRepository": LegacyUserRepository,
            "UserNotFoundError": UserNotFoundError,
        }
        if name in {
            "ensure_legacy_graph_indexes",
            "execute_legacy_debug_query",
            "LegacyEntityStore",
            "LegacyGraphStore",
            "LegacyKnowledgeReadAdapter",
            "LegacyKnowledgeWriteAdapter",
            "LegacyRelationshipStore",
            "LegacySearchIndex",
            "get_legacy_graph_stats_payload",
            "get_legacy_knowledge_read_adapter",
            "graph_stats_payload",
            "reset_legacy_graph_runtime",
        }:
            from sibyl.persistence.legacy.graph import (
                LegacyEntityStore,
                LegacyGraphStore,
                LegacyKnowledgeReadAdapter,
                LegacyKnowledgeWriteAdapter,
                LegacyRelationshipStore,
                LegacySearchIndex,
                ensure_legacy_graph_indexes,
                execute_legacy_debug_query,
                get_legacy_graph_stats_payload,
                get_legacy_knowledge_read_adapter,
                graph_stats_payload,
                reset_legacy_graph_runtime,
            )

            exports.update(
                {
                    "ensure_legacy_graph_indexes": ensure_legacy_graph_indexes,
                    "execute_legacy_debug_query": execute_legacy_debug_query,
                    "LegacyEntityStore": LegacyEntityStore,
                    "LegacyGraphStore": LegacyGraphStore,
                    "LegacyKnowledgeReadAdapter": LegacyKnowledgeReadAdapter,
                    "LegacyKnowledgeWriteAdapter": LegacyKnowledgeWriteAdapter,
                    "LegacyRelationshipStore": LegacyRelationshipStore,
                    "LegacySearchIndex": LegacySearchIndex,
                    "get_legacy_graph_stats_payload": get_legacy_graph_stats_payload,
                    "get_legacy_knowledge_read_adapter": get_legacy_knowledge_read_adapter,
                    "graph_stats_payload": graph_stats_payload,
                    "reset_legacy_graph_runtime": reset_legacy_graph_runtime,
                }
            )
        return exports[name]
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
