"""Store and query pipeline execution results per project."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class RunRecord:
    """A single pipeline execution record."""

    run_id: str
    timestamp: str
    pipeline_id: str
    pipeline_name: str
    tenant_id: str
    project_id: str
    payload: dict[str, Any]
    agent_reports: list[dict[str, Any]]
    chief_summary: dict[str, Any] | None
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunRecord:
        return cls(**data)


class StateStore:
    """File-based state store for a single project."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self.state_dir = project_root / "state"
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _record_path(self, run_id: str) -> Path:
        return self.state_dir / f"{run_id}.json"

    def _latest_path(self) -> Path:
        return self.state_dir / "latest.json"

    def save(self, record: RunRecord) -> Path:
        """Save a run record and update latest.json."""
        path = self._record_path(record.run_id)
        path.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        shutil.copy2(path, self._latest_path())
        return path

    def list(self) -> list[RunRecord]:
        """Return all stored run records, newest first."""
        records: list[RunRecord] = []
        for path in sorted(self.state_dir.glob("*.json"), reverse=True):
            if path.name == "latest.json":
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                records.append(RunRecord.from_dict(data))
            except (json.JSONDecodeError, TypeError):
                continue
        return records

    def get(self, run_id: str) -> RunRecord | None:
        """Return a specific run record."""
        path = self._record_path(run_id)
        if not path.exists():
            return None
        try:
            return RunRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError):
            return None

    def latest(self) -> RunRecord | None:
        """Return the latest run record."""
        path = self._latest_path()
        if not path.exists():
            return None
        try:
            return RunRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, TypeError):
            return None


def generate_run_id(pipeline_id: str) -> str:
    """Generate a unique run id based on timestamp."""
    now = datetime.now(timezone.utc)
    return f"{now.strftime('%Y%m%d_%H%M%S')}_{pipeline_id}"
