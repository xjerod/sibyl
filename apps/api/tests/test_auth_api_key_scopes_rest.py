from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from sibyl.api.errors import http_exception_payload
from sibyl.auth.api_key_common import ApiKeyAuth, ApiKeyMemorySpaceAuth
from sibyl.auth.dependencies import resolve_claims


def _make_request(*, method: str, path: str, token: str) -> Request:
    scope = {
        "type": "http",
        "method": method.upper(),
        "path": path,
        "headers": [
            (b"authorization", f"Bearer {token}".encode()),
            (b"host", b"testserver"),
        ],
        "query_string": b"",
        "scheme": "http",
        "server": ("testserver", 80),
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_api_key_rest_denies_without_api_scopes() -> None:
    request = _make_request(method="GET", path="/api/me", token="sk_live_test")
    session = object()

    with patch(
        "sibyl.auth.dependencies.authenticate_api_key",
        AsyncMock(
            return_value=ApiKeyAuth(
                api_key_id="00000000-0000-0000-0000-000000000000",
                user_id="00000000-0000-0000-0000-000000000001",
                organization_id="00000000-0000-0000-0000-000000000002",
                scopes=["mcp"],
            )
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await resolve_claims(request, _session=session)
        assert exc.value.status_code == 403
        assert exc.value.detail == {
            "error": "insufficient_api_scope",
            "message": "Request is missing required REST scope.",
            "remediation": "Use a REST scope that matches this request.",
            "details": {
                "expected": "api:read or api:write",
                "actual": "mcp",
            },
        }
        assert http_exception_payload(exc.value, "req_scope") == {
            "error": "insufficient_api_scope",
            "message": "Request is missing required REST scope.",
            "request_id": "req_scope",
            "remediation": "Use a REST scope that matches this request.",
            "details": {
                "expected": "api:read or api:write",
                "actual": "mcp",
            },
        }


@pytest.mark.asyncio
async def test_api_key_rest_allows_api_read_for_get() -> None:
    request = _make_request(method="GET", path="/api/me", token="sk_live_test")
    session = object()

    with patch(
        "sibyl.auth.dependencies.authenticate_api_key",
        AsyncMock(
            return_value=ApiKeyAuth(
                api_key_id="00000000-0000-0000-0000-000000000000",
                user_id="00000000-0000-0000-0000-000000000001",
                organization_id="00000000-0000-0000-0000-000000000002",
                scopes=["api:read"],
            )
        ),
    ):
        claims = await resolve_claims(request, _session=session)
        assert claims is not None
        assert claims["typ"] == "api_key"
        assert "api:read" in claims["scopes"]


@pytest.mark.asyncio
async def test_api_key_rest_claims_include_control_plane_restrictions() -> None:
    request = _make_request(method="GET", path="/api/me", token="sk_live_test")
    memory_space_id = "00000000-0000-0000-0000-000000000003"
    session = object()

    with patch(
        "sibyl.auth.dependencies.authenticate_api_key",
        AsyncMock(
            return_value=ApiKeyAuth(
                api_key_id=UUID("00000000-0000-0000-0000-000000000000"),
                user_id=UUID("00000000-0000-0000-0000-000000000001"),
                organization_id=UUID("00000000-0000-0000-0000-000000000002"),
                scopes=["api:read"],
                project_ids=["project-alpha"],
                memory_space_ids=[UUID(memory_space_id)],
                memory_spaces=[
                    ApiKeyMemorySpaceAuth(
                        memory_space_id=UUID(memory_space_id),
                        memory_scope="project",
                        scope_key="project-alpha",
                    )
                ],
            )
        ),
    ):
        claims = await resolve_claims(request, _session=session)

    assert claims is not None
    assert claims["api_key_project_ids"] == ["project-alpha"]
    assert claims["api_key_memory_space_ids"] == [memory_space_id]
    assert len(claims["api_key_memory_scope_keys"]) == 1


@pytest.mark.asyncio
async def test_api_key_rest_denies_write_without_api_write() -> None:
    request = _make_request(method="POST", path="/api/me", token="sk_live_test")
    session = object()

    with patch(
        "sibyl.auth.dependencies.authenticate_api_key",
        AsyncMock(
            return_value=ApiKeyAuth(
                api_key_id="00000000-0000-0000-0000-000000000000",
                user_id="00000000-0000-0000-0000-000000000001",
                organization_id="00000000-0000-0000-0000-000000000002",
                scopes=["api:read"],
            )
        ),
    ):
        with pytest.raises(HTTPException) as exc:
            await resolve_claims(request, _session=session)
        assert exc.value.status_code == 403
        assert exc.value.detail == {
            "error": "insufficient_api_scope",
            "message": "Request is missing required REST scope.",
            "remediation": "Use a REST scope that matches this request.",
            "details": {
                "expected": "api:write",
                "actual": "api:read",
            },
        }


@pytest.mark.asyncio
async def test_api_key_rest_allows_write_with_api_write() -> None:
    request = _make_request(method="POST", path="/api/me", token="sk_live_test")
    session = object()

    with patch(
        "sibyl.auth.dependencies.authenticate_api_key",
        AsyncMock(
            return_value=ApiKeyAuth(
                api_key_id="00000000-0000-0000-0000-000000000000",
                user_id="00000000-0000-0000-0000-000000000001",
                organization_id="00000000-0000-0000-0000-000000000002",
                scopes=["api:write"],
            )
        ),
    ):
        claims = await resolve_claims(request, _session=session)
        assert claims is not None
        assert claims["typ"] == "api_key"
        assert "api:write" in claims["scopes"]
