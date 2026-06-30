"""Tenant abstraction for forge-agent.

A Tenant represents an isolated namespace for projects, agents, pipelines,
and runtime state. It is the foundation for both single-tenant deployments
(one local tenant) and enterprise SaaS deployments (many tenants backed by
database / object storage).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class Tenant(ABC):
    """Abstract tenant: a namespace that owns projects and their runtime data."""

    def __init__(self, tenant_id: str, **kwargs: Any) -> None:
        self.tenant_id = tenant_id

    # ------------------------------------------------------------------
    # Project lifecycle
    # ------------------------------------------------------------------

    @abstractmethod
    def create_project(self, project_id: str) -> Path:
        """Create a new project and return its root path."""

    @abstractmethod
    def get_project_path(self, project_id: str) -> Path:
        """Return the root path of an existing project."""

    @abstractmethod
    def project_exists(self, project_id: str) -> bool:
        """Return True if the project exists under this tenant."""

    @abstractmethod
    def list_projects(self) -> list[str]:
        """Return all project IDs for this tenant."""

    @abstractmethod
    def delete_project(self, project_id: str) -> None:
        """Delete a project and all its data."""

    # ------------------------------------------------------------------
    # Project-scoped storage paths
    # ------------------------------------------------------------------

    @abstractmethod
    def get_state_path(self, project_id: str) -> Path:
        """Return the directory where pipeline execution results are stored."""

    @abstractmethod
    def get_logs_path(self, project_id: str) -> Path:
        """Return the directory where execution logs are stored."""

    # ------------------------------------------------------------------
    # Tenant-scoped shared resources
    # ------------------------------------------------------------------

    @abstractmethod
    def get_shared_path(self) -> Path:
        """Return the directory for tenant-wide shared assets
        (custom agent types, skills, etc.)."""

    @abstractmethod
    def get_config_path(self) -> Path:
        """Return the tenant-level configuration file/directory."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def ensure_project(self, project_id: str) -> Path:
        """Return project path, creating it if it does not exist."""
        if not self.project_exists(project_id):
            return self.create_project(project_id)
        return self.get_project_path(project_id)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(tenant_id={self.tenant_id!r})"
