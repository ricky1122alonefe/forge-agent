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
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentBoard, AgentReport
from forge_agent.core.enums import (
    Action,
    AgentStatus,
    Verdict,
)
from forge_agent.exceptions import (
    AgentNotFoundError,
    DuplicateRegistrationError,
    ForgeError,
    InvalidAgentTypeError,
    MCPNotConnectedError,
    MCPToolCallError,
    MissingDependencyError,
    PipelineNodeNotFoundError,
    ProjectAlreadyExistsError,
    ProjectNotFoundError,
    PromptNotFoundError,
    PromptVariableError,
    ProviderNotConfiguredError,
    ToolDeniedError,
    ToolNotRegisteredError,
    VersionError,
    VersionNotFoundError,
)
from forge_agent.pipeline.engine import PipelineEngine
from forge_agent.pipeline.pipeline import Pipeline, PipelineNode
from forge_agent.registry.decorators import register_agent
from forge_agent.registry.registry import AgentRegistry, get_registry
from forge_agent.scheduler.scheduler import Scheduler, ScheduleResult, ScheduleTask

__all__ = [
    "Action",
    "AgentBoard",
    "AgentContext",
    "AgentNotFoundError",
    # Registry
    "AgentRegistry",
    "AgentReport",
    "AgentStatus",
    # Core abstractions
    "BaseAgent",
    "DuplicateRegistrationError",
    # Exceptions
    "ForgeError",
    "InvalidAgentTypeError",
    "MCPNotConnectedError",
    "MCPToolCallError",
    "MissingDependencyError",
    # Pipeline
    "Pipeline",
    "PipelineEngine",
    "PipelineNode",
    "PipelineNodeNotFoundError",
    "ProjectAlreadyExistsError",
    "ProjectNotFoundError",
    "PromptNotFoundError",
    "PromptVariableError",
    "ProviderNotConfiguredError",
    "ScheduleResult",
    "ScheduleTask",
    # Scheduler
    "Scheduler",
    "ToolDeniedError",
    "ToolNotRegisteredError",
    "Verdict",
    "VersionError",
    "VersionNotFoundError",
    # Version
    "__version__",
    "get_registry",
    "register_agent",
]
