"""Self-learning / self-iteration primitives (v0.4+ core)."""

from __future__ import annotations

from forge_agent.learning.reflection import (
    HeuristicReflector,
    LLMReflector,
    ReflectionSignal,
)
from forge_agent.learning.memory import InMemoryLongTermStore, LongTermStoreProtocol
from forge_agent.learning.optimizer import EvolutionRecord, PromptOptimizer

__all__ = [
    "EvolutionRecord",
    "HeuristicReflector",
    "LLMReflector",
    "ReflectionSignal",
    "InMemoryLongTermStore",
    "LongTermStoreProtocol",
    "PromptOptimizer",
]
