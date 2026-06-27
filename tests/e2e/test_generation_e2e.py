"""End-to-end tests for the full generation pipeline (T1.4).

Tests the complete flow: requirement → generate → validate → sandbox → report
across 10 different domains using real LLM (DeepSeek).

**Requirements:**
- DEEPSEEK_API_KEY environment variable must be set
- Tests are skipped if the key is not available (CI-friendly)

**Usage:**
    # Run all e2e tests
    DEEPSEEK_API_KEY=sk-xxx pytest tests/e2e/test_generation_e2e.py -v

    # Run single domain
    DEEPSEEK_API_KEY=sk-xxx pytest tests/e2e/test_generation_e2e.py::test_generate_and_run[stock-monitor_AAPL_stock_price] -v

    # Skip e2e (no key)
    pytest tests/e2e/ -v  # auto-skip
"""
from __future__ import annotations

import os
import time

import pytest

from forge_agent.core.context import AgentContext
from forge_agent.core.enums import Verdict
from forge_agent.generator import (
    DeployMode,
    GenerationPipeline,
)
from forge_agent.llm import chat

# Skip all tests if DEEPSEEK_API_KEY is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get("DEEPSEEK_API_KEY"),
    reason="DEEPSEEK_API_KEY not set",
)


# ----------------------------------------------------------------- Test data

DOMAINS = [
    ("stock", "monitor AAPL stock price and alert on 5% daily change"),
    ("football", "predict Premier League match outcome based on recent form"),
    ("weather", "forecast tomorrow's weather in Beijing"),
    ("news", "summarize today's top 5 tech news headlines"),
    ("crypto", "track Bitcoin price and detect significant movements"),
    ("ecommerce", "recommend products based on user browsing history"),
    ("social", "analyze Twitter sentiment for a given hashtag"),
    ("health", "track daily step count and suggest fitness goals"),
    ("education", "generate quiz questions for Python basics"),
    ("generic", "categorize customer feedback into positive/negative/neutral"),
]


# ----------------------------------------------------------------- Tests

@pytest.mark.asyncio
@pytest.mark.parametrize("domain,prompt", DOMAINS)
async def test_generate_and_run(domain: str, prompt: str) -> None:
    """Full pipeline: generate agent code, validate, sandbox, produce report."""
    t0 = time.perf_counter()

    # 1. Create pipeline with real DeepSeek LLM
    pipeline = GenerationPipeline(llm_chat=chat)

    # 2. Generate and deploy (sandbox mode — no injection)
    sample_ctx = AgentContext(
        scope_id=f"e2e_{domain}",
        scope_name=f"E2E {domain}",
        domain=domain,
        payload={"test": True, "domain": domain},
    )

    outcome = await pipeline.generate_and_deploy(
        requirement=prompt,
        sample_context=sample_ctx,
        deploy_mode=DeployMode.SANDBOX_ONLY,
    )

    elapsed = time.perf_counter() - t0

    # 3. Assertions
    assert outcome.success is True, (
        f"Pipeline failed for {domain}: {outcome.notes}"
    )
    assert outcome.generation is not None
    assert outcome.generation.success is True
    assert outcome.generation.source_code is not None
    assert len(outcome.generation.source_code) > 100

    # 4. Validation passed
    assert outcome.validation is not None
    assert outcome.validation.ok is True, (
        f"Validation failed for {domain}: {outcome.validation.errors}"
    )

    # 5. Sandbox passed
    assert outcome.smoke_test is not None
    assert outcome.smoke_test.success is True, (
        f"Sandbox failed for {domain}: {outcome.smoke_test.error}"
    )

    # 6. Report is valid
    report = outcome.smoke_test.report
    assert report is not None
    assert isinstance(report, dict)
    assert "agent_id" in report
    assert report["agent_id"] != ""
    assert "verdict" in report
    assert report["verdict"] in [v.value for v in Verdict]

    # 7. Performance (log for baseline)
    print(f"\n[{domain}] Total: {elapsed:.2f}s")
    print(f"  Generation attempts: {outcome.generation.attempts}")
    print(f"  Sandbox duration: {outcome.smoke_test.duration_ms:.1f}ms")


@pytest.mark.asyncio
async def test_generation_with_invalid_requirement() -> None:
    """Pipeline should handle invalid/empty requirements gracefully."""
    pipeline = GenerationPipeline(llm_chat=chat)

    outcome = await pipeline.generate_and_deploy(
        requirement="",  # empty
        deploy_mode=DeployMode.MANUAL_REVIEW,
    )

    # Should fail gracefully (not crash)
    # Either success=False or validation fails
    if outcome.success:
        assert outcome.validation is not None
        # Empty requirement might still generate something, but validation should catch issues


@pytest.mark.asyncio
async def test_multiple_generations_independent() -> None:
    """Multiple generations should not share state or interfere."""
    pipeline = GenerationPipeline(llm_chat=chat)

    results = []
    for domain, prompt in DOMAINS[:3]:  # Test first 3 domains
        outcome = await pipeline.generate_and_deploy(
            requirement=prompt,
            deploy_mode=DeployMode.MANUAL_REVIEW,
        )
        results.append((domain, outcome))

    # All should succeed independently
    for domain, outcome in results:
        assert outcome.success is True, f"{domain} failed: {outcome.notes}"
        assert outcome.generation is not None
        assert outcome.generation.source_code is not None


# ----------------------------------------------------------------- Performance baseline

@pytest.mark.asyncio
async def test_performance_baseline() -> None:
    """Record performance metrics for a single generation."""
    pipeline = GenerationPipeline(llm_chat=chat)

    t0 = time.perf_counter()
    outcome = await pipeline.generate_and_deploy(
        requirement="monitor stock prices",
        deploy_mode=DeployMode.SANDBOX_ONLY,
    )
    total_time = time.perf_counter() - t0

    assert outcome.success is True

    # Log performance (for baseline tracking)
    print(f"\nPerformance baseline:")
    print(f"  Total time: {total_time:.2f}s")
    if outcome.generation:
        print(f"  Generation attempts: {outcome.generation.attempts}")
        print(f"  LLM provider: {outcome.generation.llm_provider}")
        print(f"  LLM model: {outcome.generation.llm_model}")
    if outcome.smoke_test:
        print(f"  Sandbox duration: {outcome.smoke_test.duration_ms:.1f}ms")
