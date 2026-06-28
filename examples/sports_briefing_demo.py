"""Sports data briefing demo: Team/Mission/Chief end-to-end example.

This demo shows how to assemble a team of domain agents that produce
a compliance-safe "data briefing" for a football match.  It does NOT
output betting recommendations or odds predictions.

Run with:

    cd /path/to/forge-agent
    python -m examples.sports_briefing_demo

"""

from __future__ import annotations

import asyncio
import json
import random
from typing import Any

from forge_agent.builtin.chief_agent import ChiefAgent
from forge_agent.core import Mission, Team
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.core.runner import TeamRunner
from forge_agent.registry.decorators import register_agent

# ---------------------------------------------------------------------------
# Mock data helpers (replace with real data sources in production)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Mock data helpers (replace with real data sources in production)
# ---------------------------------------------------------------------------


def _mock_news(home: str, away: str) -> list[str]:
    return [
        f"{home} 近期训练状态良好，主力阵容齐整。",
        f"{away} 上一场比赛客场取胜，士气正佳。",
        "两队历史交锋火药味较浓，本场关注度较高。",
    ]


def _mock_weather(city: str, _date: str) -> dict[str, Any]:
    conditions = ["晴", "多云", "小雨", "阴"]
    condition = random.choice(conditions)
    temp = random.randint(22, 34)
    wind = random.randint(1, 5)
    return {
        "city": city,
        "condition": condition,
        "temperature_c": temp,
        "wind_level": wind,
    }


def _mock_history(home: str, away: str) -> dict[str, Any]:
    return {
        "total_matches": 10,
        "home_wins": 4,
        "away_wins": 3,
        "draws": 3,
        "recent_trend": f"{home} 近 3 次主场对 {away} 保持不败。",
    }


# ---------------------------------------------------------------------------
# Domain agents
# ---------------------------------------------------------------------------


@register_agent(domain="sports", tags=["news", "briefing"])
class NewsAgent(BaseAgent):
    agent_id = "sports.news"
    name = "赛事情报专家"
    domain = "sports"

    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        home = ctx.payload.get("home", "主队")
        away = ctx.payload.get("away", "客队")
        return {
            "home": home,
            "away": away,
            "headlines": _mock_news(home, away),
        }

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        headlines = observation.get("headlines", [])
        sentiment = "neutral"
        if any("取胜" in h or "状态良好" in h for h in headlines):
            sentiment = "positive"
        if any("停赛" in h or "伤病" in h for h in headlines):
            sentiment = "negative"
        return {
            "sentiment": sentiment,
            "headlines": headlines,
            "key_point": headlines[0] if headlines else "暂无关键情报",
        }

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        sentiment = decision.get("sentiment", "neutral")
        verdict_map = {
            "positive": Verdict.LEAN_POSITIVE,
            "negative": Verdict.LEAN_NEGATIVE,
            "neutral": Verdict.NEUTRAL,
        }
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            domain=self.domain,
            verdict=verdict_map.get(sentiment, Verdict.NEUTRAL),
            confidence=0.7,
            risk=0.2,
            weight=1.0,
            evidence=[decision.get("key_point", ""), *decision.get("headlines", [])[1:]],
            recommended_action=Action.WATCH,
            raw=decision,
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
            version=self.version,
        )


@register_agent(domain="sports", tags=["weather", "briefing"])
class WeatherAgent(BaseAgent):
    agent_id = "sports.weather"
    name = "比赛天气专家"
    domain = "sports"

    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        city = ctx.payload.get("city", ctx.payload.get("home", "比赛城市"))
        date = ctx.payload.get("date", "近期")
        return _mock_weather(city, date)

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        condition = observation.get("condition", "晴")
        temp = observation.get("temperature_c", 25)
        wind = observation.get("wind_level", 1)

        impact = "轻微"
        if condition in {"小雨", "中雨"}:
            impact = "较大"
        elif wind >= 4 or temp >= 32:
            impact = "中等"

        return {
            **observation,
            "impact": impact,
            "summary": f"{observation.get('city')} 天气{condition}，{temp}℃，风力{wind}级，对比赛影响{impact}。",
        }

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        impact = decision.get("impact", "轻微")
        verdict = Verdict.NEUTRAL
        risk = 0.2
        if impact == "较大":
            verdict = Verdict.RISK
            risk = 0.6
        elif impact == "中等":
            verdict = Verdict.LEAN_NEGATIVE
            risk = 0.4
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            domain=self.domain,
            verdict=verdict,
            confidence=0.75,
            risk=risk,
            weight=0.8,
            evidence=[decision.get("summary", "")],
            recommended_action=Action.WATCH,
            raw=decision,
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
            version=self.version,
        )


