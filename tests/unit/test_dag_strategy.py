"""Tests for DAGStrategy scheduler."""

from __future__ import annotations

import pytest

from forge_agent.core.context import AgentContext
from forge_agent.scheduler.strategies import DAGStrategy
from forge_agent.scheduler.tasks import ScheduleResult, ScheduleTask


def _ctx() -> AgentContext:
    return AgentContext(scope_id="test", scope_name="test")


async def _fake_run(task: ScheduleTask) -> ScheduleResult:
    """Fake runner that succeeds and records the task id."""
    if task.task_id == "bad":
        raise RuntimeError("boom")
    return ScheduleResult(
        task_id=task.task_id,
        agent_id=task.agent_id,
        success=True,
    )


@pytest.mark.anyio
async def test_dag_runs_chain_sequentially():
    strategy = DAGStrategy()
    tasks = {
        "a": ScheduleTask(task_id="a", agent_id="a", context=_ctx()),
        "b": ScheduleTask(task_id="b", agent_id="b", context=_ctx(), dependencies=["a"]),
        "c": ScheduleTask(task_id="c", agent_id="c", context=_ctx(), dependencies=["b"]),
    }
    results = await strategy.execute(tasks, _fake_run)
    assert results["a"].success is True
    assert results["b"].success is True
    assert results["c"].success is True


@pytest.mark.anyio
async def test_dag_runs_branches_in_parallel():
    strategy = DAGStrategy()
    tasks = {
        "root": ScheduleTask(task_id="root", agent_id="root", context=_ctx()),
        "left": ScheduleTask(
            task_id="left", agent_id="left", context=_ctx(), dependencies=["root"]
        ),
        "right": ScheduleTask(
            task_id="right", agent_id="right", context=_ctx(), dependencies=["root"]
        ),
        "merge": ScheduleTask(
            task_id="merge", agent_id="merge", context=_ctx(), dependencies=["left", "right"]
        ),
    }
    results = await strategy.execute(tasks, _fake_run)
    assert all(r.success for r in results.values())
    assert set(results) == {"root", "left", "right", "merge"}


@pytest.mark.anyio
async def test_dag_skips_downstream_on_failure():
    strategy = DAGStrategy()
    tasks = {
        "ok": ScheduleTask(task_id="ok", agent_id="ok", context=_ctx()),
        "bad": ScheduleTask(task_id="bad", agent_id="bad", context=_ctx()),
        "after_bad": ScheduleTask(
            task_id="after_bad", agent_id="after_bad", context=_ctx(), dependencies=["bad"]
        ),
        "after_ok": ScheduleTask(
            task_id="after_ok", agent_id="after_ok", context=_ctx(), dependencies=["ok"]
        ),
    }
    results = await strategy.execute(tasks, _fake_run)
    assert results["ok"].success is True
    assert results["bad"].success is False
    assert results["after_bad"].success is False
    assert "dependency(s) failed" in results["after_bad"].error
    assert results["after_ok"].success is True


@pytest.mark.anyio
async def test_dag_detects_cycle():
    strategy = DAGStrategy()
    tasks = {
        "a": ScheduleTask(task_id="a", agent_id="a", context=_ctx(), dependencies=["c"]),
        "b": ScheduleTask(task_id="b", agent_id="b", context=_ctx(), dependencies=["a"]),
        "c": ScheduleTask(task_id="c", agent_id="c", context=_ctx(), dependencies=["b"]),
    }
    results = await strategy.execute(tasks, _fake_run)
    assert all(not r.success for r in results.values())
    assert any("cycle" in (r.error or "") for r in results.values())


@pytest.mark.anyio
async def test_dag_reports_unknown_dependency():
    strategy = DAGStrategy()
    tasks = {
        "a": ScheduleTask(task_id="a", agent_id="a", context=_ctx(), dependencies=["missing"]),
    }
    results = await strategy.execute(tasks, _fake_run)
    assert results["a"].success is False
    assert "unknown dependency" in results["a"].error
