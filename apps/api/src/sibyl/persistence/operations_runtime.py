"""Active operational adapters for the current runtime."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from sibyl.config import settings
from sibyl.persistence.auth_runtime import (
    confirm_password_reset,
    list_oauth_connections,
    remove_oauth_connection,
    request_password_reset,
)
from sibyl.persistence.backups_runtime import (
    attach_backup_job,
    create_backup_record,
    delete_backup_record,
    get_backup,
    get_backup_retention,
    get_backup_settings,
    list_backups,
    update_backup_settings,
)

if TYPE_CHECKING:
    get_setup_status: Any
    is_setup_mode: Any
    require_settings_admin: Any
    require_setup_mode_or_admin: Any
    require_setup_mode_or_auth: Any

_AUTH_BACKEND_MODULES = {
    "postgres": "sibyl.persistence.legacy.setup",
    "surreal": "sibyl.persistence.surreal.setup",
}

_AUTH_RUNTIME_EXPORTS = [
    "get_setup_status",
    "is_setup_mode",
    "require_settings_admin",
    "require_setup_mode_or_admin",
    "require_setup_mode_or_auth",
]

__all__ = [
    "attach_backup_job",
    "confirm_password_reset",
    "create_backup_record",
    "delete_backup_record",
    "get_backup",
    "get_backup_retention",
    "get_backup_settings",
    "get_setup_status",
    "is_setup_mode",
    "require_settings_admin",
    "require_setup_mode_or_admin",
    "require_setup_mode_or_auth",
    "list_backups",
    "list_oauth_connections",
    "remove_oauth_connection",
    "request_password_reset",
    "update_backup_settings",
]


def _auth_backend_module() -> Any:
    return import_module(_AUTH_BACKEND_MODULES[settings.auth_store])


def _make_auth_runtime_proxy(name: str) -> Any:
    async def _proxy(*args: object, **kwargs: object) -> object:
        export = getattr(_auth_backend_module(), name)
        return await export(*args, **kwargs)

    _proxy.__name__ = name
    return _proxy


for _export_name in _AUTH_RUNTIME_EXPORTS:
    globals()[_export_name] = _make_auth_runtime_proxy(_export_name)


del _export_name
