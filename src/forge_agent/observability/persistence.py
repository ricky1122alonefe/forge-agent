"""Persistence for execution traces.

Traces are written as structured JSON files under a project-level logs
directory, providing a durable audit trail of every pipeline run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from forge_agent.observability.trace import Trace


class TraceStore:
    """File-based store for pipeline execution traces.

    Layout::

        logs/
        ├── forge-agent.log          # structured text log
        ├── {trace_id}.json          # per-run trace
        └── latest_trace.json        # points to the latest trace file name
    """

    def __init__(self, logs_dir: str | Path) -> None:
        self.logs_dir = Path(logs_dir).expanduser().resolve()
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def _trace_path(self, trace_id: str) -> Path:
        return self.logs_dir / f"{trace_id}.json"

    def save(self, trace: Trace) -> Path:
        """Persist a trace to JSON and update the latest pointer."""
        path = self._trace_path(trace.trace_id)
        path.write_text(
            json.dumps(trace.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        latest = self.logs_dir / "latest_trace.json"
        latest.write_text(
            json.dumps({"latest_trace": path.name}, ensure_ascii=False), encoding="utf-8"
        )
        return path

    def get(self, trace_id: str) -> Trace | None:
        """Load a trace by id."""
        path = self._trace_path(trace_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Trace.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def list(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return metadata for the most recent traces."""
        traces = sorted(
            self.logs_dir.glob("trace_*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        result: list[dict[str, Any]] = []
        for path in traces[:limit]:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                result.append(
                    {
                        "trace_id": data.get("trace_id", path.stem),
                        "pipeline_id": data.get("pipeline_id", ""),
                        "start_time": data.get("start_time", ""),
                        "duration_ms": data.get("duration_ms", 0.0),
                        "span_count": len(data.get("spans", [])),
                    }
                )
            except (json.JSONDecodeError, OSError):
                continue
        return result
