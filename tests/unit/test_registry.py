"""Unit tests for AgentRegistry & @register_agent.

Agents are defined INSIDE each test so the autouse fixture can clear
the registry between tests.
"""

from __future__ import annotations

import pytest

from forge_agent.core.base import BaseAgent
from forge_agent.core.contracts import AgentReport
from forge_agent.core.context import AgentContext
from forge_agent.registry.decorators import register_agent
from forge_agent.registry.registry import get_registry


def _make_cls(agent_id: str, name: str, domain: str = "t", tags=None):
    # Use default-arg trick to capture variables in class body.
    class _T(BaseAgent):
        async def observe(self, ctx, _aid=agent_id, _nm=name):
            return {}

        async def decide(self, ctx, o, _aid=agent_id):
            return {}

        async def act(self, ctx, d, _aid=agent_id, _nm=name):
            return AgentReport(agent_id=_aid, name=_nm)
    _T.agent_id = agent_id
    _T.name = name
    _T.domain = domain
    _T.__name__ = name
    return _T


def test_singleton():
    assert get_registry() is get_registry()


def test_register_list():
    A = _make_cls("t.a", "A")
    B = _make_cls("t.b", "B")
    register_agent(domain="t", tags=["b"])(A)
    register_agent(domain="t", tags=["a"])(B)
    r = get_registry()
    assert "t.a" in r
    assert "t.b" in r
    assert set(r.list(domain="t")) == {"t.a", "t.b"}
    assert r.list(tag="b") == ["t.a"]


@pytest.mark.asyncio
async def test_get_initializes_once():
    A = _make_cls("t.a", "A")
    register_agent()(A)
    r = get_registry()
    a1 = await r.get("t.a")
    a2 = await r.get("t.a")
    assert a1 is a2


@pytest.mark.asyncio
async def test_unregister_clears():
    A = _make_cls("t.a", "A")
    register_agent()(A)
    r = get_registry()
    a = await r.get("t.a")
    r.unregister("t.a")
    assert "t.a" not in r


def test_duplicate_register_raises():
    A = _make_cls("t.a", "A")
    Dup = _make_cls("t.a", "Dup")
    register_agent()(A)
    r = get_registry()
    with pytest.raises(ValueError):
        r.register(Dup)
    r.register(Dup, override=True)
    assert r.get_metadata("t.a")["class_name"] == "Dup"
