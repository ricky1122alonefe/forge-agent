"""Tests for SQLiteTaskStore (S3.1).

Covers CRUD, filtering, JSON serialisation, and edge cases.
"""

from __future__ import annotations

import sqlite3

import pytest

from forge_agent.runtime.models import TaskRun, TaskStatus
from forge_agent.runtime.sqlite_store import SQLiteTaskStore


@pytest.fixture
def store(tmp_path):
    s = SQLiteTaskStore(db_path=tmp_path / "test_tasks.db")
    yield s
    s.close()


class TestCreateAndGet:
    def test_create_and_get_roundtrip(self, store: SQLiteTaskStore) -> None:
        run = TaskRun(
            pipeline_id="p1",
            tenant_id="acme",
            payload={"keyword": "labubu"},
            trigger_source="webhook",
        )
        store.create(run)
        fetched = store.get(run.run_id)
        assert fetched is not None
        assert fetched.run_id == run.run_id
        assert fetched.pipeline_id == "p1"
        assert fetched.tenant_id == "acme"
        assert fetched.status == TaskStatus.PENDING
        assert fetched.payload == {"keyword": "labubu"}
        assert fetched.trigger_source == "webhook"

    def test_get_nonexistent_returns_none(self, store: SQLiteTaskStore) -> None:
        assert store.get("nope") is None

    def test_duplicate_create_raises(self, store: SQLiteTaskStore) -> None:
        run = TaskRun(pipeline_id="p1", run_id="fixed_id")
        store.create(run)
        with pytest.raises(sqlite3.IntegrityError):
            store.create(run)


class TestUpdate:
    def test_update_status_and_result(self, store: SQLiteTaskStore) -> None:
        run = TaskRun(pipeline_id="p1")
        store.create(run)
        run.start()
        run.succeed(result={"verdict": "ok"})
        store.update(run)
        fetched = store.get(run.run_id)
        assert fetched is not None
        assert fetched.status == TaskStatus.SUCCEEDED
        assert fetched.result == {"verdict": "ok"}
        assert fetched.started_at is not None
        assert fetched.finished_at is not None

    def test_update_error_on_failure(self, store: SQLiteTaskStore) -> None:
        run = TaskRun(pipeline_id="p1")
        store.create(run)
        run.start()
        run.fail("connection timeout")
        store.update(run)
        fetched = store.get(run.run_id)
        assert fetched is not None
        assert fetched.status == TaskStatus.FAILED
        assert fetched.error == "connection timeout"

    def test_update_retry_count(self, store: SQLiteTaskStore) -> None:
        run = TaskRun(pipeline_id="p1", max_attempts=3)
        store.create(run)
        run.start()
        run.schedule_retry()
        store.update(run)
        fetched = store.get(run.run_id)
        assert fetched is not None
        assert fetched.attempts == 1
        assert fetched.status == TaskStatus.RETRYING


