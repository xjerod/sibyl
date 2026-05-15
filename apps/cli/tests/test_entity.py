"""Tests for entity CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from sibyl_cli.entity import app


@patch("sibyl_cli.entity.get_client")
def test_entity_show_renders_full_content(mock_get_client: MagicMock) -> None:
    content = "alpha " * 120 + "TAIL_SENTINEL"
    mock_client = MagicMock()
    mock_client.get_entity = AsyncMock(
        return_value={
            "id": "episode_123",
            "name": "Long memory",
            "entity_type": "episode",
            "description": "Short summary",
            "content": content,
            "metadata": {},
        }
    )
    mock_get_client.return_value = mock_client

    result = CliRunner().invoke(app, ["show", "episode_123"])

    assert result.exit_code == 0
    assert "TAIL_SENTINEL" in result.stdout
    assert "..." not in result.stdout
    mock_client.get_entity.assert_awaited_once_with("episode_123")
