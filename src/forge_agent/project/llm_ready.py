"""LLM readiness checks for real Agent runs (AGENT_PLAN A7)."""

from __future__ import annotations

from pathlib import Path

from forge_agent.platform import LocalTenant
from forge_agent.project.launcher import _configure_llm
from forge_agent.web.llm_settings import get_llm_settings_view


def ensure_llm_ready(tenant: LocalTenant, project_root: Path) -> None:
    """Raise ValueError when mock_mode is off but no usable LLM provider is configured."""
    _configure_llm(tenant, project_root)
    view = get_llm_settings_view(tenant, project_root.name)
    primary_id = view.get("primary_id")
    providers = {p["provider_id"]: p for p in view.get("providers", [])}
    if not primary_id or primary_id not in providers:
        raise ValueError("LLM 未配置：请在 LLM 设置中选择 primary provider")
    primary = providers[primary_id]
    if primary.get("needs_key") and not primary.get("key_configured"):
        raise ValueError(
            f"LLM API Key 未配置：请为 provider {primary_id!r} 设置环境变量或项目 .env"
        )
