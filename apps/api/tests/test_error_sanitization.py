"""Tests for error message sanitization.

Verifies that internal exception details are never exposed to API clients.
"""

import pytest

from sibyl.api.errors import (
    INTERNAL_ERROR,
    VALIDATION_ERROR,
)


class TestErrorConstants:
    """Tests for error message constants."""

    def test_internal_error_is_generic(self) -> None:
        """Internal error message should be generic."""
        assert "internal" in INTERNAL_ERROR.lower()
        assert "try again" in INTERNAL_ERROR.lower()
        # Should not contain implementation details
        assert "exception" not in INTERNAL_ERROR.lower()
        assert "traceback" not in INTERNAL_ERROR.lower()

    def test_validation_error_is_generic(self) -> None:
        """Validation error message should be generic."""
        assert "invalid" in VALIDATION_ERROR.lower()
        # Should not contain implementation details
        assert "exception" not in VALIDATION_ERROR.lower()


class TestNoExposedExceptions:
    """Integration tests to ensure no raw exceptions are exposed."""

    def test_500_errors_use_safe_messages(self) -> None:
        """All 500 error handlers should use safe messages."""
        import ast
        from pathlib import Path

        routes_dir = Path("src/sibyl/api/routes")

        for py_file in routes_dir.glob("*.py"):
            content = py_file.read_text()

            # Parse the AST to find HTTPException calls with status_code=500
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    # Check if it's HTTPException
                    func = node.func
                    if isinstance(func, ast.Name) and func.id == "HTTPException":
                        # Check for status_code=500 and detail=str(e)
                        for kw in node.keywords:
                            if kw.arg == "status_code":
                                if isinstance(kw.value, ast.Constant) and kw.value.value == 500:
                                    # This is a 500 error, check the detail
                                    for detail_kw in node.keywords:
                                        if detail_kw.arg == "detail":
                                            # Should NOT be str(e) or similar
                                            if isinstance(detail_kw.value, ast.Call):
                                                if isinstance(detail_kw.value.func, ast.Name):
                                                    if detail_kw.value.func.id == "str":
                                                        pytest.fail(
                                                            f"Found exposed exception in {py_file}: "
                                                            f"HTTPException(500, detail=str(e))"
                                                        )
