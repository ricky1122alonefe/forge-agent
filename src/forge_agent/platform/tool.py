"""Tool abstraction for forge-agent.

A Tool is any callable capability that an agent can invoke at runtime.
Tools are registered in a ToolRegistry and referenced by name in agent
configurations.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any

ToolCallable = Callable[..., Coroutine[Any, Any, Any]]


@dataclass
class Tool:
    """Definition of a callable tool."""

    name: str
    description: str
    handler: ToolCallable
    params: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    async def call(self, **kwargs: Any) -> Any:
        """Invoke the tool handler."""
        return await self.handler(**kwargs)
