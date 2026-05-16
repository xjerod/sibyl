from __future__ import annotations

from sibyl_core.logging.config import configure_logging, get_logger


def test_configure_logging_respects_force_color(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.delenv("NO_COLOR", raising=False)

    configure_logging(service_name="api", level="INFO")
    get_logger().info("color_probe", ok=True)

    output = capsys.readouterr().out
    assert "\x1b[" in output
    assert "color_probe" in output


def test_force_color_overrides_no_color(monkeypatch, capsys) -> None:
    monkeypatch.setenv("FORCE_COLOR", "1")
    monkeypatch.setenv("NO_COLOR", "1")

    configure_logging(service_name="api", level="INFO")
    get_logger().info("color_probe", ok=True)

    output = capsys.readouterr().out
    assert "\x1b[" in output
    assert "color_probe" in output


def test_no_color_disables_auto_color_without_force(monkeypatch, capsys) -> None:
    monkeypatch.delenv("FORCE_COLOR", raising=False)
    monkeypatch.setenv("NO_COLOR", "1")

    configure_logging(service_name="api", level="INFO")
    get_logger().info("color_probe", ok=True)

    output = capsys.readouterr().out
    assert "\x1b[" not in output
    assert "color_probe" in output
