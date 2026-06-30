"""Terminal UI for configuring agents and pipelines inside a project."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import Any

import yaml

from forge_agent.builtin import AgentTypeRegistry
from forge_agent.project.agent_builder import build_agent_yaml, build_pipeline_yaml

log = logging.getLogger(__name__)


def _input_required(prompt: str) -> str:
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("This field is required.")


def _input_optional(prompt: str, default: Any = None) -> Any:
    value = input(prompt).strip()
    if not value:
        return default
    return value


def _choose_from_list(items: list[str], prompt: str = "Select:") -> str | None:
    if not items:
        print("No items available.")
        return None
    for idx, item in enumerate(items, 1):
        print(f"  [{idx}] {item}")
    while True:
        choice = input(f"{prompt} (1-{len(items)}): ").strip()
        if choice.lower() in ("q", "quit", "exit", ""):
            return None
        try:
            idx = int(choice)
            if 1 <= idx <= len(items):
                return items[idx - 1]
        except ValueError:
            pass
        print("Invalid choice. Enter a number or q to cancel.")


def _prompt_for_params(params: list[dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for param in params:
        name = param["name"]
        ptype = param.get("type", "string")
        required = param.get("required", False)
        description = param.get("description", "")
        default = param.get("default")

        prompt = f"{name}"
        if description:
            prompt += f" ({description})"
        if default is not None:
            prompt += f" [default: {default}]"
        prompt += ": "

        value = _input_required(prompt) if required else _input_optional(prompt, default)

        if ptype == "number" and value is not None:
            with contextlib.suppress(ValueError):
                value = float(value)
        values[name] = value
    return values


def create_agent(project_root: Path, registry: AgentTypeRegistry) -> Path | None:
    """Interactive flow to create an agent YAML file."""
    type_ids = registry.list_type_ids()
    type_id = _choose_from_list(type_ids, "Select agent type")
    if type_id is None:
        return None

    type_def = registry.get(type_id)
    print(f"\nCreating agent of type '{type_id}': {type_def.get('name')}")

    agent_id = _input_required("Agent id (e.g. weibo_scraper): ")
    params = _prompt_for_params(type_def.get("params", []))

    yaml_text = build_agent_yaml(type_def, agent_id, params)
    agents_dir = project_root / "agents"
    agents_dir.mkdir(exist_ok=True)
    target = agents_dir / f"{agent_id}.yaml"
    target.write_text(yaml_text, encoding="utf-8")

    print(f"\n✓ Created agent: {target}")
    return target


def create_pipeline(project_root: Path) -> Path | None:
    """Interactive flow to create a pipeline YAML file."""
    agents_dir = project_root / "agents"
    if not agents_dir.exists():
        print("No agents found. Create an agent first.")
        return None

    agent_files = sorted(agents_dir.glob("*.yaml"))
    if not agent_files:
        print("No agents found. Create an agent first.")
        return None

    agent_ids: list[str] = []
    for yaml_file in agent_files:
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8")) or {}
        for agent in data.get("agents", []):
            agent_ids.append(agent["agent_id"])

    if not agent_ids:
        print("No agents found in YAML files.")
        return None

    print("\nSelect agents to include (comma-separated numbers, e.g. 1,3):")
    for idx, aid in enumerate(agent_ids, 1):
        print(f"  [{idx}] {aid}")

    selection = _input_required("Agents: ")
    try:
        indices = [int(x.strip()) for x in selection.split(",")]
        selected = [agent_ids[i - 1] for i in indices if 1 <= i <= len(agent_ids)]
    except ValueError:
        print("Invalid selection.")
        return None

    if not selected:
        print("No agents selected.")
        return None

    use_chief = _input_optional("Add chief agent? (y/n) [y]: ", "y")
    chief_id = "generic.chief" if use_chief in ("y", "Y", "yes", "Yes") else None

    pipeline_id = _input_required("Pipeline id (e.g. trend): ")
    pipeline_name = _input_optional("Pipeline name: ", pipeline_id)

    yaml_text = build_pipeline_yaml(
        pipeline_id,
        pipeline_name,
        selected,
        chief_id=chief_id,
        description="Pipeline generated via project TUI",
    )
    pipelines_dir = project_root / "pipelines"
    pipelines_dir.mkdir(exist_ok=True)
    target = pipelines_dir / f"{pipeline_id}.yaml"
    target.write_text(yaml_text, encoding="utf-8")

    print(f"\n✓ Created pipeline: {target}")
    return target


def run_menu(project_root: Path, tenant_id: str) -> int:
    """Run the interactive TUI loop."""
    registry = AgentTypeRegistry(
        tenant_shared_dir=project_root.parent.parent / "shared" / "agent_types"
    )

    while True:
        print("\n=== forge-agent project menu ===")
        print(f"Project: {project_root.name} | Tenant: {tenant_id}")
        print("  [1] Create agent")
        print("  [2] Create pipeline")
        print("  [3] Run pipeline")
        print("  [q] Quit")
        choice = input("Choose: ").strip().lower()

        if choice == "1":
            create_agent(project_root, registry)
        elif choice == "2":
            create_pipeline(project_root)
        elif choice == "3":
            from forge_agent.project.launcher import run_pipeline_cli

            run_pipeline_cli(project_root, tenant_id)
        elif choice in ("q", "quit", "exit", ""):
            print("Goodbye.")
            return 0
        else:
            print("Invalid choice.")
