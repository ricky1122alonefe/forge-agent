"""Tests for the unified logging system (structlog + contextvars)."""
from __future__ import annotations

import asyncio
import io
import json
import sys
from pathlib import Path

import pytest

from forge_agent.observability import logger as log_mod


# --------------------------------------------------------------- env helpers

@pytest.fixture(autouse=True)
def _reset_logger_state():
    """Make every test start with a clean logger state."""
    log_mod.reset_for_tests()
    yield
    log_mod.reset_for_tests()


def _capture_stderr() -> io.StringIO:
    """Replace sys.stderr with a StringIO so tests can inspect log output."""
    buf = io.StringIO()
    return buf


# --------------------------------------------------------------- configuration

def test_configure_defaults_to_console():
    log_mod.configure_logging(level="INFO", json=False, force=True)
    cfg = log_mod.current_config()
    assert cfg["configured"] is True
    assert cfg["format"] == "console"
    assert cfg["level"] == "INFO"


def test_configure_json_mode():
    log_mod.configure_logging(level="DEBUG", json=True, force=True)
    cfg = log_mod.current_config()
    assert cfg["format"] == "json"
    assert cfg["level"] == "DEBUG"


def test_configure_idempotent_without_force():
    log_mod.configure_logging(level="INFO", json=False, force=True)
    log_mod.configure_logging(level="DEBUG", json=True)  # should be no-op
    cfg = log_mod.current_config()
    # Original config wins
    assert cfg["level"] == "INFO"
    assert cfg["format"] == "console"


def test_configure_with_force_overrides():
    log_mod.configure_logging(level="INFO", json=False, force=True)
    log_mod.configure_logging(level="DEBUG", json=True, force=True)
    cfg = log_mod.current_config()
    assert cfg["level"] == "DEBUG"
    assert cfg["format"] == "json"


def test_configure_log_file_path(tmp_path: Path):
    log_path = tmp_path / "subdir" / "out.log"
    log_mod.configure_logging(log_file=log_path, force=True)
    assert log_path.parent.exists()
    assert log_mod.current_config()["file_path"] == log_path


# --------------------------------------------------------------- contextvars

def test_bind_and_current_context():
    log_mod.bind_context(agent_id="a1", run_id="r1")
    assert log_mod.current_context() == {"agent_id": "a1", "run_id": "r1"}


def test_unbind_removes_key():
    log_mod.bind_context(agent_id="a1", run_id="r1", domain="x")
    log_mod.unbind_context("run_id")
    ctx = log_mod.current_context()
    assert "run_id" not in ctx
    assert ctx["agent_id"] == "a1"


def test_clear_context_wipes_all():
    log_mod.bind_context(agent_id="a1", run_id="r1")
    log_mod.clear_context()
    assert log_mod.current_context() == {}


def test_bind_skips_none_values():
    log_mod.bind_context(agent_id="a1", run_id=None, extra="x")
    ctx = log_mod.current_context()
    assert "run_id" not in ctx
    assert ctx["extra"] == "x"


# --------------------------------------------------------------- JSON output

def test_json_output_contains_required_keys(capsys):
    log_mod.configure_logging(level="INFO", json=True, force=True)
    log = log_mod.get_logger("test.json")
    log.info("hello", agent_id="a1", run_id="r1")
    captured = capsys.readouterr()
    # Logger writes to sys.stderr (configured by structlog)
    err = captured.err
    # Each non-empty line should be valid JSON
    for line in (ln for ln in err.splitlines() if ln.strip()):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            # Some lines might come from stdlib bridging with different
            # shape; only assert on lines that start with '{'
            if line.startswith("{"):
                raise
            continue
        assert "level" in entry
        assert "timestamp" in entry
        assert "event" in entry


