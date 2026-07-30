"""Tests for TaskRunner (S3.2/S3.4/S3.6/S3.7).

Covers async submit, background execution, retry, cancel, recover,
and callback firing — all with mock executors (no real pipeline).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from forge_agent.runtime.models import TaskRun, TaskStatus
from forge_agent.runtime.retry import RetryPolicy
from forge_agent.runtime.sqlite_store import SQLiteTaskStore
from forge_agent.runtime.task_runner import TaskRunner

# -- mock executors ----------------------------------------------------------


class SuccessExecutor:
    """Always succeeds."""

    async def execute(
        self, pipeline_id: str, payload: dict[str, Any], run_id: str
    ) -> dict[str, Any]:
        return {"status": "done", "pipeline": pipeline_id}


class FailThenSucceedExecutor:
    """Fails N times, then succeeds."""

    def __init__(self, fail_count: int) -> None:
        self.fail_count = fail_count
        self.calls = 0

    async def execute(
        self, pipeline_id: str, payload: dict[str, Any], run_id: str
    ) -> dict[str, Any]:
        self.calls += 1
        if self.calls <= self.fail_count:
            raise RuntimeError(f"simulated failure {self.calls}")
        return {"status": "recovered", "attempts": self.calls}


class AlwaysFailExecutor:
    """Always fails."""

    async def execute(
        self, pipeline_id: str, payload: dict[str, Any], run_id: str
    ) -> dict[str, Any]:
        raise RuntimeError("permanent failure")


class SlowExecutor:
    """Sleeps before succeeding (for cancel testing)."""

    async def execute(
        self, pipeline_id: str, payload: dict[str, Any], run_id: str
    ) -> dict[str, Any]:
        await asyncio.sleep(5)
        return {"status": "done"}


# -- mock callback -----------------------------------------------------------


class MockCallback:
    """Records terminal-state callbacks."""

    def __init__(self) -> None:
        self.calls: list[TaskRun] = []

    async def on_terminal(self, run: TaskRun) -> None:
        self.calls.append(run)


# -- fixtures ----------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    s = SQLiteTaskStore(db_path=tmp_path / "test_runner.db")
    yield s
    s.close()


@pytest.fixture
def retry():
    return RetryPolicy(max_attempts=3, base_delay=0.01, max_delay=0.05)


# -- S3.2: async submit -----------------------------------------------------


class TestSubmit:
    async def test_submit_returns_pending_immediately(self, store, retry) -> None:
        runner = TaskRunner(store, SuccessExecutor(), retry=retry)
        run = await runner.submit("p1", payload={"q": "hello"})
        assert run.status == TaskStatus.PENDING
        assert run.run_id is not None

        await runner.wait(run.run_id)
        final = runner.get(run.run_id)
        assert final is not None
        assert final.status == TaskStatus.SUCCEEDED
        assert final.result == {"status": "done", "pipeline": "p1"}

    async def test_submit_persists_to_store(self, store, retry) -> None:
        runner = TaskRunner(store, SuccessExecutor(), retry=retry)
        run = await runner.submit("p1")
        assert store.get(run.run_id) is not None

    async def test_submit_with_trigger_source(self, store, retry) -> None:
        runner = TaskRunner(store, SuccessExecutor(), retry=retry)
        run = await runner.submit("p1", trigger_source="webhook", trigger_id="evt_123")
        assert run.trigger_source == "webhook"
        assert run.trigger_id == "evt_123"

    async def test_multiple_concurrent_runs(self, store, retry) -> None:
        runner = TaskRunner(store, SuccessExecutor(), retry=retry)
        runs = await asyncio.gather(
            runner.submit("p1"),
            runner.submit("p2"),
            runner.submit("p3"),
        )
        assert all(store.get(r.run_id) is not None for r in runs)
        await asyncio.gather(*[runner.wait(r.run_id) for r in runs])
        assert all(runner.get(r.run_id).status == TaskStatus.SUCCEEDED for r in runs)


# -- S3.4: retry -------------------------------------------------------------


class TestRetry:
    async def test_retry_then_success(self, store, retry) -> None:
        executor = FailThenSucceedExecutor(fail_count=2)
        runner = TaskRunner(store, executor, retry=retry)
        run = await runner.submit("p1")
        await runner.wait(run.run_id)

        final = runner.get(run.run_id)
        assert final.status == TaskStatus.SUCCEEDED
        assert final.result == {"status": "recovered", "attempts": 3}
        assert final.attempts == 2

    async def test_retry_exhausted_then_failed(self, store, retry) -> None:
        executor = AlwaysFailExecutor()
        runner = TaskRunner(store, executor, retry=retry)
        run = await runner.submit("p1")
        await runner.wait(run.run_id)

        final = runner.get(run.run_id)
        assert final.status == TaskStatus.FAILED
        assert "permanent failure" in final.error
        assert final.attempts == 3

    async def test_no_retry_when_max_zero(self, store) -> None:
        no_retry = RetryPolicy(max_attempts=0, base_delay=0.01)
        executor = FailThenSucceedExecutor(fail_count=1)
        runner = TaskRunner(store, executor, retry=no_retry)
        run = await runner.submit("p1")
        await runner.wait(run.run_id)

        final = runner.get(run.run_id)
        assert final.status == TaskStatus.FAILED
        assert final.attempts == 0


# -- S3.6: recover -----------------------------------------------------------


class TestRecover:
    async def test_recover_marks_running_as_interrupted(self, store, retry) -> None:
        runner = TaskRunner(store, SuccessExecutor(), retry=retry)
        # Manually create a running run (simulating crash mid-execution)
        crashed = TaskRun(pipeline_id="p1")
        crashed.start()
        store.create(crashed)
        store.update(crashed)

        recovered = await runner.recover()
        assert recovered == 1
        fetched = store.get(crashed.run_id)
        assert fetched.status == TaskStatus.INTERRUPTED

    async def test_recover_zero_when_none_running(self, store, retry) -> None:
        runner = TaskRunner(store, SuccessExecutor(), retry=retry)
        recovered = await runner.recover()
        assert recovered == 0

    async def test_recover_only_affects_running(self, store, retry) -> None:
        runner = TaskRunner(store, SuccessExecutor(), retry=retry)
        pending = TaskRun(pipeline_id="p1")
        succeeded = TaskRun(pipeline_id="p2")
        succeeded.start()
        succeeded.succeed()
        store.create(pending)
        store.create(succeeded)
        store.update(succeeded)

        recovered = await runner.recover()
        assert recovered == 0
        assert store.get(pending.run_id).status == TaskStatus.PENDING
        assert store.get(succeeded.run_id).status == TaskStatus.SUCCEEDED


# -- S3.7: callback ----------------------------------------------------------


class TestCallback:
    async def test_callback_fired_on_success(self, store, retry) -> None:
        cb = MockCallback()
        runner = TaskRunner(store, SuccessExecutor(), retry=retry, callback=cb)
        run = await runner.submit("p1")
        await runner.wait(run.run_id)

        assert len(cb.calls) == 1
        assert cb.calls[0].status == TaskStatus.SUCCEEDED

    async def test_callback_fired_on_failure(self, store, retry) -> None:
        cb = MockCallback()
        runner = TaskRunner(store, AlwaysFailExecutor(), retry=retry, callback=cb)
        run = await runner.submit("p1")
        await runner.wait(run.run_id)

        assert len(cb.calls) == 1
        assert cb.calls[0].status == TaskStatus.FAILED

    async def test_no_callback_when_none_registered(self, store, retry) -> None:
        runner = TaskRunner(store, SuccessExecutor(), retry=retry)
        run = await runner.submit("p1")
        await runner.wait(run.run_id)
        # Just verify no crash
        assert runner.get(run.run_id).status == TaskStatus.SUCCEEDED


# -- cancel ------------------------------------------------------------------


class TestCancel:
    async def test_cancel_running_task(self, store, retry) -> None:
        runner = TaskRunner(store, SlowExecutor(), retry=retry)
        run = await runner.submit("p1")
        await asyncio.sleep(0.05)  # let it start
        cancelled = await runner.cancel(run.run_id)
        assert cancelled is True

        await asyncio.sleep(0.1)
        final = runner.get(run.run_id)
        assert final.status in (TaskStatus.CANCELLED,)

    async def test_cancel_nonexistent(self, store, retry) -> None:
        runner = TaskRunner(store, SuccessExecutor(), retry=retry)
        assert await runner.cancel("ghost") is False

    async def test_cancel_already_terminal(self, store, retry) -> None:
        runner = TaskRunner(store, SuccessExecutor(), retry=retry)
        run = await runner.submit("p1")
        await runner.wait(run.run_id)
        assert await runner.cancel(run.run_id) is False
