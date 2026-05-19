# Sibyl Live LongMemEval Harness Spec

- Status: active implementation spec (revision 3, honest existing-API path)
- Created: 2026-05-19
- Owner: v1.0 RC quality evals
- Parent epic: `epic_c22c73b78887` (v1.0 RC: Quality evals and receipts)
- Tracking task: `09ba2791-b8e3-41c6-9d7a-1737b4097dc1`
- Related: [`docs/testing/benchmark-methodology.md`](../testing/benchmark-methodology.md),
  `benchmarks/longmemeval_bench.py`, `benchmarks/live_runtime_eval.py`, `tools/bench/eval_gate.py`

## 1. Problem

Sibyl has three retrieval evaluation surfaces, and none measures the live runtime at scale.

- `benchmarks/longmemeval_bench.py` runs LongMemEval-S (500 questions) but is an offline
  reimplementation: it imports `chromadb` and nothing from `sibyl_core`, scores against an ephemeral
  ChromaDB index with a local 384-dimension MiniLM embedder, and carries the honest `claim_boundary`
  "not live API runtime evidence."
- The context-pack live eval (`core:bench-context`) exercises the real runtime but over only 8
  hand-built fixture cases.
- The nightly regression runs the context-pack eval deterministically with mock keys.

The gap: a benchmark both at scale and against the real runtime.

## 2. Goal

A harness and CI job that run LongMemEval-S against a real, ephemeral Sibyl stack and produce
honestly-labelled retrieval metrics for the existing live API. CI spins the stack up fresh; no
developer's personal instance is involved.

This revision keeps the first Codex review's hard rule: **the spec must not assert runtime behavior
it has not verified.** The preflight proved that `/api/search` round-trips LongMemEval session
metadata, but the session path is graph full-text/hybrid rather than native vector search. The live
harness therefore measures that existing API behavior and explicitly does not claim native embedding
retrieval.

## 3. What LongMemEval Requires

LongMemEval-S is 500 questions. Each ships a haystack of prior chat sessions; a few hold the answer
evidence, the rest are distractors. The task is to retrieve the correct session(s). Each question's
haystack is isolated — question N must never retrieve question M's sessions.

Verified against the committed artifact `longmemeval_sibyl_raw_20260513.json`: answer sets are
usually multi-session — 176 questions have 1 answer session, 250 have 2, 41 have 3, and the rest
more. This fact drives the metric definitions in Section 8.

## 4. Design Overview

For each question: mint an isolated tenant, ingest its haystack through the verified
`POST /api/entities?sync=true` write path, wait for a search-readiness probe, query the verified
`/api/search` graph surface, map results back to LongMemEval session IDs, score. Aggregate into a
gate-valid `ai-memory` artifact whose claim boundary is live API graph full-text/hybrid evidence,
not native vector evidence.

## 5. Phase 0 — Preflight Contract Verification

The recorded probe under `benchmarks/preflight/` resolved the contracts enough to build an honest
existing-API harness. The earlier native-vector claim remains unsupported and is deliberately out of
scope for this harness.

1. **Ingestion + retrieval contract.** `POST /api/entities?sync=true` with `entity_type: session`,
   `skip_conflicts: true`, then `/api/search` with `types: ["session"]`, `include_documents: false`,
   returns graph results with `longmemeval_session_id` metadata intact.
2. **Retrieval-path semantics.** `/api/search` ranks these `session` records through the existing
   graph search path: full-text seed search, graph hybrid traversal, exact-name fallback, and
   temporal boosting when enabled. The preflight did not prove native vector ranking for session
   records, so the artifact records `retrieval_mode: hybrid`, `retrieval_surface: POST /api/search`,
   and `embedding_provider: none`.
3. **Readiness signal.** Sync writes are followed by a bounded `/api/search` probe against the
   throwaway org. The probe proves the namespace is visible to the query surface before scoring
   begins. It does not assert embedding dimensions.
4. **Artifact contract.** Read `tools/bench/eval_gate.py` and enumerate every field the `ai-memory`
   profile requires. Confirmed so far: a non-empty `schema_version` and `suite`; `generated_at` or
   `timestamp`; a non-empty `command`; a `runtime` block carrying `retrieval_mode`; a `dataset`
   block with `name` and `corpus_hash`; a per-question summary under one of
   `per_type`/`per_slice`/`per_category`/`per_task`; and `mode` must equal `runtime.retrieval_mode`
   and be one of `raw`, `hybrid`, `native`, `compare`. `mode: live` is invalid and will fail the
   gate.

