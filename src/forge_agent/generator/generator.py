"""CodeGenerator — turns an AgentRequirements into Python source code.

Pipeline:
    1. Build the user prompt from the spec.
    2. Call the LLM (chat function).
    3. Validate the source (ContractValidator).
    4. If validation fails, append errors to the prompt and retry.
    5. After max_attempts, return the best result.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from forge_agent.generator.prompts import (
    CODE_GENERATOR_SYSTEM,
    build_user_prompt,
)
from forge_agent.generator.requirements import AgentRequirements
from forge_agent.generator.validator import ContractValidator, ValidationResult

log = logging.getLogger(__name__)


@dataclass
class GenerationContext:
    """Inputs to CodeGenerator.generate()."""

    requirements: AgentRequirements
    mcp_tools_available: list[str] = field(default_factory=list)
    existing_agents: list[str] = field(default_factory=list)
    base_class_import: str = "from forge_agent.core.base import BaseAgent"


@dataclass
class GenerationResult:
    """The output of CodeGenerator.generate()."""

    success: bool
    source_code: str | None
    attempts: int
    validation: ValidationResult | None = None
    errors: list[str] = field(default_factory=list)
    raw_outputs: list[str] = field(default_factory=list)
    llm_provider: str | None = None
    llm_model: str | None = None


class CodeGenerator:
    """LLM-driven code generator with self-retry on validation failure."""

    def __init__(
        self,
        *,
        llm_chat: Any,
        validator: ContractValidator | None = None,
        max_attempts: int = 3,
        default_model: str | None = None,
    ) -> None:
        """Args:
            llm_chat: Async callable matching `forge_agent.llm.chat`'s signature.
            validator: ContractValidator instance.
            max_attempts: How many times to retry on validation failure.
            default_model: Default model name to pass to the LLM.
        """
        self.llm_chat = llm_chat
        self.validator = validator or ContractValidator()
        self.max_attempts = max_attempts
        self.default_model = default_model

    async def generate(self, ctx: GenerationContext) -> GenerationResult:
        """Generate code; retry on validation failure."""
        raw_outputs: list[str] = []
        last_validation: ValidationResult | None = None
        last_source: str | None = None
        last_error: str | None = None
        provider: str | None = None
        model: str | None = None

        for attempt in range(1, self.max_attempts + 1):
            user_prompt = build_user_prompt(
                ctx.requirements.to_prompt(),
                mcp_tools=ctx.mcp_tools_available,
                existing_agents=ctx.existing_agents,
            )
            if last_error:
                user_prompt += (
                    f"\n\n⚠️ 上一次生成的代码有这些问题：\n{last_error}\n"
                    f"请修复后重新输出完整代码。"
                )

            messages = [
                {"role": "system", "content": CODE_GENERATOR_SYSTEM},
                {"role": "user", "content": user_prompt},
            ]
            try:
                response = await self.llm_chat(messages, temperature=0.1)
            except Exception as exc:  # noqa: BLE001
                log.exception("LLM call failed on attempt %d", attempt)
                return GenerationResult(
                    success=False,
                    source_code=None,
                    attempts=attempt,
                    errors=[f"LLM call failed: {exc}"],
                    raw_outputs=raw_outputs,
                )

            raw = response.content if hasattr(response, "content") else str(response)
            provider = getattr(response, "provider", provider)
            model = getattr(response, "model", model)
            raw_outputs.append(raw)

            source = _extract_python_code(raw)
            last_source = source

            validation = self.validator.validate_source(source)
            last_validation = validation
            if validation.ok:
                return GenerationResult(
                    success=True,
                    source_code=source,
                    attempts=attempt,
                    validation=validation,
                    raw_outputs=raw_outputs,
                    llm_provider=provider,
                    llm_model=model,
                )
            else:
                last_error = "\n".join(validation.errors)
                log.info("Attempt %d: validation failed: %s", attempt, validation.errors)

        return GenerationResult(
            success=False,
            source_code=last_source,
            attempts=self.max_attempts,
            validation=last_validation,
            errors=(last_validation.errors if last_validation else []) + ["max attempts exceeded"],
            raw_outputs=raw_outputs,
            llm_provider=provider,
            llm_model=model,
        )


def _extract_python_code(raw: str) -> str:
    """Extract Python code from LLM output.

    Handles:
        - ```python ... ``` fences
        - ``` ... ``` fences
        - Plain text with embedded code
    """
    text = raw.strip()
    # Try to find a fenced code block
    fence_match = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    # If the text starts with `from` or `import` or `class`, assume it's raw
    if text.startswith(("from ", "import ", "class ", "@")):
        return text
    # Try to find a class definition
    class_match = re.search(r"((?:from|import|class|@).*)", text, re.DOTALL)
    if class_match:
        return class_match.group(1).strip()
    return text