@register_agent(domain="sports", tags=["history", "briefing"])
class HistoryAgent(BaseAgent):
    agent_id = "sports.history"
    name = "历史交锋专家"
    domain = "sports"

    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        home = ctx.payload.get("home", "主队")
        away = ctx.payload.get("away", "客队")
        return _mock_history(home, away)

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        home_wins = observation.get("home_wins", 0)
        total = observation.get("total_matches", 1)
        home_rate = home_wins / total if total else 0.0
        trend = observation.get("recent_trend", "")
        return {
            **observation,
            "home_win_rate": round(home_rate, 2),
            "summary": trend,
        }

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        home_rate = decision.get("home_win_rate", 0.5)
        if home_rate > 0.55:
            verdict = Verdict.LEAN_POSITIVE
        elif home_rate < 0.45:
            verdict = Verdict.LEAN_NEGATIVE
        else:
            verdict = Verdict.NEUTRAL
        home = ctx.payload.get("home", "主队")
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            domain=self.domain,
            verdict=verdict,
            confidence=0.65,
            risk=0.25,
            weight=1.2,
            evidence=[
                f"历史交锋 {decision.get('total_matches')} 场，{home} 胜 {decision.get('home_wins')} 场",
                decision.get("summary", ""),
            ],
            recommended_action=Action.WATCH,
            raw=decision,
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
            version=self.version,
        )


# ---------------------------------------------------------------------------
# Domain-specific Chief
# ---------------------------------------------------------------------------


@register_agent(domain="sports", tags=["chief", "briefing"])
class SportsChiefAgent(ChiefAgent):
    agent_id = "sports.chief"
    name = "赛事数据简报主理人"
    domain = "sports"

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        reports_raw = observation.get("reports", [])
        if not reports_raw:
            return {
                "strategy": "no_reports",
                "verdict": Verdict.NEUTRAL.value,
                "confidence": 0.0,
                "risk": 0.0,
                "summary": "无可用专家报告，无法生成简报。",
                "key_factors": [],
                "risk_hints": [],
                "data_sources": [],
            }

        reports = [self._report_from_dict(r) for r in reports_raw]

        # Aggregate evidence per source.
        key_factors: list[str] = []
        risk_hints: list[str] = []
        data_sources: list[str] = []
        for r in reports:
            source = f"{r.name} ({r.agent_id})"
            data_sources.append(source)
            for ev in r.evidence:
                key_factors.append(f"[{r.name}] {ev}")
            if r.risk >= 0.5:
                risk_hints.append(f"{r.name} 提示风险 ({r.risk:.0%})")

        avg_confidence = sum(r.confidence for r in reports) / len(reports)
        avg_risk = sum(r.risk for r in reports) / len(reports)
        verdict_value = self._weighted_verdict(reports)

        summary = (
            f"综合 {len(reports)} 位专家报告，"
            f"平均置信度 {avg_confidence:.0%}，平均风险 {avg_risk:.0%}。"
        )
        if risk_hints:
            summary += " 存在需要关注的风险因素。"
        else:
            summary += " 当前未触发显著风险。"

        return {
            "strategy": "sports_briefing",
            "verdict": verdict_value,
            "confidence": round(avg_confidence, 3),
            "risk": round(avg_risk, 3),
            "recommended_action": Action.WATCH.value,
            "summary": summary,
            "key_factors": key_factors,
            "risk_hints": risk_hints,
            "data_sources": data_sources,
        }

    @staticmethod
    def _weighted_verdict(reports: list[AgentReport]) -> str:
        if not reports:
            return Verdict.NEUTRAL.value
        score: dict[str, float] = {}
        for r in reports:
            score.setdefault(r.verdict.value, 0.0)
            score[r.verdict.value] += r.weight * r.confidence
        return max(score.items(), key=lambda kv: kv[1])[0]


# ---------------------------------------------------------------------------
# Demo entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    team = Team(
        team_id="sports_briefing",
        name="赛事数据简报小组",
        domain="sports",
        agent_ids=[
            "sports.news",
            "sports.weather",
            "sports.history",
        ],
        chief_id="sports.chief",
        mode="parallel",
    )

    mission = Mission(
        mission_id="match_briefing_demo",
        name="阿森纳 vs 利物浦 数据简报",
        description="生成一场比赛的合规数据简报，仅包含情报、天气、历史交锋信息。",
        team=team,
        payload={
            "home": "阿森纳",
            "away": "利物浦",
            "city": "伦敦",
            "date": "2026-07-01",
        },
    )

    board = await TeamRunner().run(mission)

    print("=" * 60)
    print("Mission:", mission.name)
    print("=" * 60)
    print("\n--- Member Reports ---")
    for report in board.agents:
        print(
            f"\n[{report.name}] verdict={report.verdict.value} "
            f"confidence={report.confidence:.0%} risk={report.risk:.0%}"
        )
        for ev in report.evidence:
            print(f"  - {ev}")

    print("\n--- Chief Briefing ---")
    chief_report = board.summary.get("chief_report")
    if chief_report:
        decision = chief_report.get("raw", {}).get("decision", {})
        print(f"summary: {decision.get('summary')}")
        print(f"verdict: {chief_report.get('verdict')}")
        print(f"confidence: {chief_report.get('confidence')}")
        print(f"risk: {chief_report.get('risk')}")
        print("\nkey_factors:")
        for factor in decision.get("key_factors", []):
            print(f"  - {factor}")
        print("\nrisk_hints:")
        for hint in decision.get("risk_hints", []):
            print(f"  - {hint}")
    else:
        print("No chief report produced.")

    print("\n--- Full Board JSON ---")
    print(json.dumps(board.to_dict(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
