from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import pytest
from starlette.requests import Request
from starlette.responses import Response

from sibyl.api.routes import orgs as org_routes


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
async def test_create_org_uses_legacy_graph_index_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AsyncMock()
    request = _request()
    response = Response()
    user = SimpleNamespace(id=UUID("00000000-0000-0000-0000-000000000123"))
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
    session_manager = SimpleNamespace(
        get_session_by_token=AsyncMock(return_value=None),
        rotate_tokens=AsyncMock(),
        create_session=AsyncMock(),
    )
    audit_logger = SimpleNamespace(log=AsyncMock())
    ensure_indexes = AsyncMock()

    monkeypatch.setattr(org_routes, "OrganizationManager", lambda _session: org_manager)
    monkeypatch.setattr(
        org_routes,
        "OrganizationMembershipManager",
        lambda _session: membership_manager,
    )
    monkeypatch.setattr(org_routes, "SessionManager", lambda _session: session_manager)
    monkeypatch.setattr(org_routes, "AuditLogger", lambda _session: audit_logger)
    monkeypatch.setattr(org_routes, "ensure_legacy_graph_indexes", ensure_indexes)
    monkeypatch.setattr(org_routes, "create_access_token", lambda **_kwargs: "access-token")
    monkeypatch.setattr(
        org_routes,
        "create_refresh_token",
        lambda **_kwargs: ("refresh-token", datetime.now(UTC) + timedelta(days=7)),
    )
    monkeypatch.setattr(org_routes, "select_access_token", lambda **_kwargs: None)

    body = org_routes.OrganizationCreateRequest(name="Electric Coven")

    payload = await org_routes.create_org(
        request=request,
        body=body,
        response=response,
        user=user,
        session=session,
    )

    ensure_indexes.assert_awaited_once_with(str(created_org.id))
    membership_manager.add_member.assert_awaited_once_with(
        organization_id=created_org.id,
        user_id=user.id,
        role=org_routes.OrganizationRole.OWNER,
    )
    assert response.status_code == 201
    assert payload["organization"]["id"] == str(created_org.id)
