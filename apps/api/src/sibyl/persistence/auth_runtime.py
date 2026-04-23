"""Active auth runtime adapters for the configured auth backend."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sibyl.config import settings
from sibyl.persistence.auth_common import InvalidAuthClaimsError, UserNotFoundError

if TYPE_CHECKING:
    from sibyl.persistence.legacy.auth import (
        LegacyAuthContextResolver,
        LegacyOrganizationMembershipRepository,
        LegacyOrganizationRepository,
        LegacySessionRepository,
        LegacyUserRepository,
        approve_legacy_device_authorization,
        authenticate_legacy_api_key,
        authenticate_legacy_local_user,
        create_legacy_api_key_for_user,
        create_legacy_session_record,
        deny_legacy_device_authorization,
        ensure_legacy_personal_organization,
        exchange_legacy_device_code,
        get_legacy_device_request_by_user_code,
        get_legacy_user_by_id,
        has_legacy_owner_membership,
        list_legacy_accessible_project_graph_ids,
        list_legacy_api_keys_for_user,
        list_legacy_user_organizations,
        load_legacy_refresh_session_record,
        log_legacy_audit_event,
        login_legacy_device_browser_user,
        login_legacy_github_identity,
        login_legacy_local_user,
        resolve_legacy_accessible_project_graph_ids,
        resolve_legacy_request_claims,
        resolve_legacy_request_user,
        resolve_surreal_auth_context,
        revoke_legacy_access_session,
        revoke_legacy_api_key_for_user,
        revoke_legacy_refresh_session_record,
        rotate_legacy_refresh_exchange,
        rotate_legacy_refresh_session_record,
        signup_legacy_local_user,
        start_legacy_device_authorization,
        update_legacy_auth_user,
        verify_legacy_entity_project_access,
    )

_BACKEND_MODULES = {
    "postgres": "sibyl.persistence.legacy.auth",
    "surreal": "sibyl.persistence.surreal.auth_runtime",
}

_BACKEND_NAME_OVERRIDES = {
    "surreal": {
        "LegacyAuthContextResolver": "SurrealAuthContextResolver",
        "LegacyOrganizationMembershipRepository": "SurrealOrganizationMembershipRepository",
        "LegacyOrganizationRepository": "SurrealOrganizationRepository",
        "LegacySessionRepository": "SurrealSessionRepository",
        "LegacyUserRepository": "SurrealUserRepository",
    },
}

__all__ = [
    "InvalidAuthClaimsError",
    "LegacyAuthContextResolver",
    "LegacyOrganizationMembershipRepository",
    "LegacyOrganizationRepository",
    "LegacySessionRepository",
    "LegacyUserRepository",
    "UserNotFoundError",
    "approve_legacy_device_authorization",
    "authenticate_legacy_api_key",
    "authenticate_legacy_local_user",
    "create_legacy_api_key_for_user",
    "create_legacy_project_record",
    "create_legacy_session_record",
    "delete_legacy_project_record",
    "deny_legacy_device_authorization",
    "ensure_legacy_personal_organization",
    "exchange_legacy_device_code",
    "get_legacy_device_request_by_user_code",
    "get_legacy_user_by_id",
    "has_legacy_owner_membership",
    "list_legacy_accessible_project_graph_ids",
    "list_legacy_api_keys_for_user",
    "list_legacy_oauth_connections",
    "list_legacy_user_sessions",
    "list_legacy_user_organizations",
    "load_legacy_refresh_session_record",
    "log_legacy_audit_event",
    "login_legacy_device_browser_user",
    "login_legacy_github_identity",
    "login_legacy_local_user",
    "resolve_legacy_accessible_project_graph_ids",
    "resolve_surreal_auth_context",
    "resolve_legacy_request_claims",
    "resolve_legacy_request_user",
    "revoke_legacy_access_session",
    "revoke_legacy_api_key_for_user",
    "revoke_legacy_user_session",
    "revoke_all_legacy_user_sessions",
    "revoke_legacy_refresh_session_record",
    "rotate_legacy_refresh_exchange",
    "rotate_legacy_refresh_session_record",
    "signup_legacy_local_user",
    "start_legacy_device_authorization",
    "patch_legacy_auth_user",
    "request_legacy_password_reset",
    "confirm_legacy_password_reset",
    "remove_legacy_oauth_connection",
    "update_legacy_auth_user",
    "update_legacy_project_record",
    "verify_legacy_entity_project_access",
]


def _active_backend_name() -> str:
    return settings.auth_store


def _resolve_backend_export(name: str) -> Any:
    backend = _active_backend_name()
    module = import_module(_BACKEND_MODULES[backend])
    export_name = _BACKEND_NAME_OVERRIDES.get(backend, {}).get(name, name)
    if hasattr(module, export_name):
        return getattr(module, export_name)
    return _unsupported_export(name=name, backend=backend)


def _unsupported_export(*, name: str, backend: str) -> Any:
    message = (
        f"{name} is not implemented for SIBYL_AUTH_STORE={backend!r}. "
        "Keep SIBYL_AUTH_STORE=postgres for request-time auth flows until the "
        "remaining Surreal adapters land."
    )
    if name.endswith("Resolver"):

        class _UnsupportedResolver:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                raise NotImplementedError(message)

            @classmethod
            def from_session(cls, *_args: object, **_kwargs: object):
                raise NotImplementedError(message)

            @classmethod
            def from_client(cls, *_args: object, **_kwargs: object):
                raise NotImplementedError(message)

            async def resolve(self, *_args: object, **_kwargs: object) -> object:
                raise NotImplementedError(message)

        _UnsupportedResolver.__name__ = name
        return _UnsupportedResolver

    async def _unsupported(*_args: object, **_kwargs: object) -> object:
        raise NotImplementedError(message)

    _unsupported.__name__ = name
    return _unsupported


def __getattr__(name: str) -> Any:
    if name == "InvalidAuthClaimsError":
        return InvalidAuthClaimsError
    if name == "UserNotFoundError":
        return UserNotFoundError
    if name in __all__:
        return _resolve_backend_export(name)
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


async def patch_legacy_auth_user(
    *,
    user_id: UUID,
    updates: dict[str, Any],
    organization_id: UUID | None,
    request: Any,
):
    if settings.auth_store == "surreal":
        from sibyl.persistence.surreal.auth_runtime import (
            patch_legacy_auth_user as surreal_patch_user,
        )

        return await surreal_patch_user(
            user_id=user_id,
            updates=updates,
            organization_id=organization_id,
            request=request,
        )

    from fastapi import HTTPException

    from sibyl.auth.audit import AuditLogger
    from sibyl.auth.users import UserManager
    from sibyl.db.connection import get_session

    async with get_session() as session:
        manager = UserManager(session)
        user = await manager.get_by_id(user_id)
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        changes: list[str] = []
        profile_updates: dict[str, Any] = {}
        if "email" in updates:
            profile_updates["email"] = updates["email"]
            changes.append("email")
        if "name" in updates:
            profile_updates["name"] = updates["name"]
            changes.append("name")
        if "avatar_url" in updates:
            profile_updates["avatar_url"] = updates["avatar_url"]
            changes.append("avatar_url")

        try:
            if profile_updates:
                await manager.update_profile(user, **profile_updates)
            if "bio" in updates:
                user.bio = str(updates["bio"]).strip() or None if updates["bio"] is not None else None
                changes.append("bio")
            if "timezone" in updates:
                timezone = updates["timezone"]
                user.timezone = str(timezone).strip() or "UTC" if timezone is not None else "UTC"
                changes.append("timezone")
            if "preferences" in updates:
                preferences = updates["preferences"]
                if not isinstance(preferences, dict):
                    raise ValueError("Preferences must be an object")
                user.preferences = dict(preferences)
                changes.append("preferences")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if not changes:
            raise HTTPException(status_code=400, detail="No fields to update")

        await AuditLogger(session).log(
            action="user.update_profile",
            user_id=user.id,
            organization_id=organization_id,
            request=request,
            details={"fields": changes},
        )
        return user


async def create_legacy_project_record(
    *,
    organization_id: UUID,
    owner_user_id: UUID,
    graph_project_id: str,
    name: str,
    description: str | None = None,
) -> Any:
    if settings.auth_store == "surreal":
        from sibyl.persistence.surreal.auth_runtime import (
            create_legacy_project_record as surreal_create_project_record,
        )

        return await surreal_create_project_record(
            organization_id=organization_id,
            owner_user_id=owner_user_id,
            graph_project_id=graph_project_id,
            name=name,
            description=description,
        )

    from sibyl.db.connection import get_session
    from sibyl.db.project_sync import sync_project_create

    async with get_session() as session:
        return await sync_project_create(
            session,
            organization_id=organization_id,
            owner_user_id=owner_user_id,
            graph_project_id=graph_project_id,
            name=name,
            description=description,
        )


async def update_legacy_project_record(
    *,
    organization_id: UUID,
    graph_project_id: str,
    name: str | None = None,
    description: str | None = None,
) -> bool:
    if settings.auth_store == "surreal":
        from sibyl.persistence.surreal.auth_runtime import (
            update_legacy_project_record as surreal_update_project_record,
        )

        return await surreal_update_project_record(
            organization_id=organization_id,
            graph_project_id=graph_project_id,
            name=name,
            description=description,
        )

    from sibyl.db.connection import get_session
    from sibyl.db.project_sync import sync_project_update

    async with get_session() as session:
        return await sync_project_update(
            session,
            organization_id=organization_id,
            graph_project_id=graph_project_id,
            name=name,
            description=description,
        )


async def delete_legacy_project_record(
    *,
    organization_id: UUID,
    graph_project_id: str,
) -> bool:
    if settings.auth_store == "surreal":
        from sibyl.persistence.surreal.auth_runtime import (
            delete_legacy_project_record as surreal_delete_project_record,
        )

        return await surreal_delete_project_record(
            organization_id=organization_id,
            graph_project_id=graph_project_id,
        )

    from sibyl.db.connection import get_session
    from sibyl.db.project_sync import sync_project_delete

    async with get_session() as session:
        return await sync_project_delete(
            session,
            organization_id=organization_id,
            graph_project_id=graph_project_id,
        )


async def list_legacy_user_sessions(
    *,
    user_id: UUID,
    include_expired: bool = False,
):
    if settings.auth_store == "surreal":
        from sibyl.persistence.surreal.auth_runtime import (
            list_legacy_user_sessions as surreal_list_user_sessions,
        )

        return await surreal_list_user_sessions(
            user_id=user_id,
            include_expired=include_expired,
        )

    from sibyl.auth.sessions import SessionManager
    from sibyl.db.connection import get_session

    async with get_session() as session:
        manager = SessionManager(session)
        return await manager.list_user_sessions(user_id, include_expired=include_expired)


async def revoke_all_legacy_user_sessions(
    *,
    user_id: UUID,
    exclude_token_hash: str | None = None,
) -> int:
    if settings.auth_store == "surreal":
        from sibyl.persistence.surreal.auth_runtime import (
            revoke_all_legacy_user_sessions as surreal_revoke_all_user_sessions,
        )

        return await surreal_revoke_all_user_sessions(
            user_id=user_id,
            exclude_token_hash=exclude_token_hash,
        )

    from sibyl.auth.sessions import SessionManager
    from sibyl.db.connection import get_session

    async with get_session() as session:
        manager = SessionManager(session)
        return await manager.revoke_all_sessions(user_id, exclude_token_hash=exclude_token_hash)


async def revoke_legacy_user_session(
    *,
    user_id: UUID,
    session_id: UUID,
) -> bool:
    if settings.auth_store == "surreal":
        from sibyl.persistence.surreal.auth_runtime import (
            revoke_legacy_user_session as surreal_revoke_user_session,
        )

        return await surreal_revoke_user_session(
            user_id=user_id,
            session_id=session_id,
        )

    from sibyl.auth.sessions import SessionManager
    from sibyl.db.connection import get_session

    async with get_session() as session:
        manager = SessionManager(session)
        return await manager.revoke_session(session_id, user_id)


async def request_legacy_password_reset(email: str) -> None:
    if settings.auth_store == "surreal":
        from sibyl.persistence.surreal.auth_runtime import (
            request_legacy_password_reset as surreal_request_password_reset,
        )

        await surreal_request_password_reset(email)
        return

    from sibyl.persistence.legacy.users import (
        request_legacy_password_reset as legacy_request_password_reset,
    )

    await legacy_request_password_reset(email)


async def confirm_legacy_password_reset(token: str, new_password: str) -> None:
    if settings.auth_store == "surreal":
        from sibyl.persistence.surreal.auth_runtime import (
            confirm_legacy_password_reset as surreal_confirm_password_reset,
        )

        await surreal_confirm_password_reset(token, new_password)
        return

    from sibyl.persistence.legacy.users import (
        confirm_legacy_password_reset as legacy_confirm_password_reset,
    )

    await legacy_confirm_password_reset(token, new_password)


async def list_legacy_oauth_connections(*, user_id: UUID):
    if settings.auth_store == "surreal":
        from sibyl.persistence.surreal.auth_runtime import (
            list_legacy_oauth_connections as surreal_list_oauth_connections,
        )

        return await surreal_list_oauth_connections(user_id=user_id)

    from sibyl.db.connection import get_session
    from sibyl.persistence.legacy.users import (
        list_legacy_oauth_connections as legacy_list_oauth_connections,
    )

    async with get_session() as session:
        return await legacy_list_oauth_connections(session, user_id)


async def remove_legacy_oauth_connection(
    *,
    user_id: UUID,
    connection_id: UUID,
):
    if settings.auth_store == "surreal":
        from sibyl.persistence.surreal.auth_runtime import (
            remove_legacy_oauth_connection as surreal_remove_oauth_connection,
        )

        return await surreal_remove_oauth_connection(
            user_id=user_id,
            connection_id=connection_id,
        )

    from sibyl.db.connection import get_session
    from sibyl.persistence.legacy.users import (
        remove_legacy_oauth_connection as legacy_remove_oauth_connection,
    )

    async with get_session() as session:
        return await legacy_remove_oauth_connection(
            session,
            user_id=user_id,
            connection_id=connection_id,
        )
