import hashlib
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from sibyl.api.routes import users as users_routes


@pytest.mark.asyncio
async def test_list_sessions_marks_current_from_sibyl_access_token_cookie() -> None:
    token = "access-token-value"
    current_hash = hashlib.sha256(token.encode()).hexdigest()

    session_row = SimpleNamespace(
        id=uuid4(),
        user_id=uuid4(),
        organization_id=None,
        token_hash=current_hash,
        expires_at=(datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None),
        revoked_at=None,
        user_agent=None,
        ip_address=None,
        created_at=datetime.now(UTC).replace(tzinfo=None),
        last_active_at=None,
    )

    request = MagicMock()
    request.headers = {}
    request.cookies = {"sibyl_access_token": token}

    auth = MagicMock()
    auth.user.id = session_row.user_id

    with patch.object(
        users_routes,
        "list_user_sessions",
        AsyncMock(return_value=[session_row]),
    ):
        rows = await users_routes.list_sessions(request=request, auth=auth)

    assert len(rows) == 1
    assert rows[0].is_current is True
