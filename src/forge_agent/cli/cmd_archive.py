"""`forge-agent archive` — archive an agent (mark deprecated)."""

from __future__ import annotations

import argparse


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("archive", help="Archive an agent (mark deprecated)")
    p.add_argument("agent_id", help="The agent_id")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from forge_agent.cli._helpers import get_store

    try:
        store = get_store(args.project)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    if args.agent_id not in store.manifest.agents:
        print(f"Agent {args.agent_id!r} not found.")
        return 1

    store.archive(args.agent_id)
    print(f"✓ Archived {args.agent_id}")
    return 0
