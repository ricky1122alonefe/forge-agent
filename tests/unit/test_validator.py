"""Tests for the hardened ContractValidator (T1.2).

Validates all 5 layers:
1. Structural (class / methods / classvars)
2. Import blacklist
3. Dangerous pattern (regex)
4. Cyclomatic complexity
5. Type annotation
"""
from __future__ import annotations

import pytest

from forge_agent.generator.validator import (
    ContractValidator,
    DANGEROUS_NAMES,
    ValidatorLimits,
)


# ----------------------------------------------------------------- Fixtures

@pytest.fixture
def v() -> ContractValidator:
    return ContractValidator()


@pytest.fixture
def v_strict() -> ContractValidator:
    return ContractValidator(limits=ValidatorLimits(max_complexity=5, max_function_lines=20))


# ----------------------------------------------------------------- Layer 1

def test_valid_agent_passes(v: ContractValidator) -> None:
    src = '''
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class GoodAgent(BaseAgent):
    agent_id = "test.good"
    name = "Good"

    async def observe(self, ctx: AgentContext) -> dict:
        return {}

    async def decide(self, ctx: AgentContext, obs: dict) -> dict:
        return {}

    async def act(self, ctx: AgentContext, dec: dict) -> AgentReport:
        return AgentReport(agent_id=self.agent_id, name=self.name)
'''
    r = v.validate_source(src)
    assert r.ok, f"expected ok, got errors: {r.errors}"
    assert r.info["checks_run"] == 5
    assert r.info["class_name"] == "GoodAgent"


def test_missing_methods_fails(v: ContractValidator) -> None:
    src = '''
class HalfBaked:
    agent_id = "test.half"
    name = "Half"
    async def observe(self, ctx): return {}
'''
    r = v.validate_source(src)
    assert not r.ok
    assert any("Missing required method" in e for e in r.errors)


# ----------------------------------------------------------------- Layer 2

def test_blocks_subprocess_import(v: ContractValidator) -> None:
    src = '''
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
import subprocess

class BadAgent(BaseAgent):
    agent_id = "test.bad"
    name = "Bad"
    async def observe(self, ctx: AgentContext) -> dict: return {}
    async def decide(self, ctx: AgentContext, o: dict) -> dict: return {}
    async def act(self, ctx: AgentContext, d: dict) -> AgentReport:
        return AgentReport(agent_id=self.agent_id, name=self.name)
'''
    r = v.validate_source(src)
    assert not r.ok
    assert any("subprocess" in e for e in r.errors)


def test_blocks_from_os_import_system(v: ContractValidator) -> None:
    src = '''
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from os import system

class BadAgent(BaseAgent):
    agent_id = "test.bad"
    name = "Bad"
    async def observe(self, ctx: AgentContext) -> dict: return {}
    async def decide(self, ctx: AgentContext, o: dict) -> dict: return {}
    async def act(self, ctx: AgentContext, d: dict) -> AgentReport:
        return AgentReport(agent_id=self.agent_id, name=self.name)
'''
    r = v.validate_source(src)
    assert not r.ok
    assert any("system" in e for e in r.errors)


def test_blocks_socket(v: ContractValidator) -> None:
    src = '''
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
import socket

class BadAgent(BaseAgent):
    agent_id = "test.bad"
    name = "Bad"
    async def observe(self, ctx: AgentContext) -> dict: return {}
    async def decide(self, ctx: AgentContext, o: dict) -> dict: return {}
    async def act(self, ctx: AgentContext, d: dict) -> AgentReport:
        return AgentReport(agent_id=self.agent_id, name=self.name)
'''
    r = v.validate_source(src)
    assert not r.ok
    assert any("socket" in e for e in r.errors)


# ----------------------------------------------------------------- Layer 3

def test_blocks_open_write(v: ContractValidator) -> None:
    src = '''
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class BadAgent(BaseAgent):
    agent_id = "test.bad"
    name = "Bad"
    async def observe(self, ctx: AgentContext) -> dict: return {}
    async def decide(self, ctx: AgentContext, o: dict) -> dict: return {}
    async def act(self, ctx: AgentContext, d: dict) -> AgentReport:
        with open("/etc/passwd", "w") as f:
            f.write("hacked")
        return AgentReport(agent_id=self.agent_id, name=self.name)
'''
    r = v.validate_source(src)
    assert not r.ok
    assert any("file write" in e for e in r.errors)


