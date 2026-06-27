"""Sandbox — light-weight isolated execution for generated Agents.

v0.2 implementation: AST + import-name blacklist + timeout. No real process
isolation. Good enough for dev & CI; production should upgrade to
subprocess + seccomp / RestrictedPython.

What it does:
    1. AST-parses the source to extract imported names.
    2. Checks against a deny-list (os.system, subprocess, shutil.rmtree, etc.)
    3. Runs the Agent with a sample context under an asyncio timeout.
    4. Catches all exceptions and reports them.
"""

from __future__ import annotations

import ast
import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ Config

@dataclass
class ResourceLimits:
    """Resource limits for sandboxed execution."""

    cpu_seconds: int = 10
    memory_mb: int = 256
    timeout_seconds: float = 30.0
    file_write: bool = False
    network_egress: bool = False


@dataclass
class SmokeTestResult:
    """Result of running a generated Agent under the sandbox."""

    success: bool
    agent_id: str
    duration_ms: float
    error: str | None = None
    error_type: str | None = None
    report: Any = None  # AgentReport or None
    warnings: list[str] = field(default_factory=list)


# ------------------------------------------------------------------ Deny list

# Names that the generated code MUST NOT import.
# (We strip the leading "module." in checks; bare-name match counts too.)
DENY_NAMES: set[str] = {
    "os.system", "os.exec", "os.execl", "os.execle", "os.execlp",
    "subprocess", "shutil.rmtree", "shutil.move",
    "socket",  # raw network
    "ctypes",
    "multiprocessing",
    "threading",  # generally unnecessary in async land
    "asyncio.subprocess",
    "pty", "fcntl",  # process / IO control
    "signal",
    "pickle",  # unsafe deserialization
    "marshal",
}

DENY_MODULES: set[str] = {
    "subprocess", "ctypes", "pty", "fcntl", "multiprocessing",
    "asyncio.subprocess", "signal", "socket", "pickle", "marshal",
}


# ------------------------------------------------------------------ Sandbox

class Sandbox:
    """Light-weight sandbox for generated Agents.

    Usage::

        sandbox = Sandbox()
        result = await sandbox.run_smoke_test(agent_cls, sample_context)
        if result.success:
            deploy(agent_cls)
    """

    def __init__(self, limits: ResourceLimits | None = None) -> None:
        self.limits = limits or ResourceLimits()

    # ------------------------------------------------------------------ API

    async def run_smoke_test(
        self,
        agent_cls: type,
        sample_context: Any,
    ) -> SmokeTestResult:
        """Run a generated Agent class with a sample context.

        Returns a SmokeTestResult regardless of success/failure.
        """
        agent_id = getattr(agent_cls, "agent_id", "unknown")
        t0 = time.perf_counter()

        # 1. Static check: imports
        src = getattr(agent_cls, "_source_code", None)
        if src:
            import_check = self._check_imports(src)
            if not import_check["ok"]:
                return SmokeTestResult(
                    success=False,
                    agent_id=agent_id,
                    duration_ms=(time.perf_counter() - t0) * 1000,
                    error=f"forbidden imports: {import_check['violations']}",
                    error_type="ImportCheck",
                )

        # 2. Runtime: try to instantiate + run with timeout
        try:
            agent = agent_cls()
            if hasattr(agent, "initialize"):
                await asyncio.wait_for(agent.initialize(), timeout=self.limits.timeout_seconds)
            report = await asyncio.wait_for(
                agent.run(sample_context),
                timeout=self.limits.timeout_seconds,
            )
            if hasattr(agent, "shutdown"):
                try:
                    await asyncio.wait_for(agent.shutdown(), timeout=5.0)
                except Exception:  # noqa: BLE001
                    pass
            return SmokeTestResult(
                success=True,
                agent_id=agent_id,
                duration_ms=(time.perf_counter() - t0) * 1000,
                report=report,
            )
        except asyncio.TimeoutError:
            return SmokeTestResult(
                success=False,
                agent_id=agent_id,
                duration_ms=(time.perf_counter() - t0) * 1000,
                error=f"timeout after {self.limits.timeout_seconds}s",
                error_type="Timeout",
            )
        except Exception as exc:  # noqa: BLE001
            return SmokeTestResult(
                success=False,
                agent_id=agent_id,
                duration_ms=(time.perf_counter() - t0) * 1000,
                error=f"{type(exc).__name__}: {exc}",
                error_type=type(exc).__name__,
            )

    # ------------------------------------------------------------------ Static checks

    def _check_imports(self, source: str) -> dict[str, Any]:
        """AST scan for forbidden imports."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            return {"ok": False, "violations": [f"SyntaxError: {exc}"]}
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in DENY_MODULES or alias.name in DENY_NAMES:
                        violations.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                full = node.module
                top = full.split(".")[0]
                if top in DENY_MODULES or full in DENY_NAMES:
                    violations.append(full)
                for alias in node.names:
                    if alias.name in {"system", "exec", "execl", "Popen", "rmtree"}:
                        violations.append(f"{full}.{alias.name}")
        return {"ok": not violations, "violations": violations}
