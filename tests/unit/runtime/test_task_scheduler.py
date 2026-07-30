"""Tests for TaskScheduler (S3.5).

Covers job registration, removal, enable/disable, firing, and
start/stop lifecycle — with a mock runner (no real pipeline).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from forge_agent.runtime.retry import RetryPolicy
from forge_agent.runtime.sqlite_store import SQLiteTaskStore
from forge_agent.runtime.task_runner import TaskRunner
from forge_agent.runtime.task_scheduler import TaskScheduler


class SuccessExecutor:
    async def execute(
        self, pipeline_id: str, payload: dict[str, Any], run_id: str
    ) -> dict[str, Any]:
        return {"status": "done"}


@pytest.fixture
def store(tmp_path):
    s = SQLiteTaskStore(db_path=tmp_path / "test_sched.db")
    yield s
    s.close()


@pytest.fixture
def runner(store):
    return TaskRunner(store, SuccessExecutor(), retry=RetryPolicy(max_attempts=1, base_delay=0.01))


@pytest.fixture
def scheduler(runner):
    return TaskScheduler(runner, poll_interval=0.05)


class TestJobManagement:
    def test_add_and_list_job(self, scheduler: TaskScheduler) -> None:
        job = scheduler.add_job(
            job_id="j1",
            pipeline_id="p1",
            cron="every:60",
        )
        assert job.job_id == "j1"
        assert job.pipeline_id == "p1"
        assert job.cron == "every:60"
        jobs = scheduler.list_jobs()
        assert len(jobs) == 1

    def test_add_multiple_jobs(self, scheduler: TaskScheduler) -> None:
        scheduler.add_job(job_id="j1", pipeline_id="p1", cron="every:60")
        scheduler.add_job(job_id="j2", pipeline_id="p2", cron="every:120")
        assert len(scheduler.list_jobs()) == 2

    def test_remove_job(self, scheduler: TaskScheduler) -> None:
        scheduler.add_job(job_id="j1", pipeline_id="p1", cron="every:60")
        assert scheduler.remove_job("j1") is True
        assert len(scheduler.list_jobs()) == 0

    def test_remove_nonexistent(self, scheduler: TaskScheduler) -> None:
        assert scheduler.remove_job("ghost") is False

    def test_disable_enable_job(self, scheduler: TaskScheduler) -> None:
        scheduler.add_job(job_id="j1", pipeline_id="p1", cron="every:60")
        assert scheduler.disable_job("j1") is True
        assert scheduler.list_jobs()[0].enabled is False
        assert scheduler.enable_job("j1") is True
        assert scheduler.list_jobs()[0].enabled is True


class TestIntervalParsing:
    def test_seconds(self, scheduler: TaskScheduler) -> None:
        assert scheduler._parse_interval("every:30") == 30.0

    def test_minutes(self, scheduler: TaskScheduler) -> None:
        assert scheduler._parse_interval("every:5m") == 300.0

    def test_hours(self, scheduler: TaskScheduler) -> None:
        assert scheduler._parse_interval("every:2h") == 7200.0

    def test_plain_number(self, scheduler: TaskScheduler) -> None:
        assert scheduler._parse_interval("45") == 45.0

    def test_unparseable_defaults_60(self, scheduler: TaskScheduler) -> None:
        assert scheduler._parse_interval("garbage") == 60.0


class TestFiring:
    async def test_job_fires_on_schedule(self, scheduler: TaskScheduler, store) -> None:
        scheduler.add_job(
            job_id="j1",
            pipeline_id="p1",
            cron="every:0.1",  # every 0.1 seconds
            payload={"q": "hello"},
        )
        await scheduler.start()
        await asyncio.sleep(0.3)
        await scheduler.stop()

        runs = store.list(pipeline_id="p1")
        assert len(runs) >= 1
        assert all(r.trigger_source == "schedule" for r in runs)
        assert all(r.trigger_id == "j1" for r in runs)

    async def test_disabled_job_does_not_fire(self, scheduler: TaskScheduler, store) -> None:
        scheduler.add_job(job_id="j1", pipeline_id="p1", cron="every:0.1")
        scheduler.disable_job("j1")
        await scheduler.start()
        await asyncio.sleep(0.25)
        await scheduler.stop()
        assert len(store.list(pipeline_id="p1")) == 0

    async def test_removed_job_does_not_fire(self, scheduler: TaskScheduler, store) -> None:
        scheduler.add_job(job_id="j1", pipeline_id="p1", cron="every:0.1")
        scheduler.remove_job("j1")
        await scheduler.start()
        await asyncio.sleep(0.2)
        await scheduler.stop()
        assert len(store.list(pipeline_id="p1")) == 0

    async def test_multiple_jobs_fire(self, scheduler: TaskScheduler, store) -> None:
        scheduler.add_job(job_id="j1", pipeline_id="p1", cron="every:0.1")
        scheduler.add_job(job_id="j2", pipeline_id="p2", cron="every:0.15")
        await scheduler.start()
        await asyncio.sleep(0.35)
        await scheduler.stop()
        p1_runs = store.list(pipeline_id="p1")
        p2_runs = store.list(pipeline_id="p2")
        assert len(p1_runs) >= 1
        assert len(p2_runs) >= 1


class TestLifecycle:
    async def test_start_stop_idempotent(self, scheduler: TaskScheduler) -> None:
        await scheduler.start()
        await scheduler.start()  # no-op
        await scheduler.stop()
        await scheduler.stop()  # no-op

    async def test_stop_cancels_loop(self, scheduler: TaskScheduler, store) -> None:
        scheduler.add_job(job_id="j1", pipeline_id="p1", cron="every:0.1")
        await scheduler.start()
        await asyncio.sleep(0.15)
        await scheduler.stop()
        count_after_stop = len(store.list(pipeline_id="p1"))
        await asyncio.sleep(0.2)
        # No new runs after stop
        assert len(store.list(pipeline_id="p1")) == count_after_stop