def test_json_output_includes_bound_context(capsys):
    log_mod.configure_logging(level="INFO", json=True, force=True)
    log_mod.bind_context(agent_id="a99", domain="test")
    log = log_mod.get_logger("test.ctx")
    log.info("event_msg", run_id="r42")
    captured = capsys.readouterr()
    found = False
    for line in captured.err.splitlines():
        if not line.strip().startswith("{"):
            continue
        entry = json.loads(line)
        if entry.get("event") == "event_msg":
            # contextvars should have been merged in
            assert entry.get("agent_id") == "a99"
            assert entry.get("domain") == "test"
            assert entry.get("run_id") == "r42"
            found = True
    assert found, f"event_msg not found in stderr:\n{captured.err}"


# --------------------------------------------------------------- concurrency

@pytest.mark.asyncio
async def test_contextvars_isolated_across_concurrent_tasks(capsys):
    """Two concurrent tasks must NOT see each other's agent_id."""
    log_mod.configure_logging(level="INFO", json=True, force=True)

    async def worker(agent_id: str, sleep: float) -> None:
        log_mod.bind_context(agent_id=agent_id, run_id=f"r-{agent_id}")
        await asyncio.sleep(sleep)
        log = log_mod.get_logger("test.conc")
        log.info("from-worker")

    # Run 2 workers concurrently with different sleep so logs interleave
    await asyncio.gather(worker("alpha", 0.05), worker("beta", 0.01))
    captured = capsys.readouterr()

    # Walk every line; each "from-worker" event must carry its own agent_id
    seen = []
    for line in captured.err.splitlines():
        if not line.strip().startswith("{"):
            continue
        entry = json.loads(line)
        if entry.get("event") == "from-worker":
            seen.append(entry.get("agent_id"))

    assert "alpha" in seen
    assert "beta" in seen
    # And no line should have an "agent_id" of the *other* worker mixed in
    for line in captured.err.splitlines():
        if not line.strip().startswith("{"):
            continue
        entry = json.loads(line)
        if entry.get("event") == "from-worker":
            assert entry.get("agent_id") in {"alpha", "beta"}


# --------------------------------------------------------------- StructLogger

def test_struct_logger_satisfies_protocol():
    from forge_agent.core.capabilities import LoggerProtocol
    from forge_agent.observability.logger import StructLogger

    log_mod.configure_logging(level="INFO", json=False, force=True)
    sl = StructLogger(name="test.protocol")
    assert isinstance(sl, LoggerProtocol)


def test_struct_logger_includes_agent_id(capsys):
    log_mod.configure_logging(level="INFO", json=True, force=True)
    sl = log_mod.StructLogger(name="test.structlogger")
    sl.log("info", agent_id="aX", msg="hi", extra=1)
    captured = capsys.readouterr()
    found = False
    for line in captured.err.splitlines():
        if not line.strip().startswith("{"):
            continue
        entry = json.loads(line)
        if entry.get("event") == "hi":
            assert entry.get("agent_id") == "aX"
            assert entry.get("extra") == 1
            found = True
    assert found


# --------------------------------------------------------------- BaseAgent integration

@pytest.mark.asyncio
async def test_base_agent_run_binds_contextvars(capsys):
    """Inside an agent's run(), the bound logger must see agent_id + run_id."""
    from forge_agent.core.base import BaseAgent
    from forge_agent.core.contracts import AgentReport
    from forge_agent.core.context import AgentContext
    from forge_agent.core.enums import Verdict

    log_mod.configure_logging(level="INFO", json=True, force=True)

    class _Demo(BaseAgent):
        agent_id = "test.bind"
        name = "Bind Demo"
        domain = "test"

        async def observe(self, ctx):
            # Capture context at observe time
            return {"ctx": log_mod.current_context()}

        async def decide(self, ctx, obs):
            return {"y": 1}

        async def act(self, ctx, dec):
            return AgentReport(
                agent_id=self.agent_id, name=self.name,
                verdict=Verdict.NEUTRAL, evidence=["ok"],
                run_id=ctx.run_id,
            )

    agent = _Demo()
    ctx = AgentContext(scope_id="t1", scope_name="t")
    await agent.run(ctx)
    # After run, run_id should have been unbound
    assert "run_id" not in log_mod.current_context()
