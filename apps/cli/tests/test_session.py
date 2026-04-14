"""Tests for the session bundle CLI surface."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from sibyl_cli.main import app


class _FakeClientContext:
    def __init__(self, client: MagicMock) -> None:
        self._client = client

    async def __aenter__(self) -> MagicMock:
        return self._client

    async def __aexit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
        return None


@patch("sibyl_cli.session.get_effective_server_url", return_value="http://localhost:3334")
@patch("sibyl_cli.session.get_effective_project", return_value="project_123")
@patch("sibyl_cli.session.get_current_context", return_value=("project_123", "/Users/bliss/dev/sibyl"))
@patch("sibyl_cli.session.get_active_context")
@patch("sibyl_cli.session.get_client")
def test_session_bundle_json_packages_context_tasks_and_memories(
    mock_get_client: MagicMock,
    mock_get_active_context: MagicMock,
    mock_get_current_context: MagicMock,
    mock_get_effective_project: MagicMock,
    mock_get_effective_server_url: MagicMock,
) -> None:
    context = MagicMock()
    context.name = "local"
    context.org_slug = "hyper"
    mock_get_active_context.return_value = context

    mock_client = MagicMock()
    mock_client.get_entity = AsyncMock(
        return_value={
            "id": "project_123",
            "name": "Sibyl",
            "description": "Durable project memory",
        }
    )
    mock_client.explore = AsyncMock(
        return_value={
            "entities": [
                {
                    "id": "task_1",
                    "name": "Fix session bundle",
                    "metadata": {"status": "doing", "priority": "high"},
                },
                {
                    "id": "task_2",
                    "name": "Audit raw capture",
                    "metadata": {"status": "blocked", "priority": "critical"},
                },
            ]
        }
    )
    mock_client.search = AsyncMock(
        return_value={
            "results": [
                {
                    "id": "task_1",
                    "name": "Fix session bundle",
                    "entity_type": "task",
                    "content": "task duplicate",
                    "metadata": {},
                },
                {
                    "id": "pattern_1",
                    "name": "Hook output should share a CLI contract",
                    "entity_type": "pattern",
                    "content": "[Hooks] Keep session-start thin and call a first-class bundle command.",
                    "metadata": {},
                },
            ]
        }
    )
    mock_get_client.return_value = _FakeClientContext(mock_client)

    runner = CliRunner()
    result = runner.invoke(app, ["session", "bundle", "--json"])

    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["context"]["project_name"] == "Sibyl"
    assert payload["context"]["project_description"] == "Durable project memory"
    assert payload["query"] == "Fix session bundle | Audit raw capture"
    assert payload["remember_next"] == "Unblock Audit raw capture before you pick up new work."
    assert payload["tasks"] == [
        {
            "id": "task_1",
            "name": "Fix session bundle",
            "status": "doing",
            "priority": "high",
            "feature": None,
            "branch_name": None,
        },
        {
            "id": "task_2",
            "name": "Audit raw capture",
            "status": "blocked",
            "priority": "critical",
            "feature": None,
            "branch_name": None,
        },
    ]
    assert payload["relevant_entities"] == [
        {
            "id": "pattern_1",
            "name": "Hook output should share a CLI contract",
            "entity_type": "pattern",
            "source": None,
            "preview": "Keep session-start thin and call a first-class bundle command.",
            "document_id": None,
        }
    ]

    mock_client.search.assert_awaited_once_with(
        "Fix session bundle | Audit raw capture",
        project="project_123",
        limit=5,
    )
    mock_get_effective_server_url.assert_called_once_with()
    mock_get_effective_project.assert_called_once_with()
    mock_get_current_context.assert_called_once_with()


@patch("sibyl_cli.session.get_effective_server_url", return_value="http://localhost:3334")
@patch("sibyl_cli.session.get_effective_project", return_value=None)
@patch("sibyl_cli.session.get_current_context", return_value=(None, None))
@patch("sibyl_cli.session.get_active_context", return_value=None)
@patch("sibyl_cli.session.get_client")
def test_session_bundle_without_project_guides_user_to_link_one(
    mock_get_client: MagicMock,
    mock_get_active_context: MagicMock,
    mock_get_current_context: MagicMock,
    mock_get_effective_project: MagicMock,
    mock_get_effective_server_url: MagicMock,
) -> None:
    mock_client = MagicMock()
    mock_client.explore = AsyncMock(return_value={"entities": []})
    mock_client.search = AsyncMock()
    mock_get_client.return_value = _FakeClientContext(mock_client)

    runner = CliRunner()
    result = runner.invoke(app, ["session", "bundle", "--json"])

    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["query"] is None
    assert payload["tasks"] == []
    assert payload["relevant_entities"] == []
    assert payload["remember_next"] == "Link this directory to a project so session context stays scoped."

    mock_client.get_entity.assert_not_called()
    mock_client.search.assert_not_called()
    mock_get_effective_server_url.assert_called_once_with()
    mock_get_effective_project.assert_called_once_with()
    mock_get_current_context.assert_called_once_with()


@patch("sibyl_cli.session.get_effective_server_url", return_value="http://localhost:3334")
@patch("sibyl_cli.session.get_effective_project", return_value="project_123")
@patch("sibyl_cli.session.get_current_context", return_value=("project_123", "/Users/bliss/dev/sibyl"))
@patch("sibyl_cli.session.get_active_context")
@patch("sibyl_cli.session.get_client")
def test_session_bundle_renders_human_output(
    mock_get_client: MagicMock,
    mock_get_active_context: MagicMock,
    mock_get_current_context: MagicMock,
    mock_get_effective_project: MagicMock,
    mock_get_effective_server_url: MagicMock,
) -> None:
    context = MagicMock()
    context.name = "local"
    context.org_slug = "hyper"
    mock_get_active_context.return_value = context

    mock_client = MagicMock()
    mock_client.get_entity = AsyncMock(return_value={"id": "project_123", "name": "Sibyl"})
    mock_client.explore = AsyncMock(
        return_value={
            "entities": [
                {
                    "id": "task_1",
                    "name": "Fix session bundle",
                    "metadata": {"status": "doing", "priority": "high"},
                }
            ]
        }
    )
    mock_client.search = AsyncMock(
        return_value={
            "results": [
                {
                    "id": "pattern_1",
                    "name": "Session bundles stay small",
                    "entity_type": "pattern",
                    "content": "Keep the bundle tight and readable.",
                    "metadata": {},
                }
            ]
        }
    )
    mock_get_client.return_value = _FakeClientContext(mock_client)

    runner = CliRunner()
    result = runner.invoke(app, ["session", "bundle"])

    assert result.exit_code == 0
    assert "Session Bundle" in result.stdout
    assert "Fix session bundle" in result.stdout
    assert "Session bundles stay small" in result.stdout
    assert "Remember Next" in result.stdout
