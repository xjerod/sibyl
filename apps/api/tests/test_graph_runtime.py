from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from sibyl.persistence import graph_runtime


class _ProjectDeleteDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def execute_query_raw(self, query: str, **params: object) -> object:
        self.calls.append((query, params))
        return {
            "result": [
                {"status": "OK", "result": []},
                {"status": "OK", "result": []},
                {"status": "OK", "result": []},
            ]
        }


@pytest.mark.asyncio
async def test_delete_project_graph_data_sweeps_project_scoped_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    driver = _ProjectDeleteDriver()

    monkeypatch.setattr(
        graph_runtime,
        "_get_graph_runtime",
        AsyncMock(return_value=SimpleNamespace(client=driver)),
    )
    monkeypatch.setattr(graph_runtime, "_surreal_driver_for", lambda candidate: candidate)

    await graph_runtime.delete_project_graph_data("org-123", "project-alpha")

    assert len(driver.calls) == 1
    query, params = driver.calls[0]
    assert "BEGIN TRANSACTION;" in query
    assert "LET $project_entity_ids" in query
    assert "LET $project_episode_ids" in query
    assert "DELETE FROM relates_to" in query
    assert "DELETE FROM mentions" in query
    assert "DELETE FROM has_episode" in query
    assert "DELETE FROM next_episode" in query
    assert "DELETE FROM has_member" in query
    assert "DELETE FROM entity" in query
    assert "DELETE FROM episode" in query
    assert "COMMIT TRANSACTION;" in query
    assert params == {"group_id": "org-123", "project_id": "project-alpha"}
