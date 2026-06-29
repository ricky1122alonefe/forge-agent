"""Tests for T2.2.4 — Dataset integration with generator."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from forge_agent.datasets import Dataset, DatasetItem
from forge_agent.datasets.registry import DatasetRegistry, get_registry
from forge_agent.datasets.store import LocalDatasetStore
from forge_agent.generator.generator import CodeGenerator, GenerationContext
from forge_agent.generator.prompts import build_user_prompt
from forge_agent.generator.requirements import AgentRequirements
from forge_agent.llm.protocol import LLMResponse


class TestBuildUserPromptWithDataset:
    def test_without_dataset(self):
        prompt = build_user_prompt("test spec")
        assert "test spec" in prompt
        assert "数据示例" not in prompt

    def test_with_dataset_examples(self):
        examples = [
            {"input": "https://example.com/1", "output": {"name": "Product 1"}},
            {"input": "https://example.com/2", "output": {"name": "Product 2"}},
        ]
        prompt = build_user_prompt("test spec", dataset_examples=examples)
        assert "数据示例" in prompt
        assert "示例 1" in prompt
        assert "示例 2" in prompt
        assert "Product 1" in prompt
        assert "Product 2" in prompt

    def test_dataset_examples_limit(self):
        examples = [{"input": f"test-{i}", "output": f"result-{i}"} for i in range(10)]
        prompt = build_user_prompt("test spec", dataset_examples=examples)
        # Should only show first 5 examples
        assert "示例 5" in prompt
        assert "示例 6" not in prompt


class TestGenerationContextWithDataset:
    def test_context_with_dataset(self):
        req = AgentRequirements(
            agent_id="test.agent",
            name="Test Agent",
            domain="generic",
            description="Test",
        )
        examples = [{"input": "test", "output": "result"}]
        ctx = GenerationContext(requirements=req, dataset_examples=examples)
        assert ctx.dataset_examples == examples

    def test_context_without_dataset(self):
        req = AgentRequirements(
            agent_id="test.agent",
            name="Test Agent",
            domain="generic",
            description="Test",
        )
        ctx = GenerationContext(requirements=req)
        assert ctx.dataset_examples is None


class TestCodeGeneratorWithDataset:
    @pytest.mark.asyncio
    async def test_generator_passes_dataset_to_prompt(self):
        """Verify that CodeGenerator passes dataset_examples to the prompt."""
        captured_messages = []

        async def mock_llm_chat(messages, **kwargs):
            captured_messages.extend(messages)
            return LLMResponse(
                content="""
from forge_agent.core.base import BaseAgent
from forge_agent.core.contracts import AgentReport
from forge_agent.core.context import AgentContext

class TestAgent(BaseAgent):
    agent_id = "test.agent"
    name = "Test Agent"
    domain = "generic"
    version = "1.0"

    async def observe(self, ctx: AgentContext) -> dict:
        return {}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(verdict="SAFE", confidence=1.0, evidence=[])
""",
                provider="mock",
                model="mock-model",
            )

        req = AgentRequirements(
            agent_id="test.agent",
            name="Test Agent",
            domain="generic",
            description="Test",
        )
        examples = [
            {"input": "https://example.com/1", "output": {"name": "Product 1"}},
        ]
        ctx = GenerationContext(requirements=req, dataset_examples=examples)

        generator = CodeGenerator(llm_chat=mock_llm_chat, max_attempts=1)
        result = await generator.generate(ctx)

        assert result.success
        # Check that the user prompt contains dataset examples
        user_msg = captured_messages[1]["content"]
        assert "数据示例" in user_msg
        assert "Product 1" in user_msg


class TestPipelineWithDataset:
    def setup_method(self):
        DatasetRegistry.reset_instance()
        self.tmpdir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)
        DatasetRegistry.reset_instance()

    @pytest.mark.asyncio
    async def test_pipeline_loads_dataset(self):
        """Verify that pipeline loads dataset examples when dataset_name is provided."""
        # Setup dataset
        store = LocalDatasetStore(self.tmpdir)
        ds = Dataset(name="product_examples", description="Test dataset")
        ds.add_item(
            DatasetItem(
                input="https://example.com/1",
                output={"name": "Product 1", "price": 29.99},
            )
        )
        ds.add_item(
            DatasetItem(
                input="https://example.com/2",
                output={"name": "Product 2", "price": 49.99},
            )
        )
        store.save(ds)

        registry = get_registry()
        registry.register_store("local", store)

        # Mock LLM
        async def mock_llm_chat(messages, **kwargs):
            return LLMResponse(
                content="""
from forge_agent.core.base import BaseAgent
from forge_agent.core.contracts import AgentReport
from forge_agent.core.context import AgentContext

class TestAgent(BaseAgent):
    agent_id = "test.agent"
    name = "Test Agent"
    domain = "generic"
    version = "1.0"

    async def observe(self, ctx: AgentContext) -> dict:
        return {}

    async def decide(self, ctx: AgentContext, observation: dict) -> dict:
        return {}

    async def act(self, ctx: AgentContext, decision: dict) -> AgentReport:
        return AgentReport(verdict="SAFE", confidence=1.0, evidence=[])
""",
                provider="mock",
                model="mock-model",
            )

        from forge_agent.generator.pipeline import DeployMode, GenerationPipeline

        pipeline = GenerationPipeline(llm_chat=mock_llm_chat)
        result = await pipeline.generate_and_deploy(
            requirement="Test requirement",
            deploy_mode=DeployMode.MANUAL_REVIEW,
            dataset_name="product_examples",
        )

        # Check that dataset was loaded
        assert any("dataset" in note.lower() for note in result.notes)
        assert result.success
