"""Source code access layer for the dashboard.

Wraps FileCodeStore to provide dashboard-specific code reading.
Decoupled from FastAPI — pure data access.
"""

from __future__ import annotations

from pathlib import Path


class CodeSource:
    """Data access layer for generated agent source code."""

    def __init__(self, project_root: Path) -> None:
        self._project_root = project_root
        self._store = None

    @property
    def store(self):
        """Lazy access to FileCodeStore."""
        if self._store is None:
            from forge_agent.generator.store import FileCodeStore

            store_path = self._project_root / "generated_agents"
            if store_path.exists():
                self._store = FileCodeStore(store_path)
        return self._store

    def get_source(self, agent_id: str, version: str | None = None) -> str | None:
        """Load source code for an agent. Returns None if not available."""
        if self._store is None and self.store is None:
            return None
        try:
            return self._store.load(agent_id, version)
        except Exception:
            return None

    def list_versions(self, agent_id: str) -> list[str]:
        """List all versions for an agent."""
        if self._store is None and self.store is None:
            return []
        try:
            return self._store.list_versions(agent_id)
        except Exception:
            return []
