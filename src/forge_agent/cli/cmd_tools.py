"""`forge-agent tools` — list registered tools for a tenant."""

from __future__ import annotations

import argparse
from pathlib import Path

from forge_agent.builtin.tools import register_builtin_tools
from forge_agent.platform import LocalTenant, get_tool_registry


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("tools", help="List registered tools")
    p.add_argument(
        "--tenant",
        default="default",
        help="Tenant id (default: default)",
    )
    p.add_argument(
        "--detail",
        action="store_true",
        help="Show tool descriptions",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    register_builtin_tools()

    root_dir = args.project if args.project != Path.cwd() else None
    tenant = LocalTenant(args.tenant, root_dir=root_dir)
    registry = get_tool_registry()
    registry.load_manifest(tenant.get_shared_path() / "tools.yaml")

    names = registry.list_names()
    if not names:
        print(f"No tools found for tenant {args.tenant!r}.")
        return 0

    print(f"Tools for tenant {args.tenant!r}:")
    for name in names:
        tool = registry.get(name)
        if args.detail:
            print(f"  - {name}: {tool.description}")
        else:
            print(f"  - {name}")
    return 0
