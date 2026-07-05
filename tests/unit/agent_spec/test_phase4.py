"""Tests for reasoner agent type and LLM planner hints (A4.1/A4.2)."""

from __future__ import annotations

import pytest

from forge_agent.agent_spec.from_type import generate_from_agent_type
from forge_agent.agent_spec.generator import _hints_from_requirements, generate_spec
from forge_agent.agent_spec.models import AgentPrimitive, SchemaProfile
from forge_agent.agent_spec.smoke import smoke_run_spec
from forge_agent.builtin import AgentTypeRegistry
from forge_agent.core.agent_type import AgentType
from forge_agent.generator.requirements import AgentRequirements


class TestReasonerAgentType:
    @pytest.mark.asyncio
    async def test_generate_from_reasoner_type(self) -> None:
        registry = AgentTypeRegistry()
        type_def = registry.get("reasoner")
        spec = generate_from_agent_type(
            type_def,
            "sentiment_bot",
            {"topic": "用户评论", "schema_profile": "sentiment"},
            requirement="对用户评论做情感分类",
        )
        assert spec.primitive == AgentPrimitive.REASONER
        assert spec.schema_profile == SchemaProfile.SENTIMENT
        smoke = await smoke_run_spec(spec)
        assert smoke["success"] is True


class TestLlmPlannerHints:
    def test_hints_map_analyzer_to_reasoner(self) -> None:
        parsed = AgentRequirements(
            agent_id="risk_bot",
            name="Risk",
            domain="generic",
            description="评估项目风险",
            agent_type=AgentType.ANALYZER,
            raw_requirement="评估项目风险等级",
        )
        hints = _hints_from_requirements(parsed)
        assert hints["primitive"] == AgentPrimitive.REASONER

    @pytest.mark.asyncio
    async def test_generate_spec_llm_assisted_with_mock_chat(self) -> None:
        async def mock_chat(messages, **kwargs):
            class Response:
                content = '{"agent_id":"llm_agent","name":"LLM Agent","domain":"generic","agent_type":"analyzer","description":"test"}'

            return Response()

        spec = await generate_spec(
            "评估项目风险等级",
            use_llm=True,
            llm_chat=mock_chat,
        )
        assert spec.planner == "llm_assisted"
        assert spec.primitive == AgentPrimitive.REASONER
