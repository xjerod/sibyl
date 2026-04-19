"""Tests for evaluation report metadata and filenames."""

from __future__ import annotations

import json
from pathlib import Path

from sibyl_core.evals import EvalConfig, EvalMetrics, EvalReport


def test_eval_report_save_includes_label_and_metadata(tmp_path: Path) -> None:
    config = EvalConfig(
        api_base_url="http://localhost:3334/api",
        output_dir=tmp_path,
        label="Surreal Smoke",
        metadata={"store": "surreal", "dataset": "copied-prod"},
    )
    report = EvalReport(
        config=config,
        queries=[],
        aggregated=EvalMetrics(latency_ms=42.0),
        search_type="unified",
    )

    path = report.save()

    assert "surreal_smoke" in path.name
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["label"] == "Surreal Smoke"
    assert payload["api_base_url"] == "http://localhost:3334/api"
    assert payload["metadata"] == {"store": "surreal", "dataset": "copied-prod"}
    assert payload["metrics"]["latency_ms"] == 42.0
