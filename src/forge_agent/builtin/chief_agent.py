"""ChiefAgent — generic LLM-driven synthesizer.

Maps to the "总 Agent" / "汇总" role in vertical frameworks.
Default implementation: pure aggregator (no LLM), suitable for tests.
Plug in an LLM client (openai, anthropic, deepseek, ...) by overriding `decide`.
"""

from __future__ import annotations

from typing import Any

from forge_agent.core.base import BaseAgent
from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.context import AgentContext
from forge_agent.core.enums import Action, Verdict
from forge_agent.pipeline.aggregator import Aggregator
from forge_agent.registry.decorators import register_agent


@register_agent(domain="generic", tags=["chief", "aggregator"])
class ChiefAgent(BaseAgent):
    agent_id = "generic.chief"
    name = "Generic Chief Agent"
    domain = "generic"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.aggregator = Aggregator(
            hard_risk_threshold=float((config or {}).get("hard_risk_threshold", 0.7))
        )

    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        # The "observation" of a chief agent is the list of peer reports.
        return {"ctx_payload": ctx.payload}

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        # In real life: call LLM with the peer reports in observation.
        return {"strategy": "weighted_vote", "hard_risk_threshold": self.aggregator.hard_risk_threshold}

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        # Chief acts by returning a synthesized verdict. The actual board
        # is computed by the PipelineEngine's aggregator node; here we just
        # report what we *would* synthesize.
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            domain=self.domain,
            verdict=Verdict.NEUTRAL,
            confidence=0.5,
            risk=0.0,
            weight=0.0,
            evidence=["chief agent ran (no LLM configured)"],
            recommended_action=Action.WATCH,
            raw={"decision": decision, "run_id": ctx.run_id},
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
            version=self.version,
        )

    def synthesize(self, reports: list[AgentReport], ctx: AgentContext) -> AgentBoard:
        """Public helper: turn peer reports into an AgentBoard."""
        return self.aggregator.aggregate(reports, ctx)
