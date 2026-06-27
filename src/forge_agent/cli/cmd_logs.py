"""`forge-agent logs` — inspect recent structured log output.

Reads from the local rotating log file (./logs/forge-agent.log by
default; override with --file or FORGE_LOG_FILE_PATH). The file is
written when FORGE_LOG_FILE=1 (or --log-file on `forge-agent new`).

By default, prints the last 50 entries. Use --follow to tail, --json to
dump raw JSON lines (one per line, pipeable to jq).

This command does NOT configure the global logger — it is a pure
reader of an existing file so the JSON it parses matches what was
written.
"""
from __future__ import annotations

import argparse
import json
import time
from collections import deque
from pathlib import Path
from typing import Any


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "logs",
        help="Show recent log entries (requires FORGE_LOG_FILE=1 to have written logs).",
    )
    p.add_argument(
        "--file", "-f",
        type=Path,
        default=None,
        help="Log file path (default: ./logs/forge-agent.log)",
    )
    p.add_argument(
        "--tail", "-n",
        type=int,
        default=50,
        help="Number of recent lines to show (default: 50)",
    )
    p.add_argument(
        "--follow", "-F",
        action="store_true",
        help="Like tail -f: keep reading new lines as they arrive",
    )
    p.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output raw JSON lines (one per line, jq-friendly). Default: human-readable.",
    )
    p.set_defaults(func=run)


def _default_log_file(project: Path) -> Path:
    return project / "logs" / "forge-agent.log"


def _read_last_n_lines(path: Path, n: int) -> list[str]:
    """Return the last N lines of a file efficiently (tail-from-end)."""
    if not path.exists():
        return []
    # Bounded memory: seek from end, read in chunks.
    block_size = 8192
    lines: deque[str] = deque(maxlen=n)
    with path.open("rb") as f:
        f.seek(0, 2)
        pos = f.tell()
        # Read everything in one go if the file is small.
        if pos <= block_size:
            f.seek(0)
            data = f.read(pos)
        else:
            # Bounded read: read enough trailing bytes to cover N lines.
            # Worst case: 1 byte per line; read 256 bytes per line.
            want = min(pos, max(block_size, n * 256))
            f.seek(pos - want)
            data = f.read(want)
            # Drop the first (possibly partial) line — we don't have the
            # rest of it, so we can't safely emit it.
            nl = data.find(b"\n")
            if nl >= 0:
                data = data[nl + 1:]
        for piece in data.splitlines():
            lines.append(piece.decode("utf-8", errors="replace"))
    return list(lines)


def _format_human(entry: dict[str, Any]) -> str:
    """Render a single log dict as a one-liner."""
    ts = entry.get("timestamp", "")
    lvl = (entry.get("level") or "info").upper().ljust(8)
    logger = entry.get("logger", "")
    agent = entry.get("agent_id", "")
    run = entry.get("run_id", "")
    event = entry.get("event", "")
    extra_keys = {
        k: v for k, v in entry.items()
        if k not in {"timestamp", "level", "logger", "event", "agent_id", "run_id"}
    }
    head = f"{ts} {lvl} {logger}"
    if agent:
        head += f" agent={agent}"
    if run:
        head += f" run={run}"
    line = f"{head} | {event}"
    if extra_keys:
        line += " " + " ".join(f"{k}={v!r}" for k, v in extra_keys.items())
    return line


def _parse_line(line: str) -> dict[str, Any] | None:
    """Parse a single line as JSON; return None if not valid."""
    line = line.strip()
    if not line or not line.startswith("{"):
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def run(args: argparse.Namespace) -> int:
    path = args.file or _default_log_file(args.project)
    if not path.exists():
        print(
            f"No log file at {path}.\n"
            f"Enable file logging by setting FORGE_LOG_FILE=1 in the environment, "
            f"or pass --file to point at a custom path.",
            file=__import__("sys").stderr,
        )
        return 1

    last_size = path.stat().st_size
    lines = _read_last_n_lines(path, args.tail)
    for line in lines:
        _emit(line, args.json)

    if not args.follow:
        return 0

    # ---- follow mode (tail -f semantics) ----
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            f.seek(last_size)
            while True:
                chunk = f.readline()
                if chunk:
                    _emit(chunk, args.json)
                else:
                    time.sleep(0.2)
    except KeyboardInterrupt:
        return 0


def _emit(line: str, as_json: bool) -> None:
    if as_json:
        # Pass-through (already JSON); just print as-is.
        print(line)
        return
    entry = _parse_line(line)
    if entry is None:
        # Non-JSON line (e.g. an old log); print verbatim.
        print(line)
    else:
        print(_format_human(entry))
