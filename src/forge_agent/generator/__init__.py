"""forge_agent.generator — natural-language to Agent code generation.

**Public API (v0.2):**

    Requirements
    ------------
        AgentRequirements        # structured spec
        FieldSpec
        RequirementsParser       # NL → AgentRequirements

    Generation
    ----------
        CodeGenerator            # LLM-driven code generation with retry
        GenerationContext
        GenerationResult

    Validation & Sandbox
    ---------------------
        ContractValidator        # AST-level BaseAgent contract check
        ValidationResult
        Sandbox                  # light-weight execution sandbox
        SmokeTestResult
        ResourceLimits

    Storage
    -------
        CodeStore                # Protocol
        FileCodeStore            # Filesystem implementation
        SavedCode
        Manifest                 # project-level agent registry
        AgentManifestEntry
        AgentVersionMeta

    Injection
    ---------
        AgentInjector            # validate + exec + register

    Pipeline
    --------
        GenerationPipeline       # high-level orchestrator
        GenerationOutcome
        DeployMode               # MANUAL_REVIEW / AUTO_DEPLOY / SANDBOX_ONLY
"""

from __future__ import annotations

from forge_agent.generator.generator import (
    CodeGenerator,
    GenerationContext,
    GenerationResult,
)
from forge_agent.generator.injector import AgentInjector
from forge_agent.generator.manifest import (
    AgentManifestEntry,
    AgentVersionMeta,
    Manifest,
)
from forge_agent.generator.pipeline import (
    DeployMode,
    GenerationOutcome,
    GenerationPipeline,
)
from forge_agent.generator.requirements import (
    AgentRequirements,
    FieldSpec,
    RequirementsParser,
)
from forge_agent.generator.sandbox import (
    ResourceLimits,
    Sandbox,
    SmokeTestResult,
)
from forge_agent.generator.store import FileCodeStore, SavedCode
from forge_agent.generator.validator import ContractValidator, ValidationResult

__all__ = [
    # Injector
    "AgentInjector",
    "AgentManifestEntry",
    # Requirements
    "AgentRequirements",
    "AgentVersionMeta",
    # Generation
    "CodeGenerator",
    # Validation
    "ContractValidator",
    "DeployMode",
    "FieldSpec",
    # Storage
    "FileCodeStore",
    "GenerationContext",
    "GenerationOutcome",
    # Pipeline
    "GenerationPipeline",
    "GenerationResult",
    "Manifest",
    "RequirementsParser",
    "ResourceLimits",
    # Sandbox
    "Sandbox",
    "SavedCode",
    "SmokeTestResult",
    "ValidationResult",
]
