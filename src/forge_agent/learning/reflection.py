"""Reflection engine — turn an execution into learning signals.

Two reference implementations:
    - HeuristicReflector: rule-based, no LLM (good for tests & CI).
    - LLMReflector:       LLM-driven (you bring the client).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

log = logging.getLogger(__name__)


@dataclass
class ReflectionSignal:
    """Output of a reflection pass — what the agent learns from a run."""

    agent_id: str
    score: float               # 0.0 (terrible) ~ 1.0 (great)
    notes: list[str]
    needs_evolve: bool = False
    suggested_prompt_diff: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "score": self.score,
            "notes": self.notes,
            "needs_evolve": self.needs_evolve,
            "suggested_prompt_diff": self.suggested_prompt_diff,
        }


class HeuristicReflector:
    """Simple rule-based reflector. Useful as a default or in tests."""

    async def reflect(
        self,
        agent_id: str,
        context: dict[str, Any],
        observation: dict[str, Any],
        decision: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        score = 0.5
        notes: list[str] = []
        if float(result.get("risk", 0)) >= 0.7:
            score -= 0.3
            notes.append("high risk observed")
        if float(result.get("confidence", 0)) >= 0.7 and float(result.get("risk", 0)) < 0.4:
            score += 0.2
            notes.append("high confidence + low risk")
        if result.get("warnings"):
            score -= 0.05 * len(result["warnings"])
            notes.append(f"{len(result['warnings'])} warning(s)")

        signal = ReflectionSignal(
            agent_id=agent_id,
            score=max(0.0, min(1.0, score)),
            notes=notes or ["(no signal)"],
            needs_evolve=score < 0.3,
        )
        return signal.to_dict()


class LLMReflector:
    """LLM-driven reflector. You provide the async chat function.

    Example::
        async def my_chat(messages): return "..."
        reflector = LLMReflector(chat=my_chat, model="gpt-4o")
    """

    def __init__(
        self,
        *,
        chat: Callable[[list[dict[str, str]]], Awaitable[str]],
        model: str = "gpt-4o",
    ) -> None:
        self.chat = chat
        self.model = model

    async def reflect(
        self,
        agent_id: str,
        context: dict[str, Any],
        observation: dict[str, Any],
        decision: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        import json
        messages = [
            {"role": "system", "content": "You are a reflection engine. Output JSON only."},
            {
                "role": "user",
                "content": (
                    f"Reflect on this Agent run and produce JSON with keys: "
                    f"score (0-1), notes (list), needs_evolve (bool).\n\n"
                    f"Context: {json.dumps(context, ensure_ascii=False)}\n"
                    f"Observation: {json.dumps(observation, ensure_ascii=False)}\n"
                    f"Decision: {json.dumps(decision, ensure_ascii=False)}\n"
                    f"Result: {json.dumps(result, ensure_ascii=False)}"
                ),
            },
        ]
        raw = await self.chat(messages)
        try:
            data = json.loads(raw)
            return {
                "agent_id": agent_id,
                "score": float(data.get("score", 0.5)),
                "notes": list(data.get("notes", [])),
                "needs_evolve": bool(data.get("needs_evolve", False)),
            }
        except (json.JSONDecodeError, ValueError, TypeError):
            log.exception("LLM reflector returned non-JSON; falling back to neutral signal")
            return {"agent_id": agent_id, "score": 0.5, "notes": ["(parse failed)"], "needs_evolve": False}
