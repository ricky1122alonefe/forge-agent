"""`forge-agent history` — show version history for an agent."""

from __future__ import annotations

import argparse


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("history", help="Show version history for an agent")
    p.add_argument("agent_id", help="The agent_id")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from forge_agent.cli._helpers import get_store

    try:
        store = get_store(args.project)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    entry = store.manifest.agents.get(args.agent_id)
    if not entry:
        print(f"Agent {args.agent_id!r} not found.")
        return 1

    print(f"VERSION  CREATED              REPLACES  VALID  SMOKE   STATUS")
    print("-" * 70)
    for v in entry.versions:
        status = "active" if v.version == entry.active_version else "available"
        if v.deprecated:
            status = "deprecated"
        replaces = v.supersedes or "-"
        print(
            f"{v.version:<8} {v.created_at:<20} {replaces:<9} "
            f"{v.validation_status:<6} {v.smoke_test_status:<7} {status}"
        )
    return 0
