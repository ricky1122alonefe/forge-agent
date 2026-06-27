"""AgentRequirements — structured spec for a desired Agent.

RequirementsParser — converts a natural-language request into a structured
`AgentRequirements` object. Uses an LLM (when available) to extract fields.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from forge_agent.core.agent_type import AgentType

log = logging.getLogger(__name__)


@dataclass
class FieldSpec:
    """An input or output field of an Agent."""

    name: str
    type: str  # "str" | "int" | "float" | "dict" | "list" | "bool"
    description: str
    required: bool = True
    example: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentRequirements:
    """Structured spec for a to-be-generated Agent.

    This is the input to CodeGenerator. The Generator fills in code that
    satisfies this spec, the Validator checks it, the Sandbox tests it.
    """

    agent_id: str
    name: str
    domain: str
    description: str
    agent_type: AgentType = AgentType.GENERAL
    inputs: list[FieldSpec] = field(default_factory=list)
    outputs: list[FieldSpec] = field(default_factory=list)
    capabilities_required: list[str] = field(default_factory=list)  # ["search","llm","prompt_manager"]
    mcp_tools: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)  # hard rules like "no stock trading"
    examples: list[dict[str, Any]] = field(default_factory=list)  # sample input/output
    raw_requirement: str = ""  # original natural language

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "domain": self.domain,
            "description": self.description,
            "agent_type": self.agent_type.value,
            "inputs": [f.to_dict() for f in self.inputs],
            "outputs": [f.to_dict() for f in self.outputs],
            "capabilities_required": self.capabilities_required,
            "mcp_tools": self.mcp_tools,
            "constraints": self.constraints,
            "examples": self.examples,
            "raw_requirement": self.raw_requirement,
        }

    def to_prompt(self) -> str:
        """Render the spec into a developer-friendly prompt section."""
        lines: list[str] = [
            f"Agent ID: {self.agent_id}",
            f"Name: {self.name}",
            f"Domain: {self.domain}",
            f"Type: {self.agent_type.value} ({self.agent_type.description})",
            f"Description: {self.description}",
        ]
        if self.inputs:
            lines.append("\nInputs:")
            for f in self.inputs:
                req = "required" if f.required else "optional"
                lines.append(f"  - {f.name} ({f.type}, {req}): {f.description}")
        if self.outputs:
            lines.append("\nOutputs:")
            for f in self.outputs:
                lines.append(f"  - {f.name} ({f.type}): {f.description}")
        if self.capabilities_required:
            lines.append(f"\nCapabilities required: {', '.join(self.capabilities_required)}")
        if self.mcp_tools:
            lines.append(f"MCP tools: {', '.join(self.mcp_tools)}")
        if self.constraints:
            lines.append("\nHard constraints:")
            for c in self.constraints:
                lines.append(f"  - {c}")
        if self.examples:
            lines.append("\nExamples:")
            for i, ex in enumerate(self.examples, 1):
                lines.append(f"  Example {i}: {ex}")
        return "\n".join(lines)


# ------------------------------------------------------------------ Parser

class RequirementsParser:
    """Convert natural language → `AgentRequirements`.

    Two modes:
        1. With LLM: pass `llm_chat=chat` and it will call out for parsing.
        2. Without LLM: extract obvious fields via regex + heuristics (less
           accurate, but works offline for demos and tests).

    Keyword mappings are configurable — use register_domain(), register_capability(),
    and register_agent_type_keywords() to extend at runtime.
    """

    DEFAULT_CAPABILITIES = ["log"]  # always
    COMMON_CAPABILITIES: dict[str, list[str]] = {
        "search": ["搜索", "search", "查询", "look up", "find"],
        "llm": ["大模型", "llm", "ai", "智能", "推理"],
        "prompt_manager": ["prompt", "提示词", "提示"],
        "memory": ["记忆", "memory", "历史", "history"],
    }
    DOMAIN_KEYWORDS: dict[str, list[str]] = {
        "stock": ["股票", "股价", "stock", "share", "nvda", "tsla"],
        "football": ["球赛", "足球", "比赛", "match", "football", "world cup"],
        "social": ["舆情", "微博", "twitter", "social", "评论", "评论"],
        "office": ["办公", "邮件", "邮件", "email", "office", "日程"],
        "ecommerce": ["商品", "订单", "电商", "product", "order"],
    }
    AGENT_TYPE_KEYWORDS: dict[str, list[str]] = {
        "scraper": ["抓取", "爬取", "scrape", "crawl", "fetch", "采集"],
        "analyzer": ["分析", "analyze", "统计", "insight", "洞察"],
        "monitor": ["监控", "monitor", "告警", "alert", "watch", "检测"],
        "generator": ["生成", "generate", "create", "写", "compose", "创作"],
    }

    def __init__(self, *, llm_chat: Any = None) -> None:
        """Args:
            llm_chat: Async callable matching `forge_agent.llm.chat`'s signature.
        """
        self.llm_chat = llm_chat

    # ------------------------------------------------------------------ Registration API

    @classmethod
    def register_domain(cls, domain: str, keywords: list[str]) -> None:
        """Register or extend a domain with keywords.

        Example::

            RequirementsParser.register_domain("healthcare", ["医疗", "医院", "health", "patient"])
        """
        existing = cls.DOMAIN_KEYWORDS.get(domain, [])
        for kw in keywords:
            if kw not in existing:
                existing.append(kw)
        cls.DOMAIN_KEYWORDS[domain] = existing

    @classmethod
    def register_capability(cls, capability: str, keywords: list[str]) -> None:
        """Register or extend a capability with keywords.

        Example::

            RequirementsParser.register_capability("database", ["数据库", "database", "sql", "db"])
        """
        existing = cls.COMMON_CAPABILITIES.get(capability, [])
        for kw in keywords:
            if kw not in existing:
                existing.append(kw)
        cls.COMMON_CAPABILITIES[capability] = existing

    @classmethod
    def register_agent_type_keywords(cls, agent_type: str, keywords: list[str]) -> None:
        """Register or extend keywords for an agent type.

        Example::

            RequirementsParser.register_agent_type_keywords("scraper", ["download", "下载"])
        """
        existing = cls.AGENT_TYPE_KEYWORDS.get(agent_type, [])
        for kw in keywords:
            if kw not in existing:
                existing.append(kw)
        cls.AGENT_TYPE_KEYWORDS[agent_type] = existing

    async def parse(self, requirement: str) -> AgentRequirements:
        """Parse a natural-language description into AgentRequirements."""
        if self.llm_chat is not None:
            return await self._parse_with_llm(requirement)
        return self._parse_heuristic(requirement)

    # ------------------------------------------------------------------ LLM mode

    async def _parse_with_llm(self, requirement: str) -> AgentRequirements:
        from forge_agent.generator.prompts import REQUIREMENTS_PARSER_SYSTEM

        user_msg = f"用户需求：\n{requirement}\n\n请输出 JSON。"
        try:
            response = await self.llm_chat(
                [
                    {"role": "system", "content": REQUIREMENTS_PARSER_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.1,
            )
            data = _extract_json(response.content if hasattr(response, "content") else str(response))
            return self._from_dict(data, raw=requirement)
        except Exception:  # noqa: BLE001
            log.exception("LLM requirements parse failed; falling back to heuristic")
            return self._parse_heuristic(requirement)

    def _from_dict(self, data: dict[str, Any], *, raw: str) -> AgentRequirements:
        # Parse agent_type from string or default to GENERAL
        agent_type_str = data.get("agent_type", "general")
        try:
            agent_type = AgentType.from_string(agent_type_str)
        except ValueError:
            log.warning(f"Unknown agent_type '{agent_type_str}', defaulting to GENERAL")
            agent_type = AgentType.GENERAL
        
        return AgentRequirements(
            agent_id=str(data.get("agent_id") or _slug_agent_id(data.get("name", "agent"))),
            name=str(data.get("name") or "Generated Agent"),
            domain=str(data.get("domain") or "generic"),
            description=str(data.get("description") or raw),
            agent_type=agent_type,
            inputs=[FieldSpec(**f) if isinstance(f, dict) else f for f in data.get("inputs", [])],
            outputs=[FieldSpec(**f) if isinstance(f, dict) else f for f in data.get("outputs", [])],
            capabilities_required=list(data.get("capabilities_required", [])),
            mcp_tools=list(data.get("mcp_tools", [])),
            constraints=list(data.get("constraints", [])),
            examples=list(data.get("examples", [])),
            raw_requirement=raw,
        )

    # ------------------------------------------------------------------ Heuristic mode

    def _parse_heuristic(self, requirement: str) -> AgentRequirements:
        req = requirement.strip()
        name = self._guess_name(req)
        domain = self._guess_domain(req)
        agent_id = _slug_agent_id(name)
        caps = self._guess_capabilities(req)
        agent_type = self._guess_agent_type(req)
        return AgentRequirements(
            agent_id=agent_id,
            name=name,
            domain=domain,
            description=req,
            agent_type=agent_type,
            capabilities_required=caps,
            inputs=[FieldSpec(name="payload", type="dict", description="Run payload", required=True)],
            outputs=[
                FieldSpec(name="verdict", type="str", description="Decision verdict"),
                FieldSpec(name="confidence", type="float", description="Confidence 0-1"),
                FieldSpec(name="evidence", type="list", description="Supporting evidence"),
            ],
            constraints=[],
            examples=[],
            raw_requirement=req,
        )

    def _guess_name(self, req: str) -> str:
        # First 6-12 meaningful chars
        cleaned = re.sub(r"[【】\[\]\s]+", " ", req).strip()
        if not cleaned:
            return "Generated Agent"
        # Take first phrase (split on common Chinese/English punctuation)
        for sep in ["，", ",", "。", ".", ";", "；", "（", "("]:
            if sep in cleaned:
                cleaned = cleaned.split(sep)[0]
                break
        if len(cleaned) > 30:
            cleaned = cleaned[:30]
        return cleaned or "Generated Agent"

    def _guess_domain(self, req: str) -> str:
        req_lower = req.lower()
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            for kw in keywords:
                if kw in req_lower:
                    return domain
        return "generic"

    def _guess_capabilities(self, req: str) -> list[str]:
        caps = list(self.DEFAULT_CAPABILITIES)
        req_lower = req.lower()
        for cap, keywords in self.COMMON_CAPABILITIES.items():
            for kw in keywords:
                if kw in req_lower:
                    if cap not in caps:
                        caps.append(cap)
                    break
        return caps

    def _guess_agent_type(self, req: str) -> AgentType:
        """Guess the agent type from the requirement text."""
        req_lower = req.lower()
        for agent_type_str, keywords in self.AGENT_TYPE_KEYWORDS.items():
            if any(kw in req_lower for kw in keywords):
                try:
                    return AgentType.from_string(agent_type_str)
                except ValueError:
                    log.warning(f"Unknown agent_type '{agent_type_str}' in AGENT_TYPE_KEYWORDS")
                    continue
        return AgentType.GENERAL


def _slug_agent_id(name: str) -> str:
    """Turn a name into a valid agent_id."""
    s = re.sub(r"[^a-zA-Z0-9_]+", "_", name.lower()).strip("_")
    return s or "generated_agent"


def _extract_json(text: str) -> dict[str, Any]:
    """Try to extract a JSON object from LLM output (may be wrapped in markdown)."""
    text = text.strip()
    # Strip ```json ... ``` fences
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    # Find first { ... last }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)
