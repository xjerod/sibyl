"""E2E tests for quick capture archive workflows."""

import pytest


@pytest.mark.cli
class TestArchiveWorkflow:
    """Test quick capture archive round-trips."""

    def test_capture_round_trip_through_archive(self, cli, unique_id) -> None:
        """Capture a memory and retrieve its raw archive entry."""
        title = f"E2E archive smoke {unique_id}"
        content = f"Raw archive content {unique_id}"

        capture_result = cli.capture(content, title=title)
        assert capture_result.success, f"Capture failed: {capture_result.stderr}"

        captured_entity = capture_result.json()
        assert captured_entity.get("id")
        assert captured_entity.get("name") == title
        assert captured_entity.get("metadata", {}).get("capture_mode") == "quick"
        assert captured_entity.get("metadata", {}).get("capture_surface") == "cli"

        archived_capture = cli.wait_for_archive_capture(title, capture_surface="cli")
        assert archived_capture.get("title") == title
        assert archived_capture.get("capture_surface") == "cli"
        assert archived_capture.get("entity_id") == captured_entity.get("id")

        show_result = cli.archive_show(archived_capture["id"])
        assert show_result.success, f"Archive show failed: {show_result.stderr}"

        archive_detail = show_result.json()
        assert archive_detail.get("id") == archived_capture.get("id")
        assert archive_detail.get("title") == title
        assert archive_detail.get("raw_content") == content
        assert archive_detail.get("metadata", {}).get("capture_mode") == "quick"
        assert archive_detail.get("metadata", {}).get("capture_surface") == "cli"
