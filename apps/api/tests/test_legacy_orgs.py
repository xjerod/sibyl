from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from starlette.requests import Request

from sibyl.persistence.legacy import orgs as legacy_orgs


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/orgs",
            "headers": [],
            "client": ("127.0.0.1", 3334),
        }
    )


@pytest.mark.asyncio
async def test_create_legacy_org_uses_graph_index_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    session_manager = AsyncMock()
    session_manager.__aenter__.return_value = session
    session_manager.__aexit__.return_value = False
    request = _request()
    created_org = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000456"),
        slug="electric-coven",
        name="Electric Coven",
    )
    org_manager = SimpleNamespace(
        get_by_slug=AsyncMock(return_value=None),
        create=AsyncMock(return_value=created_org),
    )
    membership_manager = SimpleNamespace(add_member=AsyncMock())
    auth_session_manager = SimpleNamespace(
        get_session_by_token=AsyncMock(return_value=None),
        rotate_tokens=AsyncMock(),
        create_session=AsyncMock(),
    )
    audit_logger = SimpleNamespace(log=AsyncMock())
    ensure_indexes = AsyncMock()

    monkeypatch.setattr(legacy_orgs, "get_session", lambda: session_manager)
    monkeypatch.setattr(legacy_orgs, "OrganizationManager", lambda _session: org_manager)
    monkeypatch.setattr(
        legacy_orgs,
        "OrganizationMembershipManager",
        lambda _session: membership_manager,
    )
    monkeypatch.setattr(legacy_orgs, "SessionManager", lambda _session: auth_session_manager)
    monkeypatch.setattr(legacy_orgs, "AuditLogger", lambda _session: audit_logger)
    monkeypatch.setattr(legacy_orgs, "ensure_legacy_graph_indexes", ensure_indexes)
    monkeypatch.setattr(legacy_orgs, "create_access_token", lambda **_kwargs: "access-token")
    monkeypatch.setattr(
        legacy_orgs,
        "create_refresh_token",
        lambda **_kwargs: ("refresh-token", datetime.now(UTC) + timedelta(days=7)),
    )
    monkeypatch.setattr(legacy_orgs, "select_access_token", lambda **_kwargs: None)

    payload = await legacy_orgs.create_legacy_org(
        request=request,
        user_id=UUID("00000000-0000-0000-0000-000000000123"),
        name="Electric Coven",
    )

    ensure_indexes.assert_awaited_once_with(str(created_org.id))
    membership_manager.add_member.assert_awaited_once_with(
        organization_id=created_org.id,
        user_id=UUID("00000000-0000-0000-0000-000000000123"),
        role=legacy_orgs.OrganizationRole.OWNER,
    )
    assert payload.id == created_org.id
    assert payload.access_token == "access-token"
