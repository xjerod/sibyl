"""Tests for CLI ID prefix resolution helpers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from sibyl_cli.client import SibylClientError
from sibyl_cli.id_resolution import resolve_id_prefix, resolve_raw_memory_id_prefix


@pytest.mark.asyncio
async def test_resolve_id_prefix_returns_unambiguous_match() -> None:
    client = MagicMock()
    client.resolve_id_prefix = AsyncMock(return_value={"matches": [{"id": "task_123456789abc"}]})

    resolved = await resolve_id_prefix(client, "123456", entity_type="task")

    assert resolved == "task_123456789abc"
    client.resolve_id_prefix.assert_awaited_once_with("123456", entity_type="task")


@pytest.mark.asyncio
async def test_resolve_id_prefix_reports_ambiguous_matches() -> None:
    client = MagicMock()
    client.resolve_id_prefix = AsyncMock(
        return_value={
            "matches": [
                {"id": "task_123456789abc"},
                {"id": "task_123456789def"},
            ]
        }
    )

    with pytest.raises(SibylClientError) as exc_info:
        await resolve_id_prefix(client, "123456", entity_type="task")

    assert "Ambiguous prefix" in str(exc_info.value)
    assert "task_123456789abc" in str(exc_info.value)
    assert "task_123456789def" in str(exc_info.value)


@pytest.mark.asyncio
async def test_resolve_id_prefix_skips_full_prefixed_ids() -> None:
    client = MagicMock()
    client.resolve_id_prefix = AsyncMock()

    resolved = await resolve_id_prefix(client, "task_123456789abc", entity_type="task")

    assert resolved == "task_123456789abc"
    client.resolve_id_prefix.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_raw_memory_id_prefix_uses_raw_memory_type() -> None:
    client = MagicMock()
    client.resolve_id_prefix = AsyncMock(return_value={"matches": [{"id": "memory-123456789abc"}]})

    resolved = await resolve_raw_memory_id_prefix(client, "memory-123")

    assert resolved == "memory-123456789abc"
    client.resolve_id_prefix.assert_awaited_once_with(
        "memory-123",
        entity_type="raw_memory",
    )
