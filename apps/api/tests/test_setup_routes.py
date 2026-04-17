from unittest.mock import AsyncMock

import pytest

from sibyl.api.routes import setup as setup_routes
from sibyl.persistence.legacy.setup import LegacySetupStatus


@pytest.mark.asyncio
async def test_get_setup_status_uses_legacy_status_and_validates_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock()
    service.get_openai_key.return_value = "sk-openai"
    service.get_anthropic_key.return_value = None

    monkeypatch.setattr(
        setup_routes,
        "get_legacy_setup_status",
        AsyncMock(return_value=LegacySetupStatus(has_users=True, has_orgs=False)),
    )
    monkeypatch.setattr(setup_routes, "get_settings_service", lambda: service)
    monkeypatch.setattr(setup_routes, "_check_openai_key", AsyncMock(return_value=(True, None)))
    monkeypatch.setattr(setup_routes, "_check_anthropic_key", AsyncMock(return_value=(False, None)))

    response = await setup_routes.get_setup_status(validate_keys=True)

    assert response.needs_setup is False
    assert response.has_users is True
    assert response.has_orgs is False
    assert response.openai_configured is True
    assert response.anthropic_configured is False
    assert response.openai_valid is True
    assert response.anthropic_valid is None


@pytest.mark.asyncio
async def test_update_config_persists_and_reports_current_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = AsyncMock()
    service.get_openai_key.return_value = "sk-openai"
    service.get_anthropic_key.return_value = "sk-anthropic"

    monkeypatch.setattr(setup_routes, "get_settings_service", lambda: service)
    monkeypatch.setattr(setup_routes, "_check_openai_key", AsyncMock(return_value=(True, None)))
    monkeypatch.setattr(
        setup_routes,
        "_check_anthropic_key",
        AsyncMock(return_value=(False, "Invalid API key")),
    )

    response = await setup_routes.update_config(
        setup_routes.ConfigUpdateRequest(
            openai_api_key="sk-openai",
            anthropic_api_key="sk-anthropic",
        )
    )

    assert response.success is True
    assert response.openai_valid is True
    assert response.anthropic_valid is False
    assert response.anthropic_error == "Invalid API key"
    service.set.assert_any_await(
        "openai_api_key",
        "sk-openai",
        is_secret=True,
        description="OpenAI API key for embeddings and entity extraction",
    )
    service.set.assert_any_await(
        "anthropic_api_key",
        "sk-anthropic",
        is_secret=True,
        description="Anthropic API key for Claude-powered extraction workflows",
    )


@pytest.mark.asyncio
async def test_get_config_status_uses_settings_service(monkeypatch: pytest.MonkeyPatch) -> None:
    service = AsyncMock()
    service.get_with_source = AsyncMock(
        side_effect=[("sk-openai", "database"), (None, "none")]
    )

    monkeypatch.setattr(setup_routes, "get_settings_service", lambda: service)

    response = await setup_routes.get_config_status()

    assert response.openai_configured is True
    assert response.anthropic_configured is False
    assert response.openai_source == "database"
    assert response.anthropic_source == "none"
