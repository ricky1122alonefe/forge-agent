"""`forge-agent use` — switch the active version of an agent."""

from __future__ import annotations

import argparse


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("use", help="Switch the active version of an agent")
    p.add_argument("agent_id", help="The agent_id")
    p.add_argument("--version", "-v", help="Target version (default: latest)")
    p.add_argument("--latest", action="store_true", help="Use the latest version")
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

    if args.latest:
        target = entry.versions[-1].version
    elif args.version:
        target = args.version
    else:
        print("Specify --version X or --latest")
        return 2

    if not entry.get_version(target):
        print(f"Version {target!r} not found for {args.agent_id}.")
        return 1

    store.activate(args.agent_id, target)
    print(f"✓ {args.agent_id} now running {target}")
    return 0
