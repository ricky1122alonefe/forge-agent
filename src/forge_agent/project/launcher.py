"""Project launcher: detect tenant/project context and dispatch TUI or CLI run."""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml

from forge_agent.core import Mission, Team
from forge_agent.core.factory import AgentFactory
from forge_agent.core.runner import TeamRunner
from forge_agent.exceptions import ForgeError
from forge_agent.llm.registry import get_registry
from forge_agent.platform import ConfigValidator, LLMConfigManager, LocalTenant
from forge_agent.project.state_store import RunRecord, StateStore, generate_run_id
from forge_agent.project.tui import run_menu

log = logging.getLogger(__name__)


def _ensure_builtin_agents() -> None:
    """Ensure built-in agents (e.g. generic.chief) are registered before a run."""
    from forge_agent.builtin.chief_agent import ChiefAgent
    from forge_agent.registry.registry import get_registry

    registry = get_registry()
    if "generic.chief" not in registry:
        registry.register(
            ChiefAgent,
            domain=ChiefAgent.domain,
            tags=["chief", "aggregator"],
        )


def _load_agents(factory: AgentFactory, agents_dir: Path) -> None:
    for yaml_file in sorted(agents_dir.glob("*.yaml")):
        log.info("Loading agents from %s", yaml_file)
        factory.load_yaml(yaml_file)


def _load_pipeline(pipeline_path: Path) -> dict:
    return yaml.safe_load(pipeline_path.read_text(encoding="utf-8")) or {}


def _detect_tenant_root(project_root: Path) -> Path | None:
    """Detect the forge-agent root directory from a local tenant project path."""
    try:
        if project_root.parent.parent.parent.name == "tenants":
            return project_root.parent.parent.parent.parent
    except IndexError:
        pass
    return None


def resolve_local_tenant(tenant_id: str, project_root: Path) -> LocalTenant:
    """Build a LocalTenant for a project, inferring storage root from path layout."""
    root_dir = _detect_tenant_root(project_root)
    return LocalTenant(tenant_id, root_dir=root_dir)


def _configure_llm(tenant: LocalTenant, project_root: Path) -> None:
    """Load the layered LLM config for this tenant/project and configure the registry."""
    cfg = LLMConfigManager(tenant).load(project_root.name)
    get_registry().configure(cfg)
    log.info(
        "LLM config loaded for tenant=%s project=%s (source=%s)",
        tenant.tenant_id,
        project_root.name,
        cfg.source_path,
    )


async def _run_pipeline(
    project_root: Path,
    tenant_id: str,
    pipeline_id: str,
    payload: dict,
    *,
    tenant: LocalTenant | None = None,
) -> RunRecord:
    _ensure_builtin_agents()
    local_tenant = tenant or resolve_local_tenant(tenant_id, project_root)
    ConfigValidator(
        project_root,
        tenant_id=local_tenant.tenant_id,
        root_dir=local_tenant.root_dir,
    ).validate(pipeline_id)

    _configure_llm(local_tenant, project_root)

    factory = AgentFactory()
    _load_agents(factory, project_root / "agents")

    pipeline_path = project_root / "pipelines" / f"{pipeline_id}.yaml"
    if not pipeline_path.exists():
        raise FileNotFoundError(f"Pipeline not found: {pipeline_path}")

    pipeline = _load_pipeline(pipeline_path)
    team = Team.from_dict(pipeline["team"])

    mission = Mission(
        mission_id=f"{pipeline_id}_run",
        name=pipeline["name"],
        description=pipeline.get("description", ""),
        team=team,
        payload=payload,
    )

    board = await TeamRunner().run(mission)

    record = RunRecord(
        run_id=generate_run_id(pipeline_id),
        timestamp=datetime.now(timezone.utc).isoformat(),
        pipeline_id=pipeline_id,
        pipeline_name=pipeline["name"],
        tenant_id=tenant_id,
        project_id=project_root.name,
        payload=payload,
        agent_reports=[
            report.model_dump() if hasattr(report, "model_dump") else dict(report.__dict__)
            for report in board.agents
        ],
        chief_summary=dict(board.summary) if board.summary else None,
        metadata={"agent_count": len(board.agents), "has_chief": board.summary is not None},
    )
    StateStore(project_root).save(record)
    return record


