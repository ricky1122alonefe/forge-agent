"""Unit tests for forge_agent.generator (v0.2)."""

from __future__ import annotations

import asyncio
import json

import pytest

from forge_agent.generator.manifest import Manifest
from forge_agent.generator.pipeline import DeployMode, GenerationPipeline
from forge_agent.generator.requirements import (
    AgentRequirements,
    FieldSpec,
    RequirementsParser,
)
from forge_agent.generator.sandbox import Sandbox
from forge_agent.generator.store import FileCodeStore
from forge_agent.generator.validator import ContractValidator

# ------------------------------------------------------------------ Requirements


def test_requirements_parser_heuristic_domain_football():
    p = RequirementsParser()  # no LLM
    req = "监控世界杯球赛，QAT vs IDN"
    spec = asyncio.run(p.parse(req))
    assert spec.domain == "football"
    assert "log" in spec.capabilities_required


def test_requirements_parser_heuristic_domain_stock():
    p = RequirementsParser()
    spec = asyncio.run(p.parse("监控NVDA股票价格"))
    assert spec.domain == "stock"


def test_requirements_parser_with_mock_llm():
    from forge_agent.llm.config import ProviderConfig
    from forge_agent.llm.protocol import LLMResponse
    from forge_agent.llm.providers.mock import MockClient

    cfg = ProviderConfig(provider_id="mock", type="mock", model="x")
    MockClient(cfg)

    async def _llm_chat(messages, **kwargs):
        # Return a JSON spec
        return LLMResponse(
            content=json.dumps(
                {
                    "agent_id": "stock.nvda",
                    "name": "NVDA Stock",
                    "domain": "stock",
                    "description": "Monitors NVDA",
                    "inputs": [{"name": "ticker", "type": "str", "description": "Symbol"}],
                    "outputs": [{"name": "verdict", "type": "str", "description": "Decision"}],
                    "capabilities_required": ["llm", "search"],
                }
            ),
            provider="mock",
            model="x",
        )

    p = RequirementsParser(llm_chat=_llm_chat)
    spec = asyncio.run(p.parse("monitor NVDA"))
    assert spec.agent_id == "stock.nvda"
    assert spec.domain == "stock"
    assert "llm" in spec.capabilities_required


# ------------------------------------------------------------------ Validator


def test_validator_rejects_incomplete_source():
    v = ContractValidator()
    r = v.validate_source("class X: pass")  # no BaseAgent, no methods
    assert not r.ok


def test_validator_passes_minimal_agent():
    v = ContractValidator()
    src = """
from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
class MyAgent(BaseAgent):
    agent_id = "test.my"
    name = "My"
    async def observe(self, ctx: AgentContext) -> dict: return {}
    async def decide(self, ctx: AgentContext, o: dict) -> dict: return {}
    async def act(self, ctx: AgentContext, d: dict) -> AgentReport:
        return AgentReport(agent_id=self.agent_id, name=self.name)
"""
    r = v.validate_source(src)
    assert r.ok or len(r.errors) == 0


# ------------------------------------------------------------------ Sandbox


@pytest.mark.asyncio
async def test_sandbox_blocks_subprocess_import(tmp_path):
    sb = Sandbox()
    bad_src = """
import subprocess
from forge_agent.core.base import BaseAgent
class BadAgent(BaseAgent):
    agent_id = "test.bad"
    name = "Bad"
    async def observe(self, ctx): return {}
    async def decide(self, ctx, o): return {}
    async def act(self, ctx, d):
        from forge_agent.core.contracts import AgentReport
        return AgentReport(agent_id=self.agent_id, name=self.name)
"""
    # Compile to a class
    ns: dict = {"__name__": "_sandbox_test"}
    from forge_agent.core.context import AgentContext

    exec(compile(bad_src, "<test>", "exec"), ns)
    cls = ns["BadAgent"]
    cls._source_code = bad_src
    result = await sb.run_smoke_test(cls, AgentContext(scope_id="t", scope_name="t"))
    assert not result.success
    assert "subprocess" in (result.error or "")


# ------------------------------------------------------------------ Store + Manifest


def test_store_save_creates_v1(tmp_path):
    store = FileCodeStore(tmp_path / "gen")
    saved = store.save(
        "stock.foo",
        "class Foo: pass",
        requirement="a foo agent",
    )
    assert saved.version == "v1"
    assert saved.is_new_agent is True
    assert (tmp_path / "gen" / "stock.foo" / "v1.py").is_file()
    assert (tmp_path / "gen" / "stock.foo" / "v1.meta.json").is_file()
    # Manifest written
    assert (tmp_path / "gen" / "MANIFEST.json").is_file()


