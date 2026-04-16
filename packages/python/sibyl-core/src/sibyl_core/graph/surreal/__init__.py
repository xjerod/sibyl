"""SurrealDB-backed GraphDriver for Graphiti.

Phase 1 of the FalkorDB to SurrealDB migration. See
`docs/research/rust-port/SPEC-v2.md` and `PHASE1-PLAN.md`.

The driver lives in-package so Sibyl can wire it into `GraphClient` via a
config flag (`SIBYL_GRAPH_BACKEND`) without modifying route code.
"""

from sibyl_core.graph.surreal.driver import SurrealDriver, SurrealDriverSession

__all__ = ["SurrealDriver", "SurrealDriverSession"]
