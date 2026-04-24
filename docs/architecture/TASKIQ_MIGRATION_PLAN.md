# Redis-Optional Coordination Plan

**Status:** Revised proposal **Owner:** Stef **Last updated:** 2026-04-21 **Supersedes:** the
earlier TaskIQ-first draft in this file

## 1. Recommendation

Do **not** make TaskIQ the first step.

The real goal is smaller and cleaner:

- `uv run sibyld serve` should work on a fresh single-machine install with only SurrealDB.
- Redis should stay available as an opt-in backend for distributed or multi-process deployments.
- Existing Redis deployments should keep today's semantics until we intentionally change them.

Those goals do **not** require swapping out `arq` right now. They require a backend boundary.

The revised plan is:

1. Introduce a `coordination/` abstraction for jobs, locks, pub/sub, and pending state.
2. Keep the current Redis + `arq` path as the `redis` backend with minimal changes.
3. Add a `local` backend for single-process installs using `asyncio` primitives.
4. Defer any TaskIQ migration until after the backend boundary exists and parity is proven.

## 2. Why The First Draft Needed Revision

The earlier draft mixed together two separate changes:

- removing Redis as a required local dependency
- replacing Sibyl's queue implementation with TaskIQ

That coupling makes the blast radius much larger than the goal requires.

After checking the current codebase and current TaskIQ docs on 2026-04-21, the main problems with a
TaskIQ-first rollout are:

1. **It weakens the "keep distributed semantics unchanged" promise.** `taskiq-redis` documents that
   `ListQueueBroker` has no acknowledgements, and recommends stream-based Redis when durability
   matters. That conflicts with the draft's promise that scaled Redis deployments preserve current
   durability semantics.

2. **Cancellation parity is not established.** Sibyl has a real `cancel_job` API today and uses
   `arq`'s queued-job abort behavior. The TaskIQ docs describe results, workers, schedulers,
   middlewares, and dynamic receivers, but they do not provide a documented drop-in equivalent to
   `job.abort()` for queued Redis jobs.

3. **The scheduler model was underspecified.** TaskIQ scheduling is a separate scheduler concept.
   The official docs explicitly call out `taskiq scheduler ...` and warn to run only one scheduler
   instance. If we ever adopt TaskIQ, worker and scheduler lifecycle must be designed deliberately
   instead of treated as a small worker rewrite.

4. **The current Sibyl runtime is already split by `store`.** `main.py` and `api/app.py` both gate
   Redis behavior behind `settings.store == "legacy"`, while `up_cmd.py` already defaults local dev
   to `SIBYL_STORE=surreal`. The original draft did not anchor the migration plan to that existing
   split.

5. **The scope was much larger than necessary.** Replacing the job library, worker CLI, scheduler
   model, and every Redis-backed coordination concern in one pass creates a lot of avoidable churn.

## 3. Current State

Redis currently backs four distinct concerns:

| Concern                    | Primary files                                                | Notes                                                                        |
| -------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| Job queue + job metadata   | `apps/api/src/sibyl/jobs/queue.py`, `worker.py`, `jobs/*.py` | `arq` with deterministic `_job_id`, recent-job ZSET, cancel/status/list APIs |
| Entity locks               | `apps/api/src/sibyl/locks.py`                                | Redis `SET NX EX` with Lua compare-and-delete / extend                       |
| Cross-pod websocket fanout | `apps/api/src/sibyl/api/pubsub.py`                           | Redis pub/sub channel                                                        |
| Pending entity registry    | `apps/api/src/sibyl/jobs/pending.py`                         | Pending markers plus queued ops lists                                        |

Additional context from the current code:

- `jobs/queue.py` exports **11** `enqueue_*` helpers and there are about **20** import sites across
  `apps/` and `packages/`.
- `apps/api/src/sibyl/main.py` and `apps/api/src/sibyl/api/app.py` have overlapping startup/shutdown
  logic.
- `settings.store` still defaults to `"legacy"`, but `apps/api/src/sibyl/cli/up_cmd.py` defaults
  local startup to `"surreal"`.
- Redis-dependent startup already degrades gracefully in several places, but the queue path is still
  a hard dependency for background work.

## 4. Revised Target Architecture

Introduce a backend boundary first.

```text
apps/api/src/sibyl/coordination/
├── __init__.py
├── broker.py
├── events.py
├── locks.py
├── pending.py
├── scheduler.py
├── _local/
│   ├── broker.py
│   ├── events.py
│   ├── locks.py
│   ├── pending.py
│   └── scheduler.py
└── _redis/
    ├── broker.py
    ├── events.py
    ├── locks.py
    ├── pending.py
    └── scheduler.py
```

