"""Tests for the Sandbox (T1.3 — real process isolation).

Covers:
- Static import checks (deny-list)
- Static network policy checks
- Subprocess execution (happy path)
- Subprocess timeout (infinite loop → SIGKILL)
- Forbidden imports rejected before execution
- Network policy violations rejected
- Filesystem isolation (chdir to temp dir)
- Legacy in-process fallback (no _source_code)
"""

from __future__ import annotations

import pytest

from forge_agent.core.context import AgentContext
from forge_agent.generator.sandbox import ResourceLimits, Sandbox, SmokeTestResult

# ----------------------------------------------------------------- Fixtures


@pytest.fixture
def sandbox() -> Sandbox:
    return Sandbox()


@pytest.fixture
def sandbox_fast() -> Sandbox:
    return Sandbox(limits=ResourceLimits(timeout_seconds=2.0, cpu_seconds=2))


@pytest.fixture
def ctx() -> AgentContext:
    return AgentContext(scope_id="test", scope_name="test")


# ----------------------------------------------------------------- Static: imports


def test_check_imports_clean(sandbox: Sandbox) -> None:
    src = "import json\nimport os\n"
    result = sandbox._check_imports(src)
    assert result["ok"] is True
    assert result["violations"] == []


def test_check_imports_subprocess_blocked(sandbox: Sandbox) -> None:
    src = "import subprocess\n"
    result = sandbox._check_imports(src)
    assert result["ok"] is False
    assert any("subprocess" in v for v in result["violations"])


def test_check_imports_socket_blocked(sandbox: Sandbox) -> None:
    src = "import socket\n"
    result = sandbox._check_imports(src)
    assert result["ok"] is False
    assert any("socket" in v for v in result["violations"])


def test_check_imports_from_os_system_blocked(sandbox: Sandbox) -> None:
    src = "from os import system\n"
    result = sandbox._check_imports(src)
    assert result["ok"] is False
    assert any("system" in v for v in result["violations"])


def test_check_imports_syntax_error(sandbox: Sandbox) -> None:
    result = sandbox._check_imports("def broken(:")
    assert result["ok"] is False
    assert any("SyntaxError" in v for v in result["violations"])


# ----------------------------------------------------------------- Static: network


def test_check_network_clean(sandbox: Sandbox) -> None:
    src = "import json\nimport os\n"
    result = sandbox._check_network(src)
    assert result["ok"] is True


def test_check_network_httpx_blocked(sandbox: Sandbox) -> None:
    src = "import httpx\n"
    result = sandbox._check_network(src)
    assert result["ok"] is False
    assert any("httpx" in v for v in result["violations"])


def test_check_network_requests_blocked(sandbox: Sandbox) -> None:
    src = "import requests\n"
    result = sandbox._check_network(src)
    assert result["ok"] is False
    assert any("requests" in v for v in result["violations"])


def test_check_network_from_aiohttp_blocked(sandbox: Sandbox) -> None:
    src = "from aiohttp import ClientSession\n"
    result = sandbox._check_network(src)
    assert result["ok"] is False
    assert any("aiohttp" in v for v in result["violations"])


# ----------------------------------------------------------------- Subprocess: happy path

_GOOD_AGENT_SRC = """\
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class GoodAgent(BaseAgent):
    agent_id = "test.good"
    name = "Good"

    async def observe(self, ctx: AgentContext) -> dict:
        return {"ok": True}

    async def decide(self, ctx: AgentContext, obs: dict) -> dict:
        return obs

    async def act(self, ctx: AgentContext, dec: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id, name=self.name, evidence=["ok"],
        )
"""


@pytest.mark.asyncio
async def test_subprocess_happy_path(sandbox: Sandbox, ctx: AgentContext) -> None:
    class GoodAgent:
        agent_id = "test.good"
        __name__ = "GoodAgent"
        _source_code = _GOOD_AGENT_SRC

    GoodAgent.__name__ = "GoodAgent"
    result = await sandbox.run_smoke_test(GoodAgent, ctx)
    assert result.success is True
    assert result.error is None
    assert result.report is not None
    assert result.report["agent_id"] == "test.good"


# ----------------------------------------------------------------- Subprocess: timeout