def test_store_save_creates_v2(tmp_path):
    store = FileCodeStore(tmp_path / "gen")
    store.save("stock.foo", "v1 code")
    saved = store.save("stock.foo", "v2 code")
    assert saved.version == "v2"
    assert saved.is_new_agent is False
    # Both versions still present
    assert (tmp_path / "gen" / "stock.foo" / "v1.py").is_file()
    assert (tmp_path / "gen" / "stock.foo" / "v2.py").is_file()


def test_store_activate_and_rollback(tmp_path):
    store = FileCodeStore(tmp_path / "gen")
    store.save("a.b", "v1")
    store.save("a.b", "v2")
    store.save("a.b", "v3")
    # v1 is auto-activated (new agent); v2/v3 are NOT auto-activated
    assert store.manifest.agents["a.b"].active_version == "v1"
    store.activate("a.b", "v3")
    assert store.manifest.agents["a.b"].active_version == "v3"
    store.rollback("a.b")
    assert store.manifest.agents["a.b"].active_version == "v2"
    store.activate("a.b", "v1")
    assert store.manifest.agents["a.b"].active_version == "v1"


def test_store_load_returns_active_version(tmp_path):
    store = FileCodeStore(tmp_path / "gen")
    store.save("a.b", "V1 CODE")
    store.save("a.b", "V2 CODE")
    store.activate("a.b", "v1")
    assert store.load("a.b") == "V1 CODE"
    store.activate("a.b", "v2")
    assert store.load("a.b") == "V2 CODE"


def test_manifest_atomic_write(tmp_path):
    m = Manifest(project="x")
    m.agents["a.b"] = type(m.agents.get("a.b", object()))()  # quick test
    p = tmp_path / "MANIFEST.json"
    # Will be empty agents; just test round-trip
    m2 = Manifest(project="y")
    m2.save(p)
    assert p.is_file()
    loaded = Manifest.load(p)
    assert loaded.project == "y"


# ------------------------------------------------------------------ Pipeline (end-to-end with mock LLM)


@pytest.mark.asyncio
async def test_pipeline_end_to_end_with_mock(tmp_path):
    from forge_agent.llm.protocol import LLMResponse

    gen_dir = tmp_path / "generated_agents"
    code_store = FileCodeStore(gen_dir)

    # Pre-built spec (so we don't have to mock the requirements parser)
    spec = AgentRequirements(
        agent_id="test.generated",
        name="Generated",
        domain="test",
        description="A test agent",
        inputs=[FieldSpec(name="payload", type="dict", description="payload")],
        outputs=[FieldSpec(name="verdict", type="str", description="verdict")],
    )

    # Mock LLM that returns a valid BaseAgent subclass
    generated_src = """
from forge_agent.core.base import BaseAgent
from forge_agent.core.contracts import AgentReport
from forge_agent.core.context import AgentContext
from forge_agent.registry.decorators import register_agent


@register_agent(domain="test")
class GeneratedAgent(BaseAgent):
    agent_id = "test.generated"
    name = "Generated"

    async def observe(self, ctx: AgentContext) -> dict:
        return {"x": 1}

    async def decide(self, ctx: AgentContext, obs: dict) -> dict:
        return {"y": obs["x"] + 1}

    async def act(self, ctx: AgentContext, dec: dict) -> AgentReport:
        return AgentReport(
            agent_id=self.agent_id, name=self.name,
            evidence=[f"y={dec['y']}"],
        )
"""

    async def _llm_chat(messages, **kwargs):
        return LLMResponse(content=generated_src, provider="mock", model="x")

    pipeline = GenerationPipeline(
        llm_chat=_llm_chat,
        code_store=code_store,
    )

    # Pre-set the spec via the parser (bypass LLM)
    async def _parse(req):
        return spec

    pipeline.requirements_parser.parse = _parse  # type: ignore[assignment]

    outcome = await pipeline.generate_and_deploy(
        requirement="Create a test agent",
        deploy_mode=DeployMode.SANDBOX_ONLY,
    )

    assert outcome.success, outcome.notes
    assert outcome.code_path is not None
    assert outcome.smoke_test is not None
    assert outcome.smoke_test.success
    # Code was saved under the spec's agent_id
    assert (gen_dir / "test.generated" / "v1.py").is_file()