### 4.1 Backends

**`redis` backend**

- Wraps the current implementations.
- Keeps `arq` for jobs in v1.
- Keeps today's lock behavior, pub/sub behavior, pending registry behavior, and job
  status/cancel/list behavior.
- Goal: near-zero behavioral change for existing Redis deployments.

**`local` backend**

- Single-process only.
- Uses `asyncio.Queue`, `asyncio.Task`, `asyncio.Lock`, and in-memory maps with TTL cleanup.
- No cross-process guarantees.
- No extra services required.

### 4.2 Config

Add an explicit coordination setting:

```python
coordination_backend: Literal["auto", "local", "redis"] = "auto"
```

Resolution rules for v1:

- `auto` + `store == "surreal"` -> `local`
- `auto` + `store == "legacy"` -> `redis`
- `local` is supported only for single-process runtime in v1
- `redis` remains the required mode for multi-process and distributed deployments

This keeps the supported matrix small while still solving the local-install problem.

### 4.3 Compatibility Surface

These public modules stay in place as stable shims:

- `sibyl.jobs.queue`
- `sibyl.jobs.pending`
- `sibyl.locks`
- `sibyl.api.pubsub`

Upstream callers keep using the same imports and function signatures while the backend is swapped
underneath.

## 5. Behavior Contract

### 5.1 Local backend

- `sibyld serve` starts the job broker and scheduler in-process.
- No separate worker process is required.
- Job state is ephemeral across process restarts.
- Queued job cancellation is supported.
- Running job cancellation is best-effort and cooperative only.
- Websocket broadcasts are local to the current process.
- Entity locks serialize only within the current process.

### 5.2 Redis backend

- Current `arq` worker process model stays intact in v1.
- Current job dedup, recent-job indexing, job status, and queued-job cancellation stay intact.
- Current Redis pub/sub and distributed locking stay intact.
- Existing deploys should not need behavior changes beyond an explicit backend setting.

## 6. Implementation Phases

Each phase should land green and be independently reviewable.

### Phase 0 - Lock down config, lifecycle, and success criteria

**Goal:** introduce backend selection without behavior change.

**Files**

- `apps/api/src/sibyl/config.py`
- `apps/api/src/sibyl/main.py`
- `apps/api/src/sibyl/api/app.py`
- `apps/api/src/sibyl/api/routes/jobs.py`
- `apps/api/src/sibyl/api/routes/admin.py`

**Changes**

- Add `coordination_backend` setting plus a resolved helper.
- Expose the resolved backend in health/debug output.
- Centralize startup selection so both app entrypoints use the same backend decision.
- Do **not** flip the global `store` default in this phase.

**Verify**

- Existing Redis dev flow still works unchanged.
- Health endpoints show the resolved backend.
- No behavior change in current tests.

### Phase 1 - Events, locks, and pending behind factories

**Goal:** move the non-queue concerns behind the new boundary first.

**New**

- `coordination/events.py`, `coordination/locks.py`, `coordination/pending.py`
- `coordination/_redis/events.py`, `locks.py`, `pending.py`
- `coordination/_local/events.py`, `locks.py`, `pending.py`

**Modified**

- `apps/api/src/sibyl/api/pubsub.py` -> shim
- `apps/api/src/sibyl/locks.py` -> shim
- `apps/api/src/sibyl/jobs/pending.py` -> shim plus backend-agnostic operation processor
- `apps/api/src/sibyl/main.py`
- `apps/api/src/sibyl/api/app.py`

**Notes**

- Move the existing Redis code with minimal edits into `_redis/`.
- Local event bus is direct callback fanout.
- Local lock backend is keyed `asyncio.Lock`.
- Local pending registry is an in-memory TTL map plus queued-op list.

**Verify**

- Existing Redis tests still pass.
- New local tests prove publish/subscribe, lock serialization, and pending TTL semantics.

### Phase 2 - Broker interface with Redis wrapper

**Goal:** preserve the existing Redis queue behavior behind a broker interface before adding local
jobs.

**New**

- `coordination/broker.py`
- `coordination/_redis/broker.py`

**Modified**

- `apps/api/src/sibyl/jobs/queue.py` -> compatibility shim over `get_broker()`
- `apps/api/src/sibyl/jobs/__init__.py`
- `apps/api/src/sibyl/api/routes/jobs.py`
- `apps/api/src/sibyl/api/routes/admin.py`
- `apps/api/src/sibyl/api/routes/crawler.py`
- `apps/api/src/sibyl/api/routes/backups.py`

**Broker API**

The interface should cover exactly what the app already needs:

