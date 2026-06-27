"""MonitoringAgent — collects system metrics during a pipeline run.

Useful as a sidecar node in a Pipeline to enrich the AgentBoard with
runtime metrics (latency, error counts, etc.).
"""

from __future__ import annotations

import time
from typing import Any

from forge_agent.core.base import BaseAgent
from forge_agent.core.contracts import AgentReport
from forge_agent.core.context import AgentContext
from forge_agent.registry.decorators import register_agent


@register_agent(domain="generic", tags=["monitoring", "sidecar"])
class MonitoringAgent(BaseAgent):
    agent_id = "generic.monitoring"
    name = "Generic Monitoring Agent"
    domain = "generic"

    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        # In real life: query Prometheus / OpenTelemetry.
        return {"metric_source": "noop", "observed_at": ctx.timestamp}

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        return {"emit_metric": True, "kind": "noop"}

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            domain=self.domain,
            verdict="neutral",  # type: ignore[arg-type]
            confidence=1.0,
            risk=0.0,
            weight=0.0,  # doesn't vote in aggregator
            evidence=["monitoring: noop (wire to your metrics backend)"],
            recommended_action="watch",  # type: ignore[arg-type]
            raw={"decision": decision, "elapsed_ms": 0},
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
            version=self.version,
        )
