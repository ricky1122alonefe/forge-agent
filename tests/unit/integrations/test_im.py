"""Tests for IM integration (S5.1-S5.5).

Covers Feishu/DingTalk event parsing, DefaultIMRouter command handling,
formatters, and IMCallback — all with mocked HTTP (no real API calls).
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from forge_agent.integrations.im.base import IMEvent, IMMessage
from forge_agent.integrations.im.callback import IMCallback
from forge_agent.integrations.im.default_router import DefaultIMRouter
from forge_agent.integrations.im.dingtalk import DingTalkAdapter
from forge_agent.integrations.im.feishu import FeishuAdapter
from forge_agent.integrations.im.text_formatter import (
    FeishuCardFormatter,
    TextReportFormatter,
)
from forge_agent.runtime.models import TaskRun
from forge_agent.runtime.retry import RetryPolicy
from forge_agent.runtime.sqlite_store import SQLiteTaskStore
from forge_agent.runtime.task_runner import TaskRunner

# -- mock executors ----------------------------------------------------------


class SuccessExecutor:
    async def execute(
        self, pipeline_id: str, payload: dict[str, Any], run_id: str
    ) -> dict[str, Any]:
        return {"chief_summary": {"verdict": "positive", "confidence": 0.85}}


class FastFailExecutor:
    async def execute(
        self, pipeline_id: str, payload: dict[str, Any], run_id: str
    ) -> dict[str, Any]:
        raise RuntimeError("boom")


# -- fixtures ----------------------------------------------------------------


@pytest.fixture
def store(tmp_path):
    s = SQLiteTaskStore(db_path=tmp_path / "test_im.db")
    yield s
    s.close()


@pytest.fixture
def runner(store):
    return TaskRunner(store, SuccessExecutor(), retry=RetryPolicy(max_attempts=0))


@pytest.fixture
def project_root(tmp_path):
    (tmp_path / "pipelines").mkdir()
    (tmp_path / "pipelines" / "trend.yaml").write_text("test", encoding="utf-8")
    (tmp_path / "pipelines" / "report.yaml").write_text("test", encoding="utf-8")
    return tmp_path


@pytest.fixture
def router(runner, project_root):
    return DefaultIMRouter(runner, project_root=project_root)


# -- S5.1: FeishuAdapter -----------------------------------------------------


def _mock_httpx_response(status_code: int = 200, json_body: dict | None = None):
    """Create a mock httpx.Response (non-async json method)."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.text = json.dumps(json_body or {})
    return resp


class TestFeishuAdapter:
    def test_parse_message_event(self) -> None:
        raw = {
            "header": {"event_type": "im.message.receive_v1"},
            "event": {
                "message": {
                    "chat_id": "oc_test123",
                    "content": json.dumps({"text": "/run trend"}),
                },
                "sender": {"sender_id": {"open_id": "u_abc"}},
            },
        }
        adapter = FeishuAdapter("https://example.com/hook")
        event = adapter.parse_event(raw)
        assert event.platform == "feishu"
        assert event.chat_id == "oc_test123"
        assert event.user_id == "u_abc"
        assert event.text == "/run trend"
        assert event.command == "/run"
        assert event.args == ["trend"]

    def test_parse_challenge(self) -> None:
        raw = {"challenge": "verify_me"}
        adapter = FeishuAdapter("https://example.com/hook")
        event = adapter.parse_event(raw)
        assert event.event_type == "challenge"
        assert event.text == "verify_me"

    def test_parse_plain_text(self) -> None:
        raw = {
            "event": {
                "message": {
                    "chat_id": "c1",
                    "content": json.dumps({"text": "hello world"}),
                },
                "sender": {"sender_id": {"open_id": "u1"}},
            },
        }
        adapter = FeishuAdapter("https://example.com/hook")
        event = adapter.parse_event(raw)
        assert event.text == "hello world"
        assert event.command == ""

    async def test_send_text(self) -> None:
        adapter = FeishuAdapter("https://example.com/hook")
        msg = IMMessage(platform="feishu", chat_id="c1", text="hello")
        mock_resp = _mock_httpx_response(200, {"code": 0})
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value = mock_client
            result = await adapter.send(msg)
        assert result is True
        sent = mock_client.post.call_args.kwargs["json"]
        assert sent["msg_type"] == "text"
        assert sent["content"]["text"] == "hello"

    async def test_send_card(self) -> None:
        adapter = FeishuAdapter("https://example.com/hook")
        msg = IMMessage(
            platform="feishu",
            chat_id="c1",
            card={"config": {}, "elements": []},
        )
        mock_resp = _mock_httpx_response(200, {"code": 0})
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value = mock_client
            result = await adapter.send(msg)
        assert result is True
        sent = mock_client.post.call_args.kwargs["json"]
        assert sent["msg_type"] == "interactive"


