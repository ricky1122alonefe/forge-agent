"""JSON helpers (dataclass → JSON)."""

from __future__ import annotations

import json
from typing import Any


def to_json(obj: Any, *, indent: int | None = 2) -> str:
    return json.dumps(obj, indent=indent, ensure_ascii=False, default=str)


def from_json(s: str) -> Any:
    return json.loads(s)
