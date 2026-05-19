# Sibyl 1.0 RC Release Packet

- Status: candidate prepared; external release receipts pending
- Version: `1.0.0-rc.1`
- Branch: `feature/sibyl-1-0-rc-plan`
- Release floor: `v0.10.0`
- Rollback target: `v0.10.0`

This packet records the repo-side evidence for the v1.0 RC candidate. The candidate SHA is the final
committed SHA on this branch at release time. The release workflow records that SHA in the
`rc-gate-receipt-*` artifact before it can tag or dispatch publishing.

Do not tag or publish until Bliss gives explicit release go-ahead.

## Decision Gate

Ship now: no.

Smallest blocker: same-SHA GitHub CI and Nightly Regression must run on the final candidate SHA,
then the release workflow must be dispatched with that Nightly Regression run ID.

Residual release risk: Docker image startup, public PyPI pages, GitHub release body, container
manifests, and clean installs from published artifacts are post-publish checks.

## Claim Matrix

| Claim                                   | Receipt                                                                                                      | Status          |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------ | --------------- |
| Active docs agree                       | `moon run docs:lint` and `moon run docs:build`                                                               | Local pass      |
| Task graph is current                   | `sibyl epic show epic_19e1dea67ebf`; `sibyl task list --status doing`; no RC todo or blocked tasks           | Local pass      |
| Source ingest is current                | `moon run adapter-ingest-gate`; `moon run large-corpus-rehearsal`                                            | Local pass      |
| Synthesis is source-grounded            | `moon run synthesis-gate`                                                                                    | Local pass      |
| Automatic memory is policy-safe         | `moon run autonomy-gate`; `moon run memory-trust-gate`; `moon run trust-control-gate`                        | Local pass      |
| Sessions are boring                     | `moon run auth-session-gate`                                                                                 | Local pass      |
| Reflection quality is current           | `moon run reflection-quality-gate`                                                                           | Local pass      |
| Context and workspace trust are current | `moon run context-quality-gate`; `moon run workspace-trust-gate`                                             | Local pass      |
| Overview performance is current         | `moon run overview-perf-gate`                                                                                | Local pass      |
| Surreal-only runtime holds              | `moon run inventory-check`; `moon run inventory-typecheck`; `moon run inventory-test`; supported grep audit  | Local pass      |
| Redis is optional locally               | `moon run api:test -- tests/test_coordination_local.py -v`; `moon run api:memory-trust-jobs-test`            | Local pass      |
| Backup/restore is release-gated         | `moon run backup-restore-gate`                                                                               | Local pass      |
| Benchmark ledger is claim-safe          | `moon run bench-gate`; Nightly Regression compare artifacts                                                  | Nightly pending |
| Package artifacts build                 | `moon run python-package-build` produced `sibyl-core`, `sibyl-dev`, and `sibyld` wheels and sdists           | Local pass      |
| Package installs work                   | Clean isolated `uv tool install` for `sibyl-dev` and `sibyld`; both entrypoints report `1.0.0rc1`            | Local pass      |
| Helm surface works                      | `helm lint charts/sibyl`; `helm template sibyl charts/sibyl` has no `graphiti`, `falkor`, or `postgres` hits | Local pass      |
| Release cut is gated                    | `.github/workflows/release.yml` runs `moon run :check` before tag/publish and validates same-SHA nightly     | Workflow guard  |
| Publish dispatch is gated               | `.github/workflows/publish.yml` runs `moon run :check` before Python and Docker artifacts                    | Workflow guard  |
| Rollback is ready                       | Roll back to `v0.10.0`; do not move tags; verify published artifacts before announcing RC                    | Operator action |

## Receipt Highlights

- `moon run :check` -> 47 completed.
- `moon run release-workflow-test` -> 6 passed.
- `moon run python-package-build` -> built `sibyl_core-1.0.0rc1`, `sibyl_dev-1.0.0rc1`, and
  `sibyld-1.0.0rc1` artifacts.
- Clean isolated install -> `sibyl 1.0.0rc1`; `sibyld 1.0.0rc1`.
- `moon run docs:build` -> build complete, with existing Rollup chunk and PURE annotation warnings.
- `helm lint charts/sibyl` -> 1 chart linted, 0 failed.
- Helm render -> 350 lines; no `graphiti`, `falkor`, or `postgres` references.

## Release Dispatch Requirements

1. Push `feature/sibyl-1-0-rc-plan`.
2. Run GitHub CI on the final candidate SHA.
3. Run Nightly Regression on the final candidate SHA and keep its baseline parity, live graph, and
   benchmark artifacts.
4. Dispatch Release with `version=1.0.0-rc.1`, `dry_run=false`, and the Nightly Regression
   `nightly_run_id`.
5. Verify the GitHub release, PyPI package pages, Docker manifests, docs install page, and clean
   installs from published artifacts before announcing the RC.