class TestList:
    def test_list_all(self, store: SQLiteTaskStore) -> None:
        for i in range(5):
            store.create(TaskRun(pipeline_id=f"p{i}"))
        runs = store.list()
        assert len(runs) == 5

    def test_list_by_tenant(self, store: SQLiteTaskStore) -> None:
        store.create(TaskRun(pipeline_id="p1", tenant_id="acme"))
        store.create(TaskRun(pipeline_id="p2", tenant_id="acme"))
        store.create(TaskRun(pipeline_id="p3", tenant_id="other"))
        runs = store.list(tenant_id="acme")
        assert len(runs) == 2
        assert all(r.tenant_id == "acme" for r in runs)

    def test_list_by_pipeline(self, store: SQLiteTaskStore) -> None:
        store.create(TaskRun(pipeline_id="pipeline_a"))
        store.create(TaskRun(pipeline_id="pipeline_a"))
        store.create(TaskRun(pipeline_id="pipeline_b"))
        runs = store.list(pipeline_id="pipeline_a")
        assert len(runs) == 2

    def test_list_by_status(self, store: SQLiteTaskStore) -> None:
        r1 = TaskRun(pipeline_id="p1")
        r2 = TaskRun(pipeline_id="p2")
        store.create(r1)
        store.create(r2)
        r1.start()
        r1.succeed()
        store.update(r1)
        succeeded = store.list(status=TaskStatus.SUCCEEDED)
        assert len(succeeded) == 1
        assert succeeded[0].run_id == r1.run_id
        pending = store.list(status=TaskStatus.PENDING)
        assert len(pending) == 1

    def test_list_limit(self, store: SQLiteTaskStore) -> None:
        for i in range(10):
            store.create(TaskRun(pipeline_id=f"p{i}"))
        runs = store.list(limit=3)
        assert len(runs) == 3

    def test_list_newest_first(self, store: SQLiteTaskStore) -> None:
        import time

        r1 = TaskRun(pipeline_id="p1")
        store.create(r1)
        time.sleep(0.01)
        r2 = TaskRun(pipeline_id="p2")
        store.create(r2)
        runs = store.list()
        assert runs[0].run_id == r2.run_id
        assert runs[1].run_id == r1.run_id


class TestListByStatus:
    def test_list_running_for_recovery(self, store: SQLiteTaskStore) -> None:
        r1 = TaskRun(pipeline_id="p1")
        r2 = TaskRun(pipeline_id="p2")
        r3 = TaskRun(pipeline_id="p3")
        store.create(r1)
        store.create(r2)
        store.create(r3)
        r1.start()
        r2.start()
        store.update(r1)
        store.update(r2)
        # r3 stays pending
        running = store.list_by_status(TaskStatus.RUNNING)
        assert len(running) == 2
        assert all(r.status == TaskStatus.RUNNING for r in running)


class TestDelete:
    def test_delete_existing(self, store: SQLiteTaskStore) -> None:
        run = TaskRun(pipeline_id="p1")
        store.create(run)
        assert store.delete(run.run_id) is True
        assert store.get(run.run_id) is None

    def test_delete_nonexistent(self, store: SQLiteTaskStore) -> None:
        assert store.delete("ghost") is False


class TestJsonSerialization:
    def test_nested_payload(self, store: SQLiteTaskStore) -> None:
        run = TaskRun(
            pipeline_id="p1",
            payload={"nested": {"list": [1, 2, 3], "dict": {"a": True}}},
        )
        store.create(run)
        fetched = store.get(run.run_id)
        assert fetched is not None
        assert fetched.payload == {"nested": {"list": [1, 2, 3], "dict": {"a": True}}}

    def test_unicode_payload(self, store: SQLiteTaskStore) -> None:
        run = TaskRun(pipeline_id="p1", payload={"keyword": "拉布布"})
        store.create(run)
        fetched = store.get(run.run_id)
        assert fetched is not None
        assert fetched.payload["keyword"] == "拉布布"

    def test_metadata_persists(self, store: SQLiteTaskStore) -> None:
        run = TaskRun(pipeline_id="p1", metadata={"trace_id": "t123"})
        store.create(run)
        fetched = store.get(run.run_id)
        assert fetched is not None
        assert fetched.metadata == {"trace_id": "t123"}


class TestRecoveryScenario:
    """Simulate crash recovery: running runs found after restart."""

    def test_find_and_mark_interrupted(self, store: SQLiteTaskStore) -> None:
        r1 = TaskRun(pipeline_id="p1")
        r2 = TaskRun(pipeline_id="p2")
        store.create(r1)
        store.create(r2)
        r1.start()  # running when crash happens
        store.update(r1)
        # r2 still pending

        # On restart: find running runs
        running = store.list_by_status(TaskStatus.RUNNING)
        assert len(running) == 1
        assert running[0].run_id == r1.run_id

        # Mark as interrupted
        r1.mark_interrupted()
        store.update(r1)
        assert store.get(r1.run_id).status == TaskStatus.INTERRUPTED
