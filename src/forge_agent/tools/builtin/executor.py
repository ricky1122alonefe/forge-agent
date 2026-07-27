"""Execute registered tools with mode-aware handlers (P3.4)."""

from __future__ import annotations

from typing import Any

from forge_agent.platform.tool_registry import get_tool_registry
from forge_agent.tools.builtin.mode import ToolMode, resolve_tool_mode


async def execute_tool(
    tool_name: str,
    *,
    keyword: str | None = None,
    tool_mode: str | ToolMode | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Call a registered tool by name."""
    from forge_agent.builtin.tools import register_builtin_tools

    register_builtin_tools()
    registry = get_tool_registry()
    tool = registry.get(tool_name)
    mode = (
        tool_mode
        if isinstance(tool_mode, ToolMode)
        else resolve_tool_mode(str(tool_mode) if tool_mode is not None else None)
    )
    result = await tool.call(keyword=keyword or "", tool_mode=mode.value, **kwargs)
    if isinstance(result, dict):
        return result
    return {"result": result, "source": "unknown"}
