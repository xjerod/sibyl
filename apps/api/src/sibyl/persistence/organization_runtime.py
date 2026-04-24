"""Active organization runtime adapters for the configured auth backend."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from sibyl.config import settings
from sibyl.persistence.organization_common import (
    can_manage_project_members as _can_manage_project_members,
)

if TYPE_CHECKING:
    accept_org_invitation: Any
    add_org_member: Any
    add_project_member: Any
    create_org: Any
    create_org_invitation: Any
    delete_org: Any
    delete_org_invitation: Any
    get_org: Any
    list_org_ids: Any
    list_org_invitations: Any
    list_org_members: Any
    list_orgs: Any
    list_project_members: Any
    remove_org_member: Any
    remove_project_member: Any
    switch_org: Any
    update_org: Any
    update_org_member_role: Any
    update_project_member_role: Any

_BACKEND_EXPORTS = [
    "accept_org_invitation",
    "add_org_member",
    "add_project_member",
    "create_org",
    "create_org_invitation",
    "delete_org",
    "delete_org_invitation",
    "get_org",
    "list_org_ids",
    "list_org_invitations",
    "list_org_members",
    "list_orgs",
    "list_project_members",
    "remove_org_member",
    "remove_project_member",
    "switch_org",
    "update_org",
    "update_org_member_role",
    "update_project_member_role",
]

_BACKEND_MODULES = {
    "postgres": (
        "sibyl.persistence.legacy.orgs",
        "sibyl.persistence.legacy.org_members",
        "sibyl.persistence.legacy.org_invitations",
        "sibyl.persistence.legacy.project_members",
    ),
    "surreal": ("sibyl.persistence.surreal.organization_runtime",),
}

__all__ = [
    "can_manage_project_members",
    "accept_org_invitation",
    "add_org_member",
    "add_project_member",
    "create_org",
    "create_org_invitation",
    "delete_org",
    "delete_org_invitation",
    "get_org",
    "list_org_ids",
    "list_org_invitations",
    "list_org_members",
    "list_orgs",
    "list_project_members",
    "remove_org_member",
    "remove_project_member",
    "switch_org",
    "update_org",
    "update_org_member_role",
    "update_project_member_role",
]

can_manage_project_members = _can_manage_project_members


def _resolve_backend_export(name: str) -> Any:
    for module_path in _BACKEND_MODULES[settings.auth_store]:
        module = import_module(module_path)
        if hasattr(module, name):
            return getattr(module, name)
    msg = f"{name} is not implemented for SIBYL_AUTH_STORE={settings.auth_store!r}"
    raise AttributeError(msg)


def _make_runtime_proxy(name: str) -> Any:
    async def _proxy(*args: object, **kwargs: object) -> object:
        export = _resolve_backend_export(name)
        return await export(*args, **kwargs)

    _proxy.__name__ = name
    return _proxy


for _export_name in _BACKEND_EXPORTS:
    if _export_name not in globals():
        globals()[_export_name] = _make_runtime_proxy(_export_name)


del _export_name
