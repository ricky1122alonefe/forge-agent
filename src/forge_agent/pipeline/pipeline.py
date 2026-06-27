"""Pipeline: declarative DAG of nodes (Agent / function / conditional / aggregator)."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from forge_agent.core.context import AgentContext

log = logging.getLogger(__name__)


class NodeType(str, Enum):
    AGENT = "agent"
    FUNCTION = "function"
    CONDITIONAL = "conditional"
    AGGREGATOR = "aggregator"


@dataclass
class PipelineNode:
    """One step in a Pipeline DAG.

    Exactly one of (agent_id, func, condition) is meaningful depending on
    node_type — see NodeType.
    """

    node_id: str
    node_type: NodeType
    agent_id: str | None = None
    func: Callable[..., Awaitable[Any]] | None = None
    condition: Callable[[dict[str, Any]], bool] | None = None
    next_nodes: list[str] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)


@dataclass
class Pipeline:
    """A named DAG of PipelineNodes."""

    pipeline_id: str
    nodes: dict[str, PipelineNode] = field(default_factory=dict)
    entry: str = ""

    def add_node(self, node: PipelineNode) -> None:
        if node.node_id in self.nodes:
            from forge_agent.exceptions import DuplicateNodeError
            raise DuplicateNodeError(node.node_id)
        self.nodes[node.node_id] = node
        if not self.entry:
            self.entry = node.node_id

    def add_edge(self, from_id: str, to_id: str) -> None:
        if from_id not in self.nodes:
            from forge_agent.exceptions import PipelineNodeNotFoundError
            raise PipelineNodeNotFoundError(from_id)
        if to_id not in self.nodes:
            from forge_agent.exceptions import PipelineNodeNotFoundError
            raise PipelineNodeNotFoundError(to_id)
        self.nodes[from_id].next_nodes.append(to_id)

    def visualize(self) -> str:
        """ASCII visualization — handy for debugging & docs."""
        lines = [f"Pipeline[{self.pipeline_id}] (entry={self.entry})"]
        for nid, node in self.nodes.items():
            arrow = " → " + ", ".join(node.next_nodes) if node.next_nodes else " (end)"
            label = node.node_type.value
            if node.node_type == NodeType.AGENT:
                label += f": {node.agent_id}"
            lines.append(f"  ├─ {nid} [{label}]{arrow}")
        return "\n".join(lines)
