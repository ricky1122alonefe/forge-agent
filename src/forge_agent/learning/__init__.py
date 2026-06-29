"""Self-learning / self-iteration primitives (v0.4+ core)."""

from __future__ import annotations

from forge_agent.learning.memory import InMemoryLongTermStore, LongTermStoreProtocol
from forge_agent.learning.optimizer import EvolutionRecord, PromptOptimizer
from forge_agent.learning.post_match import (
    MatchOutcome,
    PostMatchFeedback,
    PostMatchReflector,
)
from forge_agent.learning.reflection import (
    HeuristicReflector,
    LLMReflector,
    ReflectionSignal,
)

__all__ = [
    "EvolutionRecord",
    "HeuristicReflector",
    "InMemoryLongTermStore",
    "LLMReflector",
    "LongTermStoreProtocol",
    "MatchOutcome",
    "PostMatchFeedback",
    "PostMatchReflector",
    "PromptOptimizer",
    "ReflectionSignal",
]
