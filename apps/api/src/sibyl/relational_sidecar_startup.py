"""Bootstrap the remaining relational sidecar services during startup."""

from __future__ import annotations

import structlog

from sibyl.config import settings

log = structlog.get_logger()


async def check_relational_sidecar_connection() -> None:
    from sibyl.persistence.legacy.sidecar_startup import (
        check_relational_sidecar_connection as _check_connection,
    )

    await _check_connection()


async def run_relational_sidecar_migrations() -> None:
    from sibyl.persistence.legacy.sidecar_startup import (
        run_relational_sidecar_migrations as _run_migrations,
    )

    await _run_migrations()


async def recover_relational_sidecar_sources() -> None:
    from sibyl.persistence.legacy.sidecar_startup import (
        recover_relational_sidecar_sources as _recover_sources,
    )

    await _recover_sources()


async def load_relational_sidecar_api_keys() -> None:
    from sibyl.persistence.legacy.sidecar_startup import (
        load_relational_sidecar_api_keys as _load_api_keys,
    )

    await _load_api_keys()


async def bootstrap_relational_sidecar_support() -> bool:
    if not settings.requires_relational_support:
        log.info(
            "Relational sidecar bootstrap disabled in fully surreal mode", store=settings.store
        )
        return False

    log.warning(
        "Legacy relational runtime is deprecated; migrate this install to SurrealDB",
        store=settings.store,
        auth_store=settings.auth_store,
        suggested_store="surreal",
        suggested_auth_store="surreal",
        migration_command="moon run dev -- --migrate-legacy",
        migration_guide="docs/guide/migrating-from-falkor.md",
    )

    try:
        await check_relational_sidecar_connection()
    except Exception as exc:
        log.warning(
            "Relational sidecar unavailable at startup", error=str(exc), store=settings.store
        )
        return False

    log.info("Relational sidecar connected", host=settings.postgres_host, store=settings.store)

    try:
        await run_relational_sidecar_migrations()
    except Exception:
        log.exception("Database migration failed")
        raise

    if settings.store != "legacy":
        log.info(
            "Relational content startup skipped in surreal store mode",
            store=settings.store,
            auth_store=settings.auth_store,
        )
        return True

    try:
        await recover_relational_sidecar_sources()
    except Exception as exc:
        log.warning("Source recovery failed", error=str(exc), store=settings.store)

    try:
        await load_relational_sidecar_api_keys()
    except Exception as exc:
        log.warning("API key preload failed", error=str(exc), store=settings.store)

    return True


__all__ = [
    "bootstrap_relational_sidecar_support",
    "check_relational_sidecar_connection",
    "load_relational_sidecar_api_keys",
    "recover_relational_sidecar_sources",
    "run_relational_sidecar_migrations",
]
