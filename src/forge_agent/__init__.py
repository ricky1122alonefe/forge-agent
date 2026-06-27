"""forge-agent: A universal, contract-driven Agent factory & orchestration engine.

Public API surface (deliberately small, follows LangChain / Pydantic convention):

    Base Agent
    ----------
        BaseAgent           # Abstract base for ALL agents
        AgentContext        # Runtime context passed to agents
        AgentReport         # Standardized output contract
        AgentBoard          # Aggregated multi-agent report

    Capabilities (plug-in strategies)
    ---------------------------------
        LoggerProtocol
        SearcherProtocol
        MemoryProtocol
        ReflectionProtocol
        PromptManagerProtocol

    Infrastructure
    --------------
        AgentRegistry       # Singleton registry (lifecycle)
        register_agent      # Decorator to register
        Scheduler           # Task scheduler
        Pipeline            # DAG-style orchestration
        get_registry        # Convenience accessor

The design philosophy: **"Base never changes. Capabilities are pluggable.
Business is generated on demand."**
"""

from __future__ import annotations

from forge_agent.__version__ import __version__
from forge_agent.core.base import BaseAgent
from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.context import AgentContext
from forge_agent.core.enums import (
    Action,
    AgentStatus,
    Verdict,
)
from forge_agent.registry.decorators import register_agent
from forge_agent.registry.registry import AgentRegistry, get_registry
from forge_agent.scheduler.scheduler import Scheduler, ScheduleResult, ScheduleTask
from forge_agent.pipeline.pipeline import Pipeline, PipelineNode
from forge_agent.pipeline.engine import PipelineEngine

__all__ = [
    # Version
    "__version__",
    # Core abstractions
    "BaseAgent",
    "AgentContext",
    "AgentReport",
    "AgentBoard",
    "Action",
    "AgentStatus",
    "Verdict",
    # Registry
    "AgentRegistry",
    "get_registry",
    "register_agent",
    # Scheduler
    "Scheduler",
    "ScheduleResult",
    "ScheduleTask",
    # Pipeline
    "Pipeline",
    "PipelineNode",
    "PipelineEngine",
]
