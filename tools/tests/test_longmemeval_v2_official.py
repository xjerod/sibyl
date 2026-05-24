from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

EXPECTED_REQUIRED_TRAJECTORIES = 2
TEST_CONTENT_MAX_CHARS = 420


def _load_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_runner_module() -> ModuleType:
    return _load_module(
        Path(__file__).parents[2] / "benchmarks" / "longmemeval_v2_official.py",
        "longmemeval_v2_official",
    )


def _load_memory_module() -> ModuleType:
    return _load_module(
        Path(__file__).parents[2] / "benchmarks" / "longmemeval_v2_memory" / "sibyl_memory.py",
        "sibyl_memory",
    )


def _load_download_module() -> ModuleType:
    return _load_module(
        Path(__file__).parents[2] / "benchmarks" / "longmemeval_v2_download.py",
        "longmemeval_v2_download",
    )


def test_longmemeval_v2_download_patterns_default_to_text_context() -> None:
    module = _load_download_module()

    text_context_patterns = module.download_patterns(include_trajectory_screenshots=False)
    full_patterns = module.download_patterns(include_trajectory_screenshots=True)

    assert "trajectories.jsonl" in text_context_patterns
    assert "question_screenshots/*.png" in text_context_patterns
    assert "trajectory_screenshots/*.tar.gz" not in text_context_patterns
    assert "trajectory_screenshots/*.tar.gz" in full_patterns


def test_official_runner_plan_materializes_honest_runtime_inputs(tmp_path: Path) -> None:
    module = _load_runner_module()
    data_root = tmp_path / "data"
    output_dir = tmp_path / "out"
    _write_dataset(data_root)

    assert (
        module.main(
            [
                "--data-root",
                str(data_root),
                "--domain",
                "enterprise",
                "--tier",
                "small",
                "--output-dir",
                str(output_dir),
                "--limit",
                "1",
                "--plan-only",
                "--allow-localhost",
            ]
        )
        == 0
    )

    runtime_questions = json.loads(
        (output_dir / "runtime_inputs" / "questions.json").read_text(encoding="utf-8")
    )
    runtime_haystack = json.loads(
        (output_dir / "runtime_inputs" / "haystack.json").read_text(encoding="utf-8")
    )
    memory_config = json.loads(
        (output_dir / "runtime_inputs" / "memory_config.json").read_text(encoding="utf-8")
    )
    plan = json.loads(
        (output_dir / "longmemeval_v2_official_plan.json").read_text(encoding="utf-8")
    )

    assert [row["id"] for row in runtime_questions] == ["q-enterprise"]
    assert runtime_haystack == {"q-enterprise": ["t1", "t2"]}
    assert memory_config["memory_type"] == "sibyl_live_api"
    assert memory_config["memory_params"]["allow_localhost"] is True
    assert plan["honesty_contract"]["answer_gold_visible_to_memory"] is False
    assert plan["required_trajectory_count"] == EXPECTED_REQUIRED_TRAJECTORIES
    assert plan["requirements"]["trajectories_jsonl_exists"] is True
    assert plan["requirements"]["official_repo_configured"] is False
    assert "reader_endpoint_reachable" in plan["requirements"]
    assert "torch_available" in plan["requirements"]


def test_sibyl_memory_payloads_chunk_trajectory_by_state() -> None:
    module = _load_memory_module()

    payloads = module.build_entity_payloads_for_trajectory(
        _trajectory("t1", tree="button " + ("Priority " * 80)),
        project_id="project_lme",
        run_id="run_lme",
        content_max_chars=TEST_CONTENT_MAX_CHARS,
        include_screenshot_refs=True,
    )

    assert len(payloads) > 1
    assert {payload["entity_type"] for payload in payloads} == {"session"}
    assert all(payload["skip_conflicts"] is True for payload in payloads)
    assert all(len(str(payload["content"])) <= TEST_CONTENT_MAX_CHARS for payload in payloads)
    assert payloads[0]["metadata"]["project_id"] == "project_lme"
    assert payloads[0]["metadata"]["longmemeval_v2_trajectory_id"] == "t1"
    assert any("Screenshot:" in str(payload["content"]) for payload in payloads)


def test_sibyl_memory_context_formats_retrieved_content() -> None:
    module = _load_memory_module()

    context = module.search_results_to_memory_context(
        [
            {
                "content": "The priority filter was selected before opening incidents.",
                "score": 0.875,
                "metadata": {
                    "longmemeval_v2_trajectory_id": "t1",
                    "longmemeval_v2_chunk_index": 0,
                },
            }
        ],
        max_items=1,
        max_chars_per_item=24,
    )

    assert context == [
        {
            "type": "text",
            "value": (
                "Retrieved evidence rank 1\n"
                "Trajectory: t1\n"
                "Chunk: 0\n"
                "Score: 0.875\n\n"
                "The priority filter was"
            ),
        }
    ]


def test_sibyl_memory_query_context_strips_gold_answer() -> None:
    module = _load_memory_module()
    memory = module.SibylLiveApiMemory.__new__(module.SibylLiveApiMemory)
    module.Memory.__init__(memory, {})

    memory.set_query_context(
        question_id="q1",
        question_item={
            "id": "q1",
            "question": "Which filter was selected?",
            "answer": "Priority",
        },
    )

    context = memory.get_query_context()
    assert context["question_item"] == {
        "id": "q1",
        "question": "Which filter was selected?",
    }


def _write_dataset(root: Path) -> None:
    (root / "haystacks").mkdir(parents=True)
    (root / "questions.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "id": "q-enterprise",
                        "domain": "enterprise",
                        "environment": "workarena",
                        "question_type": "dynamic-environment",
                        "question": "Which filter was selected?",
                        "image": None,
                        "answer": "The priority filter.",
                        "eval_function": "norm_phrase_set_match",
                    }
                ),
                json.dumps(
                    {
                        "id": "q-web",
                        "domain": "web",
                        "environment": "visualwebarena",
                        "question_type": "procedure",
                        "question": "How did checkout finish?",
                        "image": None,
                        "answer": "It confirmed the order.",
                        "eval_function": "llm_gotchas_checker",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    (root / "haystacks" / "lme_v2_small.json").write_text(
        json.dumps({"q-enterprise": ["t1", "t2"], "q-web": ["t3"]}),
        encoding="utf-8",
    )
    (root / "trajectories.jsonl").write_text(
        "\n".join(json.dumps(_trajectory(trajectory_id)) for trajectory_id in ["t1", "t2", "t3"]),
        encoding="utf-8",
    )


def _trajectory(trajectory_id: str, *, tree: str = "button Priority") -> dict[str, object]:
    return {
        "id": trajectory_id,
        "domain": "enterprise",
        "environment": "workarena",
        "goal": "Resolve the assigned incident.",
        "outcome": "success",
        "start_url": "https://example.test/start",
        "states": [
            {
                "state_index": 0,
                "step": 0,
                "url": "https://example.test/start",
                "action": "click filter",
                "thought": "Need incidents",
                "accessibility_tree": tree,
                "screenshot": f"screenshots/{trajectory_id}/0.png",
            },
            {
                "state_index": 1,
                "step": 1,
                "url": "https://example.test/incidents",
                "action": None,
                "thought": None,
                "accessibility_tree": "list Incidents",
                "screenshot": f"screenshots/{trajectory_id}/1.png",
            },
        ],
    }
