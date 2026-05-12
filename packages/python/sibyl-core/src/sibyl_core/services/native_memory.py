"""Native SurrealDB memory write services."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sibyl_core.auth.memory_policy import (
    MemoryPolicyDecision,
    authorize_memory_reflect,
    authorize_memory_write,
)
from sibyl_core.models.entities import Entity, EntityType, Relationship, RelationshipType
from sibyl_core.models.reflection import ReflectionCandidate
from sibyl_core.services import get_graph_runtime
from sibyl_core.services.surreal_content import MemoryScope
from sibyl_core.tools.helpers import _generate_id
from sibyl_core.tools.responses import AddResponse


class NativeWriteMode(StrEnum):
    DISABLED = "disabled"
    ENABLED = "enabled"


@dataclass(frozen=True, slots=True)
class NativeReflectionWriteResult:
    response: AddResponse
    metadata: dict[str, Any]


def coerce_native_write_mode(value: str | NativeWriteMode | None) -> NativeWriteMode:
    if isinstance(value, NativeWriteMode):
        return value
    if value is None or not value.strip():
        return NativeWriteMode.DISABLED
    normalized = value.strip().lower()
    if normalized in {"enabled", "enable", "true", "1", "yes", "on"}:
        return NativeWriteMode.ENABLED
    return NativeWriteMode.DISABLED


def native_write_mode_from_env(environ: Mapping[str, str] | None = None) -> NativeWriteMode:
    source = os.environ if environ is None else environ
    return coerce_native_write_mode(source.get("SIBYL_NATIVE_WRITE"))


def native_reflection_write_enabled(environ: Mapping[str, str] | None = None) -> bool:
    return native_write_mode_from_env(environ) is NativeWriteMode.ENABLED


async def persist_reflection_source_native(
    *,
    title: str,
    content: str,
    organization_id: str,
    principal_id: str | None,
    domain: str | None = None,
    project: str | None = None,
    related_to: Sequence[str] | None = None,
    accessible_projects: Iterable[str] | None = None,
    memory_scope: MemoryScope | str | None = None,
    scope_key: str | None = None,
) -> NativeReflectionWriteResult:
    candidate = ReflectionCandidate(
        kind=EntityType.SESSION.value,
        title=title,
        content=content,
        reason="preserves raw reflection source material",
        confidence=1.0,
        tags=["reflection", EntityType.SESSION.value],
        metadata={"reflection_source": True},
    )
    return await persist_reflection_candidate_native(
        candidate=candidate,
        organization_id=organization_id,
        principal_id=principal_id,
        domain=domain,
        project=project,
        source_id=None,
        related_to=related_to,
        accessible_projects=accessible_projects,
        memory_scope=memory_scope,
        scope_key=scope_key,
    )


async def persist_reflection_candidate_native(
    *,
    candidate: ReflectionCandidate,
    organization_id: str,
    principal_id: str | None,
    domain: str | None = None,
    project: str | None = None,
    source_id: str | None = None,
    related_to: Sequence[str] | None = None,
    accessible_projects: Iterable[str] | None = None,
    memory_scope: MemoryScope | str | None = None,
    scope_key: str | None = None,
) -> NativeReflectionWriteResult:
    scope = _resolve_memory_scope(memory_scope, project)
    resolved_scope_key = _resolve_scope_key(scope, scope_key, project)
    policy_decisions = _authorize_reflection_write(
        principal_id=principal_id,
        memory_scope=scope,
        scope_key=resolved_scope_key,
        accessible_projects=accessible_projects,
    )
    policy_metadata = _policy_metadata(policy_decisions)
    if any(not decision.allowed for decision in policy_decisions):
        return NativeReflectionWriteResult(
            response=AddResponse(
                success=False,
                id=None,
                message=_policy_denied_message(policy_decisions),
                timestamp=datetime.now(UTC),
            ),
            metadata=policy_metadata,
        )

    runtime = await get_graph_runtime(organization_id)
    entity = _entity_from_candidate(
        candidate,
        organization_id=organization_id,
        principal_id=principal_id,
        domain=domain,
        project=project,
        source_id=source_id,
        memory_scope=scope,
        scope_key=resolved_scope_key,
        policy_metadata=policy_metadata,
    )
    created_id = await runtime.entity_manager.create_direct(entity)
    relationships = _relationships_for_promotion(
        created_id,
        project=project,
        source_id=source_id,
        related_to=related_to,
    )
    if relationships:
        await runtime.relationship_manager.create_bulk(relationships)

    return NativeReflectionWriteResult(
        response=AddResponse(
            success=True,
            id=created_id,
            message=f"Promoted natively: {candidate.title}",
            timestamp=datetime.now(UTC),
        ),
        metadata={
            **policy_metadata,
            "native_write_mode": NativeWriteMode.ENABLED.value,
            "native_write_path": "reflection_promotion",
            "native_relationship_count": len(relationships),
        },
    )


def _resolve_memory_scope(
    memory_scope: MemoryScope | str | None,
    project: str | None,
) -> MemoryScope:
    if memory_scope is not None:
        try:
            return MemoryScope(memory_scope)
        except ValueError:
            return MemoryScope.PRIVATE
    return MemoryScope.PROJECT if project else MemoryScope.PRIVATE


def _resolve_scope_key(
    memory_scope: MemoryScope,
    scope_key: str | None,
    project: str | None,
) -> str | None:
    if memory_scope is MemoryScope.PROJECT:
        return scope_key or project
    return scope_key


def _authorize_reflection_write(
    *,
    principal_id: str | None,
    memory_scope: MemoryScope,
    scope_key: str | None,
    accessible_projects: Iterable[str] | None,
) -> tuple[MemoryPolicyDecision, MemoryPolicyDecision]:
    reflect_decision = authorize_memory_reflect(
        principal_id=principal_id,
        memory_scope=memory_scope,
        scope_key=scope_key,
        accessible_projects=accessible_projects,
    )
    write_decision = authorize_memory_write(
        principal_id=principal_id,
        memory_scope=memory_scope,
        scope_key=scope_key,
        accessible_projects=accessible_projects,
    )
    return reflect_decision, write_decision


def _policy_metadata(decisions: Sequence[MemoryPolicyDecision]) -> dict[str, Any]:
    return {
        "native_write_mode": NativeWriteMode.ENABLED.value,
        "memory_scope": decisions[0].memory_scope.value,
        "scope_key": decisions[0].scope_key,
        "policy_allowed": all(decision.allowed for decision in decisions),
        "policy_reasons": [decision.reason for decision in decisions],
        "policy_actions": [decision.action.value for decision in decisions],
    }


def _policy_denied_message(decisions: Sequence[MemoryPolicyDecision]) -> str:
    denied = [decision.reason for decision in decisions if not decision.allowed]
    reason = denied[0] if denied else "unknown"
    return f"Native reflection promotion denied: {reason}"


def _entity_type(kind: str) -> EntityType:
    try:
        return EntityType(kind)
    except ValueError:
        return EntityType.EPISODE


def _entity_from_candidate(
    candidate: ReflectionCandidate,
    *,
    organization_id: str,
    principal_id: str | None,
    domain: str | None,
    project: str | None,
    source_id: str | None,
    memory_scope: MemoryScope,
    scope_key: str | None,
    policy_metadata: Mapping[str, Any],
) -> Entity:
    entity_type = _entity_type(candidate.kind)
    entity_id = _generate_id(entity_type.value, candidate.title, domain or "general")
    source_ids = [source_id] if source_id else []
    metadata = {
        **candidate.metadata,
        "category": domain,
        "tags": list(candidate.tags),
        "organization_id": organization_id,
        "capture_mode": "reflect",
        "capture_surface": "reflection",
        "remember_kind": candidate.kind,
        "reflection_reason": candidate.reason,
        "reflection_confidence": candidate.confidence,
        "raw_source_ids": source_ids,
        "source_ids": source_ids,
        **dict(policy_metadata),
    }
    if project:
        metadata["project_id"] = project
    if source_id:
        metadata["reflection_source_id"] = source_id

    return Entity(
        id=entity_id,
        entity_type=entity_type,
        name=candidate.title,
        description=candidate.content[:500],
        content=candidate.content,
        organization_id=organization_id,
        created_by=principal_id,
        metadata=metadata,
        source_file=source_id,
    )


def _relationships_for_promotion(
    entity_id: str,
    *,
    project: str | None,
    source_id: str | None,
    related_to: Sequence[str] | None,
) -> list[Relationship]:
    relationships: list[Relationship] = []
    if project and project != entity_id:
        relationships.append(
            _relationship(
                entity_id,
                project,
                RelationshipType.BELONGS_TO,
                metadata={"native_write_path": "reflection_promotion"},
            )
        )
    if source_id and source_id != entity_id:
        relationships.append(
            _relationship(
                entity_id,
                source_id,
                RelationshipType.DERIVED_FROM,
                metadata={"native_write_path": "reflection_promotion", "source_id": source_id},
            )
        )
    for related_id in related_to or ():
        if related_id in {entity_id, project, source_id}:
            continue
        relationships.append(
            _relationship(
                entity_id,
                related_id,
                RelationshipType.RELATED_TO,
                metadata={"native_write_path": "reflection_promotion"},
            )
        )
    return relationships


def _relationship(
    source_id: str,
    target_id: str,
    relationship_type: RelationshipType,
    *,
    metadata: dict[str, Any],
) -> Relationship:
    return Relationship(
        id=f"rel_{source_id}_{relationship_type.value.lower()}_{target_id}",
        source_id=source_id,
        target_id=target_id,
        relationship_type=relationship_type,
        metadata={**metadata, "created_at": datetime.now(UTC).isoformat()},
    )


__all__ = [
    "NativeReflectionWriteResult",
    "NativeWriteMode",
    "coerce_native_write_mode",
    "native_reflection_write_enabled",
    "native_write_mode_from_env",
    "persist_reflection_candidate_native",
    "persist_reflection_source_native",
]
