"""ChiefAgent — generic LLM-driven synthesizer.

Maps to the "总 Agent" / "汇总" role in vertical frameworks.
Default implementation: pure aggregator (no LLM), suitable for tests.
Plug in an LLM client (openai, anthropic, deepseek, ...) by overriding `decide`.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.pipeline.aggregator import Aggregator, board_verdict
from forge_agent.registry.decorators import register_agent

log = logging.getLogger(__name__)


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
        self.llm_mode = bool((config or {}).get("llm_mode", False))
        self.llm_provider = (config or {}).get("provider")
        self.llm_model = (config or {}).get("model")
        self.temperature = float((config or {}).get("temperature", 0.2))
        self.max_tokens = (config or {}).get("max_tokens")
        self.system_prompt = (config or {}).get("system_prompt")
        self.mock_mode = bool((config or {}).get("mock_mode", False))
        self.mock_response = (config or {}).get("mock_response", "")
        self.guard_rules: list[dict[str, Any]] = list((config or {}).get("guard_rules", []))

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
        """Synthesize peer reports. Default: weighted-majority vote; optional LLM."""
        reports_raw = observation.get("reports", [])
        if not reports_raw:
            return {
                "strategy": "no_reports",
                "verdict": Verdict.NEUTRAL.value,
                "confidence": 0.0,
                "risk": 0.0,
                "recommended_action": Action.WATCH.value,
                "summary": "No peer reports available.",
            }

        reports = [self._report_from_dict(r) for r in reports_raw]
        fallback = self._weighted_vote(reports)

        if self.llm_mode:
            llm_decision = await self._llm_synthesize(reports, observation, fallback)
            return self._apply_guardrails(llm_decision, reports)

        return self._apply_guardrails(fallback, reports)

    def _weighted_vote(self, reports: list[AgentReport]) -> dict[str, Any]:
        """Weighted-majority vote as the default (and fallback) strategy."""
        verdict_value = board_verdict(reports)
        try:
            verdict = Verdict(verdict_value)
        except ValueError:
            verdict = Verdict.NEUTRAL

        avg_confidence = sum(r.confidence for r in reports) / len(reports) if reports else 0.0
        avg_risk = sum(r.risk for r in reports) / len(reports) if reports else 0.0
        rule_guards = self._evaluate_guard_rules(reports)
        threshold_guards = [
            f"{r.agent_id} triggered hard risk ({r.risk:.2f} >= {self.aggregator.hard_risk_threshold})"
            for r in reports
            if r.is_hard_risk(self.aggregator.hard_risk_threshold)
        ]
        hard_guards = rule_guards + threshold_guards

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

    async def _llm_synthesize(
        self,
        reports: list[AgentReport],
        observation: dict[str, Any],
        fallback: dict[str, Any],
    ) -> dict[str, Any]:
        """Use an LLM to synthesize the evidence board into a final decision."""
        if self.mock_mode:
            rendered = self._render_mock(self.mock_response or "", reports, fallback)
            return self._parse_llm_response(rendered, fallback)

        system_prompt = self.system_prompt or self._default_system_prompt()
        user_prompt = self._build_user_prompt(reports, observation, fallback)

        try:
            from forge_agent.llm.protocol import ChatMessage, chat

            messages = [
                ChatMessage.system(system_prompt),
                ChatMessage.user(user_prompt),
            ]
            response = await chat(
                messages,
                provider=self.llm_provider,
                model=self.llm_model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                agent_id=self.agent_id,
            )
            return self._parse_llm_response(response.content, fallback)
        except Exception as exc:
            log.warning("LLM synthesis failed for %s: %s", self.agent_id, exc)
            fallback["llm_error"] = str(exc)
            return fallback

    def _apply_guardrails(
        self, decision: dict[str, Any], reports: list[AgentReport]
    ) -> dict[str, Any]:
        """Apply hard-risk guardrails to the chief decision.

        Combines configured guard_rules with the global risk threshold. If any
        hard guard is triggered, downgrade an EXECUTE recommendation to
        EXECUTE_CAUTIOUS and add a warning.
        """
        rule_guards = self._evaluate_guard_rules(reports)
        threshold_guards = [
            f"{r.agent_id} triggered hard risk ({r.risk:.2f} >= {self.aggregator.hard_risk_threshold})"
            for r in reports
            if r.is_hard_risk(self.aggregator.hard_risk_threshold)
        ]
        existing = decision.get("hard_guards", [])
        hard_guards = list(set(existing + rule_guards + threshold_guards))
        decision["hard_guards"] = hard_guards

        if hard_guards and decision.get("recommended_action") in {
            Action.EXECUTE.value,
            "execute",
        }:
            decision["recommended_action"] = Action.EXECUTE_CAUTIOUS.value
            decision["warnings"] = list(decision.get("warnings", []))
            decision["warnings"].append(
                "Hard risk guards triggered; recommendation downgraded to cautious."
            )
        return decision

    def _evaluate_guard_rules(self, reports: list[AgentReport]) -> list[str]:
        """Evaluate configured guard rules against all peer reports.

        Each rule has the following shape::

            {
                "name": "rule_name",
                "description": "...",
                "condition": {
                    "agent_id": "sports.odds",  # str or list[str]
                    "verdicts": ["risk", "lean_negative"],  # list[str]
                    "min_risk": 0.8,
                    "max_confidence": 0.5,
                    "min_confidence": 0.0,
                },
                "message": "{agent_id} risk {risk:.2f} too high",
                "level": "error",
            }

        The ``message`` string supports ``{agent_id}``, ``{name}``, ``{risk}``,
        ``{confidence}``, and ``{verdict}`` substitutions.
        """
        guards: list[str] = []
        for rule in self.guard_rules:
            condition = rule.get("condition", {})
            for r in reports:
                if not self._rule_matches(condition, r):
                    continue
                template = rule.get(
                    "message",
                    "{agent_id} matched guard rule {name}",
                )
                guards.append(
                    template.format(
                        name=rule.get("name", "unnamed"),
                        agent_id=r.agent_id,
                        risk=r.risk,
                        confidence=r.confidence,
                        verdict=r.verdict.value,
                    )
                )
        return guards

    @staticmethod
    def _rule_matches(condition: dict[str, Any], report: AgentReport) -> bool:
        """Return True if a single report matches the rule condition."""
        agent_ids = condition.get("agent_id")
        if agent_ids is not None:
            if isinstance(agent_ids, str):
                agent_ids = [agent_ids]
            if report.agent_id not in agent_ids:
                return False

        verdicts = condition.get("verdicts")
        if verdicts is not None and report.verdict.value not in verdicts:
            return False

        min_risk = condition.get("min_risk")
        if min_risk is not None and report.risk < float(min_risk):
            return False

        max_risk = condition.get("max_risk")
        min_confidence = condition.get("min_confidence")
        max_confidence = condition.get("max_confidence")
        return not (
            (max_risk is not None and report.risk > float(max_risk))
            or (min_confidence is not None and report.confidence < float(min_confidence))
            or (max_confidence is not None and report.confidence > float(max_confidence))
        )

    def _build_user_prompt(
        self,
        reports: list[AgentReport],
        observation: dict[str, Any],
        fallback: dict[str, Any],
    ) -> str:
        """Build a Chinese/English prompt summarizing the evidence board."""
        board = observation.get("board", {})
        lines = [
            "你是一位足球赛事综合分析首席。请基于以下专家证据板输出最终决策。",
            "",
            "=== 专家报告 ===",
        ]
        for r in reports:
            lines.append(f"\n专家: {r.name} ({r.agent_id})")
            lines.append(f"  verdict: {r.verdict.value}")
            lines.append(f"  confidence: {r.confidence:.2f}")
            lines.append(f"  risk: {r.risk:.2f}")
            lines.append(f"  weight: {r.weight:.2f}")
            lines.append(f"  recommended_action: {r.recommended_action.value}")
            for ev in r.evidence:
                lines.append(f"  evidence: {ev}")
            for warn in getattr(r, "warnings", []):
                lines.append(f"  warning: {warn}")

        lines.extend(
            [
                "",
                "=== 证据板统计 ===",
                f"agents: {board.get('n_agents', len(reports))}",
                f"avg_confidence: {board.get('avg_confidence', fallback.get('confidence', 0.0)):.2f}",
                f"avg_risk: {board.get('avg_risk', fallback.get('risk', 0.0)):.2f}",
                f"weighted_verdict: {board.get('weighted_verdict', fallback.get('verdict', 'neutral'))}",
            ]
        )

        if fallback.get("hard_guards"):
            lines.extend(["", "=== 硬风险闸门 ==="])
            for g in fallback["hard_guards"]:
                lines.append(f"- {g}")

        lines.extend(
            [
                "",
                "=== 加权投票参考 ===",
                f"verdict: {fallback.get('verdict')}",
                f"confidence: {fallback.get('confidence', 0.0):.2f}",
                f"risk: {fallback.get('risk', 0.0):.2f}",
                f"recommended_action: {fallback.get('recommended_action', 'watch')}",
                "",
                "=== 输出要求 ===",
                "只输出 JSON，不要解释。JSON 格式:",
                json.dumps(
                    {
                        "verdict": "lean_positive|lean_neutral|lean_negative|risk|neutral",
                        "confidence": 0.0,
                        "risk": 0.0,
                        "recommended_action": "execute|execute_cautious|hold|watch|stop",
                        "summary": "中文最终结论",
                        "evidence": ["支持结论的关键证据1", "关键证据2"],
                        "warnings": ["需要警惕的点"],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            ]
        )
        return "\n".join(lines)

    @staticmethod
    def _default_system_prompt() -> str:
        return (
            "你是一位足球赛事综合分析首席。"
            "你只会基于专家证据板做推理，不会臆测外部数据。"
            "当存在硬风险闸门时，必须降低推荐档位，不能直接给出 execute。"
            "输出必须是合法 JSON。"
        )

    def _parse_llm_response(self, content: str, fallback: dict[str, Any]) -> dict[str, Any]:
        """Parse the LLM response as JSON and normalize to a decision dict."""
        text = content.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        if not text:
            return fallback

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            fallback["llm_parse_error"] = "Response is not valid JSON"
            fallback["llm_raw"] = content
            return fallback

        if not isinstance(parsed, dict):
            fallback["llm_parse_error"] = "Response is not a JSON object"
            fallback["llm_raw"] = content
            return fallback

        # Normalize fields.
        verdict = parsed.get("verdict", fallback.get("verdict", Verdict.NEUTRAL.value))
        recommended_action = parsed.get(
            "recommended_action", fallback.get("recommended_action", Action.WATCH.value)
        )
        try:
            verdict_enum = Verdict(verdict)
            verdict = verdict_enum.value
        except ValueError:
            verdict_enum = Verdict.NEUTRAL
            verdict = verdict_enum.value
        try:
            action_enum = Action(recommended_action)
            recommended_action = action_enum.value
        except ValueError:
            action_enum = Action.WATCH
            recommended_action = action_enum.value

        return {
            "strategy": "llm_synthesis",
            "verdict": verdict,
            "confidence": float(parsed.get("confidence", fallback.get("confidence", 0.5))),
            "risk": float(parsed.get("risk", fallback.get("risk", 0.0))),
            "recommended_action": recommended_action,
            "summary": parsed.get("summary", fallback.get("summary", "")),
            "evidence": parsed.get("evidence", fallback.get("evidence", [])),
            "warnings": parsed.get("warnings", fallback.get("hard_guards", [])),
            "hard_guards": fallback.get("hard_guards", []),
            "llm_raw": parsed,
        }

    @staticmethod
    def _render_mock(template: str, reports: list[AgentReport], fallback: dict[str, Any]) -> str:
        """Render a mock response template with minimal variable substitution."""

        def replacer(match: re.Match[str]) -> str:
            key = match.group(1)
            if key == "n_reports":
                return str(len(reports))
            if key == "verdict":
                return str(fallback.get("verdict", ""))
            if key == "confidence":
                return f"{fallback.get('confidence', 0.0):.2f}"
            if key == "risk":
                return f"{fallback.get('risk', 0.0):.2f}"
            if key == "recommended_action":
                return str(fallback.get("recommended_action", "watch"))
            return match.group(0)

        return re.sub(r"\{(\w+)\}", replacer, template)

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        """Return a synthesized report."""
        verdict = Verdict(decision.get("verdict", Verdict.NEUTRAL.value))
        recommended_action = Action(decision.get("recommended_action", Action.WATCH.value))
        evidence = [decision.get("summary", "chief agent synthesized")]
        evidence.extend(decision.get("evidence", []))
        evidence.extend(decision.get("hard_guards", []))
        warnings = list(decision.get("warnings", []))
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            domain=self.domain,
            verdict=verdict,
            confidence=float(decision.get("confidence", 0.5)),
            risk=float(decision.get("risk", 0.0)),
            weight=0.0,
            evidence=evidence,
            warnings=warnings,
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
