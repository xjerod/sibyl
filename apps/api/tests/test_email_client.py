"""Tests for transactional email delivery helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from sibyl.config import settings
from sibyl.email.client import EmailClient


@pytest.mark.asyncio
async def test_email_client_writes_jsonl_outbox(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    outbox_path = tmp_path / "email-outbox.jsonl"
    monkeypatch.setattr(settings, "email_outbox_path", str(outbox_path))
    monkeypatch.setattr(settings, "resend_api_key", SecretStr(""))

    client = EmailClient()
    await client.send(
        to="auth-flow@example.com",
        subject="Reset your Sibyl password",
        html="<a href='http://localhost/reset-password?token=reset-token'>Reset</a>",
        text="http://localhost/reset-password?token=reset-token",
    )

    lines = outbox_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["to"] == ["auth-flow@example.com"]
    assert record["subject"] == "Reset your Sibyl password"
    assert "reset-token" in record["text"]
