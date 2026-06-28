"""PipelineConfig / PipelineLoader — run a full agent pipeline from YAML.

A pipeline config describes:
    - the mission metadata
    - static match context (home, away, city, date, ...)
    - external data sources to fetch and normalize
    - config-driven agents to register
    - a team definition (agent_ids, chief, mode)

The loader wires these pieces together and executes them via TeamRunner.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from forge_agent.core import Mission, Team
from forge_agent.core.contracts import AgentBoard
from forge_agent.core.factory import AgentFactory
from forge_agent.core.runner import TeamRunner
from forge_agent.data.normalizer import Normalizer, NormalizerConfig
from forge_agent.data.schema import OddsRecord, SchemaRecord
from forge_agent.data.source import DataSource, DataSourceConfig
from forge_agent.registry.registry import get_registry


def _deep_get(data: dict[str, Any], path: str) -> Any:
    """Resolve a dot-separated path in a nested dict."""
    current: Any = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


@dataclass
class PipelineConfig:
    """Declarative configuration for one end-to-end agent pipeline run."""

    mission: dict[str, Any] = field(default_factory=dict)
    match: dict[str, Any] = field(default_factory=dict)
    sources: list[dict[str, Any]] = field(default_factory=list)
    agents: list[dict[str, Any]] = field(default_factory=list)
    team: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineConfig:
        """Build a PipelineConfig from a parsed YAML/JSON dict."""
        return cls(
            mission=data.get("mission", {}),
            match=data.get("match", {}),
            sources=data.get("sources", []),
            agents=data.get("agents", []),
            team=data.get("team", {}),
        )


class PipelineLoader:
    """Load a pipeline config and execute it end-to-end."""

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    @classmethod
    def from_yaml(cls, path: str | Path) -> PipelineLoader:
        """Load a pipeline from a YAML file."""
        import yaml

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError("Pipeline YAML must contain a top-level mapping")
        return cls(PipelineConfig.from_dict(data))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineLoader:
        """Load a pipeline from a dict."""
        return cls(PipelineConfig.from_dict(data))

    async def run(
        self,
        *,
        extra_payload: dict[str, Any] | None = None,
        store: Any | None = None,
        aggregator: Any | None = None,
    ) -> AgentBoard:
        """Execute the configured pipeline and return the final AgentBoard."""
        # Ensure the generic chief is registered (idempotent; needed because
        # module-level decorators only run on first import).
        from forge_agent.builtin.chief_agent import ChiefAgent

        registry = get_registry()
        if "generic.chief" not in registry:
            registry.register(ChiefAgent, domain="generic", tags=["chief", "aggregator"])

        # 1. Register all config-driven agents.
        factory = AgentFactory()
        if self.config.agents:
            factory.load_dicts(self.config.agents)

        # 2. Fetch and normalize all data sources.
        records = await self._fetch_and_normalize_sources()

        # 3. Build the payload from match context + normalized records.
        payload = self._build_payload(records)
        if extra_payload:
            payload.update(extra_payload)

        # 4. Build team and mission.
        team = Team(**self.config.team, payload=payload)
        mission = Mission(
            mission_id=self.config.mission.get("mission_id", team.team_id),
            name=self.config.mission.get("name", team.name),
            description=self.config.mission.get("description", ""),
            team=team,
            payload={},
        )

        # 5. Run.
        return await TeamRunner(store=store, aggregator=aggregator).run(mission)

    async def _fetch_and_normalize_sources(self) -> list[SchemaRecord]:
        """Fetch every configured source and normalize it to a SchemaRecord."""
        records: list[SchemaRecord] = []
        for cfg in self.config.sources:
            source = DataSource(DataSourceConfig(**cfg))
            raw = await source.fetch()

            normalizer_cfg = NormalizerConfig(
                schema=cfg.get("normalizer", "odds"),
                field_map=cfg.get("field_map", {}),
                defaults=cfg.get("defaults", {}),
                transforms=cfg.get("transforms", {}),
            )
            normalizer = Normalizer(normalizer_cfg)
            record = normalizer.normalize(source, raw)
            records.append(record)
        return records

    def _build_payload(self, records: list[SchemaRecord]) -> dict[str, Any]:
        """Merge match context and normalized records into one agent payload."""
        payload: dict[str, Any] = dict(self.config.match)

        odds_records = [r for r in records if isinstance(r, OddsRecord)]
        if odds_records:
            payload.update(self._aggregate_odds(odds_records))

        # Generic evidence for all record types.
        evidence: list[str] = []
        for record in records:
            evidence.extend(record.to_evidence())
        if evidence:
            payload["source_evidence"] = evidence
            payload["sources"] = ", ".join(r.source for r in records)
            payload["source_count"] = len(records)

        return payload

    def _aggregate_odds(self, records: list[OddsRecord]) -> dict[str, Any]:
        """Aggregate multiple OddsRecords into a single set of payload fields.

        The canonical home/away names come from ``match`` config, not from the
        sources, so this method only returns odds values and source metadata.
        """
        if not records:
            return {}

        def _avg(values: list[float | None]) -> float | None:
            cleaned = [v for v in values if v is not None]
            return sum(cleaned) / len(cleaned) if cleaned else None

        home_odds = _avg([r.home_odds for r in records])
        draw_odds = _avg([r.draw_odds for r in records])
        away_odds = _avg([r.away_odds for r in records])

        result: dict[str, Any] = {
            "home_odds": home_odds,
            "draw_odds": draw_odds,
            "away_odds": away_odds,
            "odds_sources": [r.source for r in records],
        }

        if home_odds is not None and draw_odds is not None and away_odds is not None:
            result["odds_summary"] = (
                f"主队平均胜赔 {home_odds:.2f}, 平局 {draw_odds:.2f}, 客队平均胜赔 {away_odds:.2f}"
            )

        return result
