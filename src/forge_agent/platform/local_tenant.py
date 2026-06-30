"""Local file-system implementation of a Tenant."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from forge_agent.exceptions import ProjectAlreadyExistsError, ProjectNotFoundError
from forge_agent.platform.tenant import Tenant


class LocalTenant(Tenant):
    """A tenant stored on the local file system.

    Default layout::

        ~/.forge-agent/
        └── tenants/
            └── {tenant_id}/
                ├── projects/
                │   └── {project_id}/
                │       ├── agents/
                │       ├── pipelines/
                │       ├── tools/
                │       ├── configs/
                │       ├── state/
                │       ├── logs/
                │       └── run.py
                ├── shared/
                │   └── agent_types/
                └── config.yaml
    """

    DEFAULT_ROOT = Path.home() / ".forge-agent"

    def __init__(
        self,
        tenant_id: str,
        *,
        root_dir: Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(tenant_id, **kwargs)
        self.root_dir = (root_dir or self.DEFAULT_ROOT).expanduser().resolve()
        self.tenant_dir = self.root_dir / "tenants" / tenant_id
        self.projects_dir = self.tenant_dir / "projects"
        self.shared_dir = self.tenant_dir / "shared"
        self._config_path = self.tenant_dir / "config.yaml"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _project_path(self, project_id: str) -> Path:
        return self.projects_dir / project_id

    @staticmethod
    def _ensure_directory(path: Path) -> Path:
        path.mkdir(parents=True, exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    def create_project(self, project_id: str) -> Path:
        """Create the on-disk directory tree for a project."""
        if self.project_exists(project_id):
            raise ProjectAlreadyExistsError(project_id, tenant_id=self.tenant_id)

        project_root = self._project_path(project_id)
        self._ensure_directory(project_root / "agents")
        self._ensure_directory(project_root / "pipelines")
        self._ensure_directory(project_root / "tools")
        self._ensure_directory(project_root / "configs")
        self._ensure_directory(project_root / "state")
        self._ensure_directory(project_root / "logs")
        return project_root

    def get_project_path(self, project_id: str) -> Path:
        if not self.project_exists(project_id):
            raise ProjectNotFoundError(project_id, tenant_id=self.tenant_id)
        return self._project_path(project_id)

    def project_exists(self, project_id: str) -> bool:
        return self._project_path(project_id).is_dir()

    def list_projects(self) -> list[str]:
        if not self.projects_dir.exists():
            return []
        return sorted(path.name for path in self.projects_dir.iterdir() if path.is_dir())

    def delete_project(self, project_id: str) -> None:
        if not self.project_exists(project_id):
            raise ProjectNotFoundError(project_id, tenant_id=self.tenant_id)
        shutil.rmtree(self._project_path(project_id))

    # ------------------------------------------------------------------
    # Project-scoped storage paths
    # ------------------------------------------------------------------

    def get_state_path(self, project_id: str) -> Path:
        return self.get_project_path(project_id) / "state"

    def get_logs_path(self, project_id: str) -> Path:
        return self.get_project_path(project_id) / "logs"

    # ------------------------------------------------------------------
    # Tenant-scoped shared resources
    # ------------------------------------------------------------------

    def get_shared_path(self) -> Path:
        return self._ensure_directory(self.shared_dir)

    def get_config_path(self) -> Path:
        return self._config_path

    def __repr__(self) -> str:
        return f"LocalTenant(tenant_id={self.tenant_id!r}, root_dir={self.root_dir!r})"
