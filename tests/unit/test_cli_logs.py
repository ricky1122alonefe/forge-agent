"""Tests for the `forge-agent logs` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

from forge_agent.cli import cmd_logs


def _write_log_lines(path: Path, n: int) -> None:
    """Write N fake JSON log lines to a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for i in range(n):
            entry = {
                "timestamp": f"2026-06-27T10:00:{i:02d}Z",
                "level": "info",
                "logger": "forge_agent.test",
                "event": f"event_{i}",
                "agent_id": f"a{i}",
                "run_id": f"r{i}",
            }
            f.write(json.dumps(entry) + "\n")


class _Args:
    """Minimal argparse.Namespace stand-in."""

    def __init__(self, project: Path, file: Path | None, tail: int, follow: bool, as_json: bool):
        self.project = project
        self.file = file
        self.tail = tail
        self.follow = follow
        self.json = as_json


def test_logs_human_format(tmp_path: Path, capsys):
    log = tmp_path / "forge-agent.log"
    _write_log_lines(log, 3)

    args = _Args(project=tmp_path, file=log, tail=10, follow=False, as_json=False)
    rc = cmd_logs.run(args)
    assert rc == 0
    out = capsys.readouterr().out
    # Should have rendered each event_N as a human-readable line
    assert "event_0" in out
    assert "event_1" in out
    assert "event_2" in out
    # And show the level column
    assert "INFO" in out


def test_logs_json_format(tmp_path: Path, capsys):
    log = tmp_path / "forge-agent.log"
    _write_log_lines(log, 2)

    args = _Args(project=tmp_path, file=log, tail=10, follow=False, as_json=True)
    rc = cmd_logs.run(args)
    assert rc == 0
    out = capsys.readouterr().out
    lines = [ln for ln in out.splitlines() if ln.strip()]
    # Each emitted line should be valid JSON
    for ln in lines:
        entry = json.loads(ln)
        assert "event" in entry


def test_logs_tail_limit(tmp_path: Path, capsys):
    log = tmp_path / "forge-agent.log"
    _write_log_lines(log, 20)

    args = _Args(project=tmp_path, file=log, tail=5, follow=False, as_json=False)
    rc = cmd_logs.run(args)
    assert rc == 0
    out = capsys.readouterr().out
    # Only the last 5 events should be present
    for i in range(15, 20):
        assert f"event_{i}" in out
    # Earlier events should be dropped
    assert "event_0" not in out
    assert "event_10" not in out


def test_logs_missing_file(tmp_path, capsys):
    args = _Args(project=tmp_path, file=None, tail=10, follow=False, as_json=False)
    rc = cmd_logs.run(args)
    # Non-zero exit code; helpful message on stderr
    assert rc == 1
    err = capsys.readouterr().err
    assert "FORGE_LOG_FILE" in err or "log file" in err.lower()
