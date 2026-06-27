"""Shared CLI helpers."""

from __future__ import annotations

from pathlib import Path

from forge_agent.generator.store import FileCodeStore


def get_store(project: Path) -> FileCodeStore:
    """Get the FileCodeStore for a project (auto-uses generated_agents/)."""
    root = project / "generated_agents"
    if not root.is_dir():
        raise FileNotFoundError(
            f"No generated_agents/ directory at {root}. "
            "Run `forge-agent generate` first or create the directory."
        )
    return FileCodeStore(root)


def default_generated_agents_path(project: Path) -> Path:
    return project / "generated_agents"
