from __future__ import annotations

import pytest

from sibyl.services.recall_limits import (
    RECALL_MAX_CONCURRENT_ENV,
    RecallConcurrencyLimiter,
    RecallConcurrencyLimitExceededError,
)
from sibyl_core.auth import OrganizationRole


@pytest.mark.asyncio
async def test_recall_limiter_rejects_second_member_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(RECALL_MAX_CONCURRENT_ENV, raising=False)
    limiter = RecallConcurrencyLimiter(default_max_concurrent=1)

    async with limiter.slot(
        organization_id="org-1",
        user_id="user-1",
        organization_role=OrganizationRole.MEMBER,
    ):
        with pytest.raises(RecallConcurrencyLimitExceededError) as exc:
            async with limiter.slot(
                organization_id="org-1",
                user_id="user-1",
                organization_role=OrganizationRole.MEMBER,
            ):
                pass

    assert exc.value.max_concurrent == 1
    assert exc.value.user_id == "user-1"


@pytest.mark.asyncio
async def test_recall_limiter_releases_member_slot(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(RECALL_MAX_CONCURRENT_ENV, raising=False)
    limiter = RecallConcurrencyLimiter(default_max_concurrent=1)

    async with limiter.slot(
        organization_id="org-1",
        user_id="user-1",
        organization_role=OrganizationRole.MEMBER,
    ):
        pass

    async with limiter.slot(
        organization_id="org-1",
        user_id="user-1",
        organization_role=OrganizationRole.MEMBER,
    ):
        pass


@pytest.mark.asyncio
async def test_recall_limiter_bypasses_owner(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(RECALL_MAX_CONCURRENT_ENV, raising=False)
    limiter = RecallConcurrencyLimiter(default_max_concurrent=1)

    async with (
        limiter.slot(
            organization_id="org-1",
            user_id="user-1",
            organization_role=OrganizationRole.OWNER,
        ),
        limiter.slot(
            organization_id="org-1",
            user_id="user-1",
            organization_role=OrganizationRole.OWNER,
        ),
    ):
        pass


@pytest.mark.asyncio
async def test_recall_limiter_uses_environment_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(RECALL_MAX_CONCURRENT_ENV, "2")
    limiter = RecallConcurrencyLimiter(default_max_concurrent=1)

    async with (
        limiter.slot(
            organization_id="org-1",
            user_id="user-1",
            organization_role=OrganizationRole.MEMBER,
        ),
        limiter.slot(
            organization_id="org-1",
            user_id="user-1",
            organization_role=OrganizationRole.MEMBER,
        ),
    ):
        with pytest.raises(RecallConcurrencyLimitExceededError):
            async with limiter.slot(
                organization_id="org-1",
                user_id="user-1",
                organization_role=OrganizationRole.MEMBER,
            ):
                pass
