"""Tests for launcher tenant resolution."""

from __future__ import annotations

from pathlib import Path

from forge_agent.platform import LocalTenant
from forge_agent.project.launcher import _detect_tenant_root, resolve_local_tenant


def test_detect_tenant_root_from_standard_layout(tmp_path: Path) -> None:
    project_root = tmp_path / "data" / "tenants" / "acme" / "projects" / "demo"
    project_root.mkdir(parents=True)

    assert _detect_tenant_root(project_root) == (tmp_path / "data").resolve()


def test_resolve_local_tenant_uses_detected_root(tmp_path: Path) -> None:
    root = tmp_path / "data"
    tenant = LocalTenant("acme", root_dir=root)
    project_root = tenant.create_project("demo")

    resolved = resolve_local_tenant("acme", project_root)
    assert resolved.root_dir == root.resolve()
    assert resolved.tenant_id == "acme"
