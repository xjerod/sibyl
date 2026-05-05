from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from sibyl.persistence.legacy import setup as legacy_setup
from sibyl.persistence.surreal import setup as surreal_setup


def _request(*, authorization: str | None = None, cookie_token: str | None = None) -> Request:
    headers = []
    if authorization is not None:
        headers.append((b"authorization", authorization.encode()))

    scope = {"type": "http", "method": "GET", "path": "/setup/status", "headers": headers}
    if cookie_token is not None:
        scope["headers"].append((b"cookie", f"sibyl_access_token={cookie_token}".encode()))
    return Request(scope)


@pytest.mark.asyncio
async def test_is_legacy_setup_mode_when_no_users(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    result = MagicMock()
    result.scalar.return_value = 0
    session.execute.return_value = result
    session_manager = AsyncMock()
    session_manager.__aenter__.return_value = session
    session_manager.__aexit__.return_value = False

    monkeypatch.setattr(legacy_setup, "get_session", lambda: session_manager)

    result = await legacy_setup.is_legacy_setup_mode()

    assert result is True


@pytest.mark.asyncio
async def test_surreal_setup_mode_uses_direct_user_probe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.closed = False

        async def execute_query(self, query: str):
            self.calls.append(query)
            return []

        async def close(self) -> None:
            self.closed = True

    client = FakeClient()

    monkeypatch.setattr(surreal_setup, "build_surreal_auth_client", lambda: client)
    monkeypatch.setattr(
        surreal_setup.SurrealUserRepository,
        "from_client",
        lambda _client: (_ for _ in ()).throw(AssertionError("unexpected user repository")),
    )

    assert await surreal_setup.is_setup_mode() is True
    assert client.calls == ["SELECT uuid FROM users LIMIT 1;"]
    assert client.closed is True


@pytest.mark.asyncio
async def test_surreal_setup_status_batches_user_and_org_probes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeClient:
        def __init__(self) -> None:
            self.calls: list[str] = []
            self.closed = False

        async def execute_query(self, query: str):
            self.calls.append(query)
            return {
                "users": [{"uuid": str(uuid4())}],
                "organizations": [{"uuid": str(uuid4())}],
            }

        async def close(self) -> None:
            self.closed = True

    client = FakeClient()

    monkeypatch.setattr(surreal_setup, "build_surreal_auth_client", lambda: client)
    monkeypatch.setattr(
        surreal_setup.SurrealUserRepository,
        "from_client",
        lambda _client: (_ for _ in ()).throw(AssertionError("unexpected user repository")),
    )
    monkeypatch.setattr(
        surreal_setup.SurrealOrganizationRepository,
        "from_client",
        lambda _client: (_ for _ in ()).throw(AssertionError("unexpected org repository")),
    )

    status = await surreal_setup.get_setup_status()

    assert status.has_users is True
    assert status.has_orgs is True
    assert len(client.calls) == 1
    assert "RETURN" in client.calls[0]
    assert "FROM users" in client.calls[0]
    assert "FROM organizations" in client.calls[0]
    assert client.closed is True


@pytest.mark.asyncio
async def test_get_legacy_setup_status_counts_users_and_orgs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_result = MagicMock()
    user_result.scalar.return_value = 2
    org_result = MagicMock()
    org_result.scalar.return_value = 1

    session = AsyncMock()
    session.execute = AsyncMock(side_effect=[user_result, org_result])
    session_manager = AsyncMock()
    session_manager.__aenter__.return_value = session
    session_manager.__aexit__.return_value = False

    monkeypatch.setattr(legacy_setup, "get_session", lambda: session_manager)

    result = await legacy_setup.get_legacy_setup_status()

    assert result.has_users is True
    assert result.has_orgs is True


@pytest.mark.asyncio
async def test_require_legacy_setup_mode_or_auth_allows_setup_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verify = AsyncMock()
    monkeypatch.setattr(legacy_setup, "is_setup_mode", AsyncMock(return_value=True))
    monkeypatch.setattr(legacy_setup, "verify_access_token", verify)

    await legacy_setup.require_legacy_setup_mode_or_auth(_request())

    verify.assert_not_called()


@pytest.mark.asyncio
async def test_require_legacy_setup_mode_or_auth_rejects_missing_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(legacy_setup, "is_setup_mode", AsyncMock(return_value=False))

    with pytest.raises(HTTPException, match="Authentication required") as exc_info:
        await legacy_setup.require_legacy_setup_mode_or_auth(_request())

    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_require_legacy_setup_mode_or_admin_returns_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(id=user_id, is_admin=True)
    session_manager = AsyncMock()
    session_manager.__aenter__.return_value = session
    session_manager.__aexit__.return_value = False

    monkeypatch.setattr(legacy_setup, "is_setup_mode", AsyncMock(return_value=False))
    monkeypatch.setattr(legacy_setup, "verify_access_token", lambda _: {"sub": str(user_id)})
    monkeypatch.setattr(legacy_setup, "get_session", lambda: session_manager)

    result = await legacy_setup.require_legacy_setup_mode_or_admin(
        _request(authorization="Bearer token")
    )

    assert result.is_admin is True


@pytest.mark.asyncio
async def test_require_legacy_setup_mode_or_admin_rejects_non_admin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user_id = uuid4()
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(id=user_id, is_admin=False)
    session_manager = AsyncMock()
    session_manager.__aenter__.return_value = session
    session_manager.__aexit__.return_value = False

    monkeypatch.setattr(legacy_setup, "is_setup_mode", AsyncMock(return_value=False))
    monkeypatch.setattr(legacy_setup, "verify_access_token", lambda _: {"sub": str(user_id)})
    monkeypatch.setattr(legacy_setup, "get_session", lambda: session_manager)

    with pytest.raises(HTTPException, match="Admin access required") as exc_info:
        await legacy_setup.require_legacy_setup_mode_or_admin(
            _request(authorization="Bearer token")
        )

    assert exc_info.value.status_code == 403


def test_legacy_setup_exposes_neutral_helpers() -> None:
    assert hasattr(legacy_setup, "is_setup_mode")
    assert hasattr(legacy_setup, "get_setup_status")
    assert hasattr(legacy_setup, "require_setup_mode_or_auth")
    assert legacy_setup.LegacySetupStatus is legacy_setup.SetupStatus


def test_surreal_setup_exports_neutral_runtime_surface() -> None:
    assert surreal_setup.__all__ == [
        "SetupStatus",
        "SurrealOrganizationRepository",
        "SurrealUserRepository",
        "build_surreal_auth_client",
        "get_setup_status",
        "is_setup_mode",
        "require_settings_admin",
        "require_setup_mode_or_admin",
        "require_setup_mode_or_auth",
    ]
