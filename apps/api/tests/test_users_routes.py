from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from sibyl.api.routes import users as user_routes


def _auth() -> SimpleNamespace:
    return SimpleNamespace(
        session=AsyncMock(),
        ctx=SimpleNamespace(user=SimpleNamespace(id=uuid4())),
    )


@pytest.mark.asyncio
async def test_request_password_reset_uses_legacy_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_reset = AsyncMock()
    monkeypatch.setattr(user_routes, "request_legacy_password_reset", request_reset)

    response = await user_routes.request_password_reset(
        user_routes.PasswordResetRequest(email="person@example.com")
    )

    assert response["message"].startswith("If an account exists")
    request_reset.assert_awaited_once_with("person@example.com")


@pytest.mark.asyncio
async def test_confirm_password_reset_uses_legacy_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    confirm_reset = AsyncMock()
    monkeypatch.setattr(user_routes, "confirm_legacy_password_reset", confirm_reset)

    await user_routes.confirm_password_reset(
        user_routes.PasswordResetConfirmRequest(
            token="reset-token",
            new_password="new-password-123",
        )
    )

    confirm_reset.assert_awaited_once_with("reset-token", "new-password-123")


@pytest.mark.asyncio
async def test_list_connections_uses_legacy_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    auth = _auth()
    connected_at = datetime.now(UTC).replace(tzinfo=None)
    monkeypatch.setattr(
        user_routes,
        "list_legacy_oauth_connections",
        AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=uuid4(),
                    provider="github",
                    provider_user_id="123",
                    provider_email="person@example.com",
                    created_at=connected_at,
                )
            ]
        ),
    )

    response = await user_routes.list_connections(auth=auth)

    assert len(response) == 1
    assert response[0].provider == "github"
    assert response[0].connected_at is connected_at


@pytest.mark.asyncio
async def test_remove_connection_uses_legacy_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    auth = _auth()
    connection_id = uuid4()
    remove_connection = AsyncMock(return_value=SimpleNamespace(provider="github"))
    monkeypatch.setattr(user_routes, "remove_legacy_oauth_connection", remove_connection)

    await user_routes.remove_connection(connection_id=connection_id, auth=auth)

    remove_connection.assert_awaited_once_with(
        auth.session,
        user_id=auth.ctx.user.id,
        connection_id=connection_id,
    )
