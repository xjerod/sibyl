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
            "LegacyEntityStore",
            "LegacyGraphStore",
            "LegacyKnowledgeReadAdapter",
            "LegacyKnowledgeWriteAdapter",
            "LegacyRelationshipStore",
            "LegacySearchIndex",
        }:
            from sibyl.persistence.legacy.graph import (
                LegacyEntityStore,
                LegacyGraphStore,
                LegacyKnowledgeReadAdapter,
                LegacyKnowledgeWriteAdapter,
                LegacyRelationshipStore,
                LegacySearchIndex,
            )

            exports.update(
                {
                    "LegacyEntityStore": LegacyEntityStore,
                    "LegacyGraphStore": LegacyGraphStore,
                    "LegacyKnowledgeReadAdapter": LegacyKnowledgeReadAdapter,
                    "LegacyKnowledgeWriteAdapter": LegacyKnowledgeWriteAdapter,
                    "LegacyRelationshipStore": LegacyRelationshipStore,
                    "LegacySearchIndex": LegacySearchIndex,
                }
            )
        return exports[name]
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
