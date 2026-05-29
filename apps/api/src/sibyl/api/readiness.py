"""Readiness probe helpers.

Liveness (`/health`) only asserts the process is up. Readiness asks the
harder question: can this process actually serve traffic? For Sibyl that
means the SurrealDB runtime is reachable. The check connects a dedicated
auth client against the static `sibyl_auth` namespace and returns the
pooled connection without issuing a query, so it never touches a per-org
namespace or the tenant query path — a fast handshake ping, not a sweep.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import structlog

log = structlog.get_logger()


@dataclass(slots=True, frozen=True)
class DependencyStatus:
    """Result of probing a single serving dependency."""

    name: str
    ready: bool
    detail: str | None = None
    latency_ms: float | None = None


@dataclass(slots=True, frozen=True)
class ReadinessReport:
    """Aggregate readiness across every serving dependency."""

    ready: bool
    dependencies: list[DependencyStatus]

    def as_payload(self) -> dict[str, object]:
        return {
            "status": "ready" if self.ready else "not_ready",
            "dependencies": [
                {
                    "name": dep.name,
                    "ready": dep.ready,
                    **({"detail": dep.detail} if dep.detail is not None else {}),
                    **({"latency_ms": dep.latency_ms} if dep.latency_ms is not None else {}),
                }
                for dep in self.dependencies
            ],
        }


async def check_surreal_ready() -> DependencyStatus:
    """Probe SurrealDB reachability with a connect-only handshake.

    Builds the auth client (static namespace, never per-org) and checks out
    a pooled connection. `connect()` performs the websocket handshake,
    signin, and namespace selection without running a query, so it proves
    the runtime can serve traffic without holding the tenant query path.
    """
    from sibyl.persistence.surreal.auth import build_surreal_auth_client

    started = time.perf_counter()
    client = build_surreal_auth_client()
    try:
        await client.connect()
    except Exception as exc:
        log.warning("readiness_surreal_unreachable", error=str(exc))
        return DependencyStatus(
            name="surrealdb",
            ready=False,
            detail="SurrealDB runtime unreachable",
        )
    finally:
        try:
            await client.close()
        except Exception as exc:
            log.debug("readiness_surreal_close_error", error=str(exc))

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    return DependencyStatus(name="surrealdb", ready=True, latency_ms=latency_ms)


async def check_readiness() -> ReadinessReport:
    """Aggregate readiness across the dependencies needed to serve traffic."""
    dependencies = [await check_surreal_ready()]
    return ReadinessReport(
        ready=all(dep.ready for dep in dependencies),
        dependencies=dependencies,
    )


__all__ = [
    "DependencyStatus",
    "ReadinessReport",
    "check_readiness",
    "check_surreal_ready",
]
