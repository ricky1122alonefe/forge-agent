"""PromptAgent — a configurable agent driven by a prompt template and output mapping.

The agent's behavior is defined entirely through configuration:

    - prompt:        Template rendered with variables extracted from the payload.
    - variables:     Mapping of {template_var: payload_key}.
    - output_schema: Expected JSON keys and their types (used for parsing).
    - output_mapping: How parsed JSON fields map to AgentReport fields.
    - mock_mode:     If true, returns a fixed mock response instead of calling an LLM.

This makes it possible to create new agents by editing YAML instead of writing
Python classes.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from forge_agent.core.base import BaseAgent
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.enums import Action, Verdict
from forge_agent.registry.registry import get_registry

log = logging.getLogger(__name__)


class PromptAgent(BaseAgent):
    """Configuration-driven agent using a prompt template + JSON output mapping.

    Subclasses or dynamically-created classes should set:
        agent_id, name, domain, version
    and pass the runtime configuration via ``config``.
    """

    agent_id = "prompt.base"
    name = "Prompt Agent"
    domain = "generic"

    # Populated by AgentFactory for config-driven agents.
    _factory_config: dict[str, Any] | None = None

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        effective_config = {**(self._factory_config or {}), **(config or {})}
        super().__init__(effective_config)
        self.prompt_template: str = self.config.get("prompt", "")
        self.variables: dict[str, str] = self.config.get("variables", {})
        self.output_schema: dict[str, Any] = self.config.get("output_schema", {})
        self.output_mapping: dict[str, Any] = self.config.get("output_mapping", {})
        self.mock_mode: bool = self.config.get("mock_mode", False)
        self.mock_response: str = self.config.get("mock_response", "")
        self.llm_provider: str | None = self.config.get("provider")
        self.llm_model: str | None = self.config.get("model")
        self.temperature: float = float(self.config.get("temperature", 0.2))

    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        """Extract template variables from the payload."""
        observation: dict[str, Any] = {}
        for var_name, payload_key in self.variables.items():
            observation[var_name] = ctx.payload.get(payload_key)
        return observation

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        """Render the prompt, get a response, and parse it."""
        if self.mock_mode:
            rendered = self._render_prompt(observation, self.mock_response)
            return self._parse_response(rendered)

        if not self.prompt_template:
            return {"error": "No prompt template configured"}

        prompt = self._render_prompt(observation, self.prompt_template)
        try:
            from forge_agent.llm.protocol import chat

            response = await chat(
                prompt,
                provider=self.llm_provider,
                model=self.llm_model,
                temperature=self.temperature,
                agent_id=self.agent_id,
            )
            return self._parse_response(response.content)
        except Exception as exc:
            log.warning("LLM call failed for %s: %s", self.agent_id, exc)
            return {"error": f"LLM call failed: {exc}"}

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        """Map the parsed decision onto a standardized AgentReport."""
        mapped = self._map_to_report(decision)
        return AgentReport(
            agent_id=self.agent_id,
            name=self.name,
            domain=self.domain,
            verdict=mapped.get("verdict", Verdict.NEUTRAL),
            confidence=mapped.get("confidence", 0.0),
            risk=mapped.get("risk", 0.0),
            weight=mapped.get("weight", 1.0),
            evidence=mapped.get("evidence", []),
            warnings=mapped.get("warnings", []),
            recommended_action=mapped.get("recommended_action", Action.WATCH),
            metrics=mapped.get("metrics", {}),
            raw={"decision": decision, "config": self.config},
            run_id=ctx.run_id,
            timestamp=ctx.timestamp,
            version=self.version,
        )

    def _render_prompt(
        self,
        observation: dict[str, Any],
        template: str | None = None,
    ) -> str:
        """Replace only known {variable} placeholders in the template.

        Unlike ``str.format()``, this does not touch braces that are not part
        of a known variable name.  This makes it safe to render JSON mock
        responses that contain their own ``{"key": "value"}`` structures.
        """
        import re

        text = template if template is not None else self.prompt_template
        if not observation:
            return text

        pattern = re.compile("\\{(" + "|".join(re.escape(str(k)) for k in observation) + ")\\}")

        def replacer(match: re.Match[str]) -> str:
            key = match.group(1)
            value = observation.get(key)
            return str(value) if value is not None else match.group(0)

        return pattern.sub(replacer, text)

    def _parse_response(self, content: str) -> dict[str, Any]:
        """Parse LLM/mock response as JSON, falling back to a raw text field."""
        text = content.strip()
        if not text:
            return {"error": "Empty response"}

        # Strip markdown code fences if present.
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                return {"raw": text, "error": "Response is not a JSON object"}
            return parsed
        except json.JSONDecodeError:
            return {"raw": text, "error": "Response is not valid JSON"}

    def _map_to_report(self, decision: dict[str, Any]) -> dict[str, Any]:
        """Apply output_mapping to turn parsed JSON into AgentReport kwargs."""
        result: dict[str, Any] = {}

        for report_field, mapping in self.output_mapping.items():
            if isinstance(mapping, str):
                # Direct field mapping: "confidence" -> decision["confidence"]
                result[report_field] = decision.get(mapping)
            elif isinstance(mapping, dict):
                # Structured mapping with optional 'from' and 'map'.
                source = mapping.get("from", report_field)
                value = decision.get(source)
                value_map = mapping.get("map")
                if value_map is not None and value in value_map:
                    value = value_map[value]
                result[report_field] = value

        # Normalize enum fields.
        if "verdict" in result:
            result["verdict"] = self._to_verdict(result["verdict"])
        if "recommended_action" in result:
            result["recommended_action"] = self._to_action(result["recommended_action"])

        # Defaults.
        result.setdefault("confidence", 0.0)
        result.setdefault("risk", 0.0)
        result.setdefault("weight", 1.0)
        result.setdefault("evidence", [])
        result.setdefault("recommended_action", Action.WATCH)
        return result

    @staticmethod
    def _to_verdict(value: Any) -> Verdict:
        if isinstance(value, Verdict):
            return value
        try:
            return Verdict(str(value))
        except ValueError:
            return Verdict.NEUTRAL

    @staticmethod
    def _to_action(value: Any) -> Action:
        if isinstance(value, Action):
            return value
        try:
            return Action(str(value))
        except ValueError:
            return Action.WATCH


def register_prompt_agent(
    agent_id: str,
    name: str,
    domain: str,
    config: dict[str, Any],
    *,
    version: str = "0.1.0",
    tags: list[str] | None = None,
    override: bool = False,
) -> type[PromptAgent]:
    """Dynamically create a PromptAgent subclass and register it.

    This is the runtime equivalent of decorating a class with ``@register_agent``.
    """
    cls = type(
        f"{agent_id.replace('.', '_').title()}Agent",
        (PromptAgent,),
        {
            "agent_id": agent_id,
            "name": name,
            "domain": domain,
            "version": version,
            "_factory_config": config,
        },
    )
    get_registry().register(cls, domain=domain, tags=tags, override=override)
    return cls
