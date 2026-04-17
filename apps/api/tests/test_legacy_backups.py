from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from sibyl.persistence.legacy import backups as legacy_backups


@pytest.mark.asyncio
async def test_get_legacy_backup_settings_creates_default_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    session = AsyncMock()
    session.execute.return_value = result
    session_manager = AsyncMock()
    session_manager.__aenter__.return_value = session
    session_manager.__aexit__.return_value = False

    monkeypatch.setattr(legacy_backups, "get_session", lambda: session_manager)

    settings = await legacy_backups.get_legacy_backup_settings(uuid4())

    assert settings.organization_id is not None
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_legacy_backup_retention_prefers_request_value() -> None:
    retention = await legacy_backups.get_legacy_backup_retention(uuid4(), 14)

    assert retention == 14


@pytest.mark.asyncio
async def test_get_legacy_backup_raises_for_missing_record(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = MagicMock()
    result.scalar_one_or_none.return_value = None

    session = AsyncMock()
    session.execute.return_value = result
    session_manager = AsyncMock()
    session_manager.__aenter__.return_value = session
    session_manager.__aexit__.return_value = False

    monkeypatch.setattr(legacy_backups, "get_session", lambda: session_manager)

    with pytest.raises(HTTPException, match="Backup not found") as exc_info:
        await legacy_backups.get_legacy_backup(uuid4(), "backup_test")

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_legacy_backup_record_deletes_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup = SimpleNamespace(id=uuid4(), backup_id="backup_test")
    result = MagicMock()
    result.scalar_one_or_none.return_value = backup

    session = AsyncMock()
    session.execute.return_value = result
    session_manager = AsyncMock()
    session_manager.__aenter__.return_value = session
    session_manager.__aexit__.return_value = False

    monkeypatch.setattr(legacy_backups, "get_session", lambda: session_manager)

    removed = await legacy_backups.delete_legacy_backup_record(uuid4(), "backup_test")

    assert removed is backup
    session.delete.assert_awaited_once_with(backup)
    session.commit.assert_awaited_once()
