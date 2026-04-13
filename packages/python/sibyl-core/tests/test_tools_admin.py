"""Tests for sibyl_core.tools.admin."""

from __future__ import annotations

import pytest

from sibyl_core.tools.admin import rebuild_indices


class TestRebuildIndices:
    """Admin index rebuilds should report real behavior, not placeholder success."""

    @pytest.mark.asyncio
    async def test_rebuild_indices_reports_not_implemented(self) -> None:
        """The current runtime should fail honestly until rebuild support exists."""
        result = await rebuild_indices("search")

        assert result.success is False
        assert result.indices_rebuilt == []
        assert "not implemented" in result.message.lower()
        assert "search" in result.message

    @pytest.mark.asyncio
    async def test_rebuild_indices_rejects_unknown_target(self) -> None:
        """Unknown targets should return a clear validation error."""
        result = await rebuild_indices("mystery")

        assert result.success is False
        assert result.indices_rebuilt == []
        assert "unknown index type" in result.message.lower()

    @pytest.mark.asyncio
    async def test_rebuild_indices_normalizes_target_values(self) -> None:
        """Whitespace and casing should normalize before reporting."""
        result = await rebuild_indices(" ALL ")

        assert result.success is False
        assert result.indices_rebuilt == []
        assert "requested target: all" in result.message.lower()
