from __future__ import annotations

import os
import tomllib
from pathlib import Path

from sibyl.embedded import EmbeddedSurrealLock


def test_embedded_lock_writes_and_removes_lockfile(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    lock_path = tmp_path / "run" / "embedded-surreal.lock"

    with EmbeddedSurrealLock(data_dir=data_dir, lock_path=lock_path):
        payload = tomllib.loads(lock_path.read_text())
        assert payload["pid"] == os.getpid()
        assert payload["data_dir"] == str(data_dir)

    assert not lock_path.exists()


def test_embedded_lock_recovers_stale_pid(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    lock_path = tmp_path / "run" / "embedded-surreal.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text('pid = 424242\ndata_dir = "/old"\n')

    with EmbeddedSurrealLock(data_dir=data_dir, lock_path=lock_path):
        payload = tomllib.loads(lock_path.read_text())
        assert payload["pid"] == os.getpid()
        assert payload["recovered_stale_pid"] == 424242
