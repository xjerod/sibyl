from __future__ import annotations

import pytest

from sibyl.persistence import auth_runtime
from sibyl.persistence.auth_common import InvalidAuthClaimsError, UserNotFoundError
from sibyl.persistence.legacy.auth import LegacyAuthContextResolver
from sibyl.persistence.surreal.auth import SurrealAuthContextResolver
from sibyl.persistence.surreal.auth_runtime import (
    SurrealSessionRepository,
    resolve_surreal_auth_context,
)


def test_auth_runtime_uses_shared_error_types(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_runtime.settings, "auth_store", "postgres")

    assert auth_runtime.InvalidAuthClaimsError is InvalidAuthClaimsError
    assert auth_runtime.UserNotFoundError is UserNotFoundError
    assert auth_runtime.LegacyAuthContextResolver is LegacyAuthContextResolver


def test_auth_runtime_maps_resolver_name_for_surreal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_runtime.settings, "auth_store", "surreal")

    assert auth_runtime.LegacyAuthContextResolver is SurrealAuthContextResolver
    assert auth_runtime.LegacySessionRepository is SurrealSessionRepository
    assert auth_runtime.resolve_surreal_auth_context is resolve_surreal_auth_context


def test_auth_runtime_maps_auth_exports_for_surreal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_runtime.settings, "auth_store", "surreal")

    assert auth_runtime.authenticate_legacy_api_key.__module__ == (
        "sibyl.persistence.surreal.auth_runtime"
    )
