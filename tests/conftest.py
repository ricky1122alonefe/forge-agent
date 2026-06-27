"""Shared pytest fixtures & hooks.

Strategy: defer registry creation until the FIRST test that calls
`get_registry()`. Use a `pytest_collection_start` hook to clear any
singleton that may have been created during module import.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def pytest_configure(config: pytest.Config) -> None:
    """Reset the AgentRegistry before any test starts.

    Hooks into pytest_configure (very early in pytest lifecycle) so any
    state created during test collection is wiped before the first test.
    """
    from forge_agent.registry.registry import AgentRegistry

    inst = AgentRegistry._instance
    if inst is not None:
        inst._classes.clear()
        inst._instances.clear()
        inst._metadata.clear()


@pytest.fixture(autouse=True)
def _autouse_clear():
    """Wipe the AgentRegistry & LLMRegistry before & after each test."""
    from forge_agent.registry.registry import AgentRegistry
    from forge_agent.llm.registry import LLMRegistry
    from forge_agent.llm import protocol as _llm_protocol

    inst = AgentRegistry._instance
    if inst is not None:
        inst._classes.clear()
        inst._instances.clear()
        inst._metadata.clear()

    llm_inst = LLMRegistry._instance
    if llm_inst is not None:
        llm_inst._clients.clear()
        llm_inst._config = None

    # Also reset the module-level default in llm.protocol
    _llm_protocol._DEFAULT_REGISTRY = None

    yield

    if inst is not None:
        inst._classes.clear()
        inst._instances.clear()
        inst._metadata.clear()
    if llm_inst is not None:
        llm_inst._clients.clear()
        llm_inst._config = None
    _llm_protocol._DEFAULT_REGISTRY = None


@pytest.fixture
def fresh_registry():
    """Explicit accessor (same effect as autouse)."""
    yield
