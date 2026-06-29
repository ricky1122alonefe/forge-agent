"""TeamRunner: execute a Mission by running its Team of agents.

The runner coordinates:
1. Building an AgentContext from the mission payload.
2. Scheduling member agents in parallel or sequential mode.
3. Aggregating their reports into an AgentBoard.
4. Optionally invoking a Chief agent to synthesize the board.
5. Persisting evidence and reports to ForgeStore.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.mission import Mission
from forge_agent.core.team import Team
from forge_agent.pipeline.aggregator import Aggregator
from forge_agent.registry.registry import get_registry
from forge_agent.scheduler.scheduler import Scheduler
from forge_agent.scheduler.strategies import ParallelStrategy, SequentialStrategy
from forge_agent.scheduler.tasks import ScheduleTask
from forge_agent.storage import ForgeStore

log = logging.getLogger(__name__)


class TeamRunner:
    """Executes a Mission by running its Team."""

    def __init__(
        self,
        *,
        store: ForgeStore | None = None,
        aggregator: Aggregator | None = None,
    ) -> None:
        self.store = store or ForgeStore()
        self.aggregator = aggregator or Aggregator()

    async def run(self, mission: Mission) -> AgentBoard:
        """Run the mission and return the final AgentBoard.

        Steps:
            1. Build the execution context.
            2. Run member agents in the configured mode.
            3. Aggregate reports into an AgentBoard.
            4. Optionally run the chief agent.
            5. Persist evidence and report to storage.
        """
        if not mission.enabled:
            log.warning("Mission %s is disabled, skipping", mission.mission_id)
            return self._empty_board(mission)

        ctx = self._build_context(mission)
        team = mission.team
        log.info(
            "Running mission %s with team %s (%d agents)",
            mission.mission_id,
            team.name,
            len(team.agent_ids),
        )

        reports = await self._run_agents(team, ctx)
        board = self.aggregator.aggregate(reports, ctx)

        if team.chief_id:
            chief_report = await self._run_chief(team.chief_id, board, ctx)
            if chief_report:
                board.summary["chief_report"] = chief_report.to_dict()

        self._store_results(mission, board, reports)
        return board

    def _build_context(self, mission: Mission) -> AgentContext:
        team = mission.team
        payload = {**team.payload, **mission.payload}
        if team.chief_config:
            payload["chief_config"] = team.chief_config
        return AgentContext(
            scope_id=mission.mission_id,
            scope_name=mission.name,
            domain=team.domain,
            payload=payload,
            metadata={
                **team.metadata,
                **mission.metadata,
                "team_id": team.team_id,
            },
        )

    async def _run_agents(self, team: Team, ctx: AgentContext) -> list[AgentReport]:
        if not team.agent_ids:
            return []

        strategy = ParallelStrategy() if team.mode == "parallel" else SequentialStrategy()
        scheduler = Scheduler(strategy=strategy)
        for agent_id in team.agent_ids:
            scheduler.add_task(
                ScheduleTask(
                    task_id=agent_id,
                    agent_id=agent_id,
                    context=ctx,
                )
            )

        results = await scheduler.run()
        reports: list[AgentReport] = []
        for result in results.values():
            if result.report is not None:
                reports.append(result.report)
            else:
                log.warning("Agent %s produced no report: %s", result.agent_id, result.error)
        return reports

    async def _run_chief(
        self,
        chief_id: str,
        board: AgentBoard,
        ctx: AgentContext,
    ) -> AgentReport | None:
        try:
            registry = get_registry()
            # Use the team-level chief config if available. Force a fresh instance
            # so that repeated pipeline runs with different configs do not reuse a
            # stale chief.
            chief_config = ctx.payload.get("chief_config", {})
            chief = await registry.get(chief_id, config=chief_config, force_new=True)
            chief_ctx = ctx.child()
            chief_ctx.payload["reports"] = [r.to_dict() for r in board.agents]
            chief_ctx.payload["board"] = board.to_dict()
            return await chief.run(chief_ctx)
        except Exception:
            log.exception("Chief agent %s failed", chief_id)
            return None

    def _store_results(
        self,
        mission: Mission,
        board: AgentBoard,
        reports: list[AgentReport],
    ) -> None:
        ts = board.generated_at or datetime.now(timezone.utc).isoformat()
        for report in reports:
            self.store.insert(
                agent_id=mission.mission_id,
                data=report.to_dict(),
                category="evidence",
                source=report.agent_id,
                timestamp=ts,
            )
        self.store.insert(
            agent_id=mission.mission_id,
            data=board.to_dict(),
            category="report",
            source="team_runner",
            timestamp=ts,
        )

    def _empty_board(self, mission: Mission) -> AgentBoard:
        ts = datetime.now(timezone.utc).isoformat()
        return AgentBoard(
            ok=True,
            scope_id=mission.mission_id,
            scope_name=mission.name,
            generated_at=ts,
            domain=mission.team.domain,
            agents=[],
            summary={"disabled": True},
        )
