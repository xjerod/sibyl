"""Shared organization runtime DTOs and helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sibyl.db.models import OrganizationRole, ProjectRole


@dataclass
class LegacyOrgSummary:
    id: UUID
    slug: str
    name: str
    is_personal: bool = False
    role: OrganizationRole | None = None


@dataclass
class LegacyOrgAuthResult:
    id: UUID
    slug: str
    name: str
    access_token: str
    refresh_token: str
    refresh_expires: datetime


@dataclass
class LegacyOrgRoleResult:
    id: UUID
    slug: str
    name: str
    role: OrganizationRole


@dataclass
class LegacyOrgMemberChange:
    org_id: UUID
    user_id: UUID
    role: OrganizationRole | None = None


@dataclass
class LegacyInvitationRecord:
    id: UUID
    email: str
    role: OrganizationRole
    created_at: datetime | None = None
    expires_at: datetime | None = None
    accept_url: str | None = None


@dataclass
class LegacyInvitationAcceptance:
    access_token: str
    refresh_token: str
    refresh_expires: datetime
    organization_id: UUID
    invitation_id: UUID


@dataclass
class LegacyProjectMembersResult:
    members: list[dict[str, object]]
    can_manage: bool


@dataclass
class LegacyProjectMemberChange:
    org_id: UUID
    project_db_id: UUID
    user_id: UUID
    role: ProjectRole | None = None


def can_manage_legacy_project_members(
    role: ProjectRole | None,
    project: Any,
    user: Any,
) -> bool:
    """Return whether the actor can manage project members."""
    if project.owner_user_id == user.id:
        return True
    return role in {ProjectRole.OWNER, ProjectRole.MAINTAINER}