Phase 0 also found that `longmemeval_s_cleaned.json` has no empty `answer_session_ids`, so this
harness does not implement abstention scoring.

## 6. Isolation Model

One throwaway tenant per question. Sibyl is namespace-per-org (`org_<uuid_hex>`), so an isolated org
is an isolated SurrealDB namespace — the native isolation primitive, matching LongMemEval's
per-question haystack exactly. Local signup creates a personal org per user, so the harness signs up
a throwaway user per question and ingests into that org.

Rejected: a single org with per-question scope filters — that makes benchmark integrity depend on
filter correctness and risks cross-question leakage.

Concurrency: a bounded pool (`--concurrency`, default low), each worker owning its own tenant and
HTTP session. Teardown is handled by the ephemeral CI stack. Localhost runs are refused unless the
caller passes `--allow-localhost`, making accidental mutation of a developer's personal graph noisy
and explicit.

## 7. Corpus Construction

Offline and live harnesses use the same canonical text per session, or the offline-versus-live delta
measures corpus shape rather than runtime. Phase 1 extracts one shared loader that emits
`(session_id, text, timestamp)` tuples. The current offline `_build_corpus` joins user-role turns
only, one document per session; the shared loader preserves exactly that policy. The live API
receives that canonical text as entity `content`; any additional fields the API indexes are recorded
as part of the live runtime contract. The policy string (e.g. `user-turns-only-v1`) is recorded in
every artifact as `corpus_text_policy` so any future change is visible in the receipts.

## 8. Metrics

The first Codex review established that the offline `recall_at_k` is `float(any(correct in top_k))`
— binary hit@k, not recall — and that most questions have multiple answer sessions. The headline
"recall@5 0.98" on existing artifacts is therefore hit@5 and overstates quality. The shared scorer
defines three explicitly named metrics:

- `hit@k` — 1.0 if any answer session appears in the top k. This is the legacy offline metric,
  retained under its honest name for backward comparability.
- `recall@k` — true recall: `|answer_sessions ∩ top_k| / |answer_sessions|`.
- `ndcg@k` — standard nDCG where the ideal ranking is computed over all answer sessions for the
  question, not only the retrieved ones.

Headline reporting uses `recall@k` and `ndcg@k`. `hit@k` is reported alongside, labelled legacy. The
offline bench is repointed at the shared scorer; to preserve its historical numbers it keeps
emitting `hit@k` under a `legacy_` prefix in addition to the new metrics. Both harnesses score
through this one module. That is the comparability guarantee.

## 9. Report Artifact

The artifact conforms to the `ai-memory` ledger schema and passes `bench-gate --profile ai-memory`
(the field list is finalised in Phase 0). Concretely:

- `schema_version` and `suite`: both non-empty, per the `ai-memory` ledger schema — the `bench-gate`
  validator rejects an artifact missing either.
- `mode`: `hybrid` (a gate-allowed value), equal to `runtime.retrieval_mode`.
- `runtime.runtime_mode`: `live-api-ephemeral` — this is where liveness is expressed.
- `runtime`: also `graph_engine: surreal`, `store: surreal`, `retrieval_surface: POST /api/search`,
  `retrieval_semantics: existing API graph hybrid/fulltext; no native vector claim`,
  `embedding_provider: none`, `embedding_model: not-applicable`, `embedding_dimensions: 0`,
  `tokenizer_estimate_method: not-applicable`.
- `generated_at`, `command`, `sibyl_commit`, `repeat_count`, `auth_manifest_id`.
- `dataset`: `name`, `corpus_hash`, `total_entries`, `evaluated_entries`, `limit`, plus
  `corpus_text_policy`.
- `overall`: `recall@5`, `recall@10`, `ndcg@5`, `ndcg@10`, `hit@5`, `hit@10`.
- `per_type`: metrics broken down by LongMemEval question type.
- `case_results`: per-question records including ranked result IDs, scores, `result_origin`, tenant
  id, readiness attempts, ingest timing, and cross-question leakage counts.
- `claim_boundary`: "Live API runtime evidence for `/api/search` against an ephemeral Sibyl stack
  with per-question throwaway org namespaces. This artifact measures the existing graph
  hybrid/full-text path and does not claim native vector embedding retrieval."

The `ai-memory` gate currently sets no numeric thresholds. This spec does not invent them. Phase 4
sets them from the first full-run baseline, with margin.