# -- S5.5: DingTalkAdapter ---------------------------------------------------


class TestDingTalkAdapter:
    def test_parse_message(self) -> None:
        raw = {
            "text": {"content": "/status run_123 "},
            "conversationId": "cid123",
            "senderStaffId": "staff_abc",
        }
        adapter = DingTalkAdapter("https://oapi.dingtalk.com/robot/send?access_token=x")
        event = adapter.parse_event(raw)
        assert event.platform == "dingtalk"
        assert event.chat_id == "cid123"
        assert event.user_id == "staff_abc"
        assert event.command == "/status"
        assert event.args == ["run_123"]

    def test_parse_plain_text(self) -> None:
        raw = {"text": {"content": "hello"}, "conversationId": "c1"}
        adapter = DingTalkAdapter("https://example.com")
        event = adapter.parse_event(raw)
        assert event.text == "hello"
        assert event.command == ""

    async def test_send_text(self) -> None:
        adapter = DingTalkAdapter("https://example.com/hook?access_token=t")
        msg = IMMessage(platform="dingtalk", chat_id="c1", text="test msg")
        mock_resp = _mock_httpx_response(200, {"errcode": 0})
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.post.return_value = mock_resp
            mock_client_cls.return_value = mock_client
            result = await adapter.send(msg)
        assert result is True
        sent = mock_client.post.call_args.kwargs["json"]
        assert sent["msgtype"] == "text"

    def test_signed_url_with_secret(self) -> None:
        adapter = DingTalkAdapter(
            "https://example.com/hook?access_token=t",
            secret="SEC123",
        )
        url = adapter._signed_url()
        assert "timestamp=" in url
        assert "sign=" in url


# -- S5.2: DefaultIMRouter ---------------------------------------------------


