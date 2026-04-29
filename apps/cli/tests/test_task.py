"""Tests for task CLI commands."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from sibyl_cli import task


@patch("sibyl_cli.task.get_client")
def test_task_create_accepts_legacy_sync_flag(mock_get_client: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.create_task = AsyncMock(
        return_value={"success": True, "task_id": "13364346-8475-4664-8b52-eb963af2fda7"}
    )
    mock_get_client.return_value = mock_client

    runner = CliRunner()
    result = runner.invoke(
        task.app,
        [
            "create",
            "--title",
            "Restore compatibility",
            "--project",
            "project_123456789abc",
            "--priority",
            "high",
            "--sync",
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["id"] == "13364346-8475-4664-8b52-eb963af2fda7"
    assert payload["name"] == "Restore compatibility"
    assert payload["metadata"]["priority"] == "high"
    assert payload["metadata"]["project_id"] == "project_123456789abc"
    mock_client.create_task.assert_awaited_once_with(
        title="Restore compatibility",
        project_id="project_123456789abc",
        description=None,
        priority="high",
        complexity="medium",
        assignees=None,
        epic_id=None,
        feature=None,
        tags=None,
        technologies=None,
        depends_on=None,
    )


def test_validate_task_id_accepts_api_uuid() -> None:
    task_id = "13364346-8475-4664-8b52-eb963af2fda7"

    assert task._validate_task_id(task_id) == task_id


@patch("sibyl_cli.task.get_client")
def test_task_archive_stdin_json_reports_failed_ids(mock_get_client: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.archive_task = AsyncMock(
        side_effect=[
            {"success": True},
            {"success": False, "message": "already archived"},
        ]
    )
    mock_get_client.return_value = mock_client

    runner = CliRunner()
    result = runner.invoke(
        task.app,
        ["archive", "--stdin", "--yes", "--json"],
        input="task_123456789abc\nnot-a-task\n13364346-8475-4664-8b52-eb963af2fda7\n",
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["total"] == 3
    assert payload["archived"] == 1
    assert payload["failed"] == 2
    assert payload["failed_ids"] == ["not-a-task", "13364346-8475-4664-8b52-eb963af2fda7"]
    assert [item["id"] for item in payload["results"]] == [
        "task_123456789abc",
        "not-a-task",
        "13364346-8475-4664-8b52-eb963af2fda7",
    ]
    mock_client.archive_task.assert_any_await("task_123456789abc", None)
    mock_client.archive_task.assert_any_await("13364346-8475-4664-8b52-eb963af2fda7", None)
    assert mock_client.archive_task.await_count == 2


@patch("sibyl_cli.task.get_client")
def test_task_archive_stdin_accepts_uuid_ids(mock_get_client: MagicMock) -> None:
    task_id = "13364346-8475-4664-8b52-eb963af2fda7"
    mock_client = MagicMock()
    mock_client.archive_task = AsyncMock(return_value={"success": True})
    mock_get_client.return_value = mock_client

    runner = CliRunner()
    result = runner.invoke(
        task.app,
        ["archive", "--stdin", "--yes", "--json"],
        input=f"{task_id}\ntask_123456789abc\n",
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["archived"] == 2
    assert payload["failed_ids"] == []
    mock_client.archive_task.assert_any_await(task_id, None)
    mock_client.archive_task.assert_any_await("task_123456789abc", None)
