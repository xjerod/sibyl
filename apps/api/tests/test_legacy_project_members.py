"""Tests for legacy project member persistence helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from sibyl.db.models import ProjectRole
from sibyl.persistence.legacy import project_members as legacy_project_members


class TestGetLegacyProjectAndUserRole:
    @pytest.mark.asyncio
    async def test_resolves_graph_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        user_id = uuid4()
        org_id = uuid4()
        project = MagicMock()
        project.organization_id = org_id
        project.owner_user_id = user_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = project

        session = AsyncMock()
        session.execute.return_value = mock_result
        session_manager = AsyncMock()
        session_manager.__aenter__.return_value = session
        session_manager.__aexit__.return_value = False

        monkeypatch.setattr(legacy_project_members, "get_session", lambda: session_manager)

        result_project, role = await legacy_project_members.get_legacy_project_and_user_role(
            project_id="project_abc123",
            user_id=user_id,
            org_id=org_id,
        )

        assert result_project == project
        assert role == ProjectRole.OWNER

    @pytest.mark.asyncio
    async def test_project_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        session = AsyncMock()
        session.get.return_value = None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result
        session_manager = AsyncMock()
        session_manager.__aenter__.return_value = session
        session_manager.__aexit__.return_value = False

        monkeypatch.setattr(legacy_project_members, "get_session", lambda: session_manager)

        with pytest.raises(HTTPException) as exc_info:
            await legacy_project_members.get_legacy_project_and_user_role(
                project_id=str(uuid4()),
                user_id=uuid4(),
                org_id=uuid4(),
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_project_wrong_org(self, monkeypatch: pytest.MonkeyPatch) -> None:
        org_id = uuid4()
        project = MagicMock()
        project.organization_id = uuid4()

        session = AsyncMock()
        session.get.return_value = project
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result
        session_manager = AsyncMock()
        session_manager.__aenter__.return_value = session
        session_manager.__aexit__.return_value = False

        monkeypatch.setattr(legacy_project_members, "get_session", lambda: session_manager)

        with pytest.raises(HTTPException) as exc_info:
            await legacy_project_members.get_legacy_project_and_user_role(
                project_id=str(uuid4()),
                user_id=uuid4(),
                org_id=org_id,
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_direct_member_gets_their_role(self, monkeypatch: pytest.MonkeyPatch) -> None:
        user_id = uuid4()
        org_id = uuid4()
        project = MagicMock()
        project.id = uuid4()
        project.organization_id = org_id
        project.owner_user_id = uuid4()

        membership = MagicMock()
        membership.role = ProjectRole.CONTRIBUTOR
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = membership

        session = AsyncMock()
        session.get.return_value = project
        session.execute.return_value = mock_result
        session_manager = AsyncMock()
        session_manager.__aenter__.return_value = session
        session_manager.__aexit__.return_value = False

        monkeypatch.setattr(legacy_project_members, "get_session", lambda: session_manager)

        result_project, role = await legacy_project_members.get_legacy_project_and_user_role(
            project_id=str(uuid4()),
            user_id=user_id,
            org_id=org_id,
        )

        assert result_project == project
        assert role == ProjectRole.CONTRIBUTOR


class TestLegacyProjectMemberMutations:
    @pytest.mark.asyncio
    async def test_add_member_rejects_existing_membership(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        actor = MagicMock()
        actor.id = uuid4()
        org_id = uuid4()
        project = MagicMock()
        project.id = uuid4()
        project.owner_user_id = actor.id
        target_user = MagicMock()
        target_user.id = uuid4()

        existing_result = MagicMock()
        existing_result.scalar_one_or_none.return_value = object()

        session = AsyncMock()
        session.get.side_effect = [target_user]
        session.execute.side_effect = [existing_result]

        monkeypatch.setattr(
            legacy_project_members,
            "_get_legacy_project_and_user_role",
            AsyncMock(return_value=(project, ProjectRole.OWNER)),
        )
        session_manager = AsyncMock()
        session_manager.__aenter__.return_value = session
        session_manager.__aexit__.return_value = False
        monkeypatch.setattr(legacy_project_members, "get_session", lambda: session_manager)

        with pytest.raises(HTTPException) as exc_info:
            await legacy_project_members.add_legacy_project_member(
                request=MagicMock(),
                project_id="project_123",
                actor=actor,
                org_id=org_id,
                target_user_id=target_user.id,
                role=ProjectRole.CONTRIBUTOR,
            )

        assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_remove_member_allows_self_without_manage_permission(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        actor = MagicMock()
        actor.id = uuid4()
        org_id = uuid4()
        project = MagicMock()
        project.id = uuid4()
        project.owner_user_id = uuid4()
        membership = MagicMock()

        member_result = MagicMock()
        member_result.scalar_one_or_none.return_value = membership

        session = AsyncMock()
        session.execute.return_value = member_result
        session_manager = AsyncMock()
        session_manager.__aenter__.return_value = session
        session_manager.__aexit__.return_value = False

        monkeypatch.setattr(
            legacy_project_members,
            "_get_legacy_project_and_user_role",
            AsyncMock(return_value=(project, ProjectRole.VIEWER)),
        )
        monkeypatch.setattr(legacy_project_members, "get_session", lambda: session_manager)
        monkeypatch.setattr(
            legacy_project_members,
            "AuditLogger",
            lambda _session: MagicMock(log=AsyncMock()),
        )

        payload = await legacy_project_members.remove_legacy_project_member(
            request=MagicMock(),
            project_id="project_123",
            actor=actor,
            org_id=org_id,
            target_user_id=actor.id,
        )

        session.delete.assert_awaited_once_with(membership)
        assert payload.user_id == actor.id
