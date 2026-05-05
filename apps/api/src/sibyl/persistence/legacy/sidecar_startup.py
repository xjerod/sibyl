"""Legacy relational sidecar startup helpers."""

from __future__ import annotations

from sqlalchemy import text


async def check_relational_sidecar_connection() -> None:
    from sibyl.db.connection import get_session

    async with get_session() as session:
        await session.execute(text("SELECT 1"))


async def run_relational_sidecar_migrations() -> None:
    from sibyl.db.migrations import run_migrations

    await run_migrations()


async def recover_relational_sidecar_sources() -> None:
    from sibyl.api.routes.admin import recover_stuck_sources

    await recover_stuck_sources()


async def load_relational_sidecar_api_keys() -> None:
    from sibyl.services.settings import load_api_keys_from_db

    await load_api_keys_from_db()


__all__ = [
    "check_relational_sidecar_connection",
    "load_relational_sidecar_api_keys",
    "recover_relational_sidecar_sources",
    "run_relational_sidecar_migrations",
]
