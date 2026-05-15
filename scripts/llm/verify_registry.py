#!/usr/bin/env python3
"""Probe every first-class LLM registry entry against its provider."""

# ruff: noqa: E402,T201

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/python/sibyl-core/src"))

from sibyl_core.ai.registry import ModelEntry, ModelKind, llm_entries, model_registry
from sibyl_core.ai.validation import ModelValidationResult, check_model_availability

LLM_PROVIDERS = {"anthropic", "gemini", "openai"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", action="append", help="Registry alias or snapshot to probe.")
    parser.add_argument("--provider", action="append", choices=sorted(LLM_PROVIDERS))
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result JSON.")
    parser.add_argument(
        "--require-keys", action="store_true", help="Fail if any selected key is missing."
    )
    args = parser.parse_args()

    return asyncio.run(_main(args))


async def _main(args: argparse.Namespace) -> int:
    entries = _selected_entries(args.model, args.provider)
    if not entries:
        print("No LLM registry entries matched the requested filters.", file=sys.stderr)
        return 2

    verified_at = datetime.now(UTC).isoformat()
    results: list[dict[str, object]] = []
    skipped: list[dict[str, str]] = []
    failed = False

    for entry in entries:
        key = _api_key_for(entry.provider)
        if key is None:
            skipped.append(
                {"provider": entry.provider, "model": entry.alias, "reason": "missing key"}
            )
            continue

        provider = cast(Literal["anthropic", "gemini", "openai"], entry.provider)
        result = await check_model_availability(provider, entry.provider_model_id, key)
        failed = failed or _first_class_failed(entry, result)
        results.append(_result_payload(entry, result, verified_at))
        _print_result(entry, result, verified_at)

    if skipped:
        for item in skipped:
            print(f"skipped {item['provider']}:{item['model']} ({item['reason']})")
        if args.require_keys:
            failed = True

    deprecation_candidates = [
        item for item in results if item["status"] in {"model_not_found", "permission_denied"}
    ]
    if deprecation_candidates:
        print("deprecation candidates:")
        for item in deprecation_candidates:
            print(f"  {item['provider']}:{item['alias']} status={item['status']}")

    if args.json:
        print(
            json.dumps(
                {
                    "verified_at": verified_at,
                    "results": results,
                    "skipped": skipped,
                    "deprecation_candidates": deprecation_candidates,
                },
                indent=2,
                sort_keys=True,
            )
        )

    if not results and args.require_keys:
        return 2
    return 1 if failed else 0


def _selected_entries(
    aliases: list[str] | None,
    providers: list[str] | None,
) -> list[ModelEntry]:
    if aliases:
        entries = []
        for alias in aliases:
            entry = model_registry.get(alias, kind=ModelKind.LLM)
            if entry is None:
                raise SystemExit(f"Unknown LLM registry entry: {alias}")
            entries.append(entry)
    else:
        entries = llm_entries()

    if providers:
        provider_set = set(providers)
        entries = [entry for entry in entries if entry.provider in provider_set]

    return [entry for entry in entries if entry.provider in LLM_PROVIDERS]


def _result_payload(
    entry: ModelEntry,
    result: ModelValidationResult,
    verified_at: str,
) -> dict[str, object]:
    return {
        "alias": entry.alias,
        "provider": entry.provider,
        "provider_model_id": entry.provider_model_id,
        "status": result.status,
        "valid": result.valid,
        "latency_ms": result.latency_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "last_verified_at": entry.last_verified_at.isoformat(),
        "verified_at": verified_at if result.valid else None,
        "error": result.error,
    }


def _first_class_failed(entry: ModelEntry, result: ModelValidationResult) -> bool:
    return entry.warning is None and not result.valid


def _api_key_for(provider: str) -> str | None:
    for name in _key_env_names(provider):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _key_env_names(provider: str) -> tuple[str, ...]:
    return {
        "anthropic": ("SIBYL_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"),
        "gemini": ("SIBYL_GEMINI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "openai": ("SIBYL_OPENAI_API_KEY", "OPENAI_API_KEY"),
    }[provider]


def _print_result(
    entry: ModelEntry,
    result: ModelValidationResult,
    verified_at: str,
) -> None:
    status = "PASS" if result.valid else "FAIL"
    print(f"{status} {entry.provider}:{entry.alias} ({entry.provider_model_id})")
    print(f"  status={result.status} latency={result.latency_ms:.0f}ms")
    if result.valid:
        print(f"  verified_at={verified_at}")
    elif result.error:
        print(f"  error={result.error}")


if __name__ == "__main__":
    raise SystemExit(main())