- `enqueue_unique(...)`
- `enqueue(...)`
- `get_status(job_id)`
- `list_recent(...)`
- `cancel(job_id)`
- `health()`
- `startup()`
- `shutdown()`

**Important**

- Keep the Redis implementation backed by current `arq` code in v1.
- Preserve all 11 `enqueue_*` function signatures.
- Preserve job ID format and recent-job ordering.

**Verify**

- `test_jobs_queue.py` still passes after moving through the broker abstraction.
- Job list, status, and cancel routes behave exactly as they do today in Redis mode.

### Phase 3 - Local job broker

**Goal:** make local background work run without Redis.

**New**

- `coordination/_local/broker.py`

**Local broker requirements**

- FIFO queue using `asyncio.Queue`
- deterministic dedup map keyed by Sibyl's existing job IDs
- recent-job index in memory
- in-memory result store with TTL
- bounded worker concurrency
- explicit lifecycle hooks for startup and shutdown

**Semantics**

- If the same dedup key is queued twice while queued/running, return the same job ID.
- If a completed local job should be rerunnable today because Sibyl clears old `arq:result:*`,
  mirror that behavior explicitly in the local broker.
- Queued jobs can be cancelled before execution.
- Running jobs may only be cancelled cooperatively; do not pretend otherwise.

**Modified**

- `apps/api/src/sibyl/jobs/queue.py`
- `apps/api/src/sibyl/main.py`

**Verify**

- End-to-end local mode: enqueue crawl, entity creation, task update, backup, consolidation.
- Job status and recent jobs behave sensibly in local mode.
- Cancellation tests cover queued and already-running cases.

### Phase 4 - Local scheduler

**Goal:** restore scheduled maintenance work in local mode without Redis.

**New**

- `coordination/scheduler.py`
- `coordination/_local/scheduler.py`
- `coordination/_redis/scheduler.py`

**Design**

- Redis mode keeps the existing `arq` cron path in v1.
- Local mode runs a small in-process scheduler service.
- Reuse the existing schedule intent:
  - scheduled backups
  - backup cleanup
  - nightly consolidation

**Scope rule**

Do not introduce a new third-party scheduler unless the custom minute-tick loop proves insufficient.
Sibyl currently has only a small number of schedules, so the simplest thing is better here.

**Modified**

- `apps/api/src/sibyl/jobs/worker.py`
- `apps/api/src/sibyl/main.py`
- `apps/api/src/sibyl/cli/main.py`

**CLI behavior**

- In `redis` mode, `sibyld worker` keeps running the `arq` worker.
- In `local` mode, `sibyld worker` should print a clear message that background jobs run in-process
  under `sibyld serve` and exit successfully.

**Verify**

- Local mode scheduled jobs fire in tests.
- Redis mode worker CLI behavior is unchanged.

### Phase 5 - Dev ergonomics and docs

**Goal:** make the no-Redis path the happy path for local single-machine work.

**Modified**

- `tools/dev/run-surreal-dev.sh`
- `docker-compose.yml`
- `apps/api/README.md`
- `README.md`
- `apps/api/moon.yml`
- any chart values that surface runtime mode

**Changes**

- Local dev defaults to `store=surreal` and `coordination_backend=local`.
- Redis becomes opt-in in dev tooling.
- Redis service moves under an explicit profile if compose still needs it.
- Docs explain the supported runtime matrix and tradeoffs.

**Verify**

- Fresh local bootstrap works with SurrealDB only.
- Redis-backed dev flow still works when explicitly enabled.

### Phase 6 - Optional follow-up: evaluate TaskIQ after parity exists

This is a separate decision, not part of the initial implementation.

Only revisit TaskIQ after:

- local and redis backends already exist behind one broker interface
- parity tests are green
- we know exactly which semantics we are willing to change

If we revisit it later, the evaluation must answer:

1. Do we want `RedisStreamBroker` or `ListQueueBroker`, and what durability tradeoff are we
   accepting?
2. What is the real cancellation story for queued and running jobs?
3. How will worker and scheduler processes be managed in production?
4. Is the migration worth the churn now that Redis is already optional locally?

## 7. File Change Matrix

