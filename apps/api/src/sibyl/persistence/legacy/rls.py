"""Legacy relational RLS helpers."""

from __future__ import annotations

from collections.abc import Awaitable, Mapping
from typing import Protocol
from uuid import UUID

from sqlalchemy import text


class RlsSession(Protocol):
    def execute(
        self,
        statement: object,
        params: Mapping[str, object] | None = None,
    ) -> Awaitable[object]: ...


async def set_legacy_rls_context(
    session: RlsSession,
    *,
    user_id: UUID | str | None = None,
    org_id: UUID | str | None = None,
) -> None:
    await session.execute(
        text("SELECT set_config('app.user_id', :user_id, true)"),
        {"user_id": str(user_id) if user_id else ""},
    )
    await session.execute(
        text("SELECT set_config('app.org_id', :org_id, true)"),
        {"org_id": str(org_id) if org_id else ""},
    )
