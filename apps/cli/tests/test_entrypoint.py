"""Tests for the package console-script entry point."""

from __future__ import annotations

import json
from unittest.mock import patch

from sibyl_cli import entrypoint


def test_main_fast_paths_context_quick_json(monkeypatch, capsys) -> None:
    monkeypatch.setattr("sys.argv", ["sibyl", "context", "--quick", "--json"])
    payload = {
        "server": "http://localhost:3334",
        "org": "auto",
        "project": "project_123",
        "project_source": "linked",
        "auth": "valid",
    }

    with patch("sibyl_cli.context_quick.quick_context_payload", return_value=payload):
        entrypoint.main()

    assert json.loads(capsys.readouterr().out) == payload