def _print_run(record: RunRecord) -> None:
    """Print a run record to the console."""
    print(f"\nPipeline: {record.pipeline_name}")
    for report in record.agent_reports:
        print(f"  [{report.get('name', '?')}] {report.get('raw', report)}")
    if record.chief_summary:
        print(f"Chief summary: {record.chief_summary}")
    print(f"Run saved: {record.run_id}")


def run_pipeline_cli(project_root: Path, tenant_id: str) -> int:
    """Run a pipeline selected by the user."""
    pipelines_dir = project_root / "pipelines"
    if not pipelines_dir.exists():
        print("No pipelines found. Create one first.")
        return 1

    pipeline_files = sorted(pipelines_dir.glob("*.yaml"))
    if not pipeline_files:
        print("No pipelines found. Create one first.")
        return 1

    print("\nAvailable pipelines:")
    for idx, pf in enumerate(pipeline_files, 1):
        data = yaml.safe_load(pf.read_text(encoding="utf-8")) or {}
        print(f"  [{idx}] {data.get('pipeline_id', pf.stem)} - {data.get('name', '')}")

    choice = input("Select pipeline (number): ").strip()
    try:
        pipeline_id = pipeline_files[int(choice) - 1].stem
    except (ValueError, IndexError):
        print("Invalid selection.")
        return 1

    payload_str = input("Payload (YAML/JSON, default {}): ").strip() or "{}"
    payload = yaml.safe_load(payload_str) or {}
    try:
        record = asyncio.run(_run_pipeline(project_root, tenant_id, pipeline_id, payload))
    except ForgeError as exc:
        print(exc.friendly())
        return 1

    _print_run(record)
    return 0


def _detect_project_root() -> Path:
    """Detect project root from cwd or environment.

    For now we assume the current working directory is the project root.
    """
    return Path.cwd().resolve()


def _detect_tenant_id(project_root: Path) -> str:
    """Infer tenant id from the local tenant path layout."""
    # Path is expected to be: .../tenants/{tenant}/projects/{project}
    try:
        if project_root.parent.parent.parent.name == "tenants":
            return project_root.parent.parent.name
    except IndexError:
        pass
    return "default"


def _list_runs(project_root: Path) -> int:
    store = StateStore(project_root)
    records = store.list()
    if not records:
        print("No runs found.")
        return 0
    print("Recent runs:")
    for record in records:
        print(f"  - {record.run_id}: {record.pipeline_name}")
    return 0


def _rerun(project_root: Path, tenant_id: str, run_id: str) -> int:
    store = StateStore(project_root)
    record = store.get(run_id)
    if record is None:
        print(f"Run {run_id!r} not found.")
        return 1
    asyncio.run(_run_pipeline(project_root, tenant_id, record.pipeline_id, record.payload))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="forge-agent project launcher")
    parser.add_argument(
        "--pipeline",
        "-p",
        default=None,
        help="Pipeline id to run (non-interactive)",
    )
    parser.add_argument(
        "--payload",
        default="{}",
        help="YAML/JSON payload string",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        type=Path,
        help="Project root directory (default: cwd)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List historical runs",
    )
    parser.add_argument(
        "--rerun",
        default=None,
        help="Re-run a previous run by id",
    )
    args = parser.parse_args(argv)

    project_root = (args.project_root or _detect_project_root()).resolve()
    tenant_id = _detect_tenant_id(project_root)

    if args.list:
        return _list_runs(project_root)

    if args.rerun:
        return _rerun(project_root, tenant_id, args.rerun)

    if args.pipeline:
        payload = yaml.safe_load(args.payload) or {}
        try:
            record = asyncio.run(_run_pipeline(project_root, tenant_id, args.pipeline, payload))
        except ForgeError as exc:
            print(exc.friendly())
            return 1

        _print_run(record)
        return 0

    try:
        return run_menu(project_root, tenant_id)
    except ForgeError as exc:
        print(exc.friendly())
        return 1