class TestDefaultIMRouter:
    async def test_run_command(self, router: DefaultIMRouter, store) -> None:
        event = IMEvent(
            platform="feishu",
            event_type="message",
            chat_id="oc_test",
            user_id="u1",
            text="/run trend",
            command="/run",
            args=["trend"],
            raw={"event_id": "evt_1"},
        )
        reply = await router.handle(event)
        assert "✅" in reply
        assert "trend" in reply
        runs = store.list(pipeline_id="trend")
        assert len(runs) == 1
        assert runs[0].trigger_source == "im"
        assert runs[0].metadata.get("im_chat_id") == "oc_test"

    async def test_run_with_payload(self, router: DefaultIMRouter, store) -> None:
        event = IMEvent(
            platform="feishu",
            event_type="message",
            chat_id="c1",
            user_id="u1",
            text='/run trend {"q": "labubu"}',
            command="/run",
            args=["trend", '{"q": "labubu"}'],
            raw={},
        )
        reply = await router.handle(event)
        assert "✅" in reply
        runs = store.list(pipeline_id="trend")
        assert runs[0].payload == {"q": "labubu"}

    async def test_run_invalid_json(self, router: DefaultIMRouter) -> None:
        event = IMEvent(
            platform="feishu",
            event_type="message",
            chat_id="c1",
            user_id="u1",
            text="/run trend {bad json}",
            command="/run",
            args=["trend", "{bad", "json}"],
            raw={},
        )
        reply = await router.handle(event)
        assert "❌" in reply
        assert "JSON" in reply

    async def test_run_no_args(self, router: DefaultIMRouter) -> None:
        event = IMEvent(
            platform="feishu",
            event_type="message",
            chat_id="c1",
            user_id="u1",
            text="/run",
            command="/run",
            args=[],
            raw={},
        )
        reply = await router.handle(event)
        assert "Usage" in reply

    async def test_status_command(self, router: DefaultIMRouter, store) -> None:
        run = TaskRun(pipeline_id="p1")
        store.create(run)
        event = IMEvent(
            platform="feishu",
            event_type="message",
            chat_id="c1",
            user_id="u1",
            text=f"/status {run.run_id}",
            command="/status",
            args=[run.run_id],
            raw={},
        )
        reply = await router.handle(event)
        assert run.run_id in reply
        assert "pending" in reply

    async def test_status_not_found(self, router: DefaultIMRouter) -> None:
        event = IMEvent(
            platform="feishu",
            event_type="message",
            chat_id="c1",
            user_id="u1",
            text="/status ghost",
            command="/status",
            args=["ghost"],
            raw={},
        )
        reply = await router.handle(event)
        assert "not found" in reply

    async def test_list_command(self, router: DefaultIMRouter) -> None:
        event = IMEvent(
            platform="feishu",
            event_type="message",
            chat_id="c1",
            user_id="u1",
            text="/list",
            command="/list",
            args=[],
            raw={},
        )
        reply = await router.handle(event)
        assert "trend" in reply
        assert "report" in reply

    async def test_help_command(self, router: DefaultIMRouter) -> None:
        event = IMEvent(
            platform="feishu",
            event_type="message",
            chat_id="c1",
            user_id="u1",
            text="/help",
            command="/help",
            args=[],
            raw={},
        )
        reply = await router.handle(event)
        assert "/run" in reply
        assert "/status" in reply
        assert "/list" in reply

    async def test_unknown_command(self, router: DefaultIMRouter) -> None:
        event = IMEvent(
            platform="feishu",
            event_type="message",
            chat_id="c1",
            user_id="u1",
            text="/unknown",
            command="/unknown",
            args=[],
            raw={},
        )
        reply = await router.handle(event)
        assert "Unknown" in reply

    async def test_no_command_shows_help(self, router: DefaultIMRouter) -> None:
        event = IMEvent(
            platform="feishu",
            event_type="message",
            chat_id="c1",
            user_id="u1",
            text="hello",
            command="",
            args=[],
            raw={},
        )
        reply = await router.handle(event)
        assert "/run" in reply  # shows help

    async def test_challenge_event(self, router: DefaultIMRouter) -> None:
        event = IMEvent(
            platform="feishu",
            event_type="challenge",
            chat_id="",
            user_id="",
            text="verify_token_123",
            raw={},
        )
        reply = await router.handle(event)
        assert reply == "verify_token_123"


# -- S5.3: Formatters --------------------------------------------------------


class TestTextReportFormatter:
    def test_format_success(self) -> None:
        fmt = TextReportFormatter()
        msg = fmt.format_success(
            platform="feishu",
            chat_id="c1",
            run_id="run_abc",
            pipeline_id="trend",
            result={"chief_summary": {"verdict": "positive", "confidence": 0.9}},
        )
        assert "✅" in msg.text
        assert "trend" in msg.text
        assert "positive" in msg.text
        assert "0.9" in msg.text

    def test_format_success_empty_result(self) -> None:
        fmt = TextReportFormatter()
        msg = fmt.format_success(
            platform="feishu",
            chat_id="c1",
            run_id="r1",
            pipeline_id="p1",
            result={},
        )
        assert "✅" in msg.text
        assert "p1" in msg.text

    def test_format_failure(self) -> None:
        fmt = TextReportFormatter()
        msg = fmt.format_failure(
            platform="dingtalk",
            chat_id="c1",
            run_id="r1",
            pipeline_id="p1",
            error="timeout",
        )
        assert "❌" in msg.text
        assert "timeout" in msg.text


