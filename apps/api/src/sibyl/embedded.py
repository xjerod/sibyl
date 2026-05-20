"""Embedded SurrealDB single-writer guardrails."""

from __future__ import annotations

import contextlib
import os
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType

import tomli_w


def default_embedded_data_dir() -> Path:
    return Path.home() / ".sibyl" / "data" / "surreal"


def default_embedded_lock_path() -> Path:
    return Path.home() / ".sibyl" / "run" / "embedded-surreal.lock"


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@dataclass
class EmbeddedSurrealLock:
    data_dir: Path
    lock_path: Path | None = None

    def __post_init__(self) -> None:
        if self.lock_path is None:
            self.lock_path = default_embedded_lock_path()
        self.data_dir = self.data_dir.expanduser()
        self.lock_path = self.lock_path.expanduser()
        self._file = None

    def __enter__(self) -> EmbeddedSurrealLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.release()

    def acquire(self) -> None:
        import fcntl

        assert self.lock_path is not None
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        existing_pid = self._read_pid()
        self._file = self.lock_path.open("a+", encoding="utf-8")
        try:
            fcntl.flock(self._file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            detail = f"pid {existing_pid}" if existing_pid else "another process"
            raise RuntimeError(f"Embedded SurrealDB is already locked by {detail}.") from exc

        if existing_pid and not pid_alive(existing_pid):
            self._write_lock(recovered_stale_pid=existing_pid)
        else:
            self._write_lock()

    def release(self) -> None:
        import fcntl

        if self._file is None:
            return
        assert self.lock_path is not None
        try:
            self._file.seek(0)
            self._file.truncate()
            fcntl.flock(self._file.fileno(), fcntl.LOCK_UN)
        finally:
            self._file.close()
            self._file = None
        with contextlib.suppress(OSError):
            self.lock_path.unlink()

    def _read_pid(self) -> int | None:
        assert self.lock_path is not None
        if not self.lock_path.exists():
            return None
        try:
            with self.lock_path.open("rb") as stream:
                data = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError):
            return None
        value = data.get("pid")
        if not isinstance(value, int | str):
            return None
        try:
            return int(value)
        except ValueError:
            return None

    def _write_lock(self, *, recovered_stale_pid: int | None = None) -> None:
        assert self.lock_path is not None
        assert self._file is not None
        payload: dict[str, object] = {
            "pid": os.getpid(),
            "data_dir": str(self.data_dir),
            "acquired_at": datetime.now(UTC).isoformat(),
        }
        if recovered_stale_pid is not None:
            payload["recovered_stale_pid"] = recovered_stale_pid
        self._file.seek(0)
        self._file.truncate()
        self._file.write(tomli_w.dumps(payload))
        self._file.flush()
        os.fsync(self._file.fileno())
