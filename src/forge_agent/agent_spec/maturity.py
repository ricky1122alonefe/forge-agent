"""Agent maturity ladder (AGENT_PLAN A3.2)."""

from __future__ import annotations

from typing import Any

STAGES: list[dict[str, str]] = [
    {
        "id": "draft",
        "label": "草稿",
        "hint": "Mock 模式，适合本地演示与流程练习",
    },
    {
        "id": "verified",
        "label": "已验证",
        "hint": "mock_cases smoke 已通过，配置可信",
    },
    {
        "id": "connected",
        "label": "已连接",
        "hint": "已关闭 Mock 并配置真实工具",
    },
    {
        "id": "production",
        "label": "生产",
        "hint": "真实 LLM + 工具，可用于正式分析",
    },
]


def compute_maturity(agent: dict[str, Any]) -> dict[str, Any]:
    """Derive maturity stage from agent YAML fields."""
    config = agent.get("config", {}) if isinstance(agent.get("config"), dict) else {}
    meta = agent.get("_meta", {}) if isinstance(agent.get("_meta"), dict) else {}
    mock_mode = bool(config.get("mock_mode", True))
    smoke_verified = bool(meta.get("smoke_verified"))
    has_tools = bool(config.get("tools"))
    has_mock_cases = bool(agent.get("mock_cases"))

    if not mock_mode and has_tools:
        stage = "connected"
        next_step = "在 LLM 设置中配置 API Key，完成一次真实运行"
    elif not mock_mode:
        stage = "production"
        next_step = "Agent 已面向真实 LLM 运行"
    elif smoke_verified:
        stage = "verified"
        next_step = "关闭 Mock 并配置工具/LLM 以进入「已连接」"
    else:
        stage = "draft"
        next_step = "运行 mock smoke 测试或保存时自动验证"

    stage_index = next(i for i, s in enumerate(STAGES) if s["id"] == stage)
    current = STAGES[stage_index]
    return {
        "stage": stage,
        "label": current["label"],
        "hint": current["hint"],
        "next_step": next_step,
        "mock_mode": mock_mode,
        "smoke_verified": smoke_verified,
        "has_mock_cases": has_mock_cases,
        "stages": STAGES,
        "stage_index": stage_index,
    }
