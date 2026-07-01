"""Project YAML configuration validator.

Validates agent and pipeline definitions before runtime so that missing
fields, unknown templates, missing tools, and dangling agent references are
caught with a clear error message instead of a mid-run traceback.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

import yaml

from forge_agent.core.factory import AgentFactory
from forge_agent.exceptions import ConfigValidationError
from forge_agent.platform.local_tenant import LocalTenant
from forge_agent.platform.tool_registry import get_tool_registry


class ConfigValidator:
    """Validate a forge-agent project before execution."""

    _valid_team_modes: ClassVar[set[str]] = {"parallel", "sequential"}

    def __init__(
        self,
        project_root: Path,
        *,
        tenant_id: str = "default",
        root_dir: Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.tenant_id = tenant_id
        self.root_dir = root_dir

        # Seed built-in tools and any tenant-scoped tool manifest.
        self._load_tools()

        # Discover supported agent templates dynamically.
        self._templates = set(AgentFactory().list_templates())

    # ------------------------------------------------------------------
    # Built-in agent discovery
    # ------------------------------------------------------------------

    def _builtin_agent_ids(self) -> set[str]:
        """Return IDs of built-in agents registered in the global registry."""
        ids = {"generic.chief"}
        try:
            from forge_agent.builtin import ChiefAgent  # noqa: F401
            from forge_agent.registry.registry import get_registry

            ids.update(get_registry().list())
        except Exception:  # pragma: no cover - defensive fallback
            pass
        return ids

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def validate(self, pipeline_id: str) -> None:
        """Validate the whole project for a given pipeline.

        Raises:
            ConfigValidationError: if any validation error is found.
        """
        errors: list[str] = []

        agents_dir = self.project_root / "agents"
        agents_from_files = self._collect_agents_from_files(agents_dir, errors)

        pipeline_path = self.project_root / "pipelines" / f"{pipeline_id}.yaml"
        pipeline_data, pipeline_agents = self._load_pipeline(pipeline_path, errors)

        all_agents: dict[str, str] = {**agents_from_files, **pipeline_agents}

        self._validate_pipeline(pipeline_data, all_agents, errors)

        if errors:
            raise ConfigValidationError(
                errors, path=str(self.project_root / "pipelines" / f"{pipeline_id}.yaml")
            )

    def validate_agents_only(self) -> None:
        """Validate only agent YAML files in the project."""
        errors: list[str] = []
        agents_dir = self.project_root / "agents"
        self._collect_agents_from_files(agents_dir, errors)
        if errors:
            raise ConfigValidationError(errors, path=str(agents_dir))

    # ------------------------------------------------------------------
    # Tool loading
    # ------------------------------------------------------------------

    def _load_tools(self) -> None:
        """Register built-in tools and tenant/project shared manifests."""
        from forge_agent.builtin.tools import register_builtin_tools

        register_builtin_tools()
        tenant = LocalTenant(self.tenant_id, root_dir=self.root_dir)
        registry = get_tool_registry()
        registry.load_manifest(tenant.get_shared_path() / "tools.yaml")
        # Also honour project-local tools manifest if present.
        registry.load_manifest(self.project_root / "tools" / "tools.yaml")

    # ------------------------------------------------------------------
    # Agent collection
    # ------------------------------------------------------------------

    def _collect_agents_from_files(self, agents_dir: Path, errors: list[str]) -> dict[str, str]:
        """Load and validate agent definitions from agents/*.yaml.

        Returns a mapping of agent_id -> source file path.
        """
        agents: dict[str, str] = {}
        if not agents_dir.exists():
            return agents

        for yaml_file in sorted(agents_dir.glob("*.yaml")):
            raw = self._load_yaml(yaml_file, errors)
            if raw is None:
                continue

            agent_list = self._extract_agent_list(raw, str(yaml_file), errors)
            for agent in agent_list:
                self._validate_agent(agent, str(yaml_file), errors)
                agent_id = agent.get("agent_id")
                if not isinstance(agent_id, str):
                    continue
                if agent_id in agents:
                    errors.append(
                        f"Duplicate agent_id {agent_id!r} found in "
                        f"{agents[agent_id]} and {yaml_file}"
                    )
                    continue
                agents[agent_id] = str(yaml_file)
        return agents

    # ------------------------------------------------------------------
    # Pipeline loading
    # ------------------------------------------------------------------

    def _load_pipeline(
        self, pipeline_path: Path, errors: list[str]
    ) -> tuple[dict[str, Any], dict[str, str]]:
        """Load pipeline YAML and any inline agents.

        Returns (pipeline_data, inline_agent_map).
        """
        if not pipeline_path.exists():
            errors.append(f"Pipeline file not found: {pipeline_path}")
            return {}, {}

        raw = self._load_yaml(pipeline_path, errors)
        if raw is None or not isinstance(raw, dict):
            errors.append(f"Pipeline YAML must be a mapping: {pipeline_path}")
            return {}, {}

        inline_agents: dict[str, str] = {}
        if "agents" in raw and isinstance(raw["agents"], list):
            for agent in raw["agents"]:
                self._validate_agent(agent, str(pipeline_path), errors)
                agent_id = agent.get("agent_id")
                if isinstance(agent_id, str):
                    if agent_id in inline_agents:
                        errors.append(f"Duplicate inline agent_id {agent_id!r} in {pipeline_path}")
                    else:
                        inline_agents[agent_id] = str(pipeline_path)

        return raw, inline_agents

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_agent(self, agent: Any, source: str, errors: list[str]) -> None:
        """Validate a single agent definition dict."""
        if not isinstance(agent, dict):
            errors.append(f"Agent entry is not a mapping in {source}")
            return

        for field in ("agent_id", "name", "template"):
            if not agent.get(field):
                errors.append(
                    f"Agent {agent.get('agent_id', '<unknown>')!r} missing required field "
                    f"{field!r} in {source}"
                )

        template = agent.get("template")
        if template and template not in self._templates:
            errors.append(
                f"Agent {agent.get('agent_id', '<unknown>')!r} uses unknown template "
                f"{template!r}. Available: {sorted(self._templates)} in {source}"
            )

        config = agent.get("config", {})
        if not isinstance(config, dict):
            errors.append(
                f"Agent {agent.get('agent_id', '<unknown>')!r} config must be a mapping in {source}"
            )
            return

        tools = config.get("tools", [])
        if tools:
            if not isinstance(tools, list):
                errors.append(
                    f"Agent {agent.get('agent_id', '<unknown>')!r} config.tools must be a list in {source}"
                )
            else:
                registry = get_tool_registry()
                for tool_name in tools:
                    if tool_name not in registry.list_names():
                        errors.append(
                            f"Agent {agent.get('agent_id', '<unknown>')!r} references unknown tool "
                            f"{tool_name!r}. Run 'forge-agent tools' to see available tools. "
                            f"Source: {source}"
                        )

        # Template-specific config checks for prompt-based agents.
        if template in {"prompt_agent", "search_agent"} and not config.get("mock_mode"):
            if not config.get("prompt"):
                errors.append(
                    f"Agent {agent.get('agent_id', '<unknown>')!r} requires config.prompt "
                    f"when mock_mode is false in {source}"
                )
            if not config.get("output_schema"):
                errors.append(
                    f"Agent {agent.get('agent_id', '<unknown>')!r} requires config.output_schema "
                    f"in {source}"
                )
            if not config.get("output_mapping"):
                errors.append(
                    f"Agent {agent.get('agent_id', '<unknown>')!r} requires config.output_mapping "
                    f"in {source}"
                )

    def _validate_pipeline(
        self,
        pipeline: dict[str, Any],
        all_agents: dict[str, str],
        errors: list[str],
    ) -> None:
        """Validate the top-level pipeline mapping and team references."""
        source = str(
            self.project_root / "pipelines" / f"{pipeline.get('pipeline_id', '<unknown>')}.yaml"
        )

        for field in ("pipeline_id", "name", "team"):
            if not pipeline.get(field):
                errors.append(f"Pipeline missing required field {field!r} in {source}")

        team = pipeline.get("team")
        if not isinstance(team, dict):
            errors.append(f"Pipeline field 'team' must be a mapping in {source}")
            return

        for field in ("team_id", "name", "agent_ids"):
            if not team.get(field):
                errors.append(f"Team missing required field {field!r} in {source}")

        mode = team.get("mode", "parallel")
        if mode not in self._valid_team_modes:
            errors.append(
                f"Team mode {mode!r} is invalid. Use one of {sorted(self._valid_team_modes)} in {source}"
            )

        agent_ids = team.get("agent_ids", [])
        if not isinstance(agent_ids, list):
            errors.append(f"Team agent_ids must be a list in {source}")
            return

        known_agents = set(all_agents) | self._builtin_agent_ids()

        for agent_id in agent_ids:
            if agent_id not in known_agents:
                errors.append(
                    f"Team references unknown agent {agent_id!r}. "
                    f"Define it in agents/*.yaml or inline under 'agents:' in the pipeline. "
                    f"Source: {source}"
                )

        chief_id = team.get("chief_id")
        if chief_id and chief_id not in known_agents:
            errors.append(
                f"Team references unknown chief {chief_id!r}. "
                f"Define it in agents/*.yaml or inline under 'agents:' in the pipeline. "
                f"Source: {source}"
            )

    # ------------------------------------------------------------------
    # YAML utilities
    # ------------------------------------------------------------------

    def _load_yaml(self, path: Path, errors: list[str]) -> Any:
        try:
            return yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"Invalid YAML in {path}: {exc}")
            return None
        except FileNotFoundError:
            errors.append(f"File not found: {path}")
            return None

    @staticmethod
    def _extract_agent_list(raw: Any, source: str, errors: list[str]) -> list[dict[str, Any]]:
        """Extract a list of agent dicts from either {'agents': [...]} or [...]."""
        if isinstance(raw, dict) and "agents" in raw:
            agents = raw["agents"]
        elif isinstance(raw, list):
            agents = raw
        else:
            errors.append(
                f"Agent YAML must contain an 'agents:' list or be a top-level list in {source}"
            )
            return []

        if not isinstance(agents, list):
            errors.append(f"'agents' must be a list in {source}")
            return []
        return agents
