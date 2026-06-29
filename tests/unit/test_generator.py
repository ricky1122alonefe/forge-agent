"""Unit tests for the Generator (validator + injector)."""

from __future__ import annotations

from forge_agent.generator.injector import AgentInjector
from forge_agent.generator.validator import ContractValidator
from forge_agent.registry.registry import get_registry

SOURCE_OK = """
from forge_agent.core.base import BaseAgent
from forge_agent.core.contracts import AgentReport
from forge_agent.core.context import AgentContext
from forge_agent.core.enums import Verdict


class MyAgent(BaseAgent):
    agent_id = "gen.my"
    name = "My Agent"

    async def observe(self, ctx: AgentContext) -> dict:
        return {}

    async def decide(self, ctx: AgentContext, obs: dict) -> dict:
        return {}

    async def act(self, ctx: AgentContext, dec: dict) -> AgentReport:
        return AgentReport(agent_id=self.agent_id, name=self.name, verdict=Verdict.NEUTRAL)
"""


SOURCE_BAD = """
class NotAnAgent:
    def hello(self):
        return 1
"""


SOURCE_INCOMPLETE = """
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext


class HalfBaked(BaseAgent):
    agent_id = "gen.half"
    name = "Half"

    async def observe(self, ctx: AgentContext) -> dict:
        return {}
    # missing decide / act
"""


def test_validator_passes_good_source():
    v = ContractValidator()
    r = v.validate_source(SOURCE_OK)
    assert r.ok is True
    assert r.errors == []


def test_validator_flags_non_agent():
    v = ContractValidator()
    r = v.validate_source(SOURCE_BAD)
    assert r.ok is False
    assert any("No class" in e or "Missing" in e for e in r.errors)


def test_validator_flags_missing_methods():
    v = ContractValidator()
    r = v.validate_source(SOURCE_INCOMPLETE)
    assert r.ok is False
    assert any("decide" in e for e in r.errors)
    assert any("act" in e for e in r.errors)


def test_injector_registers_valid_class():
    inj = AgentInjector()
    _cls, v = inj.inject_source(SOURCE_OK)
    assert v.ok
    assert "gen.my" in get_registry()


def test_injector_rejects_invalid_source():
    inj = AgentInjector()
    _cls, v = inj.inject_source(SOURCE_INCOMPLETE)
    assert v.ok is False
    assert "gen.half" not in get_registry()
