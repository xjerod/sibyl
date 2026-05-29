"""Production-guard tests for CoreConfig embedded-store selection."""

from __future__ import annotations

import pytest

from sibyl_core.config import CoreConfig


class TestCoreConfigEmbeddedStoreGuard:
    """CoreConfig must refuse embedded stores in production like apps/api does."""

    def test_in_memory_forbidden_in_production(self) -> None:
        with pytest.raises(ValueError, match="In-memory SurrealDB is forbidden in production"):
            CoreConfig(
                _env_file=None,
                environment="production",
                surreal_url="",
            )

    def test_surrealkv_forbidden_in_production_without_single_writer_opt_in(self) -> None:
        with pytest.raises(ValueError, match="Embedded SurrealDB requires explicit single-writer"):
            CoreConfig(
                _env_file=None,
                environment="production",
                surreal_url="",
                surreal_data_dir="/var/lib/sibyl/surreal",
            )

    def test_surrealkv_allowed_in_production_with_single_writer_opt_in(self) -> None:
        config = CoreConfig(
            _env_file=None,
            environment="production",
            surreal_url="",
            surreal_data_dir="/var/lib/sibyl/surreal",
            allow_embedded_single_writer=True,
        )

        assert config.resolved_surreal_url == "surrealkv:///var/lib/sibyl/surreal"

    def test_remote_surreal_allowed_in_production(self) -> None:
        config = CoreConfig(
            _env_file=None,
            environment="production",
            surreal_url="ws://surrealdb:8000/rpc",
        )

        assert config.resolved_surreal_url == "ws://surrealdb:8000/rpc"

    def test_embedded_allowed_outside_production(self) -> None:
        config = CoreConfig(
            _env_file=None,
            environment="development",
            surreal_url="",
        )

        assert config.resolved_surreal_url == "memory://"
