"""Subprocess entry point for sandboxed agent execution.

This script runs inside an isolated subprocess. Communication protocol:

    stdin  → JSON {source, class_name, context_dict, limits}
    stdout → JSON {ok, report_dict?, error?, error_type?, duration_ms}

The subprocess applies resource limits (RLIMIT_*) before executing the agent.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import sys
import time
import traceback


def _apply_limits(limits: dict) -> None:
    """Apply POSIX resource limits (Unix only).

    Gracefully handles cases where the requested limit exceeds the
    system's hard limit (e.g. macOS RLIMIT_AS).
    """
    try:
        import resource
    except ImportError:
        return  # Windows — skip

    cpu = limits.get("cpu_seconds", 0)
    if cpu > 0:
        with contextlib.suppress(ValueError):
            resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))

    mem_mb = limits.get("memory_mb", 0)
    if mem_mb > 0:
        mem_bytes = mem_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (mem_bytes, mem_bytes))
        except ValueError:
            # macOS: hard limit may be lower than requested.
            # Try with the current hard limit as the soft limit.
            try:
                _, hard = resource.getrlimit(resource.RLIMIT_AS)
                if hard > 0:
                    resource.setrlimit(resource.RLIMIT_AS, (hard, hard))
            except (ValueError, OSError):
                pass

    if not limits.get("file_write", False):
        # Allow up to 1MB for stdout JSON output; block large file writes.
        with contextlib.suppress(ValueError):
            resource.setrlimit(resource.RLIMIT_FSIZE, (1024 * 1024, 1024 * 1024))


def main() -> None:
    t0 = time.perf_counter()

    # ---- read request from stdin ----
    raw = sys.stdin.read()
    req = json.loads(raw)

    source: str = req["source"]
    class_name: str = req["class_name"]
    context_dict: dict = req["context_dict"]
    limits: dict = req.get("limits", {})

    # ---- apply sandbox constraints ----
    work_dir = limits.get("work_dir", "")
    if work_dir and os.path.isdir(work_dir):
        os.chdir(work_dir)

    _apply_limits(limits)

    # ---- execute agent ----
    try:
        from forge_agent.core.context import AgentContext

        ctx = AgentContext(**context_dict)

        ns: dict = {}
        exec(compile(source, "<sandbox>", "exec"), ns)

        agent_cls = ns[class_name]
        agent = agent_cls()

        async def _run():
            if hasattr(agent, "initialize"):
                await agent.initialize()
            report = await agent.run(ctx)
            if hasattr(agent, "shutdown"):
                with contextlib.suppress(Exception):
                    await agent.shutdown()
            return report

        report = asyncio.run(_run())
        elapsed = (time.perf_counter() - t0) * 1000

        json.dump(
            {"ok": True, "report_dict": report.to_dict(), "duration_ms": elapsed},
            sys.stdout,
        )

    except Exception:
        elapsed = (time.perf_counter() - t0) * 1000
        json.dump(
            {
                "ok": False,
                "error": traceback.format_exc(),
                "error_type": type(sys.exc_info()[1]).__name__,
                "duration_ms": elapsed,
            },
            sys.stdout,
        )


if __name__ == "__main__":
    main()
