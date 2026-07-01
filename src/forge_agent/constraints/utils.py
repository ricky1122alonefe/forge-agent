"""Utility helpers for the constraints framework."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from forge_agent.constraints.engine import ConstraintEngine
from forge_agent.constraints.policy import ConstraintPolicy


def create_constraint_engine(config: dict[str, Any] | None) -> ConstraintEngine | None:
    """Build a ConstraintEngine from configuration.

    Config keys:
        - enabled: bool (default True). If False, returns None.
        - policies: list[dict] — inline policy definitions
        - yaml_path: str | list[str] — path(s) to YAML policy files
        - builtin: str | list[str] — name(s) of built-in policy files under
          ``src/forge_agent/builtin/constraints/``

    Examples::

        create_constraint_engine(None)  # None
        create_constraint_engine({"enabled": False})  # None

        create_constraint_engine(
            {
                "builtin": "compliance",
                "policies": [{"id": "custom", "trigger": "output", "patterns": ["x"]}],
            }
        )
    """
    cfg = dict(config or {})
    if not cfg or not cfg.get("enabled", True):
        return None

    engine = ConstraintEngine()

    # Load built-in policies.
    builtins = cfg.get("builtin", [])
    if isinstance(builtins, str):
        builtins = [builtins]
    for name in builtins:
        path = Path(__file__).resolve().parent.parent / "builtin" / "constraints" / f"{name}.yaml"
        engine.load_yaml(path)

    # Load external YAML files.
    yaml_paths = cfg.get("yaml_path", [])
    if isinstance(yaml_paths, str):
        yaml_paths = [yaml_paths]
    for path in yaml_paths:
        engine.load_yaml(path)

    # Load inline policies.
    for raw in cfg.get("policies", []):
        engine.add_policy(ConstraintPolicy.from_dict(raw))

    return engine
