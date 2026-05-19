#!/usr/bin/env python3
# ruff: noqa: E402, PLR2004, S607, T201
"""Run LongMemEval-S against the existing live `/api/search` surface."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "python" / "sibyl-core" / "src"))

from sibyl_core.evals.longmemeval import (
    CORPUS_TEXT_POLICY,
    average_metric,
    build_longmemeval_corpus,
    score_longmemeval_ranking,
)

DATASET_SHA256 = "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442"
DEFAULT_K_VALUES = [5, 10]
LIVE_RETRIEVAL_MODE = "hybrid"
AUTH_MANIFEST_ID = "ephemeral-local-signup-v1"


class LongMemEvalLiveError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _corpus_hash(path: Path) -> str:
    return f"sha256:{_sha256_file(path)}"


def _load_dataset(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_loopback_url(api_url: str) -> bool:
    host = urlparse(api_url).hostname
    if host is None:
        return False
    return host in {"localhost", "::1"} or host.startswith("127.")


def validate_target(api_url: str, *, allow_localhost: bool) -> None:
    if _is_loopback_url(api_url) and not allow_localhost:
        msg = (
            "Refusing to run LongMemEval live against localhost without "
            "--allow-localhost. This harness mutates its target by signing up "
            "throwaway users and ingesting sessions; only point it at a "
            "disposable stack."
        )
        raise LongMemEvalLiveError(msg)


def _parse_metadata(values: list[str]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            msg = f"Invalid metadata entry: {item!r}. Expected key=value."
            raise argparse.ArgumentTypeError(msg)
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            msg = f"Invalid metadata entry: {item!r}. Key cannot be empty."
            raise argparse.ArgumentTypeError(msg)
        metadata[key] = value
    return metadata


async def _post_json(
    client: httpx.AsyncClient,
    path: str,
    *,
    payload: dict[str, Any],
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await client.post(path, json=payload, params=params)
    if response.status_code >= 400:
        raise LongMemEvalLiveError(
            f"{path} failed with HTTP {response.status_code}: {response.text[:500]}"
        )
    data = response.json()
    if not isinstance(data, dict):
        raise LongMemEvalLiveError(f"{path} returned non-object JSON")
    return data


async def _get_json(client: httpx.AsyncClient, path: str) -> dict[str, Any]:
    response = await client.get(path)
    if response.status_code >= 400:
        raise LongMemEvalLiveError(
            f"{path} failed with HTTP {response.status_code}: {response.text[:500]}"
        )
    data = response.json()
    if not isinstance(data, dict):
        raise LongMemEvalLiveError(f"{path} returned non-object JSON")
    return data


async def _signup_throwaway_tenant(
    client: httpx.AsyncClient,
    *,
    run_id: str,
    case_index: int,
) -> dict[str, Any]:
    suffix = uuid4().hex[:12]
    signup = await _post_json(
        client,
        "/auth/local/signup",
        payload={
            "email": f"longmemeval-{run_id}-{case_index}-{suffix}@example.invalid",
            "password": f"SibylLongMemEval-{suffix}-password",
            "name": "LongMemEval Runner",
        },
    )
    token = str(signup.get("access_token") or "")
    if not token:
        raise LongMemEvalLiveError("signup did not return an access_token")
    client.headers.update({"Authorization": f"Bearer {token}"})
    org = signup.get("organization") if isinstance(signup.get("organization"), dict) else {}
    return {
        "organization_id": org.get("id"),
        "organization_slug": org.get("slug"),
    }


def _entity_name(*, run_id: str, case_index: int, document_index: int) -> str:
    return f"LongMemEval {run_id} case {case_index} session {document_index}"[:200]


async def _ingest_haystack(
    client: httpx.AsyncClient,
    *,
    entry: dict[str, Any],
    run_id: str,
    case_index: int,
) -> tuple[list[str], float]:
    start = time.perf_counter()
    question_id = str(entry["question_id"])
    created_ids: list[str] = []
    documents = build_longmemeval_corpus(entry)
    for document_index, document in enumerate(documents):
        created = await _post_json(
            client,
            "/entities",
            params={"sync": "true"},
            payload={
                "name": _entity_name(
                    run_id=run_id,
                    case_index=case_index,
                    document_index=document_index,
                ),
                "description": "",
                "content": document.text,
                "entity_type": "session",
                "skip_conflicts": True,
                "metadata": {
                    "longmemeval_run_id": run_id,
                    "longmemeval_case_index": case_index,
                    "longmemeval_question_id": question_id,
                    "longmemeval_session_id": document.session_id,
                    "longmemeval_haystack_index": document_index,
                    "valid_at": document.timestamp,
                    "corpus_text_policy": CORPUS_TEXT_POLICY,
                    "capture_surface": "longmemeval-live",
                },
            },
        )
        created_ids.append(str(created.get("id") or ""))
    return created_ids, (time.perf_counter() - start) * 1000


async def _verify_namespace_probe(
    client: httpx.AsyncClient,
    *,
    run_id: str,
    question_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    attempts = 0
    while True:
        attempts += 1
        search = await _post_json(
            client,
            "/search",
            payload={
                "query": "LongMemEval",
                "types": ["session"],
                "include_documents": False,
                "include_graph": True,
                "include_content": False,
                "use_enhanced": True,
                "boost_recent": False,
                "limit": 5,
            },
        )
        results = search.get("results") if isinstance(search.get("results"), list) else []
        matched = [
            result
            for result in results
            if isinstance(result, dict)
            and isinstance(result.get("metadata"), dict)
            and result["metadata"].get("longmemeval_run_id") == run_id
            and result["metadata"].get("longmemeval_question_id") == question_id
        ]
        if matched:
            return {"attempts": attempts, "result_count": len(results)}
        if time.monotonic() >= deadline:
            raise LongMemEvalLiveError(
                f"timed out waiting for searchable sessions for question {question_id}"
            )
        await asyncio.sleep(0.5)


async def _search_question(
    client: httpx.AsyncClient,
    *,
    query: str,
    limit: int,
) -> dict[str, Any]:
    return await _post_json(
        client,
        "/search",
        payload={
            "query": query,
            "types": ["session"],
            "include_documents": False,
            "include_graph": True,
            "include_content": False,
            "use_enhanced": True,
            "boost_recent": False,
            "limit": limit,
        },
    )


def _ranked_sessions(results: list[Any]) -> tuple[list[str], list[dict[str, Any]], int]:
    ranked_session_ids: list[str] = []
    ranked_results: list[dict[str, Any]] = []
    cross_question_count = 0
    seen: set[str] = set()
    current_question_id: str | None = None
    for result in results:
        if not isinstance(result, dict):
            continue
        metadata = result.get("metadata") if isinstance(result.get("metadata"), dict) else {}
        session_id = metadata.get("longmemeval_session_id")
        question_id = metadata.get("longmemeval_question_id")
        if current_question_id is None and isinstance(question_id, str):
            current_question_id = question_id
        if (
            isinstance(question_id, str)
            and current_question_id is not None
            and question_id != current_question_id
        ):
            cross_question_count += 1
        if isinstance(session_id, str) and session_id not in seen:
            ranked_session_ids.append(session_id)
            seen.add(session_id)
        ranked_results.append(
            {
                "id": result.get("id"),
                "longmemeval_session_id": session_id,
                "score": result.get("score"),
                "result_origin": result.get("result_origin"),
                "type": result.get("type"),
            }
        )
    return ranked_session_ids, ranked_results, cross_question_count


async def _run_case(
    entry: dict[str, Any],
    *,
    api_url: str,
    run_id: str,
    case_index: int,
    k_values: list[int],
    readiness_timeout_seconds: float,
    timeout_seconds: float,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    async with httpx.AsyncClient(
        base_url=api_url,
        timeout=timeout_seconds,
        headers={"Content-Type": "application/json"},
        transport=transport,
    ) as client:
        await _get_json(client, "/health")
        tenant = await _signup_throwaway_tenant(client, run_id=run_id, case_index=case_index)
        created_ids, ingest_ms = await _ingest_haystack(
            client,
            entry=entry,
            run_id=run_id,
            case_index=case_index,
        )
        readiness = await _verify_namespace_probe(
            client,
            run_id=run_id,
            question_id=str(entry["question_id"]),
            timeout_seconds=readiness_timeout_seconds,
        )
        search = await _search_question(
            client,
            query=str(entry["question"]),
            limit=max(k_values),
        )

    results = search.get("results") if isinstance(search.get("results"), list) else []
    ranked_session_ids, ranked_results, cross_question_count = _ranked_sessions(results)
    answer_session_ids = sorted(str(value) for value in entry.get("answer_session_ids", []))
    metrics = score_longmemeval_ranking(ranked_session_ids, answer_session_ids, k_values)
    return {
        "case_index": case_index,
        "question_id": entry["question_id"],
        "question_type": entry["question_type"],
        "question": entry.get("question"),
        "question_date": entry.get("question_date"),
        "answer_session_ids": answer_session_ids,
        "ranked_session_ids": ranked_session_ids,
        "ranked_results": ranked_results,
        "tenant": tenant,
        "created_entity_count": len(created_ids),
        "readiness": readiness,
        "ingest_ms": ingest_ms,
        "latency_ms": (time.perf_counter() - started) * 1000,
        "cross_question_result_count": cross_question_count,
        **metrics,
    }


async def _run_cases(
    entries: list[dict[str, Any]],
    *,
    api_url: str,
    run_id: str,
    concurrency: int,
    k_values: list[int],
    readiness_timeout_seconds: float,
    timeout_seconds: float,
    transport: httpx.AsyncBaseTransport | None,
) -> list[dict[str, Any]]:
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def run_one(case_index: int, entry: dict[str, Any]) -> dict[str, Any]:
        async with semaphore:
            return await _run_case(
                entry,
                api_url=api_url,
                run_id=run_id,
                case_index=case_index,
                k_values=k_values,
                readiness_timeout_seconds=readiness_timeout_seconds,
                timeout_seconds=timeout_seconds,
                transport=transport,
            )

    tasks = [asyncio.create_task(run_one(index, entry)) for index, entry in enumerate(entries)]
    results: list[dict[str, Any]] = []
    for completed, task in enumerate(asyncio.as_completed(tasks), start=1):
        result = await task
        results.append(result)
        progress_k = 5 if 5 in k_values else min(k_values)
        progress_key = f"recall@{progress_k}"
        recall = average_metric(results, progress_key) * 100
        print(f"  [{completed:3d}/{len(entries)}] R@{progress_k}: {recall:.1f}%")
    return sorted(results, key=lambda record: int(record["case_index"]))


def _aggregate(results: list[dict[str, Any]], k_values: list[int]) -> tuple[dict[str, float], dict]:
    metric_names = [
        f"{metric}@{k}" for k in k_values for metric in ("hit", "legacy_recall", "recall", "ndcg")
    ]
    overall = {metric: average_metric(results, metric) for metric in metric_names}
    overall["cross_question_result_count"] = sum(
        float(result["cross_question_result_count"]) for result in results
    )

    results_by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        results_by_type[str(result["question_type"])].append(result)
    per_type = {
        question_type: {metric: average_metric(type_results, metric) for metric in metric_names}
        for question_type, type_results in sorted(results_by_type.items())
    }
    return overall, per_type


async def run_benchmark(
    data_path: str | Path,
    *,
    api_url: str,
    allow_localhost: bool = False,
    limit: int | None = None,
    concurrency: int = 2,
    k_values: list[int] | None = None,
    command: list[str] | None = None,
    metadata: dict[str, str] | None = None,
    readiness_timeout_seconds: float = 30.0,
    timeout_seconds: float = 60.0,
    verify_sha256: bool = True,
    transport: httpx.AsyncBaseTransport | None = None,
) -> dict[str, Any]:
    validate_target(api_url, allow_localhost=allow_localhost)
    k_values = k_values or list(DEFAULT_K_VALUES)
    dataset_path = Path(data_path)
    dataset_sha = _sha256_file(dataset_path)
    if verify_sha256 and dataset_sha != DATASET_SHA256:
        raise LongMemEvalLiveError(
            f"dataset SHA-256 mismatch: expected {DATASET_SHA256}, got {dataset_sha}"
        )

    entries = _load_dataset(dataset_path)
    if not isinstance(entries, list):
        raise LongMemEvalLiveError("dataset must be a JSON list")
    total_entries = len(entries)
    if limit is not None:
        entries = entries[:limit]
    if not entries:
        raise LongMemEvalLiveError("no LongMemEval entries selected")

    run_id = uuid4().hex[:12]
    started = time.perf_counter()
    print("\n============================================================")
    print("  Sibyl x LongMemEval Live API Benchmark")
    print(f"  API: {api_url}")
    print(f"  Questions: {len(entries)}")
    print(f"  Concurrency: {concurrency}")
    print(f"  K values: {k_values}")
    print("============================================================\n")

    case_results = await _run_cases(
        entries,
        api_url=api_url,
        run_id=run_id,
        concurrency=concurrency,
        k_values=k_values,
        readiness_timeout_seconds=readiness_timeout_seconds,
        timeout_seconds=timeout_seconds,
        transport=transport,
    )
    elapsed = time.perf_counter() - started
    overall, per_type = _aggregate(case_results, k_values)

    print("\n============================================================")
    print("  RESULTS - live /api/search")
    print("============================================================")
    for k in k_values:
        print(
            f"  Overall H@{k}: {overall[f'hit@{k}'] * 100:.1f}%  "
            f"R@{k}: {overall[f'recall@{k}'] * 100:.1f}%  "
            f"NDCG@{k}: {overall[f'ndcg@{k}']:.3f}"
        )
    print(f"  Cross-question results: {overall['cross_question_result_count']:.0f}")
    print(f"  Time: {elapsed:.1f}s")
    print("============================================================\n")

    return {
        "schema_version": "longmemeval-live-v1",
        "suite": "LongMemEval-S live API",
        "suite_version": "live-api-search-v1",
        "generated_at": _now(),
        "sibyl_commit": _git_commit(),
        "command": command,
        "mode": LIVE_RETRIEVAL_MODE,
        "runtime": {
            "runtime_mode": "live-api-ephemeral",
            "graph_engine": "surreal",
            "store": "surreal",
            "retrieval_mode": LIVE_RETRIEVAL_MODE,
            "retrieval_surface": "POST /api/search",
            "retrieval_contract": "sync entity writes plus /api/search graph results",
            "retrieval_semantics": "existing API graph hybrid/fulltext; no native vector claim",
            "embedding_provider": "none",
            "embedding_model": "not-applicable",
            "embedding_dimensions": 0,
            "tokenizer_estimate_method": "not-applicable",
            "readiness_strategy": "sync_write_plus_search_probe",
            "per_question_isolation": "throwaway organization namespace per question",
        },
        "dataset": {
            "name": dataset_path.stem,
            "path": str(dataset_path),
            "corpus_hash": _corpus_hash(dataset_path),
            "total_entries": total_entries,
            "evaluated_entries": len(entries),
            "limit": limit,
            "corpus_text_policy": CORPUS_TEXT_POLICY,
        },
        "metadata": metadata or {},
        "repeat_count": 1,
        "auth_manifest_id": AUTH_MANIFEST_ID,
        "k_values": k_values,
        "total_questions": len(entries),
        "overall": overall,
        "per_type": per_type,
        "case_results": case_results,
        "elapsed_seconds": elapsed,
        "claim_boundary": (
            "Live API runtime evidence for /api/search against an ephemeral "
            "Sibyl stack with per-question throwaway org namespaces. This "
            "artifact measures the existing graph hybrid/full-text path and "
            "does not claim native vector embedding retrieval."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run LongMemEval-S against live /api/search.")
    parser.add_argument("data", type=Path, help="Path to longmemeval_s_cleaned.json")
    parser.add_argument("--api-url", default="http://localhost:3334/api")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--k", type=int, nargs="+", default=DEFAULT_K_VALUES)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--label", default=None)
    parser.add_argument("--metadata", action="append", default=[], metavar="KEY=VALUE")
    parser.add_argument(
        "--allow-localhost",
        action="store_true",
        help="Allow mutation of a localhost API. Use only for disposable stacks.",
    )
    parser.add_argument("--readiness-timeout", type=float, default=30.0)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--skip-sha256-check", action="store_true")
    args = parser.parse_args()

    metadata = _parse_metadata(args.metadata)
    if args.label:
        metadata["label"] = args.label

    try:
        report = asyncio.run(
            run_benchmark(
                args.data,
                api_url=args.api_url,
                allow_localhost=args.allow_localhost,
                limit=args.limit,
                concurrency=args.concurrency,
                k_values=args.k,
                command=sys.argv,
                metadata=metadata,
                readiness_timeout_seconds=args.readiness_timeout,
                timeout_seconds=args.timeout,
                verify_sha256=not args.skip_sha256_check,
            )
        )
    except LongMemEvalLiveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_path = args.output or ROOT / "benchmarks" / "results" / "ai-memory" / (
        f"longmemeval_live_api_{timestamp}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"  Results saved to {out_path}")


if __name__ == "__main__":
    main()
