"""`forge-agent agent-types` — list built-in and tenant agent types."""

from __future__ import annotations

import argparse
from pathlib import Path

from forge_agent.builtin import AgentTypeRegistry
from forge_agent.platform import LocalTenant


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("agent-types", help="List available agent types")
    p.add_argument(
        "--tenant",
        default="default",
        help="Tenant id (default: default)",
    )
    p.add_argument(
        "--detail",
        action="store_true",
        help="Show full type definitions instead of just IDs",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    root_dir = args.project if args.project != Path.cwd() else None
    tenant = LocalTenant(args.tenant, root_dir=root_dir)
    registry = AgentTypeRegistry(tenant_shared_dir=tenant.get_shared_path() / "agent_types")

    types = registry.list()
    if not types:
        print(f"No agent types found for tenant {args.tenant!r}.")
        return 0

    print(f"Agent types for tenant {args.tenant!r}:")
    for agent_type in sorted(types, key=lambda t: t["type_id"]):
        type_id = agent_type["type_id"]
        name = agent_type.get("name", type_id)
        description = agent_type.get("description", "").strip().splitlines()[0]
        print(f"  - {type_id}: {name}")
        if description:
            print(f"      {description}")
        if args.detail:
            params = agent_type.get("params", [])
            if params:
                print("      params:")
                for param in params:
                    req = "required" if param.get("required") else "optional"
                    print(f"        - {param['name']} ({param['type']}, {req})")
    return 0
