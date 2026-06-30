"""`forge-agent list-projects` — list projects for a tenant."""

from __future__ import annotations

import argparse
from pathlib import Path

from forge_agent.platform import LocalTenant


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("list-projects", help="List projects for a tenant")
    p.add_argument(
        "--tenant",
        default="default",
        help="Tenant id (default: default)",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    root_dir = args.project if args.project != Path.cwd() else None
    tenant = LocalTenant(args.tenant, root_dir=root_dir)
    projects = tenant.list_projects()

    if not projects:
        print(f"No projects found for tenant {args.tenant!r}.")
        return 0

    print(f"Projects for tenant {args.tenant!r}:")
    for project_id in projects:
        print(f"  - {project_id}")
    return 0