| File                                       | Phase | Action                                                             |
| ------------------------------------------ | ----- | ------------------------------------------------------------------ |
| `apps/api/src/sibyl/config.py`             | 0     | Add backend selection and resolution                               |
| `apps/api/src/sibyl/main.py`               | 0-4   | Centralize coordination lifecycle                                  |
| `apps/api/src/sibyl/api/app.py`            | 0-1   | Match backend lifecycle behavior                                   |
| `apps/api/src/sibyl/coordination/*`        | 1-4   | New abstraction layer                                              |
| `apps/api/src/sibyl/api/pubsub.py`         | 1     | Thin shim                                                          |
| `apps/api/src/sibyl/locks.py`              | 1     | Thin shim                                                          |
| `apps/api/src/sibyl/jobs/pending.py`       | 1     | Thin shim + operation processor                                    |
| `apps/api/src/sibyl/jobs/queue.py`         | 2-3   | Thin shim over broker                                              |
| `apps/api/src/sibyl/jobs/__init__.py`      | 2     | Re-export updated broker surface                                   |
| `apps/api/src/sibyl/jobs/worker.py`        | 4     | Keep `arq` worker path for Redis; factor schedule responsibilities |
| `apps/api/src/sibyl/cli/main.py`           | 4     | Worker command aware of backend                                    |
| `apps/api/src/sibyl/api/routes/jobs.py`    | 0-2   | Health/status/list/cancel through broker                           |
| `apps/api/src/sibyl/api/routes/admin.py`   | 0-2   | Queue health through broker                                        |
| `apps/api/src/sibyl/api/routes/crawler.py` | 2     | Cancel path through broker                                         |
| `apps/api/src/sibyl/api/routes/backups.py` | 2     | Status path through broker                                         |
| `tools/dev/run-surreal-dev.sh`             | 5     | Default local backend                                              |
| `docker-compose.yml`                       | 5     | Redis optional in dev                                              |
| `README.md`, `apps/api/README.md`          | 5     | Document runtime matrix                                            |

## 8. Testing Strategy

### 8.1 Supported matrix for v1

- `store=surreal`, `coordination_backend=local`
- `store=legacy`, `coordination_backend=redis`

Do **not** expand the matrix further until these two paths are green.

### 8.2 Parity tests

Shared broker tests should exercise:

- enqueue same dedup key twice
- rerun semantics for jobs that intentionally clear prior results
- recent-job ordering
- status transitions
- queued cancellation
- health payload shape

Shared coordination tests should exercise:

- event publish/subscribe
- lock serialization
- pending marker lifecycle
- pending queued-op processing

Local-only tests should exercise:

- in-process worker startup/shutdown
- local scheduler firing
- graceful process shutdown with queued work present

Redis-only tests should keep covering:

- existing `arq` queue behavior
- distributed lock behavior
- redis pub/sub behavior

## 9. Rollout Strategy

1. Land the abstraction and local mode without changing Redis behavior.
2. Prove local Surreal-only bootstrap works.
3. Keep Redis deploys on the existing `arq` path until parity is proven.
4. Only after that, decide whether a queue-library migration is still worth doing.

This keeps the migration additive first, then opt-in, instead of replacing the most stateful
subsystem up front.

## 10. Risks And Mitigations

| Risk                                                                | Severity | Mitigation                                                                          |
| ------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------- |
| Default runtime confusion (`store` vs `up_cmd.py`)                  | High     | Resolve backend explicitly in config and document the supported matrix              |
| Local mode behaves like distributed mode in user expectations       | Medium   | Loud startup log line: single-process, no cross-process guarantees, ephemeral state |
| Running-job cancellation is weaker in local mode                    | Medium   | Expose it as best-effort, keep queued cancellation solid, document the difference   |
| Duplicate lifecycle logic between `main.py` and `api/app.py` drifts | Medium   | Move backend resolution into shared coordination factory helpers                    |
| Migration stalls after abstractions land                            | Low      | Keep phases independently shippable and useful                                      |
| Later TaskIQ migration pressure returns                             | Low      | Treat it as a separate RFC with explicit go/no-go criteria                          |

## 11. Success Criteria

- `uv run sibyld serve` works on a fresh single-machine install with SurrealDB only.
- Local mode supports background jobs without Redis.
- Existing Redis deployments keep current queue behavior in v1.
- Health/debug output reports the resolved coordination backend.
- Dev tooling makes Redis optional instead of assumed.

## 12. Out Of Scope

- Replacing `arq` in the initial implementation
- Multi-process local coordination
- Durable local queue state across restarts
- New distributed broker backends beyond the current Redis path
- Flipping every runtime default in the same change

## 13. Sources Checked

Checked on 2026-04-21:

- TaskIQ CLI docs: worker and scheduler are distinct runtime concepts
- TaskIQ scheduling docs: run only one scheduler instance
- TaskIQ docs for state/dependencies, dynamic brokers, and middlewares
- `taskiq-redis` README: `ListQueueBroker` does not support acknowledgements

These findings are why this plan defers TaskIQ until after the backend split exists.
