"""`forge-agent generate` — generate an Agent from natural language."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from forge_agent.cli._helpers import default_generated_agents_path
from forge_agent.generator.pipeline import DeployMode, GenerationPipeline

log = logging.getLogger(__name__)


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("generate", help="Generate an Agent from a natural-language description")
    p.add_argument("requirement", help="Natural-language description of the agent")
    p.add_argument(
        "--mode",
        "-m",
        choices=[m.value for m in DeployMode],
        default=DeployMode.MANUAL_REVIEW.value,
        help="Deploy mode (default: manual_review)",
    )
    p.add_argument(
        "--provider",
        help="LLM provider ID (e.g. deepseek, ollama). Defaults to llm_providers.json primary.",
    )
    p.add_argument(
        "--code-store",
        type=Path,
        default=None,
        help="Path to the generated_agents/ directory (default: <project>/generated_agents)",
    )
    p.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save to disk; just print the generated code.",
    )
    p.add_argument(
        "--agent-id",
        help="Override the agent_id parsed from the requirement.",
    )
    p.set_defaults(func=run)


async def _run(args: argparse.Namespace) -> int:
    from forge_agent.llm import chat, list_providers

    # Pick provider
    provider = args.provider
    if not provider:
        available = list_providers()
        if not available:
            print("Error: no LLM providers configured.", file=__import__("sys").stderr)
            print(
                "Create a llm_providers.json or set $DEEPSEEK_API_KEY.",
                file=__import__("sys").stderr,
            )
            return 2
        provider = available[0]
        print(f"Using provider: {provider}")

    async def _chat(messages, **kwargs):
        # If provider is specified, pass it through; otherwise use default
        if provider:
            return await chat(messages, provider=provider, **kwargs)
        return await chat(messages, **kwargs)

    code_store_path = args.code_store or default_generated_agents_path(args.project)
    if args.no_save:
        code_store = None
    else:
        from forge_agent.generator.store import FileCodeStore

        code_store = FileCodeStore(code_store_path)

    pipeline = GenerationPipeline(
        llm_chat=_chat,
        code_store=code_store,
    )

    deploy_mode = DeployMode(args.mode)
    outcome = await pipeline.generate_and_deploy(
        requirement=args.requirement,
        deploy_mode=deploy_mode,
    )

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Agent:    {outcome.agent_id}")
    print(f"Success:  {outcome.success}")
    print(f"Mode:     {outcome.deploy_mode.value}")
    print(f"Deployed: {outcome.deployed}")
    if outcome.code_path:
        print(f"Path:     {outcome.code_path}")
    if outcome.generation:
        print(f"Attempts: {outcome.generation.attempts}")
        if outcome.generation.llm_provider:
            print(f"LLM:      {outcome.generation.llm_provider} / {outcome.generation.llm_model}")
    if outcome.validation and not outcome.validation.ok:
        print(f"Validation errors: {outcome.validation.errors}")
    if outcome.smoke_test and not outcome.smoke_test.success:
        print(f"Smoke test failed: {outcome.smoke_test.error}")
    print("\nNotes:")
    for n in outcome.notes:
        print(f"  - {n}")
    print(f"{'=' * 60}\n")

    if outcome.generation and outcome.generation.source_code and args.no_save:
        print("--- Generated Source ---")
        print(outcome.generation.source_code)

    return 0 if outcome.success else 1


def run(args: argparse.Namespace) -> int:
    return asyncio.run(_run(args))
