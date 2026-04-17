from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from tools.baselines.common import (
    CASE_FILE_ORDER,
    DEFAULT_BASELINE_EMAIL,
    DEFAULT_BASELINE_PASSWORD,
    DEFAULT_BASELINES_DIR,
    api_base_url,
    auth_headers,
    baseline_base_url,
    dump_json,
    emit,
    login_or_signup,
    mcp_base_url,
    parse_http_response,
    read_jsonl,
    validate_expectations,
)


async def execute_case(
    case: dict[str, Any],
    *,
    api_client: httpx.AsyncClient,
    token: str,
    mcp_session: ClientSession,
    email: str,
    password: str,
) -> dict[str, Any]:
    kind = case["kind"]

    if kind == "auth_login":
        response = await api_client.post(
            "/auth/local/login",
            json={"email": email, "password": password},
        )
        return parse_http_response(response)

    if kind == "rest":
        headers = auth_headers(token) if case.get("auth", "bearer") == "bearer" else {}
        response = await api_client.request(
            case["method"],
            case["path"],
            headers=headers,
            json=case.get("json"),
        )
        return parse_http_response(response)

    if kind == "mcp_list_tools":
        return (await mcp_session.list_tools()).model_dump(mode="json")

    if kind == "mcp_list_resources":
        return (await mcp_session.list_resources()).model_dump(mode="json")

    if kind == "mcp_tool":
        return (
            await mcp_session.call_tool(
                case["tool"],
                case.get("arguments"),
            )
        ).model_dump(mode="json")

    if kind == "mcp_resource":
        return (await mcp_session.read_resource(case["uri"])).model_dump(mode="json")

    raise ValueError(f"Unsupported baseline case kind: {kind}")


async def replay_case(
    case: dict[str, Any],
    *,
    api_client: httpx.AsyncClient,
    token: str,
    mcp_session: ClientSession,
    email: str,
    password: str,
) -> None:
    actual = await execute_case(
        case,
        api_client=api_client,
        token=token,
        mcp_session=mcp_session,
        email=email,
        password=password,
    )
    errors = validate_expectations(actual, case["expect"])
    if errors:
        formatted = "\n".join(f"- {error}" for error in errors)
        raise AssertionError(
            f"Baseline case {case['id']} failed:\n{formatted}\n\nActual:\n{dump_json(actual)}"
        )


async def replay_all(
    *,
    base_url: str,
    baselines_dir: Path,
    email: str,
    password: str,
) -> None:
    api_url = api_base_url(base_url)
    mcp_url = mcp_base_url(base_url)

    async with httpx.AsyncClient(base_url=api_url, timeout=30.0) as api_client:
        auth_payload = await login_or_signup(
            api_client,
            email=email,
            password=password,
        )
        token = str(auth_payload["access_token"])

    async with (
        httpx.AsyncClient(timeout=30.0, headers=auth_headers(token)) as transport_client,
        httpx.AsyncClient(base_url=api_url, timeout=30.0) as api_client,
        streamable_http_client(mcp_url, http_client=transport_client) as (
            read_stream,
            write_stream,
            _,
        ),
        ClientSession(read_stream, write_stream) as mcp_session,
    ):
        await mcp_session.initialize()
        for filename in CASE_FILE_ORDER:
            path = baselines_dir / filename
            emit(f"Replaying {path.as_posix()}")
            for case in read_jsonl(path):
                await replay_case(
                    case,
                    api_client=api_client,
                    token=token,
                    mcp_session=mcp_session,
                    email=email,
                    password=password,
                )
                emit(f"  PASS {case['id']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay the captured Sibyl baseline corpus.")
    parser.add_argument(
        "--base-url",
        default=baseline_base_url(),
        help="Base URL for the running Sibyl server.",
    )
    parser.add_argument(
        "--baselines-dir",
        type=Path,
        default=DEFAULT_BASELINES_DIR,
        help="Directory containing the generated baseline corpus files.",
    )
    parser.add_argument(
        "--email",
        default=DEFAULT_BASELINE_EMAIL,
        help="Baseline user email.",
    )
    parser.add_argument(
        "--password",
        default=DEFAULT_BASELINE_PASSWORD,
        help="Baseline user password.",
    )
    return parser.parse_args()


async def amain() -> int:
    args = parse_args()
    await replay_all(
        base_url=args.base_url,
        baselines_dir=args.baselines_dir,
        email=args.email,
        password=args.password,
    )
    emit("Baseline replay passed.")
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    raise SystemExit(main())
