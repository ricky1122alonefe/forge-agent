"""Agent discovery (entry-points + filesystem scan).

Two strategies to surface agents without manual imports:

1.  Python entry-points (preferred for plugins)::

        # in a plugin's pyproject.toml
        [project.entry-points."forge_agent.agents"]
        my_agent = "my_pkg.agents:MyAgent"

2.  Filesystem scan (useful in dev / monorepo layouts) — auto-import every
    `*_agent.py` module under a directory and let @register_agent register.

This is intentionally pluggable; the Generator (v0.2) will rely on this.
"""

from __future__ import annotations

import importlib
import importlib.util
import logging
from pathlib import Path
from typing import Iterable

log = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "forge_agent.agents"


def discover_entry_points() -> list[str]:
    """Discover agents registered via Python entry-points.

    Returns a list of successfully-registered agent_ids.
    """
    try:
        from importlib.metadata import entry_points
    except ImportError:  # pragma: no cover
        from importlib_metadata import entry_points  # type: ignore[no-redef]

    try:
        eps = entry_points(group=ENTRY_POINT_GROUP)
    except Exception:  # noqa: BLE001
        log.exception("Failed to enumerate entry-points")
        return []

    registered: list[str] = []
    for ep in eps:
        try:
            obj = ep.load()
            log.info("Loaded entry-point %s -> %s", ep.name, obj)
            registered.append(getattr(obj, "agent_id", ep.name))
        except Exception:  # noqa: BLE001
            log.exception("Failed to load entry-point %s", ep.name)
    return registered


def discover_filesystem(root: str | Path, *, package_prefix: str = "") -> int:
    """Import every `*_agent.py` under `root`, triggering @register_agent.

    Returns the number of files imported (registered agents may be fewer).
    """
    root = Path(root)
    if not root.is_dir():
        return 0
    count = 0
    for path in root.rglob("*_agent.py"):
        if path.name == "__init__.py":
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                name=f"{package_prefix}.{path.stem}" if package_prefix else path.stem,
                location=str(path),
            )
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[union-attr]
            count += 1
            log.info("Imported agent module: %s", path)
        except Exception:  # noqa: BLE001
            log.exception("Failed to import %s", path)
    return count
