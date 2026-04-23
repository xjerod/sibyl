"""Active organization runtime adapters for the configured auth backend."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from sibyl.config import settings
from sibyl.persistence.organization_common import (
    can_manage_legacy_project_members as _can_manage_legacy_project_members,
)

_RUNTIME_EXPORTS = [
    "accept_legacy_org_invitation",
    "add_legacy_org_member",
    "add_legacy_project_member",
    "create_legacy_org",
    "create_legacy_org_invitation",
    "delete_legacy_org",
    "delete_legacy_org_invitation",
    "get_legacy_org",
    "list_legacy_org_ids",
    "list_legacy_org_invitations",
    "list_legacy_org_members",
    "list_legacy_orgs",
    "list_legacy_project_members",
    "remove_legacy_org_member",
    "remove_legacy_project_member",
    "switch_legacy_org",
    "update_legacy_org",
    "update_legacy_org_member_role",
    "update_legacy_project_member_role",
]

_NEUTRAL_EXPORTS = [
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

_BACKEND_EXPORTS: dict[str, dict[str, tuple[str, str]]] = {
    "postgres": {
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
    },
    "surreal": {
        name: ("sibyl.persistence.surreal.organization_runtime", name) for name in _RUNTIME_EXPORTS
    },
}

__all__ = list(_RUNTIME_EXPORTS)
__all__.insert(0, "can_manage_project_members")
__all__.insert(0, "can_manage_legacy_project_members")
__all__.extend(_NEUTRAL_EXPORTS)
can_manage_legacy_project_members = _can_manage_legacy_project_members
can_manage_project_members = _can_manage_legacy_project_members


def _resolve_backend_export(name: str) -> Any:
    module_path, attr_name = _BACKEND_EXPORTS[settings.auth_store][name]
    return getattr(import_module(module_path), attr_name)


def _make_runtime_proxy(name: str) -> Any:
    async def _proxy(*args: object, **kwargs: object) -> object:
        export = _resolve_backend_export(name)
        return await export(*args, **kwargs)

    _proxy.__name__ = name
    return _proxy


for _export_name in _RUNTIME_EXPORTS:
    if _export_name not in globals():
        globals()[_export_name] = _make_runtime_proxy(_export_name)


async def _call_runtime_export(name: str, *args: object, **kwargs: object) -> Any:
    export = _resolve_backend_export(name)
    return await export(*args, **kwargs)


async def accept_org_invitation(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("accept_legacy_org_invitation", *args, **kwargs)


async def add_org_member(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("add_legacy_org_member", *args, **kwargs)


async def add_project_member(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("add_legacy_project_member", *args, **kwargs)


async def create_org(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("create_legacy_org", *args, **kwargs)


async def create_org_invitation(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("create_legacy_org_invitation", *args, **kwargs)


async def delete_org(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("delete_legacy_org", *args, **kwargs)


async def delete_org_invitation(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("delete_legacy_org_invitation", *args, **kwargs)


async def get_org(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("get_legacy_org", *args, **kwargs)


async def list_org_ids(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("list_legacy_org_ids", *args, **kwargs)


async def list_org_invitations(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("list_legacy_org_invitations", *args, **kwargs)


async def list_org_members(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("list_legacy_org_members", *args, **kwargs)


async def list_orgs(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("list_legacy_orgs", *args, **kwargs)


async def list_project_members(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("list_legacy_project_members", *args, **kwargs)


async def remove_org_member(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("remove_legacy_org_member", *args, **kwargs)


async def remove_project_member(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("remove_legacy_project_member", *args, **kwargs)


async def switch_org(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("switch_legacy_org", *args, **kwargs)


async def update_org(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("update_legacy_org", *args, **kwargs)


async def update_org_member_role(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("update_legacy_org_member_role", *args, **kwargs)


async def update_project_member_role(*args: object, **kwargs: object) -> Any:
    return await _call_runtime_export("update_legacy_project_member_role", *args, **kwargs)
