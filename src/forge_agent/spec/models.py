"""AgentSpec — structured definition for a generated Agent asset."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class AgentPrimitive(str, Enum):
    """Composable agent building blocks (AGENT_PLAN v1)."""

    FETCHER = "fetcher"
    SEARCHER = "searcher"
    REASONER = "reasoner"
    SYNTHESIZER = "synthesizer"
    MONITOR = "monitor"
    GENERATOR = "generator"


class SchemaProfile(str, Enum):
    """Output/prompt profile for Reasoner and related primitives."""

    ANALYSIS = "analysis"
    SENTIMENT = "sentiment"
    SUMMARY = "summary"
    EXTRACT = "extract"
    COMPARE = "compare"
    RISK = "risk"
    GENERATE = "generate"
    MONITOR = "monitor"


@dataclass
class MockCase:
    """Golden input for generate-and-test smoke runs."""

    name: str
    input: dict[str, Any]
    expect_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgentSpec:
    """Portable agent definition produced by AgentSpecGenerator."""

    agent_id: str
    name: str
    domain: str = "generic"
    template: str = "prompt_agent"
    primitive: AgentPrimitive = AgentPrimitive.REASONER
    description: str = ""
    requirement: str = ""
    planner: str = "rule"
    schema_profile: SchemaProfile = SchemaProfile.ANALYSIS
    tags: list[str] = field(default_factory=lambda: ["generated"])
    config: dict[str, Any] = field(default_factory=dict)
    mock_cases: list[MockCase] = field(default_factory=list)
    capabilities: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "domain": self.domain,
            "template": self.template,
            "primitive": self.primitive.value,
            "description": self.description,
            "requirement": self.requirement,
            "planner": self.planner,
            "schema_profile": self.schema_profile.value,
            "tags": self.tags,
            "config": self.config,
            "mock_cases": [c.to_dict() for c in self.mock_cases],
            "capabilities": dict(self.capabilities),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentSpec:
        primitive = AgentPrimitive(data.get("primitive", AgentPrimitive.REASONER.value))
        profile_raw = data.get("schema_profile", SchemaProfile.ANALYSIS.value)
        try:
            schema_profile = SchemaProfile(profile_raw)
        except ValueError:
            schema_profile = SchemaProfile.ANALYSIS
        cases = [MockCase(**c) if isinstance(c, dict) else c for c in data.get("mock_cases", [])]
        return cls(
            agent_id=str(data["agent_id"]),
            name=str(data.get("name", data["agent_id"])),
            domain=str(data.get("domain", "generic")),
            template=str(data.get("template", "prompt_agent")),
            primitive=primitive,
            description=str(data.get("description", "")),
            requirement=str(data.get("requirement", "")),
            planner=str(data.get("planner", "rule")),
            schema_profile=schema_profile,
            tags=list(data.get("tags", ["generated"])),
            config=dict(data.get("config", {})),
            mock_cases=cases,
            capabilities=dict(data.get("capabilities", {})),
        )
