from __future__ import annotations

import asyncio
import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import httpx
import pytest
from tools.bench import eval_gate


def _load_live_module() -> ModuleType:
    path = Path(__file__).parents[2] / "benchmarks" / "longmemeval_live.py"
    spec = importlib.util.spec_from_file_location("longmemeval_live", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json_response(request: httpx.Request, payload: dict[str, Any], status_code: int = 200):
    return httpx.Response(status_code, json=payload, request=request)


def test_longmemeval_live_refuses_localhost_without_explicit_allow() -> None:
    module = _load_live_module()

    with pytest.raises(module.LongMemEvalLiveError, match="Refusing to run"):
        module.validate_target("http://localhost:3334/api", allow_localhost=False)

    module.validate_target("http://localhost:3334/api", allow_localhost=True)


def test_longmemeval_live_builds_gate_valid_report(tmp_path: Path) -> None:
    module = _load_live_module()
    data_path = tmp_path / "longmemeval_s_cleaned.json"
    data_path.write_text(
        json.dumps(
            [
                {
                    "question_id": "q1",
                    "question_type": "single-session-user",
                    "question": "What did I buy?",
                    "question_date": "2026/01/03 12:00",
                    "answer_session_ids": ["s2"],
                    "haystack_session_ids": ["s1", "s2"],
                    "haystack_dates": ["2026/01/01", "2026/01/02"],
                    "haystack_sessions": [
                        [{"role": "user", "content": "I bought pencils."}],
                        [{"role": "user", "content": "I bought markers."}],
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    state: dict[str, Any] = {"token": None, "entities": []}

    async def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/health":
            return _json_response(request, {"status": "ok"})
        if path == "/api/auth/local/signup":
            state["token"] = "fixture-access-token"  # noqa: S105
            return _json_response(
                request,
                {
                    "access_token": state["token"],
                    "organization": {"id": "org-q1", "slug": "org-q1"},
                },
                status_code=201,
            )
        if path == "/api/entities":
            payload = json.loads(request.content)
            entity = {
                "id": f"entity-{len(state['entities'])}",
                "entity_type": payload["entity_type"],
                "metadata": payload["metadata"],
            }
            state["entities"].append(entity)
            return _json_response(request, entity, status_code=201)
        if path == "/api/search":
            payload = json.loads(request.content)
            query = payload["query"]
            entities = list(state["entities"])
            if query != "LongMemEval":
                entities.sort(
                    key=lambda entity: entity["metadata"]["longmemeval_session_id"] != "s2"
                )
            results = [
                {
                    "id": entity["id"],
                    "type": "session",
                    "name": "fixture",
                    "content": "",
                    "score": 1.0 - (index * 0.1),
                    "result_origin": "graph",
                    "metadata": entity["metadata"],
                }
                for index, entity in enumerate(entities)
            ]
            return _json_response(request, {"results": results, "total": len(results)})
        return _json_response(request, {"detail": "not found"}, status_code=404)

    report = asyncio.run(
        module.run_benchmark(
            data_path,
            api_url="http://ci-sibyl/api",
            limit=1,
            concurrency=1,
            k_values=[1, 2],
            command=["longmemeval_live.py", "fixture.json"],
            verify_sha256=False,
            transport=httpx.MockTransport(handler),
        )
    )

    assert report["schema_version"] == "longmemeval-live-v1"
    assert report["mode"] == "hybrid"
    assert report["runtime"]["embedding_provider"] == "none"
    assert report["runtime"]["embedding_dimensions"] == 0
    assert report["dataset"]["corpus_text_policy"] == module.CORPUS_TEXT_POLICY
    assert report["overall"]["hit@1"] == 1.0
    assert report["overall"]["recall@1"] == 1.0
    assert report["overall"]["cross_question_result_count"] == 0.0
    assert report["case_results"][0]["ranked_session_ids"] == ["s2", "s1"]
    assert eval_gate.evaluate_report(report, profile="ai-memory") == []
