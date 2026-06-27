"""`forge-agent list` — show all generated agents."""

from __future__ import annotations

import argparse


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("list", help="List all generated agents")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from forge_agent.cli._helpers import get_store

    try:
        store = get_store(args.project)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    manifest = store.manifest
    if not manifest.agents:
        print("No generated agents yet. Run: forge-agent generate ...")
        return 0

    print(f"AGENT ID                        TYPE       ACTIVE   VERSIONS   STATUS")
    print("-" * 78)
    for aid, entry in manifest.agents.items():
        status = "active" if not entry.get_active().deprecated else "deprecated" if entry.get_active().deprecated else "active"
        n = len(entry.versions)
        agent_type = entry.agent_type or "-"
        print(f"{aid:<32} {agent_type:<10} {entry.active_version:<8} {n:<10} {status}")

    if manifest.archive:
        print("\nArchived:")
        for aid in manifest.archive:
            print(f"  - {aid}")
    return 0