_LOOP_AGENT_SRC = """\
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class LoopAgent(BaseAgent):
    agent_id = "test.loop"
    name = "Loop"

    async def observe(self, ctx: AgentContext) -> dict:
        while True:
            pass

    async def decide(self, ctx: AgentContext, obs: dict) -> dict:
        return {}

    async def act(self, ctx: AgentContext, dec: dict) -> AgentReport:
        return AgentReport(agent_id=self.agent_id, name=self.name)
"""


@pytest.mark.asyncio
async def test_subprocess_timeout(
    sandbox_fast: Sandbox,
    ctx: AgentContext,
) -> None:
    class LoopAgent:
        agent_id = "test.loop"
        __name__ = "LoopAgent"
        _source_code = _LOOP_AGENT_SRC

    LoopAgent.__name__ = "LoopAgent"
    result = await sandbox_fast.run_smoke_test(LoopAgent, ctx)
    assert result.success is False
    assert result.error is not None
    # Should be either Timeout or SignalKill (CPU limit)
    assert result.error_type in ("Timeout", "SignalKill", "ProcessError")


# ----------------------------------------------------------------- Subprocess: forbidden imports

_SUBPROCESS_AGENT_SRC = """\
import subprocess
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class SubAgent(BaseAgent):
    agent_id = "test.sub"
    name = "Sub"

    async def observe(self, ctx: AgentContext) -> dict:
        return {}

    async def decide(self, ctx: AgentContext, obs: dict) -> dict:
        return {}

    async def act(self, ctx: AgentContext, dec: dict) -> AgentReport:
        return AgentReport(agent_id=self.agent_id, name=self.name)
"""


@pytest.mark.asyncio
async def test_subprocess_forbidden_import(
    sandbox: Sandbox,
    ctx: AgentContext,
) -> None:
    class SubAgent:
        agent_id = "test.sub"
        __name__ = "SubAgent"
        _source_code = _SUBPROCESS_AGENT_SRC

    SubAgent.__name__ = "SubAgent"
    result = await sandbox.run_smoke_test(SubAgent, ctx)
    assert result.success is False
    assert result.error_type == "ImportCheck"
    assert "subprocess" in (result.error or "")


# ----------------------------------------------------------------- Subprocess: network policy

_HTTP_AGENT_SRC = """\
import httpx
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class HttpAgent(BaseAgent):
    agent_id = "test.http"
    name = "Http"

    async def observe(self, ctx: AgentContext) -> dict:
        return {}

    async def decide(self, ctx: AgentContext, obs: dict) -> dict:
        return {}

    async def act(self, ctx: AgentContext, dec: dict) -> AgentReport:
        return AgentReport(agent_id=self.agent_id, name=self.name)
"""


@pytest.mark.asyncio
async def test_subprocess_network_policy(
    sandbox: Sandbox,
    ctx: AgentContext,
) -> None:
    class HttpAgent:
        agent_id = "test.http"
        __name__ = "HttpAgent"
        _source_code = _HTTP_AGENT_SRC

    HttpAgent.__name__ = "HttpAgent"
    result = await sandbox.run_smoke_test(HttpAgent, ctx)
    assert result.success is False
    assert result.error_type == "NetworkPolicy"
    assert "httpx" in (result.error or "")


@pytest.mark.asyncio
async def test_subprocess_network_allowed_when_enabled(
    ctx: AgentContext,
) -> None:
    sandbox = Sandbox(limits=ResourceLimits(network_egress=True))

    class HttpAgent:
        agent_id = "test.http"
        __name__ = "HttpAgent"
        _source_code = _HTTP_AGENT_SRC

    HttpAgent.__name__ = "HttpAgent"
    result = await sandbox.run_smoke_test(HttpAgent, ctx)
    # Should NOT be rejected by NetworkPolicy (may fail for other reasons)
    assert result.error_type != "NetworkPolicy"


# ----------------------------------------------------------------- Filesystem isolation

_WRITE_AGENT_SRC = """\
import os
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class WriteAgent(BaseAgent):
    agent_id = "test.write"
    name = "Write"

    async def observe(self, ctx: AgentContext) -> dict:
        with open("sandbox_test.txt", "w") as f:
            f.write("hello from sandbox")
        return {"cwd": os.getcwd()}

    async def decide(self, ctx: AgentContext, obs: dict) -> dict:
        return obs

    async def act(self, ctx: AgentContext, dec: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id, name=self.name,
            evidence=[dec.get("cwd", "")],
        )
"""


