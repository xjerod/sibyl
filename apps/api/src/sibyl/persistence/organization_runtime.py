"""Active organization runtime adapters for the configured auth backend."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from sibyl.config import settings
from sibyl.persistence.organization_common import (
    can_manage_project_members as _can_manage_project_members,
)

_NEUTRAL_EXPORT_ALIASES = {
    "accept_org_invitation": "accept_legacy_org_invitation",
    "add_org_member": "add_legacy_org_member",
    "add_project_member": "add_legacy_project_member",
    "create_org": "create_legacy_org",
    "create_org_invitation": "create_legacy_org_invitation",
    "delete_org": "delete_legacy_org",
    "delete_org_invitation": "delete_legacy_org_invitation",
    "get_org": "get_legacy_org",
    "list_org_ids": "list_legacy_org_ids",
    "list_org_invitations": "list_legacy_org_invitations",
    "list_org_members": "list_legacy_org_members",
    "list_orgs": "list_legacy_orgs",
    "list_project_members": "list_legacy_project_members",
    "remove_org_member": "remove_legacy_org_member",
    "remove_project_member": "remove_legacy_project_member",
    "switch_org": "switch_legacy_org",
    "update_org": "update_legacy_org",
    "update_org_member_role": "update_legacy_org_member_role",
    "update_project_member_role": "update_legacy_project_member_role",
}

_LEGACY_EXPORT_ALIASES = {
    legacy_name: neutral_name
    for neutral_name, legacy_name in _NEUTRAL_EXPORT_ALIASES.items()
}

_POSTGRES_LEGACY_EXPORTS: dict[str, tuple[str, str]] = {
    "accept_legacy_org_invitation": (
        "sibyl.persistence.legacy.org_invitations",
        "accept_legacy_org_invitation",
    ),
    "add_legacy_org_member": ("sibyl.persistence.legacy.org_members", "add_legacy_org_member"),
    "add_legacy_project_member": (
        "sibyl.persistence.legacy.project_members",
        "add_legacy_project_member",
    ),
    "create_legacy_org": ("sibyl.persistence.legacy.orgs", "create_legacy_org"),
    "create_legacy_org_invitation": (
        "sibyl.persistence.legacy.org_invitations",
        "create_legacy_org_invitation",
    ),
    "delete_legacy_org": ("sibyl.persistence.legacy.orgs", "delete_legacy_org"),
    "delete_legacy_org_invitation": (
        "sibyl.persistence.legacy.org_invitations",
        "delete_legacy_org_invitation",
    ),
    "get_legacy_org": ("sibyl.persistence.legacy.orgs", "get_legacy_org"),
    "list_legacy_org_ids": ("sibyl.persistence.legacy.orgs", "list_legacy_org_ids"),
    "list_legacy_org_invitations": (
        "sibyl.persistence.legacy.org_invitations",
        "list_legacy_org_invitations",
    ),
    "list_legacy_org_members": (
        "sibyl.persistence.legacy.org_members",
        "list_legacy_org_members",
    ),
    "list_legacy_orgs": ("sibyl.persistence.legacy.orgs", "list_legacy_orgs"),
    "list_legacy_project_members": (
        "sibyl.persistence.legacy.project_members",
        "list_legacy_project_members",
    ),
    "remove_legacy_org_member": (
        "sibyl.persistence.legacy.org_members",
        "remove_legacy_org_member",
    ),
    "remove_legacy_project_member": (
        "sibyl.persistence.legacy.project_members",
        "remove_legacy_project_member",
    ),
    "switch_legacy_org": ("sibyl.persistence.legacy.orgs", "switch_legacy_org"),
    "update_legacy_org": ("sibyl.persistence.legacy.orgs", "update_legacy_org"),
    "update_legacy_org_member_role": (
        "sibyl.persistence.legacy.org_members",
        "update_legacy_org_member_role",
    ),
    "update_legacy_project_member_role": (
        "sibyl.persistence.legacy.project_members",
        "update_legacy_project_member_role",
    ),
}

_BACKEND_EXPORTS: dict[str, dict[str, tuple[str, str]]] = {
    "postgres": {
        neutral_name: _POSTGRES_LEGACY_EXPORTS[legacy_name]
        for neutral_name, legacy_name in _NEUTRAL_EXPORT_ALIASES.items()
    },
    "surreal": {
        neutral_name: ("sibyl.persistence.surreal.organization_runtime", legacy_name)
        for neutral_name, legacy_name in _NEUTRAL_EXPORT_ALIASES.items()
    },
}

__all__ = [
    "can_manage_project_members",
    "can_manage_legacy_project_members",
]
__all__.extend(_NEUTRAL_EXPORT_ALIASES)
__all__.extend(_LEGACY_EXPORT_ALIASES)

can_manage_project_members = _can_manage_project_members
can_manage_legacy_project_members = can_manage_project_members


def _resolve_backend_export(name: str) -> Any:
    module_path, attr_name = _BACKEND_EXPORTS[settings.auth_store][name]
    return getattr(import_module(module_path), attr_name)


def _make_runtime_proxy(name: str) -> Any:
    async def _proxy(*args: object, **kwargs: object) -> object:
        export = _resolve_backend_export(name)
        return await export(*args, **kwargs)

    _proxy.__name__ = name
    return _proxy


for _neutral_name in _NEUTRAL_EXPORT_ALIASES:
    if _neutral_name not in globals():
        globals()[_neutral_name] = _make_runtime_proxy(_neutral_name)


for _legacy_name, _neutral_name in _LEGACY_EXPORT_ALIASES.items():
    globals()[_legacy_name] = globals()[_neutral_name]


del _legacy_name
del _neutral_name
