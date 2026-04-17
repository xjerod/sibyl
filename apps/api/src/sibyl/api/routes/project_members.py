"""Project membership endpoints."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field

from sibyl.api.websocket import broadcast_event
from sibyl.auth.dependencies import get_current_org_role, get_current_organization, get_current_user
from sibyl.db.models import Organization, Project, ProjectRole, User
from sibyl.persistence.legacy.project_members import (
    add_legacy_project_member,
    can_manage_legacy_project_members,
    list_legacy_project_members,
    remove_legacy_project_member,
    update_legacy_project_member_role,
)

router = APIRouter(prefix="/projects/{project_id}/members", tags=["project-members"])


class MemberAddRequest(BaseModel):
    user_id: UUID
    role: ProjectRole = Field(default=ProjectRole.CONTRIBUTOR)


class MemberRoleUpdateRequest(BaseModel):
    role: ProjectRole


def _can_manage_members(role: ProjectRole | None, project: Project, user: User) -> bool:
    return can_manage_legacy_project_members(role, project, user)


@router.get("")
async def list_members(
    project_id: str,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_organization),
    _org_role=Depends(get_current_org_role),
):
    result = await list_legacy_project_members(
        project_id=project_id,
        actor=user,
        org_id=org.id,
    )
    return {"members": result.members, "can_manage": result.can_manage}


@router.post("")
async def add_member(
    request: Request,
    project_id: str,
    body: MemberAddRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_organization),
    _org_role=Depends(get_current_org_role),
):
    membership = await add_legacy_project_member(
        request=request,
        project_id=project_id,
        actor=user,
        org_id=org.id,
        target_user_id=body.user_id,
        role=body.role,
    )

    background_tasks.add_task(
        broadcast_event,
        "permission_changed",
        {
            "user_id": str(body.user_id),
            "change_type": "project_member_added",
            "project_id": str(project_id),
            "project_role": membership.role.value,
        },
        org_id=str(org.id),
    )

    return {"user_id": str(membership.user_id), "role": membership.role.value}


@router.patch("/{user_id}")
async def update_member_role(
    request: Request,
    project_id: str,
    user_id: UUID,
    body: MemberRoleUpdateRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_organization),
    _org_role=Depends(get_current_org_role),
):
    membership = await update_legacy_project_member_role(
        request=request,
        project_id=project_id,
        actor=user,
        org_id=org.id,
        target_user_id=user_id,
        role=body.role,
    )

    background_tasks.add_task(
        broadcast_event,
        "permission_changed",
        {
            "user_id": str(user_id),
            "change_type": "project_role_changed",
            "project_id": str(project_id),
            "project_role": membership.role.value,
        },
        org_id=str(org.id),
    )

    return {"user_id": str(membership.user_id), "role": membership.role.value}


@router.delete("/{user_id}")
async def remove_member(
    request: Request,
    project_id: str,
    user_id: UUID,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_organization),
    _org_role=Depends(get_current_org_role),
):
    await remove_legacy_project_member(
        request=request,
        project_id=project_id,
        actor=user,
        org_id=org.id,
        target_user_id=user_id,
    )

    background_tasks.add_task(
        broadcast_event,
        "permission_changed",
        {
            "user_id": str(user_id),
            "change_type": "project_member_removed",
            "project_id": str(project_id),
        },
        org_id=str(org.id),
    )

    return {"success": True}
