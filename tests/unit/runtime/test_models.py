"""Tests for the TaskRun state machine (S1.3).

Covers every legal transition, illegal-transition rejection, terminal
lockdown, retry accounting, and serialization round-trip.
"""

from __future__ import annotations

import pytest

from forge_agent.runtime.models import (
    TERMINAL_STATES,
    InvalidTaskTransitionError,
    TaskRun,
    TaskStatus,
)


class TestLegalTransitions:
    """Every path permitted by the state machine must succeed."""

    def test_pending_to_running_sets_started_at(self) -> None:
        run = TaskRun(pipeline_id="p1")
        assert run.status == TaskStatus.PENDING
        assert run.started_at is None
        run.start()
        assert run.status == TaskStatus.RUNNING
        assert run.started_at is not None

    def test_running_to_succeeded_sets_result_and_finished(self) -> None:
        run = TaskRun(pipeline_id="p1")
        run.start()
        run.succeed(result={"verdict": "ok"})
        assert run.status == TaskStatus.SUCCEEDED
        assert run.result == {"verdict": "ok"}
        assert run.finished_at is not None
        assert run.is_terminal()

    def test_running_to_failed_sets_error(self) -> None:
        run = TaskRun(pipeline_id="p1")
        run.start()
        run.fail("boom")
        assert run.status == TaskStatus.FAILED
        assert run.error == "boom"
        assert run.is_terminal()

    def test_running_to_retrying_then_back_to_running(self) -> None:
        run = TaskRun(pipeline_id="p1", max_attempts=3)
        run.start()
        run.schedule_retry()
        assert run.status == TaskStatus.RETRYING
        assert run.attempts == 1
        run.start()
        assert run.status == TaskStatus.RUNNING

    def test_running_to_interrupted_can_requeue(self) -> None:
        run = TaskRun(pipeline_id="p1")
        run.start()
        run.mark_interrupted()
        assert run.status == TaskStatus.INTERRUPTED
        run.requeue()
        assert run.status == TaskStatus.PENDING

    def test_pending_to_cancelled(self) -> None:
        run = TaskRun(pipeline_id="p1")
        run.cancel()
        assert run.status == TaskStatus.CANCELLED
        assert run.is_terminal()

    def test_running_to_cancelled(self) -> None:
        run = TaskRun(pipeline_id="p1")
        run.start()
        run.cancel()
        assert run.status == TaskStatus.CANCELLED


class TestIllegalTransitions:
    """Transitions not in the table must raise InvalidTaskTransitionError."""

    @pytest.mark.parametrize(
        ("frm", "to"),
        [
            (TaskStatus.PENDING, TaskStatus.SUCCEEDED),
            (TaskStatus.PENDING, TaskStatus.FAILED),
            (TaskStatus.PENDING, TaskStatus.RETRYING),
            (TaskStatus.PENDING, TaskStatus.INTERRUPTED),
            (TaskStatus.SUCCEEDED, TaskStatus.RUNNING),
            (TaskStatus.SUCCEEDED, TaskStatus.FAILED),
            (TaskStatus.FAILED, TaskStatus.RUNNING),
            (TaskStatus.CANCELLED, TaskStatus.RUNNING),
            (TaskStatus.RETRYING, TaskStatus.SUCCEEDED),
            (TaskStatus.RETRYING, TaskStatus.FAILED),
        ],
    )
    def test_invalid_transition_raises(self, frm: str, to: str) -> None:
        run = TaskRun(pipeline_id="p1", status=frm)
        with pytest.raises(InvalidTaskTransitionError) as exc:
            run.transition(to)
        assert exc.value.current == frm
        assert exc.value.target == to

    def test_terminal_state_is_locked(self) -> None:
        run = TaskRun(pipeline_id="p1")
        run.start()
        run.succeed()
        with pytest.raises(InvalidTaskTransitionError):
            run.start()
        with pytest.raises(InvalidTaskTransitionError):
            run.fail("late")


class TestRetryAccounting:
    def test_can_retry_until_exhausted(self) -> None:
        run = TaskRun(pipeline_id="p1", max_attempts=2)
        run.start()
        assert run.can_retry()  # attempts 0 < 2
        run.schedule_retry()  # attempts 1
        run.start()
        assert run.can_retry()  # 1 < 2
        run.schedule_retry()  # attempts 2
        run.start()
        assert not run.can_retry()  # 2 < 2 False

    def test_exhausted_retries_then_fail_is_terminal(self) -> None:
        run = TaskRun(pipeline_id="p1", max_attempts=1)
        run.start()
        run.schedule_retry()  # attempts 1
        run.start()
        assert not run.can_retry()
        run.fail("exhausted")
        assert run.is_terminal()


class TestSerialization:
    def test_to_dict_contains_all_fields(self) -> None:
        run = TaskRun(
            pipeline_id="p1",
            tenant_id="acme",
            project_id="demo",
            payload={"keyword": "labubu"},
            trigger_source="im",
            trigger_id="evt_123",
            callback_url="https://example.com/cb",
        )
        d = run.to_dict()
        assert d["pipeline_id"] == "p1"
        assert d["tenant_id"] == "acme"
        assert d["status"] == TaskStatus.PENDING
        assert d["trigger_source"] == "im"
        assert d["trigger_id"] == "evt_123"

    def test_from_dict_roundtrip(self) -> None:
        run = TaskRun(
            pipeline_id="p1",
            tenant_id="acme",
            payload={"keyword": "labubu"},
            trigger_source="webhook",
        )
        run.start()
        run.succeed(result={"ok": True})
        restored = TaskRun.from_dict(run.to_dict())
        assert restored.run_id == run.run_id
        assert restored.status == TaskStatus.SUCCEEDED
        assert restored.result == {"ok": True}
        assert restored.pipeline_id == "p1"
        assert restored.trigger_source == "webhook"
        assert restored.started_at == run.started_at
        assert restored.finished_at == run.finished_at

    def test_from_dict_defaults_missing_fields(self) -> None:
        restored = TaskRun.from_dict({"pipeline_id": "p1"})
        assert restored.tenant_id == "default"
        assert restored.status == TaskStatus.PENDING
        assert restored.attempts == 0


class TestTerminalStates:
    def test_terminal_set(self) -> None:
        assert (
            frozenset({TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.CANCELLED})
            == TERMINAL_STATES
        )

    def test_non_terminal_states(self) -> None:
        for status in (
            TaskStatus.PENDING,
            TaskStatus.RUNNING,
            TaskStatus.RETRYING,
            TaskStatus.INTERRUPTED,
        ):
            assert status not in TERMINAL_STATES