@pytest.mark.asyncio
async def test_filesystem_isolation(sandbox: Sandbox, ctx: AgentContext) -> None:
    """Agent writes a file — it goes to the temp work_dir, not cwd."""
    import os

    original_cwd = os.getcwd()

    class WriteAgent:
        agent_id = "test.write"
        __name__ = "WriteAgent"
        _source_code = _WRITE_AGENT_SRC

    WriteAgent.__name__ = "WriteAgent"
    result = await sandbox.run_smoke_test(WriteAgent, ctx)
    assert result.success is True

    # File should NOT exist in the original cwd
    assert not os.path.exists(os.path.join(original_cwd, "sandbox_test.txt"))

    # The agent's cwd should be different from original (temp dir)
    if result.report and result.report.get("evidence"):
        agent_cwd = result.report["evidence"][0]
        assert agent_cwd != original_cwd


# ----------------------------------------------------------------- Legacy: in-process fallback


@pytest.mark.asyncio
async def test_inprocess_fallback(sandbox: Sandbox, ctx: AgentContext) -> None:
    """When agent has no _source_code, run in-process (legacy mode)."""
    from forge_agent.core.base import BaseAgent
    from forge_agent.core.contracts import AgentReport

    class LegacyAgent(BaseAgent):
        agent_id = "test.legacy"
        name = "Legacy"

        async def observe(self, ctx: AgentContext) -> dict:
            return {"legacy": True}

        async def decide(self, ctx: AgentContext, obs: dict) -> dict:
            return obs

        async def act(self, ctx: AgentContext, dec: dict) -> AgentReport:
            return AgentReport(
                agent_id=self.agent_id,
                name=self.name,
                evidence=["legacy"],
            )

    result = await sandbox.run_smoke_test(LegacyAgent, ctx)
    assert result.success is True
    assert result.report is not None


@pytest.mark.asyncio
async def test_inprocess_timeout(
    sandbox_fast: Sandbox,
    ctx: AgentContext,
) -> None:
    """In-process mode also respects timeout."""
    from forge_agent.core.base import BaseAgent
    from forge_agent.core.contracts import AgentReport

    class SlowAgent(BaseAgent):
        agent_id = "test.slow"
        name = "Slow"

        async def observe(self, ctx: AgentContext) -> dict:
            import asyncio

            await asyncio.sleep(100)
            return {}

        async def decide(self, ctx: AgentContext, obs: dict) -> dict:
            return {}

        async def act(self, ctx: AgentContext, dec: dict) -> AgentReport:
            return AgentReport(agent_id=self.agent_id, name=self.name)

    result = await sandbox_fast.run_smoke_test(SlowAgent, ctx)
    assert result.success is False
    assert result.error_type == "Timeout"


# ----------------------------------------------------------------- Error handling


@pytest.mark.asyncio
async def test_subprocess_runtime_error(sandbox: Sandbox, ctx: AgentContext) -> None:
    """Agent that raises an exception is caught and reported."""

    error_src = """\
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class ErrorAgent(BaseAgent):
    agent_id = "test.error"
    name = "Error"

    async def observe(self, ctx: AgentContext) -> dict:
        raise ValueError("intentional error")

    async def decide(self, ctx: AgentContext, obs: dict) -> dict:
        return {}

    async def act(self, ctx: AgentContext, dec: dict) -> AgentReport:
        return AgentReport(agent_id=self.agent_id, name=self.name)
"""

    class ErrorAgent:
        agent_id = "test.error"
        __name__ = "ErrorAgent"
        _source_code = error_src

    ErrorAgent.__name__ = "ErrorAgent"
    result = await sandbox.run_smoke_test(ErrorAgent, ctx)
    assert result.success is False
    assert result.error is not None
    assert "ValueError" in result.error or "intentional error" in result.error


# ----------------------------------------------------------------- Backward compat


def test_backward_compat_imports() -> None:
    """Old import paths still work."""
    from forge_agent.generator.sandbox import (
        ResourceLimits,
        Sandbox,
        SmokeTestResult,
    )

    assert ResourceLimits is not None
    assert Sandbox is not None
    assert SmokeTestResult is not None


def test_smoke_test_result_dataclass() -> None:
    r = SmokeTestResult(
        success=True,
        agent_id="test",
        duration_ms=10.0,
    )
    assert r.success is True
    assert r.error is None
    assert r.warnings == []
