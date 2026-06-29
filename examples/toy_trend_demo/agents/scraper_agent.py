"""ToolAgent — a PromptAgent that fetches data via MCP tools before analysing.

This agent treats social/commerce scraping as a plugin capability.  The scraper
implementations live in ``tools/`` and are registered with the forge-agent MCP
gateway.  Each agent only declares which tools it needs via the ``tools``
config key, keeping the agent itself generic and reusable.

Configuration keys:
    - tools: list[str]              # MCP tool names to call before analysis
    - keyword_variable: str          # payload key that holds the keyword
    - keyword: str                   # fallback static keyword
    - prompt: str                    # analysis prompt (receives {data} and {keyword})
    - output_schema/mapping:         # same as PromptAgent
    - provider/model:                # LLM overrides
"""

from __future__ import annotations

import json
import logging
from typing import Any

from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.templates.prompt_agent import PromptAgent
from forge_agent.llm.protocol import chat
from forge_agent.mcp.gateway import get_gateway
from forge_agent.registry.registry import get_registry

log = logging.getLogger(__name__)


class ToolAgent(PromptAgent):
    """Generic agent that calls MCP tools to collect data, then analyses it."""

    agent_id = "tool.base"
    name = "Tool Agent"
    domain = "generic"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        # `tools` is a list of MCP tool names, e.g. ["weibo.hot_search"].
        # For backwards compatibility we also support `platform`.
        self.tools: list[str] = self.config.get("tools") or []
        self.platform: str = self.config.get("platform", "mock")
        if self.platform and self.platform != "mock" and not self.tools:
            self.tools = [f"{self.platform}.scrape"]
        self.keyword_variable: str = self.config.get("keyword_variable", "keyword")
        self.static_keyword: str | None = self.config.get("keyword")

    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        keyword = ctx.payload.get(self.keyword_variable) or self.static_keyword
        observation = await super().observe(ctx)
        observation["keyword"] = keyword
        return observation

    async def _collect_data(self, keyword: str | None) -> dict[str, Any]:
        """Call configured MCP tools or fall back to the legacy scraper registry."""
        if not self.tools:
            return {
                "platform": self.platform,
                "keyword": keyword,
                "items": [],
                "note": "no tools configured",
            }

        gateway = get_gateway()
        collected: dict[str, Any] = {
            "platform": self.platform,
            "keyword": keyword,
            "tools": {},
            "items": [],
        }
        for tool_name in self.tools:
            try:
                result = await gateway.call(tool_name, {"keyword": keyword})
                collected["tools"][tool_name] = result
                # Keep a flat item list for backwards compatibility with report rendering.
                items = result.get("items", []) if isinstance(result, dict) else []
                collected["items"].extend(items)
            except Exception as exc:
                log.warning("Tool %s failed for keyword=%s: %s", tool_name, keyword, exc)
                collected["tools"][tool_name] = {"error": str(exc), "items": []}
        # If every tool returned mock data, mark the aggregated result as mock too.
        tool_results = list(collected["tools"].values())
        if tool_results and all(
            isinstance(r, dict) and r.get("note") == "mock data" for r in tool_results
        ):
            collected["note"] = "mock data"

        return collected

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        keyword = observation.get("keyword")

        # Always try to collect real data via tools; mock_mode only controls LLM analysis.
        try:
            data = await self._collect_data(keyword)
        except Exception as exc:
            log.warning("Data collection failed for %s/%s: %s", self.agent_id, keyword, exc)
            data = {
                "platform": self.platform,
                "keyword": keyword,
                "error": str(exc),
                "items": [],
                "note": "mock data",
            }

        enriched = {
            **observation,
            "platform": self.platform,
            "keyword": keyword,
            "data": json.dumps(data, ensure_ascii=False, indent=2),
            "n_items": len(data.get("items", [])),
        }

        if self.mock_mode:
            rendered = self._render_prompt(enriched, self.mock_response)
            parsed = self._parse_response(rendered)
        else:
            if not self.prompt_template:
                return {"error": "No prompt template configured"}
            prompt = self._render_prompt(enriched, self.prompt_template)
            try:
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
                return {"error": f"LLM call failed: {exc}"}

        parsed["platform"] = self.platform
        parsed["keyword"] = keyword
        parsed["raw_data"] = data
        return parsed

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        report = await super().act(ctx, decision)
        report.raw["platform"] = decision.get("platform")
        report.raw["keyword"] = decision.get("keyword")
        report.raw["data"] = decision.get("raw_data")
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


# Backwards-compatible alias for existing YAML configs that use ``template: scraper_agent``.
ScraperAgent = ToolAgent
register_scraper_agent = register_tool_agent
