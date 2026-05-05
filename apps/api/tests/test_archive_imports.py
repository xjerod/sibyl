from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "sibyl.persistence.auth_archive",
        "sibyl.persistence.content_archive",
    ],
)
def test_archive_imports_do_not_load_legacy_db_connection(module_name: str) -> None:
    script = (
        "import importlib, json, sys; "
        f"importlib.import_module({module_name!r}); "
        "print(json.dumps('sibyl.db.connection' in sys.modules))"
    )

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        capture_output=True,
        check=True,
        text=True,
    )

    assert json.loads(result.stdout) is False
