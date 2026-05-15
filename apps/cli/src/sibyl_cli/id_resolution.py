"""Client-side helpers for resolving short graph ID prefixes."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sibyl_cli.client import SibylClientError


def _is_full_uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _is_full_prefixed_id(value: str, entity_type: str | None) -> bool:
    if not entity_type:
        return "_" in value and len(value) >= 12
    return value.startswith(f"{entity_type}_") and len(value) >= len(entity_type) + 13


async def resolve_id_prefix(
    client: Any,
    value: str,
    *,
    entity_type: str | None = None,
) -> str:
    """Resolve a potentially short graph ID to a full ID."""
    candidate = value.strip()
    if not candidate:
        raise SibylClientError("ID cannot be empty", status_code=400, detail="ID cannot be empty")
    if _is_full_uuid(candidate) or _is_full_prefixed_id(candidate, entity_type):
        return candidate

    response = await client.resolve_id_prefix(candidate, entity_type=entity_type)
    matches = response.get("matches", [])
    if not matches:
        label = f" {entity_type}" if entity_type else ""
        raise SibylClientError(
            f"No{label} ID matches prefix: {candidate}",
            status_code=404,
            detail=f"No{label} ID matches prefix: {candidate}",
        )
    if len(matches) > 1:
        ids = [str(match.get("id", "")) for match in matches]
        raise SibylClientError(
            f"Ambiguous prefix; matches: {', '.join(ids)}",
            status_code=409,
            detail=f"Ambiguous prefix; matches: {', '.join(ids)}",
        )
    resolved = str(matches[0].get("id") or "")
    if not resolved:
        raise SibylClientError(
            f"No ID matches prefix: {candidate}",
            status_code=404,
            detail=f"No ID matches prefix: {candidate}",
        )
    return resolved


async def resolve_raw_memory_id_prefix(client: Any, value: str) -> str:
    return await resolve_id_prefix(client, value, entity_type="raw_memory")
