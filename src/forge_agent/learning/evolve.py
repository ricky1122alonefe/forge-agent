"""Evolve runtime — extracted from BaseAgent (S6.3).

Performs a full evolution cycle: reflection → optimiser → evolve.
Keeps BaseAgent thin: the evolution orchestration lives here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from forge_agent.core.base import BaseAgent
    from forge_agent.core.context import AgentContext


async def run_evolution(agent: BaseAgent, ctx: AgentContext) -> dict[str, Any]:
    """Self-iteration hook — full evolution cycle.

    1. Run reflection on the last execution (from memory)
    2. Check if evolution is needed via PromptOptimizer
    3. If needed, evolve the prompt and register new version
    4. Return evolution result

    Override ``BaseAgent.evolve`` in subclasses for custom strategies.
    """
    from forge_agent.learning.optimizer import PromptOptimizer

    # Reconstruct last run from memory
    try:
        recent = await agent.memory.query(agent_id=agent.agent_id)
    except Exception:
        recent = []

    if not recent:
        return {"evolved": False, "reason": "no execution history to reflect on"}

    last_run = recent[-1] if recent else {}
    observation = last_run.get("observation", {})
    decision = last_run.get("decision", {})
    result = last_run.get("result", {})

    # Run reflection
    try:
        signal = await agent.reflector.reflect(
            agent_id=agent.agent_id,
            context=ctx.to_dict(),
            observation=observation,
            decision=decision,
            result=result,
        )
    except Exception as exc:
        agent.log("warning", f"evolve(): reflection failed: {exc}")
        return {"evolved": False, "reason": f"reflection failed: {exc}"}

    # Check if evolution is needed
    optimizer = PromptOptimizer(prompt_manager=agent.prompt_manager)
    if not optimizer.should_evolve(signal):
        return {
            "evolved": False,
            "reason": "reflection score above threshold",
            "score": signal.get("score"),
        }

    # Perform evolution
    try:
        evolve_result = await optimizer.evolve(agent.agent_id, signal)
        if evolve_result.get("evolved"):
            agent.log(
                "info",
                f"evolve(): {agent.agent_id} evolved "
                f"{evolve_result.get('old_version')} → {evolve_result.get('new_version')}",
            )
        return evolve_result
    except Exception as exc:
        agent.log("error", f"evolve(): evolution failed: {exc}")
        return {"evolved": False, "reason": f"evolution failed: {exc}"}
