---
title: SurrealDB Migration Release Notes
description: Release guidance for the SurrealDB-first storage cutover
---

# SurrealDB Migration Release Notes

Sibyl now starts the SurrealDB runtime by default. New installs should use SurrealDB for graph,
content, and auth. Do not start new deployments on FalkorDB or PostgreSQL auth.

Legacy FalkorDB runtime support was retired after the v0.6.0 compatibility release. PostgreSQL auth
was removed after the same release, and active content/RAG runtime paths now resolve through
SurrealDB. Structured auth/content archive export now reads SurrealDB; retained `postgres.sql`
payloads are restore-only evidence for rehearsal or rollback validation.

## What changed

- `moon run dev` starts the SurrealDB runtime.
- `SIBYL_STORE=surreal` and `SIBYL_AUTH_STORE=surreal` are the default settings.
- The local `moon run dev-legacy` fallback has been retired after the v0.6.0 compatibility release.
- `moon run dev` detects local legacy data before creating a fresh Surreal dev runtime.
- The live local FalkorDB migration wrapper has been retired; use archive import instead.

## Existing local installs

If you have an old local FalkorDB + PostgreSQL install, export an archive before upgrading, then
import it into SurrealDB:

```bash
uv run --directory apps/api sibyld migrate import <archive> --yes --clean
```

Use `--restore-database-dump` only for rehearsal or rollback validation.

## Existing production installs

Use the full migration playbook, not the local shortcut:

1. Back up the legacy install.
2. Export the legacy archive.
3. Rehearse the archive against a disposable SurrealDB target.
4. Import into SurrealDB.
5. Start a Surreal-backed API on a private cutover endpoint.
6. Run archive verification.
7. Run the auth-flow replay against the Surreal-backed API.
8. Run the auth-flow replay against the target API.
9. Run the Surreal cutover gate while writes are frozen.
10. Freeze legacy auth/RBAC writes during the rollback window.

Start with [Migrating from FalkorDB](./migrating-from-falkor.md).

Use SurrealDB 3.x for the target runtime, and pin the exact server image/tag used during rehearsal
before cutting over production.

Release owners should execute the live gate checklist in
`docs/architecture/SURREALDB_PHASE2_LIVE_GATES.md` before tagging the SurrealDB-first release.

`sibyld migrate auth-flow-compare` refuses to compare one API to itself by default. Start one
legacy-auth API and one Surreal-auth API, then pass distinct `--postgres-base-url` and
`--surreal-base-url` values. Use `--allow-same-base-url` only when debugging the harness itself.

## Compatibility window

These paths stay available while Phase 3 removes the remaining legacy storage:

- `SIBYL_STORE=legacy`
- PostgreSQL content archive export
- FalkorDB graph archive export

The old PostgreSQL auth/RBAC runtime and active PostgreSQL content sidecars have been removed.
Remaining PostgreSQL consumers are archive readers/exporters and ambient legacy startup/sync code
that will be retired in the Phase 3 storage cleanup.

## Rollback posture

The migration is explicit and archive-backed. Upgrading does not destructively rewrite your legacy
data. If a cutover fails before Surreal accepts new writes, point traffic back to the legacy API.

Once Surreal accepts new production writes, treating PostgreSQL as an instant read-write rollback is
unsafe. Restore from the pre-cutover archive and replay any Surreal-only writes deliberately.
