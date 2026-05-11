---
title: Storage Modes
description: The supported storage configurations and when to pick each
---

# Storage Modes

Sibyl's active runtime is SurrealDB. `SIBYL_STORE=legacy` remains accepted only as a migration-era
input and is normalized by local startup paths.

| Mode                          | `SIBYL_STORE` | Auth store | Coordination | External services              |
| ----------------------------- | ------------- | ---------- | ------------ | ------------------------------ |
| **Fully Surreal** _(default)_ | `surreal`     | SurrealDB  | `local`      | SurrealDB                      |
| **Archive rehearsal**         | `surreal`     | SurrealDB  | `local`      | SurrealDB + PostgreSQL sidecar |

Active auth, content, crawler, raw-capture, graph, and RAG runtime paths resolve through SurrealDB.
PostgreSQL remains only for archive import/restore policy until Phase 3 removes that support. Fully
Surreal is the only recommended target for new deployments. `SIBYL_AUTH_STORE=postgres` was removed
after the v0.6.0 compatibility release.

Existing installs should read the
[SurrealDB migration release notes](./surrealdb-migration-release-notes.md) before upgrading.

Set `SIBYL_COORDINATION_BACKEND=auto` (the default) and sibyld picks the right coordination backend
for each mode. Override it only when you need Redis-backed coordination for multi-process Surreal
dev.

## Fully Surreal (default)

**Pick this for:** new installs, self-hosted local dev, simpler ops.

Graph, content, and auth all live in one SurrealDB instance, with per-org isolation via namespaces
(`org_<uuid_hex>`). No PostgreSQL, no Redis, no FalkorDB.

```bash
SIBYL_STORE=surreal
# SIBYL_SURREAL_URL=ws://surrealdb:8000/rpc  (or)
# SIBYL_SURREAL_DATA_DIR=./.moon/cache/surreal-dev
```

- **Dev:** `moon run dev` starts local SurrealDB backed by RocksDB automatically.
- **Prod:** run SurrealDB as a service (`ws://` or `http://` URL). In-memory mode (`memory://`) is
  rejected by the production config validator.
- **Server version:** use SurrealDB 3.x, and pin the exact server image/tag in production.

## Archive Rehearsal

**Pick this for:** validating retained migration archives or database dump restore behavior.

```bash
SIBYL_STORE=surreal
SIBYL_COORDINATION_BACKEND=local
```

- SurrealDB backs graph, auth/RBAC, content, and RAG runtime paths
- PostgreSQL dump payloads remain available only for migration and rollback evidence
- Redis/Valkey is optional for distributed coordination

## Switching modes

- **New install:** leave defaults alone. Fully Surreal is the default.
- **Legacy → Surreal:** see [migrating-from-falkor.md](./migrating-from-falkor.md). The migration is
  CLI-driven (`sibyld migrate export|import|verify`) and supports rehearsal runs.
- **Local legacy dev install:** `moon run dev` detects existing legacy data before starting a fresh
  Surreal runtime. Import a previously exported archive with
  `uv run --directory apps/api sibyld migrate import <archive> --yes --clean`.
- **PostgreSQL auth removal:** if an old `.env` still sets `SIBYL_AUTH_STORE=postgres`, remove it.
  The server rejects that value, and `moon run dev` normalizes local startup back to Surreal auth.
