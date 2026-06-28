"""SearchAgent — a configurable agent that searches, then analyzes results.

This template is useful for "intelligence gathering" experts in vertical
pipelines (e.g. football news, injury reports, rumors).  The agent:

    1. Renders a search query from the payload variables.
    2. Executes the search (mock / web / knowledge backend).
    3. Feeds the results into a prompt (or mock response) to produce a verdict.

Everything is driven by configuration, so a new search expert can be added
with YAML only.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from forge_agent.core.context import AgentContext
from forge_agent.core.contracts import AgentReport
from forge_agent.core.templates.prompt_agent import PromptAgent
from forge_agent.registry.registry import get_registry
from forge_agent.search.knowledge import KeywordKnowledgeSearcher
from forge_agent.search.web import WebSearcher

log = logging.getLogger(__name__)


class SearchAgent(PromptAgent):
    """Config-driven agent: search external sources, then synthesize a report."""

    agent_id = "search.base"
    name = "Search Agent"
    domain = "generic"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self.query_template: str = self.config.get("query_template", "{query}")
        self.search_backend: str = self.config.get("search_backend", "mock")
        self.mock_results: list[dict[str, Any]] = self.config.get("mock_results", [])
        self.search_kwargs: dict[str, Any] = self.config.get("search_kwargs", {})

    async def observe(self, ctx: AgentContext) -> dict[str, Any]:
        """Extract template variables from the payload, plus query hint."""
        observation = await super().observe(ctx)
        # Allow the config to define a raw query directly in the payload.
        observation.setdefault("query", ctx.payload.get("query", ""))
        return observation

    async def decide(self, ctx: AgentContext, observation: dict[str, Any]) -> dict[str, Any]:
        """Search, then analyze the results with the configured prompt."""
        query = self._render_prompt(observation, self.query_template)

        if self.mock_mode:
            results = list(self.mock_results)
        else:
            results = await self._execute_search(query)

        # Enrich observation with search output so the prompt can reference it.
        enriched = {
            **observation,
            "query": query,
            "search_results": json.dumps(results, ensure_ascii=False),
            "n_results": len(results),
        }

        if self.mock_mode:
            rendered = self._render_prompt(enriched, self.mock_response)
            parsed = self._parse_response(rendered)
        else:
            if not self.prompt_template:
                return {"error": "No prompt template configured"}
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
                return {"error": f"LLM call failed: {exc}"}

        # Preserve search metadata for downstream consumers / audit.
        parsed["query"] = query
        parsed["search_results"] = results
        parsed["search_backend"] = self.search_backend
        return parsed

    async def act(self, ctx: AgentContext, decision: dict[str, Any]) -> AgentReport:
        """Return a standard AgentReport with search metadata attached."""
        report = await super().act(ctx, decision)
        report.raw["search"] = {
            "query": decision.get("query"),
            "backend": decision.get("search_backend"),
            "results": decision.get("search_results", []),
        }
        return report

    async def _execute_search(self, query: str) -> list[dict[str, Any]]:
        """Dispatch to the configured search backend."""
        if self.search_backend == "web":
            searcher = WebSearcher()
            return await searcher.search(query, **self.search_kwargs)
        if self.search_backend == "knowledge":
            corpus_dir = self.search_kwargs.get("corpus_dir", "knowledge")
            searcher = KeywordKnowledgeSearcher(corpus_dir)
            return await searcher.search(query, **self.search_kwargs)
        if self.search_backend == "mock":
            return []
        log.warning("Unknown search backend %r for %s", self.search_backend, self.agent_id)
        return []


def register_search_agent(
    agent_id: str,
    name: str,
    domain: str,
    config: dict[str, Any],
    *,
    version: str = "0.1.0",
    tags: list[str] | None = None,
    override: bool = False,
) -> type[SearchAgent]:
    """Dynamically create a SearchAgent subclass and register it."""
    cls = type(
        f"{agent_id.replace('.', '_').title()}SearchAgent",
        (SearchAgent,),
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
