"""Tests for raw capture archive CLI commands."""

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


@patch("sibyl_cli.archive.get_client")
def test_archive_list_renders_capture_table(mock_get_client: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.list_raw_captures = AsyncMock(
        return_value={
            "captures": [
                {
                    "id": "raw_123",
                    "title": "Quick memory",
                    "entity_type": "episode",
                    "capture_surface": "dashboard",
                }
            ],
            "has_more": False,
        }
    )
    mock_get_client.return_value = _FakeClientContext(mock_client)

    runner = CliRunner()
    result = runner.invoke(app, ["archive", "list"])

    assert result.exit_code == 0
    assert "Quick memory" in result.stdout
    mock_client.list_raw_captures.assert_awaited_once_with(
        entity_type=None,
        capture_surface=None,
        limit=20,
        offset=0,
    )


@patch("sibyl_cli.archive.get_client")
def test_archive_show_renders_raw_content(mock_get_client: MagicMock) -> None:
    mock_client = MagicMock()
    mock_client.get_raw_capture = AsyncMock(
        return_value={
            "id": "raw_123",
            "entity_id": "episode_123",
            "title": "Quick memory",
            "entity_type": "episode",
            "capture_surface": "dashboard",
            "created_at": "2026-04-14T16:00:00Z",
            "tags": ["alpha", "beta"],
            "metadata": {"capture_mode": "quick"},
            "raw_content": "remember this exact text",
        }
    )
    mock_get_client.return_value = _FakeClientContext(mock_client)

    runner = CliRunner()
    result = runner.invoke(app, ["archive", "show", "raw_123"])

    assert result.exit_code == 0
    assert "remember this exact text" in result.stdout
    assert "Quick memory" in result.stdout
    mock_client.get_raw_capture.assert_awaited_once_with("raw_123")
