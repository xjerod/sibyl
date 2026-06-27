from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
import typer

from sibyl_cli.logs import _stream_logs


class _FakeConnectionClosed(Exception):
    pass


class _FakeWebSocket:
    async def __aenter__(self) -> _FakeWebSocket:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def recv(self) -> str:
        raise _FakeConnectionClosed


def test_stream_logs_requires_resolved_client_token(capsys: pytest.CaptureFixture[str]) -> None:
    client = SimpleNamespace(base_url="https://sibyl.example/api", auth_token=None)

    with pytest.raises(typer.Exit):
        import asyncio

        asyncio.run(_stream_logs(client, None, None))

    assert "Authentication required" in capsys.readouterr().out


def test_stream_logs_uses_resolved_client_url_and_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connect_urls: list[str] = []

    def connect(url: str) -> _FakeWebSocket:
        connect_urls.append(url)
        return _FakeWebSocket()

    monkeypatch.setitem(
        sys.modules,
        "websockets",
        SimpleNamespace(connect=connect, ConnectionClosed=_FakeConnectionClosed),
    )
    client = SimpleNamespace(
        base_url="https://sibyl.example/api",
        auth_token="scoped-access-token",
    )

    import asyncio

    asyncio.run(_stream_logs(client, None, None))

    assert connect_urls == ["wss://sibyl.example/api/logs/stream?token=scoped-access-token"]
