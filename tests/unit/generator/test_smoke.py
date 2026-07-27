"""Smoke tests for the code generator module (S2 safety net).

Covers AgentRequirements construction, ContractValidator (valid/invalid/
dangerous), and CodeGenerator.generate() with a mock LLM — no real API
key needed.
"""

from __future__ import annotations

from forge_agent.core.agent_type import AgentType
from forge_agent.generator.generator import (
    CodeGenerator,
    GenerationContext,
    GenerationResult,
)
from forge_agent.generator.requirements import AgentRequirements, FieldSpec
from forge_agent.generator.validator import ContractValidator
from forge_agent.llm.protocol import LLMResponse

# -- a valid BaseAgent subclass source ----------------------------------------

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

SOURCE_SYNTAX_ERROR = "def broken(:\n    pass"

SOURCE_DANGEROUS = """
import os

class DangerousAgent:
    agent_id = "bad"
    name = "Bad"

    def run(self):
        os.system("rm -rf /")
"""


class TestRequirements:
    def test_construction_defaults(self) -> None:
        req = AgentRequirements(
            agent_id="test.agent",
            name="Test",
            domain="generic",
            description="A test agent",
        )
        assert req.agent_id == "test.agent"
        assert req.agent_type == AgentType.GENERAL
        assert req.inputs == []
        assert req.mcp_tools == []

    def test_with_fields(self) -> None:
        req = AgentRequirements(
            agent_id="test.agent",
            name="Test",
            domain="generic",
            description="test",
            inputs=[FieldSpec(name="keyword", type="str", description="search term")],
            outputs=[FieldSpec(name="verdict", type="str", description="result")],
        )
        assert len(req.inputs) == 1
        assert req.inputs[0].name == "keyword"
        assert req.outputs[0].type == "str"


class TestValidator:
    def test_valid_source_passes(self) -> None:
        v = ContractValidator()
        result = v.validate_source(SOURCE_OK)
        assert result.ok is True
        assert result.errors == []

    def test_syntax_error_fails(self) -> None:
        v = ContractValidator()
        result = v.validate_source(SOURCE_SYNTAX_ERROR)
        assert result.ok is False
        assert any("SyntaxError" in e for e in result.errors)

    def test_dangerous_import_flagged(self) -> None:
        v = ContractValidator()
        result = v.validate_source(SOURCE_DANGEROUS)
        assert result.ok is False
        # Should flag os.system or dangerous pattern
        all_msgs = " ".join(result.errors + result.warnings)
        assert "system" in all_msgs.lower() or "dangerous" in all_msgs.lower() or "os" in all_msgs

    def test_empty_source_fails(self) -> None:
        v = ContractValidator()
        result = v.validate_source("")
        assert result.ok is False


class TestCodeGenerator:
    """generate() with a mock LLM that returns valid source."""

    @staticmethod
    def _mock_llm(source: str = SOURCE_OK) -> object:
        async def _chat(messages, *, provider=None, model=None, **kwargs):
            return LLMResponse(
                content=source,
                provider="mock",
                model="mock-model",
            )

        return _chat

    async def test_generate_returns_result(self) -> None:
        gen = CodeGenerator(llm_chat=self._mock_llm(), max_attempts=1)
        ctx = GenerationContext(
            requirements=AgentRequirements(
                agent_id="gen.my",
                name="My",
                domain="generic",
                description="test",
            )
        )
        result = await gen.generate(ctx)
        assert isinstance(result, GenerationResult)
        assert result.attempts >= 1

    async def test_generate_success_with_valid_code(self) -> None:
        gen = CodeGenerator(llm_chat=self._mock_llm(SOURCE_OK), max_attempts=1)
        ctx = GenerationContext(
            requirements=AgentRequirements(
                agent_id="gen.my",
                name="My",
                domain="generic",
                description="test",
            )
        )
        result = await gen.generate(ctx)
        assert result.success is True
        assert result.source_code is not None
        assert "class MyAgent" in result.source_code

    async def test_generate_retries_on_failure(self) -> None:
        """When LLM returns invalid code, generator retries up to max_attempts."""
        gen = CodeGenerator(llm_chat=self._mock_llm(SOURCE_SYNTAX_ERROR), max_attempts=2)
        ctx = GenerationContext(
            requirements=AgentRequirements(
                agent_id="gen.bad",
                name="Bad",
                domain="generic",
                description="test",
            )
        )
        result = await gen.generate(ctx)
        assert result.success is False
        assert result.attempts == 2
        assert len(result.errors) > 0
