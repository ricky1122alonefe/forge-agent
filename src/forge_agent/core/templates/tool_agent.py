"""ToolAgent — fetch data via built-in tools, then analyze with prompt/LLM (P3.4)."""

from __future__ import annotations

import json
import logging
from typing import Any

from forge_agent.builtin.tools.executor import execute_tool
from forge_agent.builtin.tools.mode import ToolMode, resolve_tool_mode
from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.templates.prompt_agent import PromptAgent
from forge_agent.registry.registry import get_registry

log = logging.getLogger(__name__)


class ToolAgent(PromptAgent):
    """Agent that invokes configured tools before LLM/mock analysis."""

    agent_id = "tool.base"
    name = "Tool Agent"
    domain = "generic"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        tools = self.config.get("tools") or []
        self.tools: list[str] = list(tools) if isinstance(tools, list) else []
        self.platform: str = str(self.config.get("platform", "generic"))
        self.tool_mode: str = str(self.config.get("tool_mode", "auto"))
        self.keyword_variable: str = self.config.get("keyword_variable", "keyword")
        self.static_keyword: str | None = self.config.get("keyword")

    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        keyword = ctx.payload.get(self.keyword_variable) or self.static_keyword
        observation = await super().observe(ctx)
        observation["keyword"] = keyword
        observation["platform"] = self.platform
        return observation

    async def _collect_data(self, keyword: str | None) -> dict[str, Any]:
        if not self.tools:
            return {
                "platform": self.platform,
                "keyword": keyword,
                "items": [],
                "source": "none",
                "note": "no tools configured",
            }

        mode = resolve_tool_mode(self.tool_mode)
        if self.mock_mode:
            mode = ToolMode.MOCK

        collected: dict[str, Any] = {
            "platform": self.platform,
            "keyword": keyword,
            "tool_mode": mode.value,
            "tools": {},
            "items": [],
        }
        sources: set[str] = set()

        for tool_name in self.tools:
            try:
                result = await execute_tool(
                    tool_name,
                    keyword=keyword or "",
                    tool_mode=mode,
                )
            except Exception as exc:
                log.warning("Tool %s failed for keyword=%s: %s", tool_name, keyword, exc)
                result = {
                    "platform": self.platform,
                    "keyword": keyword,
                    "items": [],
                    "source": "fallback",
                    "error": str(exc),
                }
            collected["tools"][tool_name] = result
            if isinstance(result, dict):
                sources.add(str(result.get("source", "unknown")))
                items = result.get("items", [])
                if isinstance(items, list):
                    collected["items"].extend(items)

        if sources == {"mock"}:
            collected["source"] = "mock"
        elif "real" in sources:
            collected["source"] = "real" if "fallback" not in sources else "mixed"
        elif "fallback" in sources:
            collected["source"] = "fallback"
        else:
            collected["source"] = next(iter(sources), "unknown")
        return collected

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        keyword = observation.get("keyword")

        if self.mock_mode:
            parsed = self._parse_response(self._render_prompt(observation, self.mock_response))
            parsed["platform"] = self.platform
            parsed["keyword"] = keyword
            parsed["raw_data"] = {"source": "mock", "skipped_tools": True}
            return parsed

        data = await self._collect_data(keyword)
        enriched = {
            **observation,
            "platform": self.platform,
            "keyword": keyword,
            "data": json.dumps(data, ensure_ascii=False, indent=2),
            "n_items": len(data.get("items", [])),
        }

        if not self.prompt_template:
            return {"error": "No prompt template configured", "raw_data": data}

        prompt = self._render_prompt(enriched, self.prompt_template)
        try:
            from forge_agent.llm.protocol import chat

            response = await chat(
                prompt,
                provider=self.llm_provider,
                model=self.llm_model,
                temperature=self.temperature,
                agent_id=self.agent_id,
            )
            parsed = self._parse_response(response.content)
        except Exception as exc:
            log.warning("LLM call failed for %s: %s", self.agent_id, exc)
            return {"error": f"LLM call failed: {exc}", "raw_data": data}

        parsed["platform"] = self.platform
        parsed["keyword"] = keyword
        parsed["raw_data"] = data
        return parsed

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        report = await super().act(ctx, decision)
        report.raw["platform"] = decision.get("platform")
        report.raw["keyword"] = decision.get("keyword")
        report.raw["data"] = decision.get("raw_data")
        report.raw["tool_mode"] = self.tool_mode
        return report


def register_tool_agent(
    agent_id: str,
    name: str,
    domain: str,
    config: dict[str, Any],
    *,
    version: str = "0.1.0",
    tags: list[str] | None = None,
    override: bool = False,
) -> type[ToolAgent]:
    """Dynamically create a ToolAgent subclass and register it."""
    cls = type(
        f"{agent_id.replace('.', '_').title()}ToolAgent",
        (ToolAgent,),
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


register_scraper_agent = register_tool_agent
