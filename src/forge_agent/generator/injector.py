"""Agent Injector — register a (validated) class into the running process.

v0.2+ will:
    1. Generate source via LLM.
    2. Validate via ContractValidator.
    3. Inject via AgentInjector (this file).
    4. Smoke-test via Sandbox (v0.2b).

For now we only support the in-process path; cross-process injection
(remote Pipeline nodes) is v0.3+.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import uuid
from pathlib import Path
from typing import Any, Type

from forge_agent.core.base import BaseAgent
from forge_agent.generator.validator import ContractValidator, ValidationResult
from forge_agent.registry.registry import get_registry

log = logging.getLogger(__name__)


class AgentInjector:
    """Register a dynamically-created Agent class into the live Registry.

    Three entry points:
        1. inject_source(source_str)    — from LLM output
        2. inject_file(path)            — from a file on disk
        3. inject_class(cls)            — already-imported
    """

    def __init__(self, *, validator: ContractValidator | None = None) -> None:
        self.validator = validator or ContractValidator()
        self.registry = get_registry()

    def inject_source(
        self,
        source: str,
        *,
        module_name: str | None = None,
        override: bool = True,
    ) -> tuple[Type[BaseAgent], ValidationResult]:
        """Validate → exec module → register class → return (class, validation)."""
        v = self.validator.validate_source(source)
        if not v.ok:
            log.error("Source failed validation: %s", v.errors)
            return type, v  # type: ignore[return-value]

        module_name = module_name or f"_generated_agent_{uuid.uuid4().hex[:8]}"
        module = type(sys)(module_name)
        # Inject the base class namespace so generated code can `from forge_agent...`
        from forge_agent import core as _core
        module.__dict__.update({
            "BaseAgent": BaseAgent,
            "AgentContext": _core.AgentContext,
            "AgentReport": _core.AgentReport,
        })
        try:
            exec(compile(source, f"<generated:{module_name}>", "exec"), module.__dict__)
        except Exception as exc:  # noqa: BLE001
            v.ok = False
            v.errors.append(f"Execution error: {exc}")
            return type, v  # type: ignore[return-value]

        # Find the BaseAgent subclass
        cls: Type[BaseAgent] | None = None
        for obj in module.__dict__.values():
            if isinstance(obj, type) and issubclass(obj, BaseAgent) and obj is not BaseAgent:
                cls = obj
                break
        if cls is None:
            v.ok = False
            v.errors.append("No BaseAgent subclass found after exec")
            return type, v  # type: ignore[return-value]

        self.registry.register(cls, override=override)
        return cls, v

    def inject_file(
        self,
        path: str | Path,
        *,
        module_name: str | None = None,
    ) -> tuple[Type[BaseAgent], ValidationResult]:
        p = Path(path)
        source = p.read_text(encoding="utf-8")
        return self.inject_source(source, module_name=module_name or p.stem)

    def inject_class(self, cls: Type[BaseAgent]) -> ValidationResult:
        v = self.validator.validate_class(cls)
        if v.ok:
            self.registry.register(cls, override=True)
        return v
