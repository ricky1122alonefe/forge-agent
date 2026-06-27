"""PipelineEngine: executes a Pipeline using the Scheduler.

Supports:
    - AGENT nodes (delegate to Scheduler)
    - FUNCTION nodes (call user function)
    - CONDITIONAL nodes (route by condition(state))
    - AGGREGATOR nodes (collect all prior reports into an AgentBoard)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.context import AgentContext
from forge_agent.pipeline.aggregator import Aggregator
from forge_agent.pipeline.pipeline import NodeType, Pipeline, PipelineNode
from forge_agent.scheduler.scheduler import Scheduler, ScheduleTask

log = logging.getLogger(__name__)


class PipelineEngine:
    """Runs a Pipeline DAG and returns the final state dict."""

    def __init__(self, *, aggregator: Aggregator | None = None) -> None:
        self.aggregator = aggregator or Aggregator()

    async def run(self, pipeline: Pipeline, ctx: AgentContext) -> dict[str, Any]:
        """Execute the pipeline starting from `pipeline.entry`.

        Returns a dict like:
            {
                "ctx": AgentContext,
                "reports": {node_id: AgentReport, ...},
                "board":  AgentBoard | None,
                "extra":  {...user function outputs...},
            }
        """
        state: dict[str, Any] = {
            "ctx": ctx,
            "reports": {},
            "extra": {},
        }
        log.info("Pipeline[%s] starting from %s", pipeline.pipeline_id, pipeline.entry)
        await self._walk(pipeline, pipeline.entry, ctx, state, set())
        log.info("Pipeline[%s] done. %d node(s) executed.", pipeline.pipeline_id, len(state["reports"]))
        return state

    # ------------------------------------------------------------------ Internal

    async def _walk(
        self,
        pipeline: Pipeline,
        node_id: str,
        ctx: AgentContext,
        state: dict[str, Any],
        visited: set[str],
    ) -> None:
        if not node_id:
            return
        if node_id in visited:
            log.warning("Cycle detected at %s, skipping", node_id)
            return
        visited = visited | {node_id}

        node = pipeline.nodes.get(node_id)
        if node is None:
            log.warning("Node %s not found, skipping", node_id)
            return

        # ---- Dispatch by node type ----
        if node.node_type == NodeType.AGENT:
            await self._run_agent_node(node, ctx, state)
        elif node.node_type == NodeType.FUNCTION:
            await self._run_function_node(node, ctx, state)
        elif node.node_type == NodeType.CONDITIONAL:
            chosen = self._run_conditional_node(node, state)
            if chosen:
                await self._walk(pipeline, chosen, ctx, state, visited)
            return
        elif node.node_type == NodeType.AGGREGATOR:
            board = self._run_aggregator_node(node, ctx, state)
            state["board"] = board
            return  # aggregator is typically a terminal node

        # ---- Walk next nodes (default: sequential) ----
        for nxt in node.next_nodes:
            await self._walk(pipeline, nxt, ctx, state, visited)

    async def _run_agent_node(
        self,
        node: PipelineNode,
        ctx: AgentContext,
        state: dict[str, Any],
    ) -> None:
        assert node.agent_id, f"AGENT node {node.node_id} missing agent_id"
        log.info("  → agent node %s (%s)", node.node_id, node.agent_id)
        scheduler = Scheduler()
        scheduler.add_task(
            ScheduleTask(
                task_id=node.node_id,
                agent_id=node.agent_id,
                context=ctx,
            )
        )
        results = await scheduler.run()
        report = results[node.node_id].report
        if report is not None:
            state["reports"][node.node_id] = report

    async def _run_function_node(
        self,
        node: PipelineNode,
        ctx: AgentContext,
        state: dict[str, Any],
    ) -> None:
        assert node.func, f"FUNCTION node {node.node_id} missing func"
        log.info("  → function node %s", node.node_id)
        out = await node.func(ctx, state, **(node.config or {}))
        state["extra"][node.node_id] = out

    def _run_conditional_node(
        self,
        node: PipelineNode,
        state: dict[str, Any],
    ) -> str | None:
        assert node.condition, f"CONDITIONAL node {node.node_id} missing condition"
        if not node.next_nodes:
            return None
        # Map truthy next → first, falsy next → second (or first if only one)
        truthy = node.next_nodes[0]
        falsy = node.next_nodes[1] if len(node.next_nodes) > 1 else None
        branch = truthy if node.condition(state) else falsy
        log.info("  → conditional node %s → %s", node.node_id, branch)
        return branch

    def _run_aggregator_node(
        self,
        node: PipelineNode,
        ctx: AgentContext,
        state: dict[str, Any],
    ) -> AgentBoard:
        log.info("  → aggregator node %s", node.node_id)
        reports: list[AgentReport] = list(state["reports"].values())
        return self.aggregator.aggregate(reports, ctx)
