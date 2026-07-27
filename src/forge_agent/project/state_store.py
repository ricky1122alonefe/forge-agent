"""Deprecated: import from forge_agent.runtime.state_store instead.

This shim keeps existing imports working during the S2 migration.
Will be removed once all references point to runtime.state_store.
"""

from __future__ import annotations

from forge_agent.runtime.state_store import (  # noqa: F401
    RunRecord,
    StateStore,
    generate_run_id,
)
