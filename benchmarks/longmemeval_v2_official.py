#!/usr/bin/env python3
"""Run Sibyl through the official LongMemEval-V2 harness."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.request import urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
CORE_SRC = ROOT / "packages" / "python" / "sibyl-core" / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(CORE_SRC) not in sys.path:
    sys.path.insert(0, str(CORE_SRC))

from sibyl_core.evals.longmemeval_v2 import (  # noqa: E402
    load_longmemeval_v2_haystack,
    load_longmemeval_v2_questions,
    summarize_longmemeval_v2_inputs,
)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_root = Path(args.data_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    runtime_dir = output_dir / "runtime_inputs"
    runtime_dir.mkdir(parents=True, exist_ok=True)

    selected_questions = materialize_runtime_questions(
        data_root=data_root,
        domain=args.domain,
        question_ids=parse_question_ids(args.question_ids),
        limit=args.limit,
        output_path=runtime_dir / "questions.json",
    )
    selected_haystack = materialize_runtime_haystack(
        data_root=data_root,
        tier=args.tier,
        selected_questions=selected_questions,
        output_path=runtime_dir / "haystack.json",
    )
    memory_config = build_memory_config(args)
    memory_config_path = runtime_dir / "memory_config.json"
    write_json(memory_config_path, memory_config)

    plan = build_run_plan(
        args=args,
        data_root=data_root,
        output_dir=output_dir,
        runtime_dir=runtime_dir,
        memory_config_path=memory_config_path,
        selected_questions=selected_questions,
        selected_haystack=selected_haystack,
    )
    write_json(output_dir / "longmemeval_v2_official_plan.json", plan)
    print(json.dumps(plan, indent=2, sort_keys=True))
    if args.plan_only:
        return 0

    official_repo = resolve_official_repo(args.official_repo)
    ensure_official_harness(official_repo)
    sys.path.insert(0, str(official_repo))
    import benchmarks.longmemeval_v2_memory.sibyl_memory  # noqa: F401
    from evaluation.harness import main as harness_main

    old_argv = sys.argv
    try:
        sys.argv = build_harness_argv(
            args=args,
            data_root=data_root,
            output_dir=output_dir,
            runtime_dir=runtime_dir,
            memory_config_path=memory_config_path,
        )
        harness_main()
    finally:
        sys.argv = old_argv
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run LongMemEval-V2 with Sibyl memory.")
    parser.add_argument("--official-repo", default=os.getenv("LME_V2_OFFICIAL_REPO"))
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--domain", choices=["web", "enterprise"], required=True)
    parser.add_argument("--tier", choices=["small", "medium"], default="small")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--question-ids", nargs="*", default=None)
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--save-memory", action="store_true")
    parser.add_argument("--skip-evaluation", action="store_true")
    parser.add_argument("--load-memory-dir", default=None)

    parser.add_argument("--api-url", default=os.getenv("SIBYL_API_URL", "http://127.0.0.1:3334/api"))
    parser.add_argument("--api-token", default=os.getenv("SIBYL_API_TOKEN", ""))
    parser.add_argument("--email", default=os.getenv("LME_SIBYL_EMAIL", ""))
    parser.add_argument("--password", default=os.getenv("LME_SIBYL_PASSWORD", ""))
    parser.add_argument("--project-id", default="")
    parser.add_argument("--run-id", default=os.getenv("LME_V2_RUN_ID", f"lme-v2-{uuid4().hex[:12]}"))
    parser.add_argument("--allow-localhost", action="store_true")
    parser.add_argument("--no-signup", action="store_true")
    parser.add_argument("--content-max-chars", type=int, default=50_000)
    parser.add_argument("--search-limit", type=int, default=12)
    parser.add_argument("--max-context-items", type=int, default=8)
    parser.add_argument("--max-context-chars-per-item", type=int, default=18_000)
    parser.add_argument("--include-screenshot-refs", action="store_true")

    parser.add_argument("--reader-model", default=os.getenv("READER_MODEL", "Qwen/Qwen3.5-9B"))
    parser.add_argument("--reader-base-url", default=os.getenv("READER_BASE_URL", "http://localhost:8023/v1"))
    parser.add_argument("--reader-api-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--reader-disable-thinking", action="store_true")
    parser.add_argument("--reader-temperature", type=float, default=0.6)
    parser.add_argument("--reader-top-p", type=float, default=0.95)
    parser.add_argument("--reader-top-k", type=int, default=20)
    parser.add_argument("--reader-max-concurrent-requests", type=int, default=16)
    parser.add_argument("--max-completion-tokens", type=int, default=20_000)
    parser.add_argument("--memory-context-max-tokens", type=int, default=200_000)
    parser.add_argument("--timeout-seconds", type=float, default=43_200.0)

    parser.add_argument("--evaluator-model", default=os.getenv("EVALUATOR_MODEL", "gpt-5.2"))
    parser.add_argument("--evaluator-base-url", default=os.getenv("EVALUATOR_BASE_URL", ""))
    parser.add_argument("--evaluator-api-key-env", default=os.getenv("EVALUATOR_API_KEY_ENV", "OPENAI_API_KEY"))
    parser.add_argument("--evaluator-reasoning-effort", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--evaluator-max-completion-tokens", type=int, default=4096)
    parser.add_argument("--evaluator-timeout-seconds", type=float, default=43_200.0)
    parser.add_argument("--prompt-build-max-workers", type=int, default=1)
    parser.add_argument("--shuffle-questions-seed", type=int, default=None)
    return parser.parse_args(argv)


def parse_question_ids(raw_values: list[str] | None) -> list[str] | None:
    if not raw_values:
        return None
    ids = []
    for raw_value in raw_values:
        ids.extend(item.strip() for item in raw_value.split(",") if item.strip())
    return ids or None


def materialize_runtime_questions(
    *,
    data_root: Path,
    domain: str,
    question_ids: list[str] | None,
    limit: int | None,
    output_path: Path,
) -> list[dict[str, Any]]:
    questions = [
        question
        for question in load_longmemeval_v2_questions(data_root / "questions.jsonl")
        if question.domain == domain
    ]
    if question_ids:
        requested = set(question_ids)
        questions = [question for question in questions if question.id in requested]
        found = {question.id for question in questions}
        missing = requested - found
        if missing:
            msg = f"Unknown question ids for {domain}: {sorted(missing)}"
            raise RuntimeError(msg)
    if limit is not None:
        if limit <= 0:
            msg = "--limit must be positive"
            raise RuntimeError(msg)
        questions = questions[:limit]
    if not questions:
        msg = "No questions selected"
        raise RuntimeError(msg)

    rows: list[dict[str, Any]] = []
    for question in questions:
        row: dict[str, Any] = {
            "id": question.id,
            "domain": question.domain,
            "environment": question.environment,
            "question_type": question.question_type,
            "question": question.question,
            "answer": question.answer,
            "eval_function": question.eval_function,
        }
        if question.image is not None:
            image_path = data_root / question.image
            if not image_path.exists():
                msg = f"Missing question image: {image_path}"
                raise RuntimeError(msg)
            row["question"] = {"text": question.question, "image": str(image_path.resolve())}
        rows.append(row)
    write_json(output_path, rows)
    return rows


def materialize_runtime_haystack(
    *,
    data_root: Path,
    tier: str,
    selected_questions: list[dict[str, Any]],
    output_path: Path,
) -> dict[str, list[str]]:
    haystack = load_longmemeval_v2_haystack(haystack_path(data_root, tier))
    selected_haystack = {}
    for question in selected_questions:
        question_id = str(question["id"])
        if question_id not in haystack:
            msg = f"Missing haystack entry for question {question_id}"
            raise RuntimeError(msg)
        selected_haystack[question_id] = list(haystack[question_id])
    write_json(output_path, selected_haystack)
    return selected_haystack


def build_memory_config(args: argparse.Namespace) -> dict[str, object]:
    params: dict[str, object] = {
        "api_url": args.api_url,
        "api_token": args.api_token,
        "email": args.email,
        "password": args.password,
        "project_id": args.project_id,
        "run_id": args.run_id,
        "allow_localhost": args.allow_localhost,
        "allow_signup": not args.no_signup,
        "content_max_chars": args.content_max_chars,
        "search_limit": args.search_limit,
        "max_context_items": args.max_context_items,
        "max_context_chars_per_item": args.max_context_chars_per_item,
        "include_screenshot_refs": args.include_screenshot_refs,
    }
    return {"memory_type": "sibyl_live_api", "memory_params": params}


def haystack_path(data_root: Path, tier: str) -> Path:
    nested = data_root / "haystacks" / f"lme_v2_{tier}.json"
    if nested.exists():
        return nested
    return data_root / f"lme_v2_{tier}.json"


def build_run_plan(
    *,
    args: argparse.Namespace,
    data_root: Path,
    output_dir: Path,
    runtime_dir: Path,
    memory_config_path: Path,
    selected_questions: list[dict[str, Any]],
    selected_haystack: dict[str, list[str]],
) -> dict[str, Any]:
    all_questions = load_longmemeval_v2_questions(data_root / "questions.jsonl")
    question_by_id = {question.id: question for question in all_questions}
    selected_question_models = [question_by_id[str(row["id"])] for row in selected_questions]
    required_trajectories = sorted({tid for ids in selected_haystack.values() for tid in ids})
    llm_eval_count = sum(
        1
        for row in selected_questions
        if str(row["eval_function"]).split("(", 1)[0]
        in {"llm_abstention_checker", "llm_gotchas_checker"}
    )
    return {
        "schema_version": "sibyl-longmemeval-v2-official-plan-v1",
        "domain": args.domain,
        "tier": args.tier,
        "method": "sibyl_live_api",
        "data_root": str(data_root),
        "output_dir": str(output_dir),
        "runtime_dir": str(runtime_dir),
        "memory_config_path": str(memory_config_path),
        "official_repo": args.official_repo,
        "plan_only": args.plan_only,
        "save_memory": args.save_memory,
        "skip_evaluation": args.skip_evaluation,
        "load_memory_dir": args.load_memory_dir,
        "trajectory_path": str(data_root / "trajectories.jsonl"),
        "trajectory_path_exists": (data_root / "trajectories.jsonl").exists(),
        "question_count": len(selected_questions),
        "required_trajectory_count": len(required_trajectories),
        "llm_eval_count": llm_eval_count,
        "reader_model": args.reader_model,
        "reader_base_url": args.reader_base_url,
        "evaluator_model": args.evaluator_model,
        "requirements": build_requirement_status(args=args, data_root=data_root),
        "summary": summarize_longmemeval_v2_inputs(
            selected_question_models,
            selected_haystack,
        ),
        "honesty_contract": {
            "answer_gold_visible_to_memory": False,
            "question_gold_ids_visible_to_memory": False,
            "memory_surface": "Sibyl live API /entities and /search",
            "reader_surface": "official harness reader model",
            "scoring_surface": "official deterministic and LLM scoring functions",
        },
    }


def build_requirement_status(*, args: argparse.Namespace, data_root: Path) -> dict[str, bool]:
    official_repo = Path(args.official_repo).expanduser().resolve() if args.official_repo else None
    return {
        "official_repo_configured": official_repo is not None,
        "official_harness_exists": bool(
            official_repo and (official_repo / "evaluation" / "harness.py").exists()
        ),
        "trajectories_jsonl_exists": (data_root / "trajectories.jsonl").exists(),
        "reader_api_key_env_set": bool(os.getenv(args.reader_api_key_env)),
        "reader_endpoint_reachable": reader_endpoint_reachable(args.reader_base_url),
        "evaluator_api_key_env_set": bool(os.getenv(args.evaluator_api_key_env)),
        "transformers_available": importlib.util.find_spec("transformers") is not None,
        "torch_available": importlib.util.find_spec("torch") is not None,
    }


def reader_endpoint_reachable(base_url: str) -> bool:
    if not base_url:
        return True
    models_url = f"{base_url.rstrip('/')}/models"
    try:
        with urlopen(models_url, timeout=2) as response:
            return 200 <= int(response.status) < 500
    except Exception:
        return False


def build_harness_argv(
    *,
    args: argparse.Namespace,
    data_root: Path,
    output_dir: Path,
    runtime_dir: Path,
    memory_config_path: Path,
) -> list[str]:
    argv = [
        "evaluation.harness",
        "--domain",
        args.domain,
        "--questions-path",
        str(runtime_dir / "questions.json"),
        "--haystack-path",
        str(runtime_dir / "haystack.json"),
        "--trajectories-path",
        str(data_root / "trajectories.jsonl"),
        "--memory-config-path",
        str(memory_config_path),
        "--output-dir",
        str(output_dir),
        "--model",
        args.reader_model,
        "--api-key-env",
        args.reader_api_key_env,
        "--temperature",
        str(args.reader_temperature),
        "--top-p",
        str(args.reader_top_p),
        "--top-k",
        str(args.reader_top_k),
        "--max-completion-tokens",
        str(args.max_completion_tokens),
        "--memory-context-max-tokens",
        str(args.memory_context_max_tokens),
        "--reader-max-concurrent-requests",
        str(args.reader_max_concurrent_requests),
        "--timeout-seconds",
        str(args.timeout_seconds),
        "--prompt-build-max-workers",
        str(args.prompt_build_max_workers),
        "--evaluator-model",
        args.evaluator_model,
        "--evaluator-api-key-env",
        args.evaluator_api_key_env,
        "--evaluator-reasoning-effort",
        args.evaluator_reasoning_effort,
        "--evaluator-max-completion-tokens",
        str(args.evaluator_max_completion_tokens),
        "--evaluator-timeout-seconds",
        str(args.evaluator_timeout_seconds),
    ]
    if args.save_memory:
        argv.append("--save-memory")
    if args.skip_evaluation:
        argv.append("--skip-evaluation")
    if args.load_memory_dir:
        argv.extend(["--load-memory-dir", args.load_memory_dir])
    if args.reader_base_url:
        argv.extend(["--base-url", args.reader_base_url])
    if args.reader_disable_thinking:
        argv.append("--reader-disable-thinking")
    if args.evaluator_base_url:
        argv.extend(["--evaluator-base-url", args.evaluator_base_url])
    if args.shuffle_questions_seed is not None:
        argv.extend(["--shuffle-questions-seed", str(args.shuffle_questions_seed)])
    return argv


def resolve_official_repo(raw_path: str | None) -> Path:
    if not raw_path:
        msg = "Set --official-repo or LME_V2_OFFICIAL_REPO to the LongMemEval-V2 checkout"
        raise RuntimeError(msg)
    return Path(raw_path).expanduser().resolve()


def ensure_official_harness(path: Path) -> None:
    if not (path / "evaluation" / "harness.py").exists():
        msg = f"Missing official evaluation/harness.py under {path}"
        raise RuntimeError(msg)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
