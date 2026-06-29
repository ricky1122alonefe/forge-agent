"""Football Intel Agent — a domain-specific Agent built on top of forge-agent.

This is the **v2** version of `match_agents/experts.py:intel_agent`.
It demonstrates:

    1. Subclassing BaseAgent.
    2. Overriding observe / decide / act to match the original semantics.
    3. Using a pluggable prompt (so the same agent can be re-prompoted later
       without touching code — v0.2+ Generator scenario).
    4. Registering via @register_agent.

The original `intel_agent` from match_agents/experts.py produces an
AgentReport with `verdict`, `confidence`, `risk`, `evidence`, etc.
We keep that contract 1:1.
"""

from __future__ import annotations

import json
from typing import Any

from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.registry.decorators import register_agent

# v1 prompt: matches the original "intel agent" semantics.
INTEL_PROMPT_V1 = """你是足球比赛情报分析 Agent。

比赛: {match_name}
赛事: {competition}
开赛: {kickoff}
主队: {home_team}
客队: {away_team}

可用的数据信号:
{signals}

请基于上述信息，输出 JSON:
{{
  "verdict": "lean_home" | "lean_draw" | "lean_away" | "skip" | "risk" | "neutral",
  "confidence": 0.0-1.0,
  "risk": 0.0-1.0,
  "evidence": ["证据1", "证据2", ...],
  "warnings": ["风险1", ...],
  "recommended_action": "buy" | "single_only" | "skip" | "watch"
}}
只输出 JSON，不要解释。
"""


@register_agent(domain="football", tags=["intel", "evidence"])
class FootballIntelAgent(BaseAgent):
    """v2 version of the original `intel_agent` from match_agents/experts.py."""

    agent_id = "football.intel"
    name = "Football Intel Agent"
    domain = "football"
    version = "2.0.0"

    async def _on_init(self) -> None:
        # Register default prompt; the Generator can add v2/v3 later.
        self.prompt_manager.register(self.agent_id, version="v1", template=INTEL_PROMPT_V1)

    # ---------------------------------------------------------------- observe
    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        """Pull signals from ctx.payload (set by the polling layer).

        In the original `intel_agent`, this called `enrich_match_factors()`.
        Here we expect the polling layer to have already enriched the payload,
        keeping this Agent **purely** about analysis (separation of concerns).
        """
        payload = ctx.payload or {}
        signals = {
            "odds_snapshot": payload.get("odds_snapshot", {}),
            "news": payload.get("news", {}),
            "form": payload.get("form", {}),
            "h2h": payload.get("h2h", {}),
        }
        return {
            "match_name": ctx.scope_name or payload.get("match", ""),
            "competition": payload.get("competition", ""),
            "kickoff": payload.get("kickoff", ""),
            "home_team": payload.get("home_team", ""),
            "away_team": payload.get("away_team", ""),
            "signals": signals,
        }

    # ----------------------------------------------------------------- decide
    async def decide(
        self,
        ctx: AgentContext,
        observation: dict[str, Any],
    ) -> dict[str, Any]:
        """Render the prompt. In production, this is where you'd call an LLM.

        For now we **do not** call an LLM (kept offline / testable).
        The Generator (v0.2+) can inject the LLM call automatically.
        """
        prompt = self.prompt_manager.render(
            self.agent_id,
            variables={
                "match_name": observation.get("match_name", ""),
                "competition": observation.get("competition", ""),
                "kickoff": observation.get("kickoff", ""),
                "home_team": observation.get("home_team", ""),
                "away_team": observation.get("away_team", ""),
                "signals": json.dumps(observation.get("signals", {}), ensure_ascii=False, indent=2),
            },
        )
        return {"prompt": prompt, "model": self.config.get("model", "deepseek-chat")}

    # -------------------------------------------------------------------- act
    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        """Heuristic fallback when no LLM is wired.

        Returns a neutral report so the pipeline stays runnable.
        Once an LLM client is wired (in decide()), the parsed JSON should
        fill in verdict / confidence / risk / evidence.
        """
        self.log("info", f"intel agent acting on {ctx.scope_id} (no LLM configured)")

        # Heuristic placeholder: if odds_snapshot has a strong favorite, lean that way.
        signals = (ctx.payload or {}).get("signals") or {}
        odds = signals.get("odds_snapshot") or {}
        verdict = Verdict.NEUTRAL
        confidence = 0.3
        risk = 0.2
        action = Action.WATCH
        evidence: list[str] = ["(heuristic) no LLM configured; using odds hint"]
        warnings: list[str] = []

        try:
            home = float(odds.get("home") or 0)
            draw = float(odds.get("draw") or 0)
            away = float(odds.get("away") or 0)
            if home and draw and away:
                min_odd = min(home, draw, away)
                if min_odd == home and home < 1.6:
                    verdict = Verdict.LEAN_POSITIVE  # mapped: lean_home
                    confidence = 0.6
                    action = Action.EXECUTE_CAUTIOUS
                    evidence.append(f"home odds={home} < 1.6 → lean home")
                elif min_odd == away and away < 1.6:
                    verdict = Verdict.LEAN_NEGATIVE  # mapped: lean_away
                    confidence = 0.6
                    action = Action.EXECUTE_CAUTIOUS
                    evidence.append(f"away odds={away} < 1.6 → lean away")
        except (TypeError, ValueError):
            warnings.append("could not parse odds_snapshot")

        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            domain=self.domain,
            verdict=verdict,
            confidence=confidence,
            risk=risk,
            weight=1.2,
            evidence=evidence,
            warnings=warnings,
            recommended_action=action,
            raw={"decision": decision, "scope_id": ctx.scope_id},
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
            version=self.version,
        )