def test_blocks_eval(v: ContractValidator) -> None:
    src = '''
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class BadAgent(BaseAgent):
    agent_id = "test.bad"
    name = "Bad"
    async def observe(self, ctx: AgentContext) -> dict: return {}
    async def decide(self, ctx: AgentContext, o: dict) -> dict: return {}
    async def act(self, ctx: AgentContext, d: dict) -> AgentReport:
        result = eval("1+1")
        return AgentReport(agent_id=self.agent_id, name=self.name)
'''
    r = v.validate_source(src)
    assert not r.ok
    assert any("eval" in e for e in r.errors)


def test_blocks_rmtree(v: ContractValidator) -> None:
    src = '''
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
import shutil

class BadAgent(BaseAgent):
    agent_id = "test.bad"
    name = "Bad"
    async def observe(self, ctx: AgentContext) -> dict: return {}
    async def decide(self, ctx: AgentContext, o: dict) -> dict: return {}
    async def act(self, ctx: AgentContext, d: dict) -> AgentReport:
        shutil.rmtree("/")
        return AgentReport(agent_id=self.agent_id, name=self.name)
'''
    r = v.validate_source(src)
    assert not r.ok
    assert any("rmtree" in e for e in r.errors)


# ----------------------------------------------------------------- Layer 4

def test_blocks_high_complexity(v_strict: ContractValidator) -> None:
    """Function with >5 if branches exceeds strict cap."""
    src = '''
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class ComplexAgent(BaseAgent):
    agent_id = "test.complex"
    name = "Complex"
    async def observe(self, ctx: AgentContext) -> dict: return {}
    async def decide(self, ctx: AgentContext, o: dict) -> dict: return {}
    async def act(self, ctx: AgentContext, d: dict) -> AgentReport:
        if a:
            if b:
                if c:
                    if d:
                        if e:
                            if f:
                                pass
        return AgentReport(agent_id=self.agent_id, name=self.name)
'''
    r = v_strict.validate_source(src)
    assert not r.ok
    assert any("too complex" in e for e in r.errors)


def test_default_complexity_allows_10(v: ContractValidator) -> None:
    """Default cap is 10 — 7-branch function should pass."""
    src = '''
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class OkAgent(BaseAgent):
    agent_id = "test.ok"
    name = "Ok"
    async def observe(self, ctx: AgentContext) -> dict: return {}
    async def decide(self, ctx: AgentContext, o: dict) -> dict: return {}
    async def act(self, ctx: AgentContext, d: dict) -> AgentReport:
        if a: pass
        if b: pass
        if c: pass
        if e: pass
        if f: pass
        if g: pass
        if h: pass
        return AgentReport(agent_id=self.agent_id, name=self.name)
'''
    r = v.validate_source(src)
    complexity_errors = [e for e in r.errors if "too complex" in e]
    assert not complexity_errors, f"unexpected: {complexity_errors}"


# ----------------------------------------------------------------- Layer 5

def test_blocks_missing_return_type(v: ContractValidator) -> None:
    src = '''
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport

class UntypedAgent(BaseAgent):
    agent_id = "test.untyped"
    name = "Untyped"
    async def observe(self, ctx):
        return {}
    async def decide(self, ctx, o):
        return {}
    async def act(self, ctx, d):
        return AgentReport(agent_id=self.agent_id, name=self.name)
'''
    r = v.validate_source(src)
    assert not r.ok
    assert any("missing return type" in e for e in r.errors)


# ----------------------------------------------------------------- Misc

def test_syntax_error_short_circuits(v: ContractValidator) -> None:
    r = v.validate_source("def broken(:")
    assert not r.ok
    assert any("SyntaxError" in e for e in r.errors)


def test_dangerous_names_completeness() -> None:
    """Sanity: blacklists cover the critical attack surface."""
    from forge_agent.generator.validator import DANGEROUS_MODULES
    all_blocked = DANGEROUS_NAMES | DANGEROUS_MODULES
    must_have = {"os.system", "shutil.rmtree", "subprocess", "eval", "exec", "__import__"}
    assert must_have.issubset(all_blocked), (
        f"missing: {must_have - all_blocked}"
    )


def test_validate_class_method(v: ContractValidator) -> None:
    """validate_class (already-imported) is the fast path."""
    from forge_agent.core.base import BaseAgent
    from forge_agent.core.contracts import AgentReport
    from forge_agent.core.context import AgentContext
    from forge_agent.core.enums import Verdict

    class Demo(BaseAgent):
        agent_id = "test.demo"
        name = "Demo"
        async def observe(self, ctx: AgentContext) -> dict: return {}
        async def decide(self, ctx: AgentContext, o: dict) -> dict: return {}
        async def act(self, ctx: AgentContext, d: dict) -> AgentReport:
            return AgentReport(agent_id=self.agent_id, name=self.name, verdict=Verdict.NEUTRAL)

    r = v.validate_class(Demo)
    assert r.ok
