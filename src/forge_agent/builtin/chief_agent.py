"""ChiefAgent — generic LLM-driven synthesizer.

Maps to the "总 Agent" / "汇总" role in vertical frameworks.
Default implementation: pure aggregator (no LLM), suitable for tests.
Plug in an LLM client (openai, anthropic, deepseek, ...) by overriding `decide`.
"""

from __future__ import annotations

from typing import Any

from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.pipeline.aggregator import Aggregator, board_verdict
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
        """Collect peer reports from the context payload."""
        raw_reports = ctx.payload.get("reports", [])
        board = ctx.payload.get("board")
        reports: list[AgentReport] = []
        if isinstance(raw_reports, list):
            for item in raw_reports:
                if isinstance(item, AgentReport):
                    reports.append(item)
                elif isinstance(item, dict):
                    reports.append(self._report_from_dict(item))
        return {
            "reports": [r.to_dict() for r in reports],
            "board": board
            if isinstance(board, dict)
            else (board.to_dict() if isinstance(board, AgentBoard) else {}),
            "n_reports": len(reports),
        }

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        """Synthesize peer reports. Default: weighted-majority vote."""
        reports_raw = observation.get("reports", [])
        if not reports_raw:
            return {
                "strategy": "no_reports",
                "verdict": Verdict.NEUTRAL.value,
                "confidence": 0.0,
                "risk": 0.0,
                "summary": "No peer reports available.",
            }

        reports = [self._report_from_dict(r) for r in reports_raw]
        verdict_value = board_verdict(reports)
        try:
            verdict = Verdict(verdict_value)
        except ValueError:
            verdict = Verdict.NEUTRAL

        avg_confidence = sum(r.confidence for r in reports) / len(reports) if reports else 0.0
        avg_risk = sum(r.risk for r in reports) / len(reports) if reports else 0.0
        hard_guards = [
            f"{r.agent_id} triggered hard risk ({r.risk:.2f} >= {self.aggregator.hard_risk_threshold})"
            for r in reports
            if r.is_hard_risk(self.aggregator.hard_risk_threshold)
        ]

        recommended_action = Action.WATCH
        if verdict in {Verdict.LEAN_POSITIVE}:
            recommended_action = Action.EXECUTE if not hard_guards else Action.EXECUTE_CAUTIOUS
        elif verdict in {Verdict.LEAN_NEGATIVE, Verdict.RISK}:
            recommended_action = Action.HOLD if not hard_guards else Action.STOP

        summary_parts = [
            f"{len(reports)} peer reports, weighted verdict: {verdict.value}",
            f"average confidence: {avg_confidence:.2f}, average risk: {avg_risk:.2f}",
        ]
        if hard_guards:
            summary_parts.append(f"hard guards: {len(hard_guards)}")

        return {
            "strategy": "weighted_vote",
            "verdict": verdict.value,
            "confidence": avg_confidence,
            "risk": avg_risk,
            "recommended_action": recommended_action.value,
            "hard_guards": hard_guards,
            "summary": "; ".join(summary_parts),
        }

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        """Return a synthesized report."""
        verdict = Verdict(decision.get("verdict", Verdict.NEUTRAL.value))
        recommended_action = Action(decision.get("recommended_action", Action.WATCH.value))
        evidence = [decision.get("summary", "chief agent synthesized")]
        evidence.extend(decision.get("hard_guards", []))
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            domain=self.domain,
            verdict=verdict,
            confidence=float(decision.get("confidence", 0.5)),
            risk=float(decision.get("risk", 0.0)),
            weight=0.0,
            evidence=evidence,
            recommended_action=recommended_action,
            raw={"decision": decision, "run_id": ctx.run_id},
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
            version=self.version,
        )

    def synthesize(self, reports: list[AgentReport], ctx: AgentContext) -> AgentBoard:
        """Public helper: turn peer reports into an AgentBoard."""
        return self.aggregator.aggregate(reports, ctx)

    @staticmethod
    def _report_from_dict(data: dict[str, Any]) -> AgentReport:
        """Rebuild an AgentReport from its serialized dict."""
        from forge_agent.core.enums import Action, Verdict

        report_data = dict(data)
        if "verdict" in report_data:
            try:
                report_data["verdict"] = Verdict(report_data["verdict"])
            except ValueError:
                report_data["verdict"] = Verdict.NEUTRAL
        if "recommended_action" in report_data:
            try:
                report_data["recommended_action"] = Action(report_data["recommended_action"])
            except ValueError:
                report_data["recommended_action"] = Action.WATCH

        # These fields are passed explicitly below.
        timestamp = report_data.pop("timestamp", "")
        run_id = report_data.pop("run_id", "")
        version = report_data.pop("version", "0.1.0")
        # weight is part of AgentReport; keep it if present.

        return AgentReport(
            **report_data,
            timestamp=timestamp,
            run_id=run_id,
            version=version,
        )
