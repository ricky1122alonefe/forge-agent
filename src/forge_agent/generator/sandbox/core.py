"""Sandbox — isolated execution for generated Agents.

v0.3 (T1.3): Real process isolation.

Architecture:
    1. **StaticCheck** — AST-based import deny-list + network policy (fast reject)
    2. **SubprocessRunner** — runs agent code in a separate Python process with:
       - Resource limits (CPU / memory / file size) via ``resource.setrlimit``
       - Filesystem isolation (chdir to temp directory)
       - Timeout with SIGKILL fallback
       - stdout/stderr capture

Backward compatible: the ``Sandbox`` class keeps the same ``run_smoke_test``
API from v0.2.  When ``_source_code`` is not attached to the agent class,
the sandbox falls back to in-process execution (legacy mode).
"""
from __future__ import annotations

import ast
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
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

DENY_NAMES: set[str] = {
    "os.system", "os.exec", "os.execl", "os.execle", "os.execlp",
    "subprocess", "shutil.rmtree", "shutil.move",
    "socket",
    "ctypes",
    "multiprocessing",
    "threading",
    "asyncio.subprocess",
    "pty", "fcntl",
    "signal",
    "pickle",
    "marshal",
}

DENY_MODULES: set[str] = {
    "subprocess", "ctypes", "pty", "fcntl", "multiprocessing",
    "asyncio.subprocess", "signal", "socket", "pickle", "marshal",
}

# Modules/patterns that indicate network egress.
NETWORK_MODULES: set[str] = {
    "httpx", "aiohttp", "urllib", "urllib2", "requests",
    "httplib", "http.client",
}


# ------------------------------------------------------------------ Sandbox

class Sandbox:
    """Isolated sandbox for generated Agents.

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

        src = getattr(agent_cls, "_source_code", None)

        # --- Phase 1: static checks (fast reject) ---
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

            if not self.limits.network_egress:
                net_check = self._check_network(src)
                if not net_check["ok"]:
                    return SmokeTestResult(
                        success=False,
                        agent_id=agent_id,
                        duration_ms=(time.perf_counter() - t0) * 1000,
                        error=f"network policy violation: {net_check['violations']}",
                        error_type="NetworkPolicy",
                    )

        # --- Phase 2: subprocess execution ---
        if src:
            return await self._run_in_subprocess(
                agent_cls, src, sample_context, t0,
            )

        # --- Fallback: in-process (legacy, no source available) ---
        return await self._run_in_process(agent_cls, sample_context, t0)

    # ------------------------------------------------------------------ Subprocess

    async def _run_in_subprocess(
        self,
        agent_cls: type,
        source: str,
        sample_context: Any,
        t0: float,
    ) -> SmokeTestResult:
        """Run agent code in an isolated subprocess."""
        agent_id = getattr(agent_cls, "agent_id", "unknown")
        class_name = agent_cls.__name__

        with tempfile.TemporaryDirectory(prefix="forge_sandbox_") as work_dir:
            request = {
                "source": source,
                "class_name": class_name,
                "context_dict": sample_context.to_dict()
                    if hasattr(sample_context, "to_dict")
                    else {"scope_id": str(sample_context)},
                "limits": {
                    "cpu_seconds": self.limits.cpu_seconds,
                    "memory_mb": self.limits.memory_mb,
                    "file_write": self.limits.file_write,
                    "work_dir": work_dir,
                },
            }

            try:
                result = await self._spawn_subprocess(request)
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

            elapsed = (time.perf_counter() - t0) * 1000
            returncode, stdout_data, stderr_data = result

            # Signal death
            if returncode < 0:
                sig = -returncode
                sig_name = _signal_name(sig)
                return SmokeTestResult(
                    success=False,
                    agent_id=agent_id,
                    duration_ms=elapsed,
                    error=f"killed by signal {sig} ({sig_name})",
                    error_type="SignalKill",
                )

            # Non-zero exit (no JSON output)
            if returncode != 0 and not stdout_data.strip():
                return SmokeTestResult(
                    success=False,
                    agent_id=agent_id,
                    duration_ms=elapsed,
                    error=f"process exited with code {returncode}: "
                          f"{stderr_data[:500]}",
                    error_type="ProcessError",
                )

            # Parse JSON response
            try:
                response = json.loads(stdout_data)
            except json.JSONDecodeError:
                return SmokeTestResult(
                    success=False,
                    agent_id=agent_id,
                    duration_ms=elapsed,
                    error=f"invalid subprocess output (rc={returncode}): "
                          f"{stdout_data[:200]}",
                    error_type="InvalidOutput",
                )

            if response.get("ok"):
                return SmokeTestResult(
                    success=True,
                    agent_id=agent_id,
                    duration_ms=response.get("duration_ms", elapsed),
                    report=response.get("report_dict"),
                )

            return SmokeTestResult(
                success=False,
                agent_id=agent_id,
                duration_ms=response.get("duration_ms", elapsed),
                error=response.get("error", "unknown error"),
                error_type=response.get("error_type", "Unknown"),
            )

    async def _spawn_subprocess(
        self, request: dict,
    ) -> tuple[int, str, str]:
        """Spawn a subprocess and return (returncode, stdout, stderr)."""
        entry_script = str(
            Path(__file__).parent.parent / "_subprocess_entry.py"
        )
        if not os.path.exists(entry_script):
            raise FileNotFoundError(
                f"Subprocess entry script not found: {entry_script}"
            )

        python_path = os.pathsep.join(sys.path)
        env = os.environ.copy()
        env["PYTHONPATH"] = python_path

        input_data = json.dumps(request)

        proc = await asyncio.create_subprocess_exec(
            sys.executable, entry_script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=input_data.encode()),
                timeout=self.limits.timeout_seconds,
            )
        except asyncio.TimeoutError:
            _kill_process_tree(proc)
            raise

        return (
            proc.returncode or 0,
            stdout_bytes.decode(errors="replace"),
            stderr_bytes.decode(errors="replace"),
        )

    # ------------------------------------------------------------------ In-process (legacy)

    async def _run_in_process(
        self,
        agent_cls: type,
        sample_context: Any,
        t0: float,
    ) -> SmokeTestResult:
        """Fallback: run agent in the current process (no isolation)."""
        agent_id = getattr(agent_cls, "agent_id", "unknown")
        try:
            agent = agent_cls()
            if hasattr(agent, "initialize"):
                await asyncio.wait_for(
                    agent.initialize(),
                    timeout=self.limits.timeout_seconds,
                )
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
                names = node.names  # local ref for Python 3.14 compat
                for alias in names:
                    if alias.name in {
                        "system", "exec", "execl", "Popen", "rmtree",
                    }:
                        violations.append(f"{full}.{alias.name}")
        return {"ok": not violations, "violations": violations}

    def _check_network(self, source: str) -> dict[str, Any]:
        """AST scan for network egress attempts."""
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {"ok": True, "violations": []}
        violations: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top in NETWORK_MODULES:
                        violations.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                top = node.module.split(".")[0]
                if top in NETWORK_MODULES:
                    violations.append(node.module)
        return {"ok": not violations, "violations": violations}


# ------------------------------------------------------------------ Helpers

def _kill_process_tree(proc: asyncio.subprocess.Process) -> None:
    """Kill a subprocess and all its children."""
    if proc.pid is None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, OSError, PermissionError):
        try:
            proc.kill()
        except ProcessLookupError:
            pass


def _signal_name(sig: int) -> str:
    """Return human-readable signal name."""
    try:
        return signal.Signals(sig).name
    except (ValueError, AttributeError):
        return f"signal_{sig}"
