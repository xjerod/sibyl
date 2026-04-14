"""Tests that packaged CLI assets stay in sync with repo-local sources."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_packaged_skill_and_hook_assets_match_repo_sources() -> None:
    """Embedded CLI assets should mirror the repo-local copies exactly."""
    file_pairs = [
        (
            REPO_ROOT / "skills" / "sibyl" / "SKILL.md",
            REPO_ROOT / "apps" / "cli" / "src" / "sibyl_cli" / "data" / "skills" / "sibyl" / "SKILL.md",
        ),
        (
            REPO_ROOT / "skills" / "sibyl" / "EXAMPLES.md",
            REPO_ROOT / "apps" / "cli" / "src" / "sibyl_cli" / "data" / "skills" / "sibyl" / "EXAMPLES.md",
        ),
        (
            REPO_ROOT / "skills" / "sibyl" / "WORKFLOWS.md",
            REPO_ROOT / "apps" / "cli" / "src" / "sibyl_cli" / "data" / "skills" / "sibyl" / "WORKFLOWS.md",
        ),
        (
            REPO_ROOT / "hooks" / "session-start.py",
            REPO_ROOT / "apps" / "cli" / "src" / "sibyl_cli" / "data" / "hooks" / "session-start.py",
        ),
        (
            REPO_ROOT / "hooks" / "user-prompt-submit.py",
            REPO_ROOT / "apps" / "cli" / "src" / "sibyl_cli" / "data" / "hooks" / "user-prompt-submit.py",
        ),
    ]

    mismatches = [
        f"{source.relative_to(REPO_ROOT)} != {packaged.relative_to(REPO_ROOT)}"
        for source, packaged in file_pairs
        if source.read_text() != packaged.read_text()
    ]

    assert mismatches == []
