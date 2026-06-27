"""Prompt optimizer — version & swap prompts based on reflection signals.

This is the **seed** of the self-iteration loop. v0.4 will wire it into a
background scheduler that triggers evolve() on agents whose reflection
score drops below threshold.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from forge_agent.core.capabilities import PromptManagerProtocol

log = logging.getLogger(__name__)


@dataclass
class EvolutionRecord:
    """Record of a single prompt evolution event."""

    agent_id: str
    old_version: str
    new_version: str
    reason: str
    score_before: float
    score_after: float | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "reason": self.reason,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "notes": self.notes,
        }


class PromptOptimizer:
    """Decide when a prompt needs a new version based on reflection signals.

    Features:
        - ``should_evolve()``: decide based on score / needs_evolve flag
        - ``bump_version()``: register a new prompt version
        - ``evolve()``: full evolution cycle (analyze → improve → register)
        - ``get_history()``: view evolution history for an agent
        - ``analyze_trend()``: analyze score trend from recent reflections
    """

    def __init__(
        self,
        *,
        prompt_manager: PromptManagerProtocol,
        evolve_threshold: float = 0.3,
        llm_chat: Callable[[list[dict[str, str]]], Awaitable[str]] | None = None,
        max_history: int = 50,
    ) -> None:
        self.prompt_manager = prompt_manager
        self.evolve_threshold = evolve_threshold
        self.llm_chat = llm_chat
        self._history: dict[str, list[EvolutionRecord]] = {}
        self._reflection_history: dict[str, list[dict[str, Any]]] = {}
        self._max_history = max_history

    def should_evolve(self, signal: dict[str, Any]) -> bool:
        """Decide whether the agent should evolve its prompt.

        Returns True if:
            - signal has ``needs_evolve=True``, OR
            - signal score is below ``evolve_threshold``, OR
            - score trend is consistently declining
        """
        if bool(signal.get("needs_evolve", False)):
            return True
        score = float(signal.get("score", 1.0))
        if score < self.evolve_threshold:
            return True
        # Check trend if we have enough history
        agent_id = signal.get("agent_id", "")
        if agent_id:
            trend = self.analyze_trend(agent_id)
            if trend.get("declining", False) and score < 0.5:
                return True
        return False

    def bump_version(
        self,
        agent_id: str,
        new_template: str,
        *,
        version: str | None = None,
    ) -> str:
        """Register a new prompt version; auto-increment if version is None."""
        if version is None:
            existing = self.prompt_manager.list_versions(agent_id)
            next_v = f"v{len(existing) + 1}"
            version = next_v
        self.prompt_manager.register(agent_id, version, new_template)
        log.info("PromptOptimizer: bumped %s → %s", agent_id, version)
        return version

    def record_reflection(self, signal: dict[str, Any]) -> None:
        """Record a reflection signal for trend analysis."""
        agent_id = signal.get("agent_id", "unknown")
        if agent_id not in self._reflection_history:
            self._reflection_history[agent_id] = []
        self._reflection_history[agent_id].append(signal)
        # Keep only recent history
        if len(self._reflection_history[agent_id]) > self._max_history:
            self._reflection_history[agent_id] = self._reflection_history[agent_id][-self._max_history:]

    def analyze_trend(self, agent_id: str) -> dict[str, Any]:
        """Analyze score trend from recent reflections.

        Returns a dict with:
            - ``trend``: "improving" | "declining" | "stable"
            - ``avg_score``: average score over recent reflections
            - ``declining``: bool, True if consistently declining
            - ``count``: number of reflections analyzed
        """
        history = self._reflection_history.get(agent_id, [])
        if len(history) < 2:
            return {"trend": "stable", "avg_score": 1.0, "declining": False, "count": len(history)}

        scores = [float(s.get("score", 0.5)) for s in history[-10:]]  # last 10
        avg = sum(scores) / len(scores)

        # Simple trend: compare first half vs second half
        mid = len(scores) // 2
        first_half = sum(scores[:mid]) / max(mid, 1)
        second_half = sum(scores[mid:]) / max(len(scores) - mid, 1)

        diff = second_half - first_half
        if diff > 0.05:
            trend = "improving"
        elif diff < -0.02:
            trend = "declining"
        else:
            trend = "stable"

        # Declining = last 3+ scores are all below threshold and trending down
        declining = (
            trend == "declining"
            and len(scores) >= 3
            and all(s < self.evolve_threshold for s in scores[-3:])
        )

        return {
            "trend": trend,
            "avg_score": round(avg, 3),
            "declining": declining,
            "count": len(scores),
        }

    async def evolve(
        self,
        agent_id: str,
        signal: dict[str, Any],
    ) -> dict[str, Any]:
        """Full evolution cycle: analyze → improve → register new version.

        If ``llm_chat`` is configured, uses LLM to improve the prompt.
        Otherwise, applies simple heuristic improvements based on the signal.

        Returns:
            Dict with ``evolved``, ``old_version``, ``new_version``, ``reason``.
        """
        # Record the reflection
        self.record_reflection(signal)

        # Get current prompt
        try:
            current_template = self.prompt_manager.get(agent_id)
        except KeyError:
            return {"evolved": False, "reason": f"no prompt registered for {agent_id}"}

        current_versions = self.prompt_manager.list_versions(agent_id)
        old_version = current_versions[-1] if current_versions else "v0"

        # Generate improved prompt
        improved = await self._improve_prompt(agent_id, current_template, signal)

        if improved == current_template:
            return {"evolved": False, "reason": "no improvement suggested"}

        # Register new version
        new_version = self.bump_version(agent_id, improved)

        # Record evolution
        record = EvolutionRecord(
            agent_id=agent_id,
            old_version=old_version,
            new_version=new_version,
            reason=signal.get("notes", ["score below threshold"])[0] if signal.get("notes") else "score below threshold",
            score_before=float(signal.get("score", 0.0)),
            notes=signal.get("notes", []),
        )
        self._history.setdefault(agent_id, []).append(record)

        return {
            "evolved": True,
            "old_version": old_version,
            "new_version": new_version,
            "reason": record.reason,
        }

    async def _improve_prompt(
        self,
        agent_id: str,
        current_template: str,
        signal: dict[str, Any],
    ) -> str:
        """Generate an improved version of the prompt."""
        if self.llm_chat:
            return await self._llm_improve(agent_id, current_template, signal)
        return self._heuristic_improve(current_template, signal)

    async def _llm_improve(
        self,
        agent_id: str,
        current_template: str,
        signal: dict[str, Any],
    ) -> str:
        """Use LLM to improve the prompt based on reflection signal."""
        import json

        notes = signal.get("notes", [])
        suggested_diff = signal.get("suggested_prompt_diff")
        score = signal.get("score", 0.0)

        messages = [
            {"role": "system", "content": (
                "You are a prompt engineer. Given a current prompt template and "
                "reflection feedback, output an improved prompt template. "
                "Output ONLY the improved template text, nothing else."
            )},
            {"role": "user", "content": (
                f"Agent: {agent_id}\n"
                f"Current score: {score}\n"
                f"Feedback notes: {json.dumps(notes, ensure_ascii=False)}\n"
                f"Suggested changes: {json.dumps(suggested_diff, ensure_ascii=False) if suggested_diff else 'none'}\n\n"
                f"Current prompt template:\n{current_template}\n\n"
                f"Output the improved template:"
            )},
        ]

        try:
            improved = await self.llm_chat(messages)  # type: ignore[misc]
            improved = improved.strip()
            if improved and improved != current_template:
                return improved
        except Exception:  # noqa: BLE001
            log.exception("LLM-based prompt improvement failed; falling back to heuristic")

        return self._heuristic_improve(current_template, signal)

    @staticmethod
    def _heuristic_improve(template: str, signal: dict[str, Any]) -> str:
        """Apply simple heuristic improvements based on reflection signal."""
        notes = signal.get("notes", [])
        suggested_diff = signal.get("suggested_prompt_diff")

        improved = template

        # If there's a suggested diff, try to apply it
        if suggested_diff and isinstance(suggested_diff, dict):
            additions = suggested_diff.get("add", "")
            if additions:
                improved = improved.rstrip() + "\n\n# Improvement based on reflection:\n" + additions

        # Add reflection notes as guidance
        if notes:
            guidance = "; ".join(str(n) for n in notes[:3])
            improved = improved.rstrip() + f"\n\n# Areas to improve: {guidance}"

        return improved

    def get_history(self, agent_id: str) -> list[dict[str, Any]]:
        """Get evolution history for an agent."""
        records = self._history.get(agent_id, [])
        return [r.to_dict() for r in records]
