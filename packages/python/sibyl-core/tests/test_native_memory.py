from __future__ import annotations

from sibyl_core.services.native_memory import (
    NativeWriteMode,
    coerce_native_write_mode,
    native_write_mode_from_env,
)


def test_native_write_mode_defaults_disabled() -> None:
    assert coerce_native_write_mode(None) is NativeWriteMode.DISABLED
    assert coerce_native_write_mode("") is NativeWriteMode.DISABLED
    assert native_write_mode_from_env({}) is NativeWriteMode.DISABLED


def test_native_write_mode_accepts_enabled_values() -> None:
    assert coerce_native_write_mode("enabled") is NativeWriteMode.ENABLED
    assert coerce_native_write_mode("true") is NativeWriteMode.ENABLED
    assert native_write_mode_from_env({"SIBYL_NATIVE_WRITE": "1"}) is NativeWriteMode.ENABLED
