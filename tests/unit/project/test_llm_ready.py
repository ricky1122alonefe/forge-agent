"""Tests for LLM readiness gate (AGENT_PLAN A7.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from forge_agent.platform.local_tenant import LocalTenant
from forge_agent.project.llm_ready import ensure_llm_ready


def test_ensure_llm_ready_requires_key_for_deepseek(tmp_path: Path) -> None:
    tenant = LocalTenant("acme", root_dir=tmp_path / "data")
    project_root = tenant.create_project("demo")
    with pytest.raises(ValueError, match="API Key"):
        ensure_llm_ready(tenant, project_root)