## 10. Temporal Questions — Known Limitation

The first review found that preserving session timestamps into `valid_at` does **not** make
retrieval temporally aware: `SearchRequest` exposes no `as_of` / reference-time parameter, and
temporal boosting is computed relative to now. So the harness ingests real timestamps but does not
claim temporal-aware retrieval for temporal-reasoning questions. Those questions are still scored,
and the `per_type` breakdown will expose how the runtime does without temporal grounding — itself
useful evidence. An eval-time `as_of` path is explicitly out of scope here and noted as future work.

## 11. Abstention

Phase 0 found no entries with empty `answer_session_ids` in `longmemeval_s_cleaned.json`, so this
harness drops the abstention claim entirely.

## 12. CLI: `benchmarks/longmemeval_live.py`

Arguments: positional `dataset`; `--api-url` (default `http://localhost:3334/api`); `--limit N`;
`--concurrency N`; `--output PATH`; `--label`; `--metadata key=value`; `--allow-localhost`;
`--readiness-timeout`; `--timeout`; `--skip-sha256-check`. It fails fast if the stack is
unreachable, if the dataset hash is unexpected, or if the target is localhost without the explicit
disposable-stack override. It reuses the shared corpus loader and scorer.

## 13. CI Jobs

Two jobs, not one, added to `.github/workflows/eval.yml`:

- `longmemeval-live-smoke` — small `--limit` (e.g. 25), low concurrency, runs on every
  `workflow_dispatch`; bounded and reliable.
- `longmemeval-live-full` — the 500-question run, separate `workflow_dispatch` path with a raised
  `timeout-minutes`, gated and artifact-uploaded.

Both reuse the live eval environment recipe: SurrealDB, moon toolchain, backend, and worker. The
dataset is fetched from Hugging Face (`xiaowu0162/longmemeval-cleaned`,
`longmemeval_s_cleaned.json`), SHA-256 verified against
`d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442`, and cached by hash. This harness
does not make client-side embedding calls; the budget is wall-clock and database churn in the
ephemeral stack, controlled by `--limit` and `--concurrency`.

## 14. Phasing

- **Phase 0 — Preflight.** Section 5. Recorded probes for the ingestion, retrieval-path, readiness,
  and artifact contracts, plus the abstention question. Native vector retrieval was not proven;
  existing `/api/search` graph retrieval was.
- **Phase 1 — Shared scoring and corpus.** Extract the shared `(session_id, text, timestamp)` loader
  and the three-metric scorer (`hit@k`, `recall@k`, `ndcg@k`). Repoint `longmemeval_bench.py` at
  both. Verify: offline `hit@k` is unchanged versus a pre-extraction run on the same dataset.
- **Phase 2 — Live harness.** Build `longmemeval_live.py` against the resolved existing-API
  contracts. Verify with mocked HTTP tests locally, then with CI against an ephemeral stack.
  Localhost mutation requires `--allow-localhost`.
- **Phase 3 — CI jobs.** Add the smoke and full jobs. Verify: a smoke `workflow_dispatch` run is
  green and uploads a gate-valid artifact.
- **Phase 4 — Ledger integration.** Run the full 500-question evaluation, commit the artifact as a
  citable row in `benchmarks/results/ai-memory/manifest.json`, set `ai-memory` thresholds from the
  observed baseline with margin, and document the suite in `benchmark-methodology.md`.

## 15. Definition of Done

- Phase 0 probes are committed and the four contracts are proven, not assumed.
- A shared corpus loader and three-metric scorer back both harnesses; offline `hit@k` is unchanged.
- `longmemeval_live.py` emits a gate-valid `ai-memory` artifact in ephemeral CI with verified
  per-question isolation.
- The smoke and full CI jobs run on `workflow_dispatch`, are green, and gate.
- A full 500-question artifact is a citable manifest row whose `claim_boundary` is live runtime
  evidence and whose metrics are named honestly.
- `benchmark-methodology.md` documents the suite.

## 16. Recommendation

Build the existing-API harness now. The offline bench stays as an algorithm baseline; the live
harness shows how the shipped `/api/search` graph path behaves in a real ephemeral runtime. A future
native-vector LongMemEval harness can be specced separately if the app grows a verified vector
search surface for session entities. The core warning still stands: a benchmark that passes its gate
with numbers that do not mean what their labels claim is worse than no benchmark.
