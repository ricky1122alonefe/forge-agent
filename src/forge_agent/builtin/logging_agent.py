"""LoggingAgent — minimal reference implementation of BaseAgent.

It does nothing useful on its own; it exists to:
    1. Demonstrate the observe → decide → act cycle.
    2. Serve as a starter template for new Agents.
    3. Be used in tests as a "always-registered" agent.

A real Agent plugs in search/LLM/DB; this one only logs.
"""

from __future__ import annotations

from typing import Any

from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.registry.decorators import register_agent


@register_agent(domain="generic", tags=["example", "logging"])
class LoggingAgent(BaseAgent):
    agent_id = "generic.logging"
    name = "Logging Agent (Example)"
    domain = "generic"

    async def _on_init(self) -> None:
        # Register a default prompt version so the agent is fully usable
        self.prompt_manager.register(
            self.agent_id,
            version="v1",
            template=(
                "You are a logging agent.\n"
                "Context: scope_id={scope_id}, scope_name={scope_name}\n"
                "Payload: {payload}\n"
                "Produce a brief, neutral log line."
            ),
        )

    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        self.log("info", f"observing scope={ctx.scope_id}")
        return {"raw_payload": ctx.payload, "timestamp": ctx.timestamp}

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        # In a real agent this is where you'd call an LLM using prompt_manager.
        prompt = self.prompt_manager.render(
            self.agent_id,
            {
                "scope_id": ctx.scope_id,
                "scope_name": ctx.scope_name,
                "payload": observation,
            },
        )
        self.log("info", "deciding with rendered prompt")
        return {"prompt": prompt, "chosen_action": "log_only"}

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            domain=self.domain,
            verdict=Verdict.NEUTRAL,
            confidence=0.5,
            risk=0.0,
            weight=1.0,
            evidence=[f"prompt length={len(decision.get('prompt', ''))}"],
            recommended_action=Action.WATCH,
            raw={"decision": decision, "run_id": ctx.run_id},
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
            version=self.version,
        )
