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
        "sibyl.auth.rls",
    ],
)
def test_storage_neutral_imports_do_not_load_relational_stack(module_name: str) -> None:
    script = (
        "import importlib, json, sys; "
        f"importlib.import_module({module_name!r}); "
        "print(json.dumps({"
        "'db': 'sibyl.db.connection' in sys.modules, "
        "'sqlalchemy': 'sqlalchemy' in sys.modules"
        "}))"
    )

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        capture_output=True,
        check=True,
        text=True,
    )

    assert json.loads(result.stdout) == {"db": False, "sqlalchemy": False}
