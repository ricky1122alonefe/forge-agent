"""GenerationPipeline — orchestrates the full "natural language → Agent" flow.

The high-level API used by `forge-agent generate` CLI and by external projects.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from forge_agent.generator.generator import CodeGenerator, GenerationContext, GenerationResult
from forge_agent.generator.registry_getter import get_registry_lazy
from forge_agent.generator.requirements import RequirementsParser
from forge_agent.generator.sandbox import Sandbox, SmokeTestResult
from forge_agent.generator.store import FileCodeStore, SavedCode
from forge_agent.generator.validator import ContractValidator, ValidationResult

log = logging.getLogger(__name__)


class DeployMode(str, Enum):
    """How to handle a freshly generated agent."""

    MANUAL_REVIEW = "manual_review"  # Generate + save + validate, but don't inject
    AUTO_DEPLOY = "auto_deploy"  # Generate + save + validate + sandbox + inject
    SANDBOX_ONLY = "sandbox_only"  # Generate + save + validate + sandbox; no inject


@dataclass
class GenerationOutcome:
    """Final result of a full pipeline run."""

    success: bool
    agent_id: str
    requirement: str
    deploy_mode: DeployMode
    deployed: bool
    code_path: str | None
    generation: GenerationResult | None
    validation: ValidationResult | None
    smoke_test: SmokeTestResult | None
    saved: SavedCode | None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: list[str] = field(default_factory=list)


class GenerationPipeline:
    """Top-level API: turn a natural-language request into a working Agent.

    Usage::

        pipeline = GenerationPipeline(llm_chat=chat)
        result = await pipeline.generate_and_deploy(
            requirement="监控英伟达股价，30分钟涨幅>5%就通知我",
            deploy_mode=DeployMode.MANUAL_REVIEW,
        )
        if result.success:
            print(f"Saved: {result.code_path}")
    """

    def __init__(
        self,
        *,
        llm_chat: Any,
        code_store: FileCodeStore | None = None,
        sandbox: Sandbox | None = None,
        validator: ContractValidator | None = None,
        requirements_parser: RequirementsParser | None = None,
        code_generator: CodeGenerator | None = None,
        agent_registry: Any = None,  # forge_agent.registry.registry.AgentRegistry
        max_generation_attempts: int = 3,
    ) -> None:
        self.llm_chat = llm_chat
        self.code_store = code_store
        self.sandbox = sandbox or Sandbox()
        self.validator = validator or ContractValidator()
        self.requirements_parser = requirements_parser or RequirementsParser(llm_chat=llm_chat)
        self.agent_registry = agent_registry if agent_registry is not None else get_registry_lazy()
        self.code_generator = code_generator or CodeGenerator(
            llm_chat=llm_chat,
            validator=self.validator,
            max_attempts=max_generation_attempts,
        )

    async def generate_and_deploy(
        self,
        requirement: str,
        *,
        sample_context: Any = None,
        deploy_mode: DeployMode = DeployMode.MANUAL_REVIEW,
        project_root: str | None = None,
        dataset_name: str | None = None,
    ) -> GenerationOutcome:
        """End-to-end: requirement → spec → code → validate → sandbox → save → (deploy)."""
        notes: list[str] = []

        # 1. Parse requirements
        spec = await self.requirements_parser.parse(requirement)
        notes.append(f"Parsed spec: agent_id={spec.agent_id}, domain={spec.domain}")

        # 1.5 Load dataset examples if specified
        dataset_examples = None
        if dataset_name:
            from forge_agent.datasets.registry import get_registry

            registry = get_registry()
            ds = registry.load(dataset_name)
            if ds is not None:
                dataset_examples = [
                    {"input": item.input, "output": item.output} for item in ds.sample(n=5)
                ]
                notes.append(
                    f"Loaded {len(dataset_examples)} examples from dataset '{dataset_name}'"
                )

        # 1.6 Get available MCP tools from gateway
        mcp_tools_available: list[str] = []
        try:
            from forge_agent.mcp.gateway import get_gateway

            gw = get_gateway()
            mcp_tools_available = gw.list_tools()
            if mcp_tools_available:
                notes.append(f"MCP tools available: {len(mcp_tools_available)}")
        except Exception:
            pass  # MCP gateway not configured; proceed without tools

        # 2. Generate code
        gen_ctx = GenerationContext(
            requirements=spec,
            existing_agents=list(self.agent_registry.list()),
            dataset_examples=dataset_examples,
            mcp_tools_available=mcp_tools_available,
        )
        generation = await self.code_generator.generate(gen_ctx)
        if not generation.success or not generation.source_code:
            return GenerationOutcome(
                success=False,
                agent_id=spec.agent_id,
                requirement=requirement,
                deploy_mode=deploy_mode,
                deployed=False,
                code_path=None,
                generation=generation,
                validation=generation.validation,
                smoke_test=None,
                saved=None,
                notes=[*notes, "code generation failed"],
            )
        notes.append(f"Generated in {generation.attempts} attempt(s)")

        # 3. Save to CodeStore (if configured)
        saved: SavedCode | None = None
        if self.code_store is not None:
            saved = self.code_store.save(
                spec.agent_id,
                generation.source_code,
                requirement=requirement,
                created_by="cli",
                llm_provider=generation.llm_provider,
                llm_model=generation.llm_model,
                validation_status="passed"
                if (generation.validation and generation.validation.ok)
                else "failed",
                validation_errors=(generation.validation.errors if generation.validation else []),
                agent_type=spec.agent_type.value,
            )
            notes.append(f"Saved to {saved.code_path}")

        # 4. Optionally: sandbox smoke test
        smoke_test: SmokeTestResult | None = None
        if deploy_mode in (DeployMode.AUTO_DEPLOY, DeployMode.SANDBOX_ONLY):
            smoke_test = await self._smoke_test(
                generation.source_code, spec.agent_id, sample_context
            )
            notes.append(
                f"Smoke test: {'passed' if smoke_test.success else 'failed: ' + (smoke_test.error or '?')}"
            )
            if not smoke_test.success and deploy_mode == DeployMode.AUTO_DEPLOY:
                # Update manifest to reflect smoke test failure
                if self.code_store and saved:
                    entry = self.code_store.manifest.agents.get(spec.agent_id)
                    if entry:
                        vmeta = entry.get_version(saved.version)
                        if vmeta:
                            vmeta.smoke_test_status = "failed"
                            vmeta.smoke_test_error = smoke_test.error
                            self.code_store.flush_manifest()
                return GenerationOutcome(
                    success=False,
                    agent_id=spec.agent_id,
                    requirement=requirement,
                    deploy_mode=deploy_mode,
                    deployed=False,
                    code_path=str(saved.code_path) if saved else None,
                    generation=generation,
                    validation=generation.validation,
                    smoke_test=smoke_test,
                    saved=saved,
                    notes=[*notes, "smoke test failed; not deployed"],
                )

        # 5. Optionally: deploy (inject into Registry)
        deployed = False
        if deploy_mode == DeployMode.AUTO_DEPLOY and saved:
            try:
                from forge_agent.generator.injector import AgentInjector

                inj = AgentInjector(validator=self.validator)
                _cls, v_result = inj.inject_source(
                    generation.source_code,
                    module_name=f"_generated_{spec.agent_id.replace('.', '_')}",
                )
                deployed = v_result.ok
                if deployed:
                    notes.append(f"Deployed: registered {spec.agent_id}")
                else:
                    notes.append(f"Deploy failed: {v_result.errors}")
            except Exception as exc:
                notes.append(f"Deploy exception: {exc}")
                log.exception("Deploy failed")

        return GenerationOutcome(
            success=True,
            agent_id=spec.agent_id,
            requirement=requirement,
            deploy_mode=deploy_mode,
            deployed=deployed,
            code_path=str(saved.code_path) if saved else None,
            generation=generation,
            validation=generation.validation,
            smoke_test=smoke_test,
            saved=saved,
            notes=notes,
        )

    async def _smoke_test(
        self,
        source: str,
        agent_id: str,
        sample_context: Any,
    ) -> SmokeTestResult:
        """Run the generated code through the sandbox."""
        from forge_agent.generator.injector import AgentInjector

        # Default sample context for football-like agents
        if sample_context is None:
            from forge_agent.core.context import AgentContext

            sample_context = AgentContext(
                scope_id="smoke_test",
                scope_name="smoke",
                domain="generic",
                payload={"ticker": "NVDA", "match": "QAT vs IDN", "odds_snapshot": {}},
            )

        inj = AgentInjector(validator=self.validator)
        try:
            cls, v_result = inj.inject_source(
                source,
                module_name=f"_smoke_{agent_id.replace('.', '_')}",
            )
        except Exception as exc:
            return SmokeTestResult(
                success=False,
                agent_id=agent_id,
                duration_ms=0,
                error=f"inject failed: {exc}",
                error_type=type(exc).__name__,
            )
        if not v_result.ok:
            return SmokeTestResult(
                success=False,
                agent_id=agent_id,
                duration_ms=0,
                error=f"validation failed: {v_result.errors}",
                error_type="Validation",
            )
        # Stash source code on the class for the sandbox to inspect imports
        cls._source_code = source
        return await self.sandbox.run_smoke_test(cls, sample_context)
