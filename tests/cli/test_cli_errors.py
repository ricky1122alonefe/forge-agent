"""Tests for CLI friendly error handling."""

from __future__ import annotations

from forge_agent.cli import main
from forge_agent.llm.exceptions import LLMAuthError


def test_main_prints_friendly_message_for_forge_error(capsys, monkeypatch) -> None:
    async def _fake_test(args) -> int:
        raise LLMAuthError(
            "API key for 'deepseek' not found.",
            provider="deepseek",
            hint="请设置 DEEPSEEK_API_KEY",
        )

    monkeypatch.setattr("forge_agent.cli.cmd_llm._test_async", _fake_test)

    rc = main(["llm", "test", "deepseek"])

    assert rc == 1
    captured = capsys.readouterr()
    assert "请设置 DEEPSEEK_API_KEY" in captured.err
    assert "Traceback" not in captured.err