class TestFeishuCardFormatter:
    def test_format_success_card(self) -> None:
        fmt = FeishuCardFormatter()
        msg = fmt.format_success(
            platform="feishu",
            chat_id="c1",
            run_id="r1",
            pipeline_id="p1",
            result={"chief_summary": {"verdict": "positive", "confidence": 0.9}},
        )
        assert msg.card is not None
        assert msg.card["header"]["template"] == "green"
        elements = msg.card["elements"]
        assert len(elements) >= 3
        assert any("positive" in str(e) for e in elements)

    def test_format_failure_card(self) -> None:
        fmt = FeishuCardFormatter()
        msg = fmt.format_failure(
            platform="feishu",
            chat_id="c1",
            run_id="r1",
            pipeline_id="p1",
            error="connection refused",
        )
        assert msg.card is not None
        assert msg.card["header"]["template"] == "red"
        assert any("connection refused" in str(e) for e in msg.card["elements"])


# -- S5.4: IMCallback --------------------------------------------------------


class TestIMCallback:
    async def test_callback_on_success(self) -> None:
        adapter = AsyncMock(spec=FeishuAdapter)
        adapter.platform = "feishu"
        adapter.send.return_value = True
        fmt = TextReportFormatter()
        cb = IMCallback(adapter, fmt, default_chat_id="oc_test")

        run = TaskRun(pipeline_id="p1")
        run.start()
        run.succeed(result={"chief_summary": {"verdict": "ok"}})

        await cb.on_terminal(run)
        adapter.send.assert_called_once()
        msg = adapter.send.call_args[0][0]
        assert msg.chat_id == "oc_test"
        assert "✅" in msg.text

    async def test_callback_on_failure(self) -> None:
        adapter = AsyncMock(spec=FeishuAdapter)
        adapter.platform = "feishu"
        adapter.send.return_value = True
        cb = IMCallback(adapter, TextReportFormatter(), default_chat_id="c1")

        run = TaskRun(pipeline_id="p1")
        run.start()
        run.fail("network error")

        await cb.on_terminal(run)
        adapter.send.assert_called_once()
        msg = adapter.send.call_args[0][0]
        assert "❌" in msg.text
        assert "network error" in msg.text

    async def test_callback_skips_cancelled(self) -> None:
        adapter = AsyncMock(spec=FeishuAdapter)
        cb = IMCallback(adapter, TextReportFormatter(), default_chat_id="c1")

        run = TaskRun(pipeline_id="p1")
        run.cancel()

        await cb.on_terminal(run)
        adapter.send.assert_not_called()

    async def test_callback_skips_when_no_chat_id(self) -> None:
        adapter = AsyncMock(spec=FeishuAdapter)
        cb = IMCallback(adapter, TextReportFormatter())  # no default_chat_id

        run = TaskRun(pipeline_id="p1")
        run.start()
        run.succeed(result={})

        await cb.on_terminal(run)
        adapter.send.assert_not_called()

    async def test_callback_uses_metadata_chat_id(self) -> None:
        adapter = AsyncMock(spec=FeishuAdapter)
        adapter.platform = "feishu"
        adapter.send.return_value = True
        cb = IMCallback(adapter, TextReportFormatter())

        run = TaskRun(pipeline_id="p1", metadata={"im_chat_id": "oc_from_meta"})
        run.start()
        run.succeed(result={})

        await cb.on_terminal(run)
        adapter.send.assert_called_once()
        msg = adapter.send.call_args[0][0]
        assert msg.chat_id == "oc_from_meta"
