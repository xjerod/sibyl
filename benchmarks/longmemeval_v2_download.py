#!/usr/bin/env python3
"""Download the public LongMemEval-V2 data needed for Sibyl evals."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

DEFAULT_REPO_ID = "xiaowu0162/longmemeval-v2"
TEXT_CONTEXT_PATTERNS = [
    "questions.jsonl",
    "haystacks/*.json",
    "trajectories.jsonl",
    "question_screenshots/*.png",
    "README.md",
    "SCHEMA.md",
    "DATA_CARD.md",
    "checksums.sha256",
    "LICENSE",
]
TRAJECTORY_SCREENSHOT_PATTERNS = ["trajectory_screenshots/*.tar.gz"]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data_root = Path(args.data_root).expanduser().resolve()
    if args.force and data_root.exists():
        shutil.rmtree(data_root)

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        msg = "Missing huggingface_hub. Run through moon or uv with huggingface-hub."
        raise RuntimeError(msg) from exc

    patterns = download_patterns(include_trajectory_screenshots=args.include_trajectory_screenshots)
    snapshot_download(
        repo_id=args.repo_id,
        repo_type="dataset",
        revision=args.revision,
        local_dir=str(data_root),
        allow_patterns=patterns,
    )
    summary = build_summary(
        data_root,
        repo_id=args.repo_id,
        revision=args.revision,
        include_trajectory_screenshots=args.include_trajectory_screenshots,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download LongMemEval-V2 data for Sibyl.")
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    parser.add_argument("--revision", default=None)
    parser.add_argument("--include-trajectory-screenshots", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args(argv)


def download_patterns(*, include_trajectory_screenshots: bool) -> list[str]:
    patterns = list(TEXT_CONTEXT_PATTERNS)
    if include_trajectory_screenshots:
        patterns.extend(TRAJECTORY_SCREENSHOT_PATTERNS)
    return patterns


def build_summary(
    data_root: Path,
    *,
    repo_id: str,
    revision: str | None,
    include_trajectory_screenshots: bool,
) -> dict[str, Any]:
    files = [path for path in data_root.rglob("*") if path.is_file()]
    required = [
        data_root / "questions.jsonl",
        data_root / "haystacks" / "lme_v2_small.json",
        data_root / "haystacks" / "lme_v2_medium.json",
        data_root / "trajectories.jsonl",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        msg = f"LongMemEval-V2 download missing required files: {missing}"
        raise RuntimeError(msg)
    return {
        "repo_id": repo_id,
        "revision": revision,
        "data_root": str(data_root),
        "mode": "full" if include_trajectory_screenshots else "text-context",
        "file_count": len(files),
        "size_bytes": sum(path.stat().st_size for path in files),
        "questions_jsonl": str((data_root / "questions.jsonl").resolve()),
        "trajectories_jsonl": str((data_root / "trajectories.jsonl").resolve()),
        "next": [
            "moon run bench-longmemeval-v2-official -- --plan-only ...",
            "moon run bench-longmemeval-v2-official-full -- ...",
        ],
    }


if __name__ == "__main__":
    raise SystemExit(main())
